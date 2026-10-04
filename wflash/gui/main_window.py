"""Main window: composed from the mixins, all sharing one `self.ui` built from main_window.ui.

This module owns the state the mixins share (settings, adapter, debug context, worker
registry, closing guard), the profile bar, the settings dialog and the shutdown path.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QDialog, QMainWindow, QMessageBox

from wflash.core.debug_bundle import DebugContext
from wflash.core.errors import GitLabError, ProfileError
from wflash.core.logging_setup import get_logger, register_secret, set_verbose
from wflash.core.profile import Profile, list_profiles, load_profile
from wflash.core.settings import AppSettings, get_token, set_token
from wflash.core.winidea_adapter import WinIDEAAdapter
from wflash.gui.flash_mixin import FlashMixin
from wflash.gui.gitlab_browser import ClientFactory, GitlabBrowserMixin, default_client_factory
from wflash.gui.log_panel import LogPanelMixin
from wflash.gui.mapping_table import MappingTableMixin
from wflash.gui.settings_dialog import SettingsDialog
from wflash.gui.ui_main_window import Ui_MainWindow
from wflash.gui.workers import WorkerRegistry

log = get_logger("ui")


class MainWindow(GitlabBrowserMixin, MappingTableMixin, FlashMixin, LogPanelMixin, QMainWindow):
    def __init__(
        self,
        settings: AppSettings,
        adapter: WinIDEAAdapter,
        client_factory: ClientFactory = default_client_factory,
        log_file: Path | None = None,
        settings_path: Path | None = None,
        pool: QThreadPool | None = None,
    ) -> None:
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.settings = settings
        self.adapter = adapter
        self.log_file = log_file
        self._client_factory = client_factory
        self._settings_path = settings_path
        self.ctx = DebugContext()
        self.profile: Profile | None = None
        self._closing = False
        self._pool = pool or QThreadPool(self)
        self._workers = WorkerRegistry(self._pool, self)  # main thread, in __init__ (rule 6)

        self._init_log_panel()  # first, so the other parts' start-up is logged
        self._init_mapping_table()
        self._init_gitlab_browser()
        self._init_flash()
        self.ui.comboBox_profile.currentIndexChanged.connect(self._on_profile_selected)
        self.ui.pushButton_reloadProfiles.clicked.connect(self.reload_profiles)
        self.ui.pushButton_settings.clicked.connect(self.open_settings)

        self.reload_profiles()
        self.refresh_instances()
        self._update_flash_controls()

    # -- shared helpers -------------------------------------------------------------
    def show_error(self, exc: BaseException) -> None:
        text = str(exc)
        hint = getattr(exc, "hint", "")
        if hint:
            text += f"\n\nHint: {hint}"
        text += "\n\nUse 'Export debug bundle…' in the log panel to collect logs for support."
        title = "WFlash — rollback failed" if getattr(exc, "rollback_failed", False) else "WFlash error"
        QMessageBox.critical(self, title, text)

    def _save_settings(self) -> None:
        try:
            self.settings.save(self._settings_path)
        except OSError as exc:
            log.warning("Cannot save settings: %s", exc)

    # -- profiles -------------------------------------------------------------------
    def reload_profiles(self, *_args) -> None:
        directory = self.settings.resolved_profiles_dir()
        paths = list_profiles(directory)
        combo = self.ui.comboBox_profile
        combo.blockSignals(True)
        combo.clear()
        for path in paths:
            combo.addItem(path.stem, str(path))
        if paths:
            index = next((i for i, p in enumerate(paths) if p.name == self.settings.last_profile), 0)
            combo.setCurrentIndex(index)
        combo.blockSignals(False)
        if not paths:
            log.warning("No profiles found in %s", directory)
        self._on_profile_selected()

    def _on_profile_selected(self, *_args) -> None:
        data = self.ui.comboBox_profile.currentData()
        self.profile = None
        self.clear_mapping()
        if data is None:
            self.set_gitlab_profile(None)
            self._update_flash_controls()
            return
        path = Path(data)
        try:
            profile = load_profile(path)
        except ProfileError as exc:
            log.error("%s", exc)
            self.ctx.add_error(exc)
            self.set_gitlab_profile(None)
            self.show_error(exc)
            self._update_flash_controls()
            return
        self.profile = profile
        self.ctx.profile_path = path
        self.ui.checkBox_reset.setChecked(profile.post_flash.reset)
        self.ui.checkBox_run.setChecked(profile.post_flash.run)
        self.set_gitlab_profile(profile)
        self.settings.last_profile = path.name
        self._save_settings()
        log.info("Profile loaded: %s (%s)", profile.name, path)
        self._update_flash_controls()

    # -- settings -------------------------------------------------------------------
    def open_settings(self, *_args) -> None:
        if self.flash_active() or self.gitlab_busy():
            return
        dialog = SettingsDialog(self.settings, get_token(self.settings.gitlab_url) or "", self)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        if dialog.cache_cleared:
            self.clear_mapping()  # the loaded artifact's files are gone
        if not accepted:
            return
        self.settings = dialog.result_settings()
        token = dialog.result_token()
        if token and self.settings.gitlab_url:
            register_secret(token)
            try:
                set_token(self.settings.gitlab_url, token)
            except GitLabError as exc:
                log.error("%s", exc)
                self.show_error(exc)
        set_verbose(self.settings.verbose)
        self._save_settings()
        log.info("Settings saved")
        self.reload_profiles()

    # -- shutdown -------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        # Minimal for now; Task 21 adds cancel + bounded wait + rollback reporting.
        self._detach_log_panel()
        super().closeEvent(event)
