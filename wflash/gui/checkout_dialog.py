"""Checkout popup: switch the developer's source repo to a branch or a commit.

Every git and GitLab call runs on a pool thread through the host window's WorkerRegistry,
under a "checkout-" key, so closing the main window also waits for it. The threading rules
are GitlabDialog's (CLAUDE.md, Threading model):

- Rule 4: `_generation` is bumped *before* anything is cancelled; a result started under an
  older generation is dropped in its slot.
- Rule 8: every slot handed to the registry is a bound method of this QDialog.
- Rule 3: closing waits for this dialog's workers with a bound and parks stragglers.

Git itself refuses nothing here: `source_repo` refuses a checkout while the repo has local
changes, and never stashes, resets or forces.
"""
from __future__ import annotations

import dataclasses
from functools import partial
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCompleter, QDialog, QHeaderView, QTableWidgetItem

from wflash.core.errors import CancelledError
from wflash.core.logging_setup import get_logger
from wflash.core.source_repo import (
    CommitInfo,
    RepoState,
    checkout_branch,
    checkout_commit,
    fetch,
    list_branches,
    list_commits,
    read_state,
)
from wflash.gui.ui_checkout_dialog import Ui_CheckoutDialog
from wflash.gui.workers import WorkerContext

log = get_logger("ui.checkout")

WORKER_PREFIX = "checkout-"
DIALOG_CLOSE_TIMEOUT_S = 10.0
COMMIT_LIMIT = 50
PIPELINE_LOOKUPS = 15  # one GitLab request per commit: only the newest ones
SHORT = 8
COMMIT_COLUMN, DATE_COLUMN, MESSAGE_COLUMN, PIPELINE_COLUMN = range(4)
PIPELINE_TEXT = {"success": "Passed", "failed": "Failed", "canceled": "Canceled", "running": "Running"}


class CheckoutDialog(QDialog):
    checkedOut = Signal()
    activity = Signal(str)  # what the dialog is doing, "" when idle: shown on the Flash progress bar

    def __init__(self, host) -> None:
        super().__init__(host)
        self.ui = Ui_CheckoutDialog()
        self.ui.setupUi(self)
        self._host = host
        self._path: Path | None = None
        self._project = ""
        self._generation = 0  # bumped before every cancel (threading rule 4)
        self._keys: dict[str, int] = {}  # running worker key -> generation at start
        self._commits: list[CommitInfo] = []
        self._accept_when_idle = False
        header = self.ui.tableWidget_commits.horizontalHeader()
        for column in range(self.ui.tableWidget_commits.columnCount()):
            mode = QHeaderView.ResizeMode.Stretch if column == MESSAGE_COLUMN else QHeaderView.ResizeMode.ResizeToContents
            header.setSectionResizeMode(column, mode)
        # Many branches: typing filters the list by any part of the name (user request, 2026-11-09).
        # Designer cannot configure the editable combo's completer.
        combo = self.ui.comboBox_branch
        completer = combo.completer()
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        combo.currentIndexChanged.connect(self._on_branch_changed)
        combo.editTextChanged.connect(self._update_controls)
        combo.lineEdit().returnPressed.connect(self._on_branch_typed)
        self.ui.pushButton_fetch.clicked.connect(self.fetch_remote)
        self.ui.pushButton_checkout.clicked.connect(self.checkout_selected)
        self.ui.pushButton_cancelCheckout.clicked.connect(self.reject)
        self.ui.tableWidget_commits.itemSelectionChanged.connect(self._update_controls)
        self.ui.tableWidget_commits.cellDoubleClicked.connect(self._on_commit_double_clicked)

    # -- life cycle -----------------------------------------------------------------------
    def prepare(self, repo_path: Path, project: str = "", title: str = "") -> None:
        """Called before open(): reset everything and read the repo again. `title` names the part."""
        if not hasattr(self, "_base_title"):
            self._base_title = self.windowTitle()
        self.setWindowTitle(f"{self._base_title} — {title}" if title else self._base_title)
        self._path = Path(repo_path)
        self._project = project
        self._commits = []
        self._accept_when_idle = False
        self.ui.comboBox_branch.blockSignals(True)
        self.ui.comboBox_branch.clear()
        self.ui.comboBox_branch.blockSignals(False)
        self.ui.tableWidget_commits.setRowCount(0)
        self.ui.label_currentState.setText("Current: -")
        self.ui.label_checkoutError.clear()
        self._start("branches", partial(_read_branches, self._path), self._on_branches_read, "Reading the repo…")

    def done(self, result: int) -> None:
        self._stop_workers(wait=True)
        super().done(result)

    def abort_for_close(self) -> None:
        """The main window is closing: drop every pending result (it cancels and waits itself)."""
        self._generation += 1
        self._accept_when_idle = False

    def busy(self) -> bool:
        return bool(self._keys)

    def _stale(self, key: str) -> bool:
        return self._keys.get(key) != self._generation

    def _start(self, name: str, fn: Callable[[WorkerContext], object], on_succeeded, status: str) -> None:
        key = self._host._workers.start(
            f"{WORKER_PREFIX}{name}", fn,
            on_succeeded=on_succeeded, on_failed=self._on_failed, on_finished=self._on_finished,
        )
        self._keys[key] = self._generation
        self.ui.label_checkoutStatus.setText(status)
        self.activity.emit(status)
        self._update_controls()

    def _stop_workers(self, wait: bool) -> None:
        if not self._keys:
            return
        self._generation += 1  # rule 4: results already queued are now stale
        for key in list(self._keys):
            self._host._workers.cancel(key)
        if wait and not self._host._workers.wait_idle(DIALOG_CLOSE_TIMEOUT_S, prefix=WORKER_PREFIX):
            keys = self._host._workers.abandon_running(prefix=WORKER_PREFIX)
            log.warning("Git work did not stop within %.0f s; abandoned: %s", DIALOG_CLOSE_TIMEOUT_S, keys)
            for key in keys:
                self._keys.pop(key, None)

    def _update_controls(self, *_args) -> None:
        idle = not self.busy()
        self.ui.comboBox_branch.setEnabled(idle and self.ui.comboBox_branch.count() > 0)
        self.ui.pushButton_fetch.setEnabled(idle and self._path is not None)
        self.ui.pushButton_checkout.setEnabled(idle and self._selected_row() is not None and bool(self._chosen_branch()))

    def _selected_row(self) -> int | None:
        rows = self.ui.tableWidget_commits.selectionModel().selectedRows()
        return rows[0].row() if rows and rows[0].row() < len(self._commits) else None

    # -- results ------------------------------------------------------------------------
    def _on_failed(self, key: str, exc: BaseException) -> None:
        if self._stale(key):
            log.debug("Dropping the result of stopped git work %s: %s", key, exc)
            return
        if isinstance(exc, CancelledError):
            return
        hint = getattr(exc, "hint", "")
        log.error("%s%s", exc, f" (hint: {hint})" if hint else "")
        self.ui.label_checkoutError.setText(f"{exc} {hint}".strip())

    def _on_finished(self, key: str) -> None:
        self._keys.pop(key, None)
        if not self.busy():
            self.ui.label_checkoutStatus.clear()
            self.activity.emit("")
            if self._accept_when_idle:
                self._accept_when_idle = False
                self.accept()
                return
        self._update_controls()

    def _show_state(self, state: RepoState) -> None:
        changes = f"{len(state.changes)} file(s) with local changes" if state.dirty else "no local changes"
        self.ui.label_currentState.setText(
            f"Current: {state.branch or '(detached)'} · {state.commit[:SHORT]} · {changes}"
        )

    def _on_branches_read(self, key: str, result) -> None:
        if self._stale(key):
            return
        state, branches = result
        self._show_state(state)
        combo = self.ui.comboBox_branch
        wanted = self._chosen_branch() or state.branch
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(branches)
        # Editable combo: setCurrentText would only change the text, not the chosen branch.
        combo.setCurrentIndex(branches.index(wanted) if wanted in branches else (0 if branches else -1))
        combo.blockSignals(False)
        self._load_commits()

    def _chosen_branch(self) -> str:
        """The branch the commits belong to: "" while the typed text names no branch."""
        combo = self.ui.comboBox_branch
        index = combo.currentIndex()
        name = combo.itemText(index) if index >= 0 else ""
        return name if name and combo.currentText() == name else ""

    def _on_branch_typed(self) -> None:
        """Enter in the branch field: pick the branch with exactly that name, or say there is none."""
        combo = self.ui.comboBox_branch
        text = combo.currentText().strip()
        index = combo.findText(text)
        if index < 0:
            self.ui.label_checkoutError.setText(f"No branch named {text!r}.")
            self._update_controls()
            return
        if index == combo.currentIndex():
            combo.setEditText(combo.itemText(index))
            self._update_controls()
        else:
            combo.setCurrentIndex(index)

    def _on_branch_changed(self, *_args) -> None:
        self.ui.label_checkoutError.clear()
        self._load_commits()

    def _load_commits(self) -> None:
        branch = self._chosen_branch()
        self.ui.tableWidget_commits.setRowCount(0)
        self._commits = []
        if not branch or self._path is None:
            self._update_controls()
            return
        url_of = getattr(self._host, "gitlab_url", None)
        settings = dataclasses.replace(self._host.settings, gitlab_url=url_of() if callable(url_of) else self._host.settings.gitlab_url)
        job = partial(_read_commits, self._path, branch, self._host._client_factory, settings, self._project)
        self._start("commits", job, self._on_commits_read, f"Reading {branch}…")

    def _on_commits_read(self, key: str, result) -> None:
        if self._stale(key):
            return
        branch, commits, pipelines = result
        if branch != self._chosen_branch():
            return  # the user picked another branch meanwhile; its own read is on the way
        self._commits = commits
        table = self.ui.tableWidget_commits
        table.setRowCount(len(commits))
        for row, info in enumerate(commits):
            cells = (info.commit[:SHORT], info.date, info.subject, pipelines.get(info.commit, ""))
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setToolTip(info.commit if column == COMMIT_COLUMN else text)
                table.setItem(row, column, item)
        self._update_controls()

    # -- actions ------------------------------------------------------------------------
    def fetch_remote(self, *_args) -> None:
        if self.busy() or self._path is None:
            return
        self.ui.label_checkoutError.clear()
        self._start("fetch", partial(_fetch_and_read, self._path), self._on_branches_read, "Fetching…")

    def _on_commit_double_clicked(self, row: int, _column: int) -> None:
        self.ui.tableWidget_commits.selectRow(row)
        self.checkout_selected()

    def checkout_selected(self, *_args) -> None:
        row = self._selected_row()
        branch = self._chosen_branch()
        if self.busy() or row is None or self._path is None or not branch:
            return
        commit = self._commits[row].commit
        self.ui.label_checkoutError.clear()
        if row == 0:
            job, what = partial(_checkout, checkout_branch, self._path, branch), branch
        else:
            job, what = partial(_checkout, checkout_commit, self._path, commit), commit[:SHORT]
        self._start("do", job, self._on_checked_out, f"Checking out {what}…")

    def _on_checked_out(self, key: str, state: RepoState) -> None:
        if self._stale(key):
            return
        log.info("Checked out %s at %s", state.branch or "(detached)", state.commit[:SHORT])
        self._show_state(state)
        self.checkedOut.emit()
        self._accept_when_idle = True  # close once the registry has let the worker go


# -- worker functions (pool thread: no Qt) -------------------------------------------------
def _read_branches(path: Path, ctx: WorkerContext):
    return read_state(path), list_branches(path)


def _fetch_and_read(path: Path, ctx: WorkerContext):
    fetch(path)
    ctx.cancel.raise_if_cancelled()
    return _read_branches(path, ctx)


def _checkout(action, path: Path, target: str, ctx: WorkerContext) -> RepoState:
    action(path, target)
    return read_state(path)


def _read_commits(path: Path, branch: str, client_factory, settings, project: str, ctx: WorkerContext):
    commits = list_commits(path, branch, COMMIT_LIMIT)
    return branch, commits, _pipeline_statuses(client_factory, settings, project, branch, commits, ctx)


def _pipeline_statuses(client_factory, settings, project: str, branch: str, commits, ctx: WorkerContext) -> dict:
    """Best effort: the newest pipeline of each commit, preferring one on this branch. '-' when GitLab is not available."""
    if client_factory is None or not project or not settings.gitlab_url:
        return {c.commit: "-" for c in commits}
    try:
        client = client_factory(settings)
        project_id = client.get_project_id(project)
        statuses = {}
        for info in commits[:PIPELINE_LOOKUPS]:
            ctx.cancel.raise_if_cancelled()
            pipelines = client.list_pipelines_for_commit(project_id, info.commit)
            on_branch = [p for p in pipelines if p.ref and (branch == p.ref or branch.endswith("/" + p.ref))]
            chosen = (on_branch or pipelines)[:1]
            statuses[info.commit] = PIPELINE_TEXT.get(chosen[0].status, chosen[0].status.capitalize()) if chosen else "None"
        return statuses
    except CancelledError:
        raise
    except Exception as exc:  # the column is a convenience; never let it break checkout
        log.warning("Pipeline status not available: %s", exc)
        return {c.commit: "-" for c in commits}
