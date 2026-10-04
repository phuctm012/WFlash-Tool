"""Load from GitLab popup (layout in gitlab_dialog.ui): CI artifact and Package Registry tabs.

The dialog finds and downloads firmware, then emits `firmwareReady(path, source)` and
closes; the main window builds the mapping from it. Every GitLab call runs on the main
window's WorkerRegistry under a "gitlab-" key, so closing the main window also waits for
the dialog's work (CLAUDE.md threading model):

- Rule 4: `_generation` is bumped *before* anything is cancelled (Stop, close, main
  window shutdown); every completion slot drops results of an older generation.
- Rule 8: every slot handed to the registry is a bound method of this QDialog.
- Rule 3: closing waits for the dialog's own workers with a bound, pumping events
  (`WorkerRegistry.wait_idle(prefix="gitlab-")`), and parks stragglers instead of hanging.
- Rule 7: downloads report bytes through `WorkerContext.progress`, which raises once the
  token is cancelled, so Stop takes effect inside the transfer.

The main window keeps one instance for its whole life (never deleted while a worker might
still report to it) and calls `prepare()` before each `open()`.

Host contract (MainWindow, or tests.gui_stubs.HostWindow): `settings`, `profile`, `ctx`,
`_workers`, `_client_factory`, `_save_settings()`, `show_error()`, `_update_flash_controls()`.
"""
from __future__ import annotations

import dataclasses
import datetime
import logging
from functools import partial
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QDialog, QFileDialog, QHeaderView, QPushButton, QTableWidgetItem

from wflash.core.artifact_cache import ArtifactCache
from wflash.core.errors import CancelledError, GitLabError
from wflash.core.firmware_fetch import (
    JobRow,
    browse_jobs,
    fetch_ci_artifact,
    fetch_package,
    find_latest_job,
    latest_package,
)
from wflash.core.firmware_source import short_timestamp
from wflash.core.gitlab_client import GitLabClient, PackageVersion
from wflash.core.logging_setup import get_logger, redact, register_secret
from wflash.core.settings import AppSettings, get_token, set_token
from wflash.gui.style import repolish
from wflash.gui.ui_gitlab_dialog import Ui_GitlabDialog
from wflash.gui.workers import WorkerContext

# Same logger as the core client: the dialog's own lines reach the log file and the
# debug bundle, redacted like everything else.
log = get_logger("gitlab")

ClientFactory = Callable[[AppSettings], GitLabClient]
WORKER_PREFIX = "gitlab-"
DIALOG_CLOSE_TIMEOUT_S = 10.0
JOB_DOWNLOAD_COLUMN = 5
VERSION_DOWNLOAD_COLUMN = 2
VERSIONS_TO_LIST = 20

_tls_warning_logged = False  # "Verify TLS" off is logged once per session


def default_client_factory(settings: AppSettings) -> GitLabClient:
    """Called on a worker thread: builds a client from the settings and the keyring token."""
    token = get_token(settings.gitlab_url)
    if not settings.gitlab_url or not token:
        raise GitLabError(
            "GitLab URL or token is not configured",
            hint="Open Load from GitLab… and enter the GitLab URL and a Personal Access Token (scope read_api).",
        )
    return GitLabClient(
        settings.gitlab_url, token, ca_bundle=settings.ca_bundle or None, verify=settings.verify_tls
    )


def warn_tls_disabled_once(url: str) -> None:
    global _tls_warning_logged
    if _tls_warning_logged:
        return
    _tls_warning_logged = True
    log.warning(
        "TLS certificate verification is OFF for %s. Use this only on a trusted network; "
        "if GitLab uses an internal certificate, set its CA bundle instead.",
        url,
    )


def byte_progress(ctx: WorkerContext) -> Callable[[int, int], None]:
    """Turn the client's (bytes_done, bytes_total) into worker progress (raises after a cancel)."""

    def on_bytes(done: int, total: int) -> None:
        if total:
            ctx.progress(int(done * 100 / total), f"Downloading {done / 1e6:.1f} / {total / 1e6:.1f} MB")
        else:
            ctx.progress(None, f"Downloading {done / 1e6:.1f} MB")

    return on_bytes


class GitlabDialog(QDialog):
    firmwareReady = Signal(object, object)  # Path of the extracted files, FirmwareSource

    def __init__(self, host) -> None:
        super().__init__(host)
        self.ui = Ui_GitlabDialog()
        self.ui.setupUi(self)
        self._host = host
        self._generation = 0  # bumped before every cancel (threading rule 4)
        self._keys: dict[str, int] = {}  # running worker key -> generation at start
        self._stopped: set[str] = set()  # keys cancelled by Stop/close: show "Cancelled"
        self._profile_key: str | None = None
        self._token_saved_for: tuple[str, str] = ("", "")  # (url, token) known to be in the keyring
        self._job_rows: list[JobRow] = []
        self._jobs_project: tuple[str, int] | None = None  # project the job table was listed from
        self._versions: list[PackageVersion] = []
        self._versions_project: tuple[str, int] | None = None
        self._downloading_button: QPushButton | None = None

        self.ui.plainTextEdit_gitlabLog.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        for table, stretch in ((self.ui.tableWidget_jobs, 1), (self.ui.tableWidget_versions, 0)):
            header = table.horizontalHeader()
            for column in range(table.columnCount()):
                mode = QHeaderView.ResizeMode.Stretch if column == stretch else QHeaderView.ResizeMode.ResizeToContents
                header.setSectionResizeMode(column, mode)
        self._reset_progress()

        self.ui.pushButton_loadRefs.clicked.connect(self.load_refs)
        self.ui.pushButton_browseJobs.clicked.connect(self.browse_jobs)
        self.ui.pushButton_downloadSelected.clicked.connect(self.download_selected)
        self.ui.tableWidget_jobs.cellDoubleClicked.connect(self._on_job_double_clicked)
        self.ui.pushButton_fetchLatest.clicked.connect(self.fetch_latest)
        self.ui.pushButton_browseVersions.clicked.connect(self.browse_versions)
        self.ui.tableWidget_versions.cellDoubleClicked.connect(self._on_version_double_clicked)
        self.ui.pushButton_stopDownload.clicked.connect(self.stop)
        self.ui.pushButton_cancel.clicked.connect(self.reject)
        self.ui.pushButton_browseCa.clicked.connect(self._browse_ca)
        self.ui.checkBox_verifyTls.toggled.connect(self._on_verify_toggled)
        self.ui.lineEdit_ciProject.textChanged.connect(self._update_ci_project_label)
        self.ui.lineEdit_ciProject.editingFinished.connect(self._store_ci_project)
        self._update_controls()

    # -- opening and closing ----------------------------------------------------------
    def prepare(self) -> None:
        """Load the current settings and profile into the fields; called before each open()."""
        settings = self._host.settings
        self.ui.lineEdit_gitlabUrl.setText(settings.gitlab_url)
        token = (get_token(settings.gitlab_url) or "") if settings.gitlab_url else ""
        self._token_saved_for = (settings.gitlab_url, token)
        self.ui.lineEdit_token.setText(token)
        self.ui.checkBox_verifyTls.setChecked(settings.verify_tls)
        self.ui.lineEdit_caBundle.setText(settings.ca_bundle)
        self._on_verify_toggled(settings.verify_tls)
        self.ui.lineEdit_pkgProject.setText(settings.package_project)
        self.ui.lineEdit_packageName.setText(settings.package_name)
        key = self._profile_key_now()
        if key != self._profile_key:
            # Another profile: its project and jobs are different, start the CI tab afresh.
            self._profile_key = key
            profile = self._host.profile
            override = settings.ci_project_overrides.get(key, "")
            self.ui.lineEdit_ciProject.setText(override or (profile.gitlab.project if profile else ""))
            self.ui.comboBox_ref.clear()
            self.ui.comboBox_jobName.clear()
            self.ui.comboBox_jobName.setEditText(settings.ci_job_name)
            self._fill_jobs([], None)
        self._update_ci_project_label()
        self._reset_progress()
        self._set_status("Ready")
        self._update_controls()

    def done(self, result: int) -> None:
        # Accept (firmware ready), Cancel, Esc and the window's X all end here.
        self._stop_workers(wait=True)
        self._store_fields()
        super().done(result)

    def abort_for_close(self) -> None:
        """The main window is closing: drop every pending result (it cancels and waits itself)."""
        self._generation += 1
        self._stopped.update(self._keys)

    # -- state --------------------------------------------------------------------------
    def busy(self) -> bool:
        return bool(self._keys)

    def _stale(self, key: str) -> bool:
        return self._keys.get(key) != self._generation

    def _profile_key_now(self) -> str:
        profile = self._host.profile
        return self._host.settings.last_profile or (profile.name if profile else "")

    def ci_project(self) -> str:
        profile = self._host.profile
        return self.ui.lineEdit_ciProject.text().strip() or (profile.gitlab.project if profile else "")

    def _current_ref(self) -> str:
        return self.ui.comboBox_ref.currentText().strip()

    def _job_name(self) -> str:
        return self.ui.comboBox_jobName.currentText().strip()

    def _update_controls(self, *_args) -> None:
        busy = self.busy()
        for widget in (
            self.ui.groupBox_connection,
            self.ui.lineEdit_ciProject,
            self.ui.comboBox_ref,
            self.ui.pushButton_loadRefs,
            self.ui.comboBox_jobName,
            self.ui.pushButton_downloadSelected,
            self.ui.pushButton_browseJobs,
            self.ui.tableWidget_jobs,
            self.ui.lineEdit_pkgProject,
            self.ui.lineEdit_packageName,
            self.ui.pushButton_fetchLatest,
            self.ui.pushButton_browseVersions,
            self.ui.tableWidget_versions,
        ):
            widget.setEnabled(not busy)
        self.ui.pushButton_stopDownload.setEnabled(busy)

    def _update_ci_project_label(self, *_args) -> None:
        profile = self._host.profile
        text = self.ui.lineEdit_ciProject.text().strip()
        self.ui.label_ciProjectSource.setVisible(
            profile is not None and (not text or text == profile.gitlab.project)
        )

    def _on_verify_toggled(self, checked: bool) -> None:
        # The CA bundle only matters while certificates are verified.
        self.ui.lineEdit_caBundle.setEnabled(checked)
        self.ui.pushButton_browseCa.setEnabled(checked)

    # -- status, log --------------------------------------------------------------------
    def _note(self, level: int, text: str) -> None:
        log.log(level, "%s", text)
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.ui.plainTextEdit_gitlabLog.appendPlainText(f"{stamp} {logging.getLevelName(level)}: {redact(text)}")

    def _set_status(self, text: str, error: bool = False) -> None:
        label = self.ui.label_downloadStatus
        label.setText(redact(text))
        label.setProperty("state", "error" if error else "")
        repolish(label)

    def _reset_progress(self) -> None:
        bar = self.ui.progressBar_download
        bar.setRange(0, 100)
        bar.setValue(0)

    def _busy_progress(self, text: str) -> None:
        self.ui.progressBar_download.setRange(0, 0)
        self._set_status(text)

    def _fail_input(self, text: str) -> None:
        """A field is missing or wrong: say so in the dialog, no modal box."""
        self._set_status(text, error=True)
        self._note(logging.WARNING, text)

    # -- settings -----------------------------------------------------------------------
    def _store_ci_project(self) -> None:
        profile = self._host.profile
        key = self._profile_key or self._profile_key_now()
        if profile is None or not key:
            return
        text = self.ui.lineEdit_ciProject.text().strip()
        overrides = self._host.settings.ci_project_overrides
        if not text or text == profile.gitlab.project:
            overrides.pop(key, None)
        else:
            overrides[key] = text

    def _store_fields(self) -> None:
        """Copy the fields to the settings and save them (never the token)."""
        settings = self._host.settings
        url = self.ui.lineEdit_gitlabUrl.text().strip().rstrip("/")
        if not url or url.startswith(("http://", "https://")):
            settings.gitlab_url = url
        settings.ca_bundle = self.ui.lineEdit_caBundle.text().strip()
        settings.verify_tls = self.ui.checkBox_verifyTls.isChecked()
        settings.ci_job_name = self._job_name()
        settings.package_project = self.ui.lineEdit_pkgProject.text().strip()
        settings.package_name = self.ui.lineEdit_packageName.text().strip()
        self._store_ci_project()
        self._host._save_settings()

    def _commit_connection(self) -> bool:
        """Validate and save the connection before an operation; store a new token in the keyring."""
        url = self.ui.lineEdit_gitlabUrl.text().strip().rstrip("/")
        if not url.startswith(("http://", "https://")):
            self._fail_input("Enter the GitLab URL (https://…) first.")
            return False
        ca = self.ui.lineEdit_caBundle.text().strip()
        if self.ui.checkBox_verifyTls.isChecked() and ca and not Path(ca).is_file():
            self._fail_input(f"CA bundle file not found: {ca}")
            return False
        self._store_fields()
        token = self.ui.lineEdit_token.text().strip()
        if token:
            register_secret(token)
            if (url, token) != self._token_saved_for:
                try:
                    set_token(url, token)
                except GitLabError as exc:
                    self._report_error(exc)
                    return False
                self._token_saved_for = (url, token)
                self._note(logging.INFO, "Token stored in the system keyring")
        if not self._host.settings.verify_tls:
            warn_tls_disabled_once(url)
        return True

    def _browse_ca(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CA bundle", self.ui.lineEdit_caBundle.text(), "Certificates (*.pem *.crt *.cer);;All files (*)"
        )
        if path:
            self.ui.lineEdit_caBundle.setText(path)

    # -- workers --------------------------------------------------------------------------
    def _snapshot(self) -> AppSettings:
        # Workers get their own copy; the GUI thread may keep editing the settings.
        return dataclasses.replace(self._host.settings)

    def _start(self, name: str, fn: Callable[[WorkerContext], object], on_succeeded, progress: bool = False) -> None:
        key = self._host._workers.start(
            f"{WORKER_PREFIX}{name}",
            fn,
            on_succeeded=on_succeeded,
            on_failed=self._on_failed,
            on_finished=self._on_finished,
            on_progress=self._on_progress if progress else None,
        )
        self._keys[key] = self._generation
        self._update_controls()
        self._host._update_flash_controls()

    def stop(self, *_args) -> None:
        if not self.busy():
            return
        self._note(logging.WARNING, "Stop requested")
        self._set_status("Stopping…")
        self._stop_workers(wait=False)

    def _stop_workers(self, wait: bool) -> None:
        if not self._keys:
            return
        self._generation += 1  # rule 4: results already queued are now stale
        for key in list(self._keys):
            self._stopped.add(key)
            self._host._workers.cancel(key)
        if not wait:
            return
        if not self._host._workers.wait_idle(DIALOG_CLOSE_TIMEOUT_S, prefix=WORKER_PREFIX):
            keys = self._host._workers.abandon_running(prefix=WORKER_PREFIX)
            log.warning("GitLab work did not stop within %.0f s; abandoned: %s", DIALOG_CLOSE_TIMEOUT_S, keys)
            for key in keys:
                self._keys.pop(key, None)
                self._stopped.discard(key)
            self._update_controls()

    def _on_progress(self, percent, message: str) -> None:
        if all(self._stale(key) for key in self._keys):
            return
        bar = self.ui.progressBar_download
        if percent is None:
            bar.setRange(0, 0)
        else:
            bar.setRange(0, 100)
            bar.setValue(percent)
        self._set_status(message)

    def _on_failed(self, key: str, exc: BaseException) -> None:
        if self._stale(key):
            log.debug("Dropping the result of stopped GitLab work %s: %s", key, exc)
            return
        self._reset_progress()
        if isinstance(exc, CancelledError):
            self._set_status("Cancelled")
            return
        self._report_error(exc)

    def _report_error(self, exc: BaseException) -> None:
        hint = getattr(exc, "hint", "")
        self._set_status(f"Failed: {exc}", error=True)
        self._note(logging.ERROR, f"{exc}" + (f" (hint: {hint})" if hint else ""))
        self._host.ctx.add_error(exc)  # no flash can run while this modal dialog is open
        self._host.show_error(exc)

    def _on_finished(self, key: str) -> None:
        self._keys.pop(key, None)
        stopped = key in self._stopped
        self._stopped.discard(key)
        if not self.busy():
            if self._downloading_button is not None:
                self._refresh_download_buttons()
                self._downloading_button = None
            if self.ui.progressBar_download.maximum() == 0:
                self._reset_progress()
            if stopped:
                self._reset_progress()
                self._set_status("Cancelled")
        self._update_controls()
        self._host._update_flash_controls()

    # -- CI artifact tab ---------------------------------------------------------------
    def load_refs(self, *_args) -> None:
        if self.busy() or not self._commit_connection():
            return
        project = self.ci_project()
        factory, settings = self._host._client_factory, self._snapshot()

        def job(ctx: WorkerContext):
            client = factory(settings)
            project_id = client.get_project_id(project)
            return client.list_refs(project_id)

        self._note(logging.INFO, f"Loading branches and tags of {project}")
        self._busy_progress("Loading branches/tags…")
        self._start("refs", job, self._on_refs_loaded)

    def _on_refs_loaded(self, key: str, refs) -> None:
        if self._stale(key):
            return
        combo = self.ui.comboBox_ref
        current = combo.currentText().strip()
        combo.blockSignals(True)
        combo.clear()
        for ref in refs:
            combo.addItem(ref.name)
            if ref.kind == "tag":
                combo.setItemData(combo.count() - 1, "tag", Qt.ItemDataRole.ToolTipRole)
        names = [ref.name for ref in refs]
        if current:
            combo.setEditText(current)
        elif names:
            combo.setCurrentIndex(names.index("main") if "main" in names else 0)
        combo.blockSignals(False)
        self._note(logging.INFO, f"Loaded {len(refs)} branches/tags")
        self._set_status("Ready")

    def browse_jobs(self, *_args) -> None:
        if self.busy() or not self._commit_connection():
            return
        ref = self._current_ref()
        if not ref:
            self._fail_input("Choose a branch or tag first (Load branches/tags).")
            return
        project, job_filter = self.ci_project(), self._host.profile.gitlab.job_filter
        factory, settings = self._host._client_factory, self._snapshot()

        def job(ctx: WorkerContext):
            client = factory(settings)
            project_id = client.get_project_id(project)
            return project, project_id, ref, browse_jobs(client, project_id, ref, job_filter, cancel=ctx.cancel)

        self._note(logging.INFO, f"Listing jobs '{job_filter}' with artifacts on {ref}")
        self._busy_progress("Loading jobs…")
        self._start("jobs", job, self._on_jobs_loaded)

    def _on_jobs_loaded(self, key: str, result) -> None:
        if self._stale(key):
            return
        project, project_id, ref, rows = result
        self._fill_jobs(rows, (project, project_id))
        names = sorted({row.job_name for row in rows})
        combo = self.ui.comboBox_jobName
        typed = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(names)
        combo.setEditText(typed)
        combo.blockSignals(False)
        if rows:
            self._note(logging.INFO, f"Found {len(rows)} job(s) with artifacts on {ref}")
        else:
            self._note(logging.WARNING, f"No job with artifacts on {ref} matches the profile filter")
        self._set_status("Ready")

    def _fill_jobs(self, rows: list[JobRow], project: tuple[str, int] | None) -> None:
        self._job_rows = rows
        self._jobs_project = project
        table = self.ui.tableWidget_jobs
        table.clearSelection()
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            cells = (f"#{row.pipeline_id}", row.job_name, row.ref, row.status, row.when)
            for column, text in enumerate(cells):
                table.setItem(index, column, QTableWidgetItem(text))
            button = QPushButton()
            # GUI-thread signal from a GUI-thread widget: a partial is fine here; the lambda
            # ban (threading rule 8) is about signals emitted from pool threads.
            button.clicked.connect(partial(self._download_job_row, index))
            table.setCellWidget(index, JOB_DOWNLOAD_COLUMN, button)
        self._refresh_download_buttons()

    def _refresh_download_buttons(self) -> None:
        settings = self._host.settings
        if self._jobs_project is not None:
            cache = ArtifactCache(settings.resolved_cache_dir())
            _, project_id = self._jobs_project
            for index, row in enumerate(self._job_rows):
                button = self.ui.tableWidget_jobs.cellWidget(index, JOB_DOWNLOAD_COLUMN)
                button.setText("Cached" if cache.has(project_id, row.job_id) else "Download")
        if self._versions_project is not None:
            cache = ArtifactCache(settings.resolved_package_cache_dir())
            _, project_id = self._versions_project
            for index, version in enumerate(self._versions):
                button = self.ui.tableWidget_versions.cellWidget(index, VERSION_DOWNLOAD_COLUMN)
                button.setText("Cached" if cache.has(project_id, version.id) else "Download")

    def job_button(self, index: int) -> QPushButton:
        return self.ui.tableWidget_jobs.cellWidget(index, JOB_DOWNLOAD_COLUMN)

    def version_button(self, index: int) -> QPushButton:
        return self.ui.tableWidget_versions.cellWidget(index, VERSION_DOWNLOAD_COLUMN)

    def _on_job_double_clicked(self, row: int, _column: int) -> None:
        self._download_job_row(row)

    def _download_job_row(self, index: int, *_args) -> None:
        if self.busy() or not 0 <= index < len(self._job_rows) or not self._commit_connection():
            return
        self._start_job_download(self._job_rows[index], self.job_button(index))

    def download_selected(self, *_args) -> None:
        """The selected row's job; with no row selected, the newest successful job of ref + job name."""
        if self.busy() or not self._commit_connection():
            return
        selected = self.ui.tableWidget_jobs.selectionModel().selectedRows()
        if selected:
            index = selected[0].row()
            self._start_job_download(self._job_rows[index], self.job_button(index))
            return
        ref = self._current_ref()
        if not ref:
            self._fail_input("Choose a branch or tag first (Load branches/tags).")
            return
        project, job_filter, job_name = self.ci_project(), self._host.profile.gitlab.job_filter, self._job_name()
        factory, settings = self._host._client_factory, self._snapshot()
        cache_root, max_jobs = settings.resolved_cache_dir(), settings.max_cached_jobs

        def job(ctx: WorkerContext):
            client = factory(settings)
            project_id = client.get_project_id(project)
            row = find_latest_job(client, project_id, ref, job_filter, job_name, cancel=ctx.cancel)
            ctx.progress(None, f"Job #{row.job_id} {row.job_name} (pipeline #{row.pipeline_id})")
            cache = ArtifactCache(cache_root, max_jobs)
            return fetch_ci_artifact(client, project, project_id, row, cache, byte_progress(ctx), ctx.cancel)

        wanted = f"'{job_name}'" if job_name else f"matching '{job_filter}'"
        self._note(logging.INFO, f"Looking for the newest successful job {wanted} on {ref}")
        self._busy_progress("Looking for the newest job…")
        self._start("download", job, self._on_download_succeeded, progress=True)

    def _start_job_download(self, row: JobRow, button: QPushButton | None) -> None:
        project, project_id = self._jobs_project
        factory, settings = self._host._client_factory, self._snapshot()
        cache_root, max_jobs = settings.resolved_cache_dir(), settings.max_cached_jobs

        def job(ctx: WorkerContext):
            client = factory(settings)
            cache = ArtifactCache(cache_root, max_jobs)
            return fetch_ci_artifact(client, project, project_id, row, cache, byte_progress(ctx), ctx.cancel)

        self._mark_downloading(button)
        self._note(logging.INFO, f"Downloading the artifact of job #{row.job_id} {row.job_name}")
        self._busy_progress("Starting download…")
        self._start("download", job, self._on_download_succeeded, progress=True)

    def _mark_downloading(self, button: QPushButton | None) -> None:
        self._downloading_button = button
        if button is not None:
            button.setText("Downloading…")

    def _on_download_succeeded(self, key: str, result) -> None:
        if self._stale(key):
            log.info("Download finished after Stop/close; not loading it")
            return
        path, source = result
        self.ui.progressBar_download.setRange(0, 100)
        self.ui.progressBar_download.setValue(100)
        self._set_status(f"Ready: {source.title}")
        self._note(logging.INFO, f"Firmware ready: {source.title} ({source.cache_note}) at {path}")
        self.firmwareReady.emit(path, source)
        self.accept()

    # -- Package Registry tab ------------------------------------------------------------
    def _package_fields(self) -> tuple[str, str] | None:
        project = self.ui.lineEdit_pkgProject.text().strip()
        name = self.ui.lineEdit_packageName.text().strip()
        if not project or not name:
            self._fail_input("Enter the package project and the package name first.")
            return None
        return project, name

    def fetch_latest(self, *_args) -> None:
        if self.busy() or not self._commit_connection():
            return
        fields = self._package_fields()
        if fields is None:
            return
        project, name = fields
        factory, settings = self._host._client_factory, self._snapshot()
        cache_root, max_jobs = settings.resolved_package_cache_dir(), settings.max_cached_jobs

        def job(ctx: WorkerContext):
            client = factory(settings)
            project_id = client.get_project_id(project)
            version = latest_package(client, project_id, name)
            ctx.progress(None, f"Latest version: {version.version}")
            cache = ArtifactCache(cache_root, max_jobs)
            return fetch_package(client, project, project_id, version, cache, byte_progress(ctx), ctx.cancel)

        self._note(logging.INFO, f"Fetching the latest version of package {name} from {project}")
        self._busy_progress("Looking for the latest version…")
        self._start("download", job, self._on_download_succeeded, progress=True)

    def browse_versions(self, *_args) -> None:
        if self.busy() or not self._commit_connection():
            return
        fields = self._package_fields()
        if fields is None:
            return
        project, name = fields
        factory, settings = self._host._client_factory, self._snapshot()

        def job(ctx: WorkerContext):
            client = factory(settings)
            project_id = client.get_project_id(project)
            return project, project_id, client.list_package_versions(project_id, name, limit=VERSIONS_TO_LIST)

        self._note(logging.INFO, f"Listing versions of package {name}")
        self._busy_progress("Loading versions…")
        self._start("versions", job, self._on_versions_loaded)

    def _on_versions_loaded(self, key: str, result) -> None:
        if self._stale(key):
            return
        project, project_id, versions = result
        self._versions = versions
        self._versions_project = (project, project_id)
        table = self.ui.tableWidget_versions
        table.clearSelection()
        table.setRowCount(len(versions))
        for index, version in enumerate(versions):
            table.setItem(index, 0, QTableWidgetItem(version.version))
            table.setItem(index, 1, QTableWidgetItem(short_timestamp(version.created_at)))
            button = QPushButton()
            button.clicked.connect(partial(self._download_version_row, index))  # GUI-thread signal
            table.setCellWidget(index, VERSION_DOWNLOAD_COLUMN, button)
        self._refresh_download_buttons()
        self._note(logging.INFO, f"Found {len(versions)} version(s)")
        self._set_status("Ready")

    def _on_version_double_clicked(self, row: int, _column: int) -> None:
        self._download_version_row(row)

    def _download_version_row(self, index: int, *_args) -> None:
        if self.busy() or not 0 <= index < len(self._versions) or not self._commit_connection():
            return
        version = self._versions[index]
        project, project_id = self._versions_project
        factory, settings = self._host._client_factory, self._snapshot()
        cache_root, max_jobs = settings.resolved_package_cache_dir(), settings.max_cached_jobs

        def job(ctx: WorkerContext):
            client = factory(settings)
            cache = ArtifactCache(cache_root, max_jobs)
            return fetch_package(client, project, project_id, version, cache, byte_progress(ctx), ctx.cancel)

        self._mark_downloading(self.version_button(index))
        self._note(logging.INFO, f"Downloading package {version.name} {version.version}")
        self._busy_progress("Starting download…")
        self._start("download", job, self._on_download_succeeded, progress=True)
