"""Developer panel: source repo, build, Advanced Debug, and the rows of a profile with builds.

Firmware for a profile with `builds` comes from the commit the source repo is on: one click
finds the build's FFI and ELF jobs of that commit and loads both. BM and FBL come from their
own repos, through the Load from GitLab popup. The CAL file is taken from the workspace folder.

Host contract: `self.ui`, `self.profile`, `self.settings`, `self.ctx`, `self._workers`,
`self._closing`, `self._client_factory`, `self._gitlab_dialog`, `self._save_settings()`,
`self.set_mapping_rows()`, `self.selected_instance()`, `self.flash_active()`,
`self._update_flash_controls()`.
"""
from __future__ import annotations

import dataclasses
import os
from functools import partial
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMenu

from wflash.core.artifact_cache import NamedArtifactCache, build_cache_path
from wflash.core.errors import WFlashError
from wflash.core.file_matcher import MappingRow, build_mapping_for_role
from wflash.core.firmware_fetch import fetch_named_artifact, find_build_jobs
from wflash.core.firmware_source import FirmwareSource
from wflash.core.flash_plan import find_cal_files
from wflash.core.logging_setup import get_logger
from wflash.core.source_repo import RepoState, read_state
from wflash.gui.workers import WorkerContext

log = get_logger("ui.source")

REPO_WORKER = "source-repo"
LOAD_WORKER = "source-load"
DEBUG_ROLES = ("bm", "fbl")
SHORT = 8
NOT_LOADED = "Not loaded"
NO_CAL = "No CAL file next to the workspace"


class SourcePanelMixin:
    def _init_source_panel(self) -> None:
        self.repo_state: RepoState | None = None
        self._role_rows: dict[str, list[MappingRow]] = {}  # loaded rows per role
        self._role_sources: dict[str, FirmwareSource] = {}  # ffi, elf, bm, fbl
        self._cal_row: MappingRow | None = None
        self._repo_key: str | None = None
        self._load_key: str | None = None
        ui = self.ui
        ui.pushButton_browseRepo.clicked.connect(self._browse_repo)
        ui.lineEdit_sourceRepo.editingFinished.connect(self._on_repo_edited)
        ui.pushButton_loadBuild.clicked.connect(self.load_build_firmware)
        ui.comboBox_build.currentIndexChanged.connect(self._on_build_changed)
        ui.checkBox_advancedDebug.toggled.connect(self._on_advanced_toggled)
        ui.pushButton_loadBm.clicked.connect(partial(self._open_debug_dialog, "bm"))
        ui.pushButton_loadFbl.clicked.connect(partial(self._open_debug_dialog, "fbl"))
        ui.comboBox_instance.currentIndexChanged.connect(self._on_instance_changed)
        # Designer cannot attach a menu to a button: two loads, FFI and ELF, by hand.
        self._choose_menu = QMenu(ui.pushButton_chooseJob)
        self._choose_menu.addAction("FFI (.s3)…").triggered.connect(partial(self._open_app_dialog, "ffi"))
        self._choose_menu.addAction("ELF (.elf)…").triggered.connect(partial(self._open_app_dialog, "elf"))
        ui.pushButton_chooseJob.setMenu(self._choose_menu)
        ui.frame_developer.setVisible(False)

    # -- state ------------------------------------------------------------------------
    def developer_mode(self) -> bool:
        return self.profile is not None and bool(self.profile.builds)

    def advanced_debug(self) -> bool:
        return self.developer_mode() and self.ui.checkBox_advancedDebug.isChecked()

    def current_build(self):
        name = self.ui.comboBox_build.currentText()
        return self.profile.build(name) if self.developer_mode() and name else None

    def _profile_key(self) -> str:
        return self.settings.last_profile or (self.profile.name if self.profile else "")

    def source_busy(self) -> bool:
        return self._workers.has_running("source-")

    def cal_file_name(self) -> str:
        row = self._cal_row
        return row.selected.name if row is not None and row.selected is not None else ""

    def flash_request_extras(self) -> dict:
        if not self.developer_mode():
            return {}
        return {"profile": self.profile, "advanced": self.advanced_debug(), "cal_file": self.cal_file_name()}

    def flash_block_reason(self) -> str:
        """Why Flash must stay off although the rows may look complete; "" when nothing blocks."""
        if not self.developer_mode():
            return ""
        if self._cal_row is not None and not self._cal_row.candidates:
            return "No CAL file was found next to the workspace. Copy the *_CAL_T008_*.sre file there, then click Refresh."
        build = self.current_build()
        bm = self._role_sources.get("bm")
        if self.advanced_debug() and build is not None and bm is not None and bm.job_name != build.bm_job:
            return f"{bm.job_name} does not fit {build.name}. Load {build.bm_job} for BM."
        return ""

    # -- profile ----------------------------------------------------------------------
    def update_developer_panel(self) -> None:
        """Called after a profile is selected: show the developer panel for a profile with builds."""
        dev = self.developer_mode()
        ui = self.ui
        ui.frame_developer.setVisible(dev)
        ui.label_firmwareSource.setVisible(not dev)
        ui.frame_sourceCard.setVisible(not dev)
        if dev:
            ui.pushButton_loadFromGitlab.setVisible(False)
        self._role_rows, self._role_sources, self._cal_row = {}, {}, None
        self.repo_state = None
        ui.label_loadStatus.clear()
        ui.label_bmSource.setText(NOT_LOADED)
        ui.label_fblSource.setText(NOT_LOADED)
        ui.frame_advancedDebug.setVisible(dev and bool(self.profile.debug_sources))
        if not dev:
            self._show_block_reason()
            return
        key = self._profile_key()
        ui.comboBox_build.blockSignals(True)
        ui.comboBox_build.clear()
        ui.comboBox_build.addItems([b.name for b in self.profile.builds])
        last = self.settings.last_build.get(key, "")
        if last in [b.name for b in self.profile.builds]:
            ui.comboBox_build.setCurrentText(last)
        ui.comboBox_build.blockSignals(False)
        ui.lineEdit_sourceRepo.setText(self.settings.source_repos.get(key, ""))
        self._show_repo_state(None)
        self.rebuild_developer_rows()
        self.refresh_source_repo()

    # -- source repo ------------------------------------------------------------------
    def _browse_repo(self, *_args) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Source repo", self.ui.lineEdit_sourceRepo.text())
        if folder:
            self.ui.lineEdit_sourceRepo.setText(folder)
            self._on_repo_edited()

    def _on_repo_edited(self, *_args) -> None:
        if not self.developer_mode():
            return
        self.settings.source_repos[self._profile_key()] = self.ui.lineEdit_sourceRepo.text().strip()
        self._save_settings()
        self.refresh_source_repo()

    def refresh_source_repo(self, *_args) -> None:
        path = self.ui.lineEdit_sourceRepo.text().strip()
        if not self.developer_mode() or not path or self._workers.is_running(self._repo_key):
            if not path:
                self._show_repo_state(None)
            return
        self._repo_key = self._workers.start(
            REPO_WORKER, partial(_read_repo, Path(path)),
            on_succeeded=self._on_repo_read, on_failed=self._on_repo_failed,
            on_finished=self._on_source_worker_finished,
        )
        self._update_flash_controls()

    def _on_repo_read(self, _key: str, state: RepoState) -> None:
        if self._closing:
            return
        self._show_repo_state(state)

    def _on_repo_failed(self, _key: str, exc: BaseException) -> None:
        if self._closing:
            return
        self._show_repo_state(None)
        self.ui.label_repoChanges.setText(f"{exc} {getattr(exc, 'hint', '')}".strip())

    def _show_repo_state(self, state: RepoState | None) -> None:
        self.repo_state = state
        ui = self.ui
        if state is None:
            ui.label_repoBranch.setText("Branch: -")
            ui.label_repoCommit.setText("Commit: -")
            ui.label_repoChanges.clear()
            ui.pushButton_loadBuild.setText("Load firmware for this commit")
        else:
            ui.label_repoBranch.setText(f"Branch: {state.branch or '(detached)'}")
            ui.label_repoCommit.setText(f"Commit: {state.commit[:SHORT]}")
            ui.pushButton_loadBuild.setText(f"Load firmware for {state.commit[:SHORT]}")
            self._update_repo_notes()
        self._update_flash_controls()

    def _update_repo_notes(self) -> None:
        state = self.repo_state
        if state is None:
            return
        notes = []
        if state.dirty:
            notes.append(f"{len(state.changes)} file(s) have local changes: the build will not match your source exactly.")
        else:
            notes.append("No local changes.")
        loaded = {src.commit for role, src in self._role_sources.items() if role in ("ffi", "elf") and src.commit}
        if loaded and state.commit not in loaded and not any(state.commit.startswith(c) for c in loaded):
            notes.append("Loaded firmware is from another commit.")
        self.ui.label_repoChanges.setText(" ".join(notes))

    # -- loading the build --------------------------------------------------------------
    def _on_build_changed(self, *_args) -> None:
        if not self.developer_mode():
            return
        self.settings.last_build[self._profile_key()] = self.ui.comboBox_build.currentText()
        self._save_settings()
        self._show_block_reason()
        self._update_flash_controls()

    def _app_project(self) -> str:
        return self.settings.ci_project_overrides.get(self._profile_key(), "") or self.profile.gitlab.project

    def load_build_firmware(self, *_args) -> None:
        build = self.current_build()
        state = self.repo_state
        if build is None or state is None or self.source_busy() or self.flash_active() or self._closing:
            return
        settings = dataclasses.replace(self.settings)
        self.ui.label_loadStatus.setText(f"Looking for {build.ffi_job} and {build.elf_job} of {state.commit[:SHORT]}…")
        self._load_key = self._workers.start(
            LOAD_WORKER,
            partial(_load_build, self._client_factory, settings, self._app_project(), build, state),
            on_succeeded=self._on_build_loaded, on_failed=self._on_build_failed,
            on_finished=self._on_source_worker_finished,
        )
        self._update_flash_controls()

    def _on_build_loaded(self, _key: str, result) -> None:
        if self._closing:
            return
        (ffi_path, ffi_source), (elf_path, elf_source) = result
        self._take_role("ffi", ffi_path, ffi_source)
        self._take_role("elf", elf_path, elf_source)
        self.ui.label_loadStatus.setText(
            f"FFI: {ffi_source.job_name} · {ffi_source.commit[:SHORT]} · {ffi_source.cache_note}\n"
            f"ELF: {elf_source.job_name} · {elf_source.commit[:SHORT]} · {elf_source.cache_note}"
        )

    def _on_build_failed(self, _key: str, exc: BaseException) -> None:
        if self._closing:
            return
        hint = getattr(exc, "hint", "")
        self.ui.label_loadStatus.setText(f"{exc} {hint}".strip())
        if not isinstance(exc, WFlashError):
            log.error("Loading the build failed: %s", exc)

    def _on_source_worker_finished(self, _key: str) -> None:
        if not self._closing:
            self._update_flash_controls()

    # -- loading by hand (popup) -------------------------------------------------------------
    def _open_app_dialog(self, part: str, *_args) -> None:
        build = self.current_build()
        if build is None or self.flash_active() or self._closing:
            return
        self._loading_source = f"app:{part}"
        job = build.ffi_job if part == "ffi" else build.elf_job
        label = "FFI (.s3)" if part == "ffi" else "ELF (.elf)"
        self._gitlab_dialog.prepare(label, job, cache=("build", part.upper(), build.name))
        self._gitlab_dialog.open()

    def _open_debug_dialog(self, role: str, *_args) -> None:
        if not self.developer_mode() or self.flash_active() or self._closing:
            return
        source = self.profile.debug_sources.get(role)
        if source is None:
            return
        self._loading_source = f"debug:{role}"
        jobs = {b.bm_job for b in self.profile.builds} if role == "bm" else {source.job or "*"}
        job_filter = jobs.pop() if len(jobs) == 1 else os.path.commonprefix(sorted(jobs)) + "*"
        self._gitlab_dialog.prepare(role.upper(), job_filter, project=source.project, cache=("debug", role))
        self._gitlab_dialog.open()

    def on_developer_firmware(self, path: Path, source: FirmwareSource) -> None:
        """firmwareReady from the popup while a profile with builds is selected."""
        kind, _, role = (self._loading_source or "").partition(":")
        if kind == "app" and role in ("ffi", "elf"):
            self._take_role(role, path, source)
            self.ui.label_loadStatus.setText(f"{role.upper()}: {source.title} · {source.cache_note}")
        elif kind == "debug" and role in DEBUG_ROLES:
            self._take_role(role, path, source)
            label = self.ui.label_bmSource if role == "bm" else self.ui.label_fblSource
            ref = source.detail.split(" · ")[1] if source.detail.count(" · ") >= 1 else ""
            label.setText(f"{source.job_name} · {ref} · {source.commit[:SHORT]}")
        else:
            log.error("Firmware arrived for no known part: %s", source.title)

    def _take_role(self, role: str, path: Path, source: FirmwareSource) -> None:
        self._role_rows[role] = build_mapping_for_role(self.profile, {role}, path)
        self._role_sources[role] = source
        self.ctx.source = {key: src.to_dict() for key, src in self._role_sources.items()}
        log.info("%s loaded: %s (%s) from %s", role.upper(), source.title, source.cache_note, path)
        self.rebuild_developer_rows()
        self._update_repo_notes()
        self._update_developer_warning()

    # -- rows -------------------------------------------------------------------------------
    def _on_advanced_toggled(self, *_args) -> None:
        self.rebuild_developer_rows()

    def _on_instance_changed(self, *_args) -> None:
        if self.developer_mode():
            self._cal_row = None
            self.rebuild_developer_rows()

    def rebuild_developer_rows(self) -> None:
        if not self.developer_mode():
            return
        advanced = self.advanced_debug()
        self.ui.pushButton_loadBm.setEnabled(advanced)
        self.ui.pushButton_loadFbl.setEnabled(advanced)
        rows: list[MappingRow] = []
        for spec in self.profile.programs:
            if spec.role in DEBUG_ROLES and not advanced:
                continue
            if spec.role == "cal":
                rows.append(self._calibration_row(spec))
                continue
            rows.append(self._loaded_row("program", spec.winidea_entry, spec, spec.offset))
        for spec in self.profile.applications:
            if spec.role in DEBUG_ROLES and not advanced:
                continue
            rows.append(self._loaded_row("application", spec.winidea_app, spec, None))
        self.set_mapping_rows(rows, None)
        self._show_block_reason()

    def _loaded_row(self, kind: str, target: str, spec, offset) -> MappingRow:
        for row in self._role_rows.get(spec.role, []):
            if row.kind == kind and row.target == target:
                return row
        return MappingRow(kind, target, spec.pattern, role=spec.role, offset=offset, missing_text=NOT_LOADED)

    def _calibration_row(self, spec) -> MappingRow:
        instance = self.selected_instance()
        folder = Path(instance["workspace"]).parent if instance else None
        files = find_cal_files(folder, spec.pattern) if folder is not None and folder.is_dir() else []
        previous = self._cal_row
        if previous is not None and previous.candidates == files:
            return previous  # keeps the user's choice among several
        row = MappingRow(
            "program", spec.pattern, spec.pattern, files, files[0] if len(files) == 1 else None,
            root=folder, role="cal", offset=spec.offset, missing_text=NO_CAL if not files else "",
        )
        self._cal_row = row
        return row

    def _show_block_reason(self) -> None:
        reason = self.flash_block_reason()
        self.ui.label_flashBlocked.setText(reason)
        self.ui.label_flashBlocked.setVisible(bool(reason))

    def _update_developer_warning(self) -> None:
        commits = {role: src.commit for role, src in self._role_sources.items() if role in ("ffi", "elf") and src.commit}
        different = len(set(commits.values())) > 1
        label = self.ui.label_commitWarning
        label.setVisible(different)
        if different:
            names = ", ".join(f"{role.upper()}: {commit[:SHORT]}" for role, commit in commits.items())
            text = f"FFI and ELF come from different commits ({names}). Symbols may not match the flashed firmware."
            label.setText(text)
            log.warning("%s", text)
        self._show_block_reason()


def _read_repo(path: Path, _ctx: WorkerContext) -> RepoState:
    return read_state(path)


def _load_build(client_factory, settings, project: str, build, state: RepoState, ctx: WorkerContext):
    """Worker: the build's FFI and ELF jobs of the repo's commit, into folders named after it."""
    client = client_factory(settings)
    project_id = client.get_project_id(project)
    ffi, elf = find_build_jobs(client, project_id, state.commit, build.ffi_job, build.elf_job, cancel=ctx.cancel)
    cache = NamedArtifactCache(settings.resolved_cache_dir(), settings.max_cached_jobs)
    ffi_rel = build_cache_path(state.branch, state.commit, build.name, "FFI")
    elf_rel = build_cache_path(state.branch, state.commit, build.name, "ELF")
    ctx.progress(None, f"Downloading {ffi.job_name}")
    first = fetch_named_artifact(client, project, project_id, ffi, cache, ffi_rel, cancel=ctx.cancel, keep=[elf_rel])
    ctx.progress(None, f"Downloading {elf.job_name}")
    second = fetch_named_artifact(client, project, project_id, elf, cache, elf_rel, cancel=ctx.cancel, keep=[ffi_rel])
    return first, second
