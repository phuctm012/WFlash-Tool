"""One part of the GitLab tab: App, Boot Manager or Flash Bootloader (spec 2026-11-09).

Each part has a project, an optional repository (required for App), and a Firmware mode:

- "commit": the firmware follows the commit checked out in the repository. After a Checkout,
  a Reload, the window coming back to the front, or a build change, the part finds the
  pipeline of that exact commit and loads its artifact (cache first). A job still on its way
  is polled every POLL_S seconds for up to WAIT_LIMIT_S. Never during a flash; it never flashes.
- "manual": the job is chosen in the Load from GitLab popup (Choose Job) and kept.

Threading (CLAUDE.md): this is a QObject built on the GUI thread, so its bound methods are
valid slots for WorkerRegistry (rule 8). `_generation` is bumped before anything is cancelled
and every completion slot drops a result started under an older generation (rule 4).
"""
from __future__ import annotations

import json
import time
from functools import partial
from pathlib import Path, PurePath

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QFileDialog, QMenu

from wflash.core.artifact_cache import MARKER, NamedArtifactCache, build_cache_path, debug_cache_path
from wflash.core.errors import PipelineNotReady, WFlashError
from wflash.core.firmware_fetch import fetch_named_artifact, find_commit_jobs
from wflash.core.firmware_source import FirmwareSource
from wflash.core.gitlab_url import project_path, split_gitlab_url
from wflash.core.logging_setup import get_logger
from wflash.core.source_repo import RepoState, read_state
from wflash.gui.workers import WorkerContext

log = get_logger("ui.part")

SHORT = 8
POLL_S = 30
WAIT_LIMIT_S = 60 * 60
COMMIT, MANUAL = "commit", "manual"
LABELS = {"app": "App", "bm": "Boot Manager", "fbl": "Flash Bootloader"}
ROLES = {"app": ("ffi", "elf"), "bm": ("bm",), "fbl": ("fbl",)}
NO_REPO = "-"


def _ref_of(source: FirmwareSource) -> str:
    parts = source.detail.split(" · ")
    return parts[1] if len(parts) > 1 else ""


def error_text(exc: BaseException) -> str:
    """Message and hint as one line: "No pipeline for x yet. Push the commit…"."""
    message, hint = str(exc).strip(), str(getattr(exc, "hint", "") or "").strip()
    if hint and message and message[-1] not in ".…!?:":
        message += "."
    return f"{message} {hint}".strip()


def status_line(role: str, source: FirmwareSource) -> str:
    """`FFI: <job> · <branch> · <commit8> · Cached` (spec 3.2)."""
    origin = source.cache_note.split(" · ")[0]
    fields = [source.job_name, _ref_of(source), source.commit[:SHORT], origin]
    return f"{role.upper()}: " + " · ".join(f for f in fields if f)


class PartController(QObject):
    """State and actions of one part; the widgets live in main_window.ui, named after the part."""

    firmwareChanged = Signal()
    busyChanged = Signal()
    progress = Signal(object, str)  # percent or None, text (shown on the Flash bar)

    def __init__(self, host, name: str) -> None:
        super().__init__(host)
        self.host = host
        self.name = name
        self.label = LABELS[name]
        self.roles = ROLES[name]
        ui = host.ui
        self.w_project = getattr(ui, f"lineEdit_{name}Project")
        self.w_repo = getattr(ui, f"lineEdit_{name}Repo")
        self.w_browse = getattr(ui, f"pushButton_{name}Browse")
        self.w_branch = getattr(ui, f"label_{name}Branch")
        self.w_checkout = getattr(ui, f"pushButton_{name}Checkout")
        self.w_commit = getattr(ui, f"label_{name}Commit")
        self.w_reload = getattr(ui, f"pushButton_{name}Reload")
        self.w_mode_commit = getattr(ui, f"radioButton_{name}Commit")
        self.w_mode_manual = getattr(ui, f"radioButton_{name}Manual")
        self.w_choose = getattr(ui, f"pushButton_{name}ChooseJob")
        self.w_status = getattr(ui, f"label_{name}Status")
        self.w_build = ui.comboBox_appBuild if name == "app" else getattr(ui, f"label_{name}Build")

        self.profile = None
        self.profile_file = ""
        self.repo_state: RepoState | None = None
        self.loaded: dict[str, tuple[Path, FirmwareSource]] = {}
        self._loaded_key: tuple | None = None  # (commit, jobs, project) last tried; blocks automatic retries
        self._loaded_for: tuple | None = None  # (commit, jobs, project) of what `loaded` holds by commit
        self._generation = 0
        self._starts: dict[str, int] = {}  # worker key -> generation at start (rule 4)
        self._repo_key: str | None = None
        self._load_key: str | None = None
        self._load_for: tuple | None = None
        self._reported: tuple | None = None  # a not-ready report already shown for this key
        self._failed = False  # the last load failed; `_loaded_key` then blocks only automatic retries
        self._pending_after_flash = False
        self._wait_started: float | None = None
        self._wait_timer = QTimer(self)
        self._wait_timer.setSingleShot(True)
        self._wait_timer.timeout.connect(self._on_wait_tick)

        self.w_browse.clicked.connect(self._browse)
        self.w_repo.editingFinished.connect(self._on_repo_edited)
        self.w_project.editingFinished.connect(self._on_project_edited)
        self.w_reload.clicked.connect(self.reload)
        self.w_checkout.clicked.connect(self.open_checkout)
        self.w_mode_commit.toggled.connect(self._on_mode_toggled)
        self.w_choose.clicked.connect(self._on_choose_clicked)
        if name == "app":
            # Designer cannot attach a menu to a button: FFI and ELF are chosen one by one.
            self._choose_menu = QMenu(self.w_choose)
            self._choose_menu.addAction("FFI (.s3)…").triggered.connect(partial(self.choose_job, "ffi"))
            self._choose_menu.addAction("ELF (.elf)…").triggered.connect(partial(self.choose_job, "elf"))

    # -- configuration ------------------------------------------------------------------
    def key(self) -> str:
        return f"{self.profile_file}#{self.name}"

    def default_project(self) -> str:
        if self.profile is None:
            return ""
        if self.name == "app":
            return self.profile.gitlab.project
        source = self.profile.debug_sources.get(self.name)
        return source.project if source else ""

    def full_project(self) -> str:
        text = self.w_project.text().strip() or self.default_project()
        return project_path(split_gitlab_url(self.host.gitlab_url())[1], text)

    def jobs(self) -> list[str]:
        build = self.host.current_build()
        if self.name == "app":
            return [build.ffi_job, build.elf_job] if build else []
        if self.name == "bm":
            return [build.bm_job] if build else []
        source = self.profile.debug_sources.get("fbl") if self.profile else None
        return [source.job or "build"] if source else []

    def available(self) -> bool:
        if self.profile is None or not self.profile.builds:
            return False
        return self.name == "app" or self.name in self.profile.debug_sources

    def has_repo(self) -> bool:
        return bool(self.w_repo.text().strip())

    @property
    def mode(self) -> str:
        return COMMIT if self.w_mode_commit.isChecked() else MANUAL

    def configure(self, profile, profile_file: str) -> None:
        """A profile was selected: fill the fields from the settings and the profile."""
        self.abort()
        self.profile = profile
        self.profile_file = profile_file
        self.repo_state = None
        self.loaded = {}
        self._loaded_key = self._reported = None
        settings = self.host.settings
        if not self.available():
            return
        self.w_project.setText(settings.part_projects.get(self.key(), "") or self.default_project())
        self.w_repo.setText(settings.part_repos.get(self.key(), ""))
        mode = settings.part_modes.get(self.key(), COMMIT if self.has_repo() or self.name == "app" else MANUAL)
        self._set_mode(mode, save=False)
        self._update_build_text()
        self._show_repo_state(None)
        self._restore_manual()
        self._update_controls()
        self.refresh_repo()

    def _set_mode(self, mode: str, save: bool = True) -> None:
        for widget in (self.w_mode_commit, self.w_mode_manual):
            widget.blockSignals(True)
        self.w_mode_commit.setChecked(mode == COMMIT)
        self.w_mode_manual.setChecked(mode != COMMIT)
        for widget in (self.w_mode_commit, self.w_mode_manual):
            widget.blockSignals(False)
        if save:
            self.host.settings.part_modes[self.key()] = mode
            self.host._save_settings()

    def _update_build_text(self) -> None:
        if self.name != "app":
            jobs = self.jobs()
            self.w_build.setText(jobs[0] if jobs else "-")

    def on_build_changed(self) -> None:
        self._update_build_text()
        self._stop_waiting()
        self._reported = None
        if self.mode == COMMIT:
            self.load_for_commit()

    # -- user edits ---------------------------------------------------------------------
    def _browse(self, *_args) -> None:
        folder = QFileDialog.getExistingDirectory(self.host, f"{self.label} repository", self.w_repo.text())
        if folder:
            self.w_repo.setText(folder)
            self._on_repo_edited()

    def _on_repo_edited(self, *_args) -> None:
        if self.profile is None:
            return
        path = self.w_repo.text().strip()
        repos = self.host.settings.part_repos
        if path:
            repos[self.key()] = path
        else:
            repos.pop(self.key(), None)
            if self.name != "app" and self.mode == COMMIT:
                self._set_mode(MANUAL)  # no repository: the job is chosen manually
                self._take_mode_firmware()
        self.host._save_settings()
        self._update_controls()
        self.refresh_repo()

    def _on_project_edited(self, *_args) -> None:
        if self.profile is None:
            return
        text = self.w_project.text().strip()
        projects = self.host.settings.part_projects
        if not text or text == self.default_project():
            projects.pop(self.key(), None)
            self.w_project.setText(self.default_project())
        else:
            projects[self.key()] = text
        self.host._save_settings()

    def _on_mode_toggled(self, *_args) -> None:
        if self.profile is None:
            return
        self.host.settings.part_modes[self.key()] = self.mode
        self.host._save_settings()
        self._stop_waiting()
        self._reported = None
        if self.mode == MANUAL and self.loading():
            # Rule 4: the commit load still on its way must not overwrite a manual choice.
            self._generation += 1
            self.host._workers.cancel(self._load_key)
            self._load_for = None
        self._take_mode_firmware()

    def _take_mode_firmware(self) -> None:
        """What is loaded belongs to the other mode: never show (or flash) a manual job as
        "From commit", or the commit's firmware as "Manual". The commit is loaded again
        (from the cache when it was downloaded before); Manual gets its remembered job back."""
        self.loaded = {}
        self._loaded_key = None
        self._failed = False
        self.host.drop_part_firmware(self)
        self._update_controls()
        if self.mode == COMMIT:
            self._show_status("")
            self.load_for_commit()
        else:
            self._restore_manual()
            if not self.loaded:
                self._show_status("Press Choose Job to pick a job.")

    def _on_choose_clicked(self, *_args) -> None:
        if self.name == "app":
            self._choose_menu.exec(self.w_choose.mapToGlobal(self.w_choose.rect().bottomLeft()))
        else:
            self.choose_job(self.roles[0])

    def choose_job(self, role: str, *_args) -> None:
        self.host.open_part_dialog(self, role)

    def open_checkout(self, *_args) -> None:
        path = self.w_repo.text().strip()
        if path and not self.host.flash_active() and not self.host._closing:
            self.host.open_checkout_for(self, Path(path))

    # -- controls and status ------------------------------------------------------------
    def busy(self) -> bool:
        return self.host._workers.is_running(self._repo_key) or self.host._workers.is_running(self._load_key)

    def loading(self) -> bool:
        return self.host._workers.is_running(self._load_key)

    def waiting(self) -> bool:
        return self._wait_timer.isActive()

    def _update_controls(self) -> None:
        flashing = self.host.flash_active()
        repo = self.has_repo()
        idle = not flashing and not self.loading()
        self.w_checkout.setEnabled(repo and idle)
        self.w_reload.setEnabled(repo and not flashing)
        self.w_mode_commit.setEnabled(repo or self.name == "app")
        if not repo and self.name != "app" and self.mode == COMMIT:
            self._set_mode(MANUAL, save=False)
        self.w_choose.setEnabled(self.mode == MANUAL and idle)
        for widget in (self.w_project, self.w_repo, self.w_browse, self.w_mode_manual):
            widget.setEnabled(not flashing)
        if self.name == "app":
            self.w_build.setEnabled(not flashing and not self.loading())

    def set_flashing(self, flashing: bool) -> None:
        self._update_controls()
        if not flashing and self._pending_after_flash:
            self._pending_after_flash = False
            self.load_for_commit()

    def _show_repo_state(self, state: RepoState | None, error: str = "") -> None:
        self.repo_state = state
        if state is None:
            self.w_branch.setText(NO_REPO)
            self.w_commit.setText(error or NO_REPO)
            return
        self.w_branch.setText(state.branch or "(detached)")
        changes = (f"{len(state.changes)} file(s) have local changes." if state.dirty else "No local changes.")
        self.w_commit.setText(f"{state.commit[:SHORT]} · {changes}")

    def stale_reason(self) -> str:
        """From commit: the firmware held must be that of the repository's exact commit, build and
        project (CLAUDE.md: never from another commit). "" when it is, or nothing is loaded."""
        if not self.available() or self.mode != COMMIT or not self.loaded:
            return ""
        key = self.commit_key()
        if key == self._loaded_for:
            return ""
        if self.repo_state is None:
            return f"{self.label}: the repository cannot be read. Reload it, or select Manual."
        held = self._loaded_for[0][:SHORT] if self._loaded_for else "?"
        if self._loaded_for is not None and self._loaded_for[0] != self.repo_state.commit:
            return (f"{self.label} firmware is for commit {held}, but the repository is at "
                    f"{self.repo_state.commit[:SHORT]}. Wait for its pipeline, or select Manual.")
        return f"{self.label} firmware does not fit the selected build or project yet."

    def status_text(self) -> str:
        return self.w_status.text()

    def _show_status(self, text: str | None = None) -> None:
        if text is None:
            text = "\n".join(status_line(role, src) for role, (_p, src) in self.loaded.items())
        self.w_status.setText(text)
        self.firmwareChanged.emit()

    # -- repository ---------------------------------------------------------------------
    def refresh_repo(self, *_args) -> None:
        if not self.available() or self.host._closing:
            return
        path = self.w_repo.text().strip()
        if not path:
            self._show_repo_state(None)
            if self.name == "app" and self.mode == COMMIT and not self.loaded:
                self._show_status("Choose the App repository, or select Manual.")
            return
        if self.host._workers.is_running(self._repo_key):
            return
        self._repo_key = self.host._workers.start(
            f"part-repo-{self.name}", partial(_read_repo, Path(path)),
            on_succeeded=self._on_repo_read, on_failed=self._on_repo_failed, on_finished=self._on_worker_finished,
        )
        self._starts[self._repo_key] = self._generation
        self.busyChanged.emit()

    def reload(self, *_args) -> None:
        """Reload button: read the repository again and try the load again, even after a failure."""
        self.retry()
        self.refresh_repo()

    def retry(self) -> None:
        """Forget a failed load so the next trigger tries again (connection or settings changed)."""
        if self._failed and not self.loading():
            self._loaded_key = None
            self._reported = None

    def on_window_activated(self) -> None:
        if self.available() and self.has_repo() and not self.host.flash_active():
            self.refresh_repo()

    def _stale(self, key: str) -> bool:
        return self.host._closing or self._starts.pop(key, None) != self._generation

    def _on_repo_read(self, key: str, state: RepoState) -> None:
        if self._stale(key):
            return
        moved = self.repo_state is None or self.repo_state.commit != state.commit
        self._show_repo_state(state)
        if moved:
            self._stop_waiting()
        if self.mode == COMMIT:
            self.load_for_commit()

    def _on_repo_failed(self, key: str, exc: BaseException) -> None:
        if self._stale(key):
            return
        self._show_repo_state(None, error_text(exc))

    # -- loading by commit --------------------------------------------------------------
    def commit_key(self) -> tuple | None:
        state = self.repo_state
        jobs = self.jobs()
        if state is None or not jobs:
            return None
        return (state.commit, tuple(jobs), self.full_project())

    def load_for_commit(self, *_args) -> None:
        """Load the artifact of the checked-out commit, unless it is loaded or being loaded."""
        if not self.available() or self.mode != COMMIT or self.host._closing or not self.host.part_enabled(self.name):
            return
        key = self.commit_key()
        if key is None or key == self._loaded_key or (self.loading() and key == self._load_for):
            return
        if self.host.flash_active():
            self._pending_after_flash = True
            return
        if self.loading():
            self.host._workers.cancel(self._load_key)  # the commit moved on: the old load is stale
        state = self.repo_state
        build = self.host.current_build()
        settings = self.host.gitlab_settings()
        roles = self.roles
        rels = [self._cache_rel(role, state, job, build) for role, job in zip(roles, self.jobs())]
        self._load_for = key
        self._show_status(f"Looking for {', '.join(self.jobs())} of {state.commit[:SHORT]}…")
        self._load_key = self.host._workers.start(
            f"part-load-{self.name}",
            partial(_load_commit, self.host._client_factory, settings, key[2], state, list(key[1]), list(roles), rels),
            on_succeeded=self._on_loaded, on_failed=self._on_load_failed,
            on_finished=self._on_worker_finished, on_progress=self._on_progress,
        )
        self._starts[self._load_key] = self._generation
        self._update_controls()
        self.busyChanged.emit()

    def _cache_rel(self, role: str, state: RepoState, job: str, build) -> PurePath:
        if self.name == "app" and build is not None:
            return build_cache_path(state.branch, state.commit, build.name, role.upper())
        return debug_cache_path(role, state.branch or "detached", state.commit, job)

    def _on_progress(self, percent, text: str) -> None:
        if not self.host._closing:
            self.progress.emit(percent, text)

    def _on_loaded(self, key: str, results) -> None:
        if self._stale(key) or self.mode != COMMIT:
            return
        waited = self._wait_started is not None
        self._failed = False
        self.loaded = {role: (path, source) for role, path, source in results}
        self._loaded_key = self._loaded_for = self._load_for
        self._reported = None
        self._stop_waiting()
        for role, path, source in results:
            log.info("%s loaded from its commit: %s (%s) from %s", role.upper(), source.title, source.cache_note, path)
            self.host.take_part_firmware(self, role, path, source)
        self._show_status()
        if waited:  # the user may be elsewhere while the pipeline ran (spec 4.9)
            commit = self.repo_state.commit[:SHORT] if self.repo_state else ""
            self.host.notify(f"Firmware ready: {self.label} {commit}".strip())

    def _on_load_failed(self, key: str, exc: BaseException) -> None:
        if self._stale(key):
            return
        if isinstance(exc, PipelineNotReady) and exc.waiting:
            self._start_waiting()
            self._show_status(str(exc))
            return
        self._stop_waiting()
        self._failed = True
        text = error_text(exc)
        if self._reported != self._load_for:
            self._reported = self._load_for
            log.warning("%s: %s", self.label, text)
        self._show_status(text)
        if not isinstance(exc, WFlashError):
            log.error("Loading %s failed: %s", self.label, exc)
        # Not retried until something changes: commit, build, mode, the connection, or Reload.
        self._loaded_key = self._load_for

    def _on_worker_finished(self, _key: str) -> None:
        if self.host._closing:
            return
        self._update_controls()
        self.busyChanged.emit()

    # -- waiting for a pipeline ---------------------------------------------------------
    def _start_waiting(self) -> None:
        now = time.monotonic()
        if self._wait_started is None:
            self._wait_started = now
            log.info("%s: waiting for the pipeline of %s", self.label, self.repo_state.commit[:SHORT] if self.repo_state else "?")
        if now - self._wait_started >= WAIT_LIMIT_S:
            self._stop_waiting()
            self._show_status("Stopped waiting after 60 min.")
            return
        self._loaded_key = None
        self._wait_timer.start(int(POLL_S * 1000))

    def _stop_waiting(self) -> None:
        self._wait_timer.stop()
        self._wait_started = None

    def _on_wait_tick(self) -> None:
        if self.host._closing or self.mode != COMMIT:
            return
        self._load_for = None
        self.load_for_commit()

    # -- manual -------------------------------------------------------------------------
    def take_manual(self, role: str, path: Path, source: FirmwareSource) -> None:
        """Firmware chosen in the popup; remembered for the next session."""
        self.loaded[role] = (path, source)
        stored = json.loads(self.host.settings.part_manual.get(self.key(), "{}") or "{}")
        stored[role] = {"path": str(path), "source": source.to_dict()}
        self.host.settings.part_manual[self.key()] = json.dumps(stored)
        self.host._save_settings()
        self._show_status()

    def _restore_manual(self) -> None:
        if self.mode != MANUAL:
            return
        try:
            stored = json.loads(self.host.settings.part_manual.get(self.key(), "{}") or "{}")
        except ValueError:
            stored = {}
        missing = False
        for role, entry in stored.items():
            path = Path(entry.get("path", ""))
            if role in self.roles and (path / MARKER).is_file():
                source = FirmwareSource(**entry["source"])
                self.loaded[role] = (path, source)
                self.host.take_part_firmware(self, role, path, source)
            elif role in self.roles:
                missing = True
        if self.loaded:
            self._show_status()
        elif missing:
            self._show_status("Previous job is no longer in the download folder.")

    # -- life cycle ---------------------------------------------------------------------
    def abort(self) -> None:
        """Drop pending results and stop waiting (profile change, close). Rule 4: bump first."""
        self._generation += 1
        self._stop_waiting()
        self._pending_after_flash = False
        for key in (self._repo_key, self._load_key):
            if key is not None:
                self.host._workers.cancel(key)


def _read_repo(path: Path, _ctx: WorkerContext) -> RepoState:
    return read_state(path)


def _load_commit(client_factory, settings, project: str, state: RepoState, jobs: list[str], roles: list[str],
                 rels: list[PurePath], ctx: WorkerContext):
    """Worker: the named jobs of the commit's newest good pipeline, into folders named after them."""
    client = client_factory(settings)
    project_id = client.get_project_id(project)
    rows = find_commit_jobs(client, project_id, state.commit, jobs, cancel=ctx.cancel)
    cache = NamedArtifactCache(settings.resolved_cache_dir(), settings.max_cached_jobs)
    results = []
    for index, (role, row, rel) in enumerate(zip(roles, rows, rels)):
        keep = [other for other in rels if other != rel]

        def on_bytes(done: int, total: int, role=role, row=row) -> None:
            text = f"Downloading {role.upper()} artifact ({row.job_name} · {state.commit[:SHORT]})"
            ctx.progress(int(done * 100 / total) if total else None, text)

        path, source = fetch_named_artifact(client, project, project_id, row, cache, rel, on_bytes, ctx.cancel, keep)
        results.append((role, path, source))
    return results

