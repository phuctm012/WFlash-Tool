"""GitLab tab mixin: App, Boot Manager and Flash Bootloader for a profile with `builds`.

Replaces the developer panel (spec 2026-11-09). Each part is a PartController (part_controller.py);
this mixin wires them to the window, builds the planned mapping rows from what they loaded,
draws the "Firmware to flash" summary on the Flash tab and shows their downloads and the
checkout on the Flash progress bar while no flash runs.

Host contract: `self.ui`, `self.profile`, `self.settings`, `self.ctx`, `self._workers`,
`self._closing`, `self._client_factory`, `self._gitlab_dialog`, `self._save_settings()`,
`self.set_mapping_rows()`, `self.selected_instance()`, `self.flash_active()`,
`self._update_flash_controls()`, `self.show_side_progress()`, `self.clear_side_progress()`,
`self.notify()`, `self.gitlab_url()`, `self.gitlab_settings()`.
"""
from __future__ import annotations

import html
from pathlib import Path

from wflash.core.file_matcher import MappingRow, build_mapping_for_role
from wflash.core.firmware_source import FirmwareSource
from wflash.core.flash_plan import find_cal_files
from wflash.core.logging_setup import get_logger
from wflash.gui.checkout_dialog import CheckoutDialog
from wflash.gui.part_controller import COMMIT, SHORT, PartController
from wflash.gui.theme import current_theme

log = get_logger("ui.gitlab_tab")

DEBUG_ROLES = ("bm", "fbl")
NOT_LOADED = "Not loaded"
NO_CAL = "No CAL file next to the workspace"
PART_OF_ROLE = {"ffi": "app", "elf": "app", "bm": "bm", "fbl": "fbl"}


class GitlabTabMixin:
    def _init_gitlab_tab(self) -> None:
        self._role_rows: dict[str, list[MappingRow]] = {}
        self._role_sources: dict[str, FirmwareSource] = {}
        self._cal_row: MappingRow | None = None
        self._side_progress = False
        self._parts_flashing = False
        self._checkout_part: PartController | None = None
        self.parts = {name: PartController(self, name) for name in ("app", "bm", "fbl")}
        for part in self.parts.values():
            part.firmwareChanged.connect(self.render_summary)
            part.busyChanged.connect(self._on_parts_busy_changed)
            part.progress.connect(self._on_part_progress)
        ui = self.ui
        ui.comboBox_appBuild.currentIndexChanged.connect(self._on_build_changed)
        ui.checkBox_advancedDebug.toggled.connect(self._on_advanced_toggled)
        ui.comboBox_instance.currentIndexChanged.connect(self._on_instance_changed)
        self._checkout_dialog = CheckoutDialog(self)  # built here, on the GUI thread (rule 6)
        self._checkout_dialog.checkedOut.connect(self._on_checked_out)
        self._checkout_dialog.activity.connect(self._on_checkout_activity)
        self._set_gitlab_tab_visible(False)

    # -- state ------------------------------------------------------------------------
    def developer_mode(self) -> bool:
        return self.profile is not None and bool(self.profile.builds)

    def advanced_debug(self) -> bool:
        return self.developer_mode() and self.ui.checkBox_advancedDebug.isChecked()

    def part_enabled(self, name: str) -> bool:
        return name == "app" or self.advanced_debug()

    def current_build(self):
        name = self.ui.comboBox_appBuild.currentText()
        return self.profile.build(name) if self.developer_mode() and name else None

    def _profile_key(self) -> str:
        return self.settings.last_profile or (self.profile.name if self.profile else "")

    def source_busy(self) -> bool:
        return any(part.loading() for part in self.parts.values()) or self._checkout_dialog.busy()

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
        for name, part in self.parts.items():
            reason = part.stale_reason() if self.part_enabled(name) else ""
            if reason:
                return reason
        build = self.current_build()
        bm = self._role_sources.get("bm")
        if self.advanced_debug() and build is not None and bm is not None and bm.job_name != build.bm_job:
            return f"{bm.job_name} does not fit {build.name}. Load {build.bm_job} for BM."
        return ""

    # -- profile ----------------------------------------------------------------------
    def _set_gitlab_tab_visible(self, visible: bool) -> None:
        tabs = self.ui.tabWidget_main
        tabs.setTabVisible(tabs.indexOf(self.ui.tab_gitlab), visible)

    def update_developer_panel(self) -> None:
        """Called after a profile is selected: the GitLab tab for a profile with builds."""
        dev = self.developer_mode()
        ui = self.ui
        self._set_gitlab_tab_visible(dev)
        ui.frame_firmwareSummary.setVisible(dev)
        ui.frame_gitlabSource.setVisible(not dev)
        self._role_rows, self._role_sources, self._cal_row = {}, {}, None
        profile_file = self.settings.last_profile
        if dev:
            key = self._profile_key()
            ui.comboBox_appBuild.blockSignals(True)
            ui.comboBox_appBuild.clear()
            ui.comboBox_appBuild.addItems([b.name for b in self.profile.builds])
            last = self.settings.last_build.get(key, "")
            if last in [b.name for b in self.profile.builds]:
                ui.comboBox_appBuild.setCurrentText(last)
            ui.comboBox_appBuild.blockSignals(False)
            has_debug = bool(self.profile.debug_sources)
            ui.checkBox_advancedDebug.setVisible(has_debug)
            ui.checkBox_advancedDebug.blockSignals(True)
            ui.checkBox_advancedDebug.setChecked(has_debug and self.settings.advanced_debug)
            ui.checkBox_advancedDebug.blockSignals(False)
            ui.widget_debugParts.setVisible(self.advanced_debug())
            ui.groupBox_bm.setVisible("bm" in self.profile.debug_sources)
            ui.groupBox_fbl.setVisible("fbl" in self.profile.debug_sources)
        for part in self.parts.values():
            part.configure(self.profile if dev else None, profile_file)
        if dev:
            self.rebuild_developer_rows()
        else:
            self._show_block_reason()
        self.render_summary()

    # -- GitLab connection for workers ------------------------------------------------
    def gitlab_url(self) -> str:
        profile_url = self.profile.gitlab.url if self.profile is not None else None
        return self.settings.gitlab_url_for(self.settings.last_profile, profile_url)

    # -- parts --------------------------------------------------------------------------
    def _on_build_changed(self, *_args) -> None:
        if not self.developer_mode():
            return
        self.settings.last_build[self._profile_key()] = self.ui.comboBox_appBuild.currentText()
        self._save_settings()
        for name in ("app", "bm"):
            self.parts[name].on_build_changed()
        self._show_block_reason()
        self.render_summary()
        self._update_flash_controls()

    def _on_advanced_toggled(self, *_args) -> None:
        if not self.developer_mode():
            return
        self.settings.advanced_debug = self.ui.checkBox_advancedDebug.isChecked()
        self._save_settings()
        self.ui.widget_debugParts.setVisible(self.advanced_debug())
        if self.advanced_debug():
            for name in DEBUG_ROLES:
                if self.parts[name].mode == COMMIT:
                    self.parts[name].load_for_commit()
        self.rebuild_developer_rows()
        self.render_summary()

    def open_part_dialog(self, part: PartController, role: str) -> None:
        """Manual mode: the Load from GitLab popup for one role of a part."""
        build = self.current_build()
        if build is None or self.flash_active() or self._closing:
            return
        self._loading_source = f"part:{part.name}:{role}"
        job = part.jobs()[part.roles.index(role)] if part.jobs() else "*"
        label = {"ffi": "FFI (.s3)", "elf": "ELF (.elf)"}.get(role, role.upper())
        cache = ("build", role.upper(), build.name) if part.name == "app" else ("debug", role)
        self._gitlab_dialog.prepare(label, job, project=part.full_project(), cache=cache)
        self._gitlab_dialog.open()

    def on_developer_firmware(self, path: Path, source: FirmwareSource) -> None:
        """firmwareReady from the popup while a profile with builds is selected."""
        kind, _, rest = (self._loading_source or "").partition(":")
        name, _, role = rest.partition(":")
        part = self.parts.get(name) if kind == "part" else None
        if part is None or role not in part.roles:
            log.error("Firmware arrived for no known part: %s", source.title)
            return
        part.take_manual(role, path, source)
        self.take_part_firmware(part, role, path, source)

    def take_part_firmware(self, part: PartController, role: str, path: Path, source: FirmwareSource) -> None:
        self.take_part_firmwares(part, [(role, path, source)])

    def take_part_firmwares(self, part: PartController, items) -> None:
        """Every role of one load at once: the commit check sees FFI and ELF of the same load,
        never the new FFI beside the previous ELF (user report, 2026-11-10)."""
        for role, path, source in items:
            self._role_rows[role] = build_mapping_for_role(self.profile, {role}, path)
            self._role_sources[role] = source
            log.info("%s loaded: %s (%s) from %s", role.upper(), source.title, source.cache_note, path)
        self.ctx.source = {key: src.to_dict() for key, src in self._role_sources.items()}
        self.rebuild_developer_rows()
        self._update_developer_warning()
        self.render_summary()

    def drop_part_firmware(self, part: PartController) -> None:
        """The part switched mode: its rows go back to Not loaded until the other mode loads."""
        for role in part.roles:
            self._role_rows.pop(role, None)
            self._role_sources.pop(role, None)
        self.ctx.source = {key: src.to_dict() for key, src in self._role_sources.items()}
        self.rebuild_developer_rows()
        self._update_developer_warning()
        self.render_summary()

    def retry_parts(self) -> None:
        """The GitLab connection changed: let every part try its load again."""
        if not self.developer_mode():
            return
        for name, part in self.parts.items():
            part.retry()
            if self.part_enabled(name) and part.mode == COMMIT:
                part.load_for_commit()

    def open_checkout_for(self, part: PartController, path: Path) -> None:
        self._checkout_part = part
        self._checkout_dialog.prepare(path, part.full_project(), part.label)
        self._checkout_dialog.open()  # window-modal: nothing else can start while it is open

    def _on_checked_out(self) -> None:
        part = self._checkout_part
        if part is not None and not self._closing:
            part.refresh_repo()

    def refresh_source_repo_on_activate(self) -> None:
        """The window got the focus back: a commit or a checkout may have happened meanwhile."""
        if self.developer_mode() and not self.flash_active() and not self._closing:
            for name, part in self.parts.items():
                if self.part_enabled(name):
                    part.on_window_activated()

    def sync_parts_flashing(self) -> None:
        flashing = self.flash_active()
        if flashing != self._parts_flashing:
            self._parts_flashing = flashing
            for part in self.parts.values():
                part.set_flashing(flashing)

    def abort_parts(self) -> None:
        for part in self.parts.values():
            part.abort()

    # -- progress on the Flash bar ------------------------------------------------------
    def _on_part_progress(self, percent, text: str) -> None:
        if self._closing or self.flash_active():
            return
        self._side_progress = True
        self.show_side_progress(percent, text)

    def _on_checkout_activity(self, text: str) -> None:
        if self._closing or self.flash_active():
            return
        if text:
            self._side_progress = True
            self.show_side_progress(None, text)
        else:
            self._on_parts_busy_changed()

    def _on_parts_busy_changed(self) -> None:
        if self._closing:
            return
        if self._side_progress and not self.source_busy() and not self.flash_active():
            self._side_progress = False
            self.clear_side_progress()
        self.render_summary()
        self._show_block_reason()
        self._update_flash_controls()

    # -- rows -------------------------------------------------------------------------------
    def _on_instance_changed(self, *_args) -> None:
        if self.developer_mode():
            self._cal_row = None
            self.rebuild_developer_rows()

    def rebuild_developer_rows(self) -> None:
        if not self.developer_mode():
            return
        advanced = self.advanced_debug()
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

    # -- summary on the Flash tab -------------------------------------------------------
    def render_summary(self) -> None:
        if self._closing:
            return
        ui = self.ui
        if not self.developer_mode():
            for label in (ui.label_summaryApp, ui.label_summaryBm, ui.label_summaryFbl):
                label.clear()
            return
        ui.label_summaryApp.setText(self._part_summary(self.parts["app"]))
        for name, label in (("bm", ui.label_summaryBm), ("fbl", ui.label_summaryFbl)):
            shown = self.advanced_debug() and name in self.profile.debug_sources
            label.setVisible(shown)
            if shown:
                label.setText(self._part_summary(self.parts[name]))
        ui.label_summaryAdvanced.setText(f"Advanced Debug: {'on' if self.advanced_debug() else 'off'}")

    def _part_summary(self, part: PartController) -> str:
        t = current_theme()
        source = next((src for _p, src in part.loaded.values()), None)
        if part.loading():
            status = "Loading…"
        elif part.waiting():
            status = "Waiting for pipeline…"
        elif source is not None:
            status = source.cache_note.split(" · ")[0]
        else:
            status = NOT_LOADED
        mode = "From commit" if part.mode == COMMIT else "Manual"
        first = ("Build", self.ui.comboBox_appBuild.currentText()) if part.name == "app" else (
            "Job", source.job_name if source else (part.jobs() or ["-"])[0])
        ref = source.detail.split(" · ")[1] if source is not None and source.detail.count(" · ") >= 1 else "-"
        rows = [first, ("Branch", ref), ("Commit", source.commit[:SHORT] if source and source.commit else "-"),
                ("Status", status)]
        cells = "".join(
            f"<tr><td style='color:{t['muted']};padding-right:10px'>{html.escape(k)}</td>"
            f"<td>{html.escape(str(v))}</td></tr>" for k, v in rows
        )
        pill = (f"<span style='background:{t['surface']};color:{t['primary']};font-size:small'>"
                f"&nbsp;{html.escape(mode)}&nbsp;</span>")
        return f"<b>{html.escape(part.label)}</b> {pill}<table cellspacing='0' cellpadding='1'>{cells}</table>"
