"""Main window: composed from the mixins, all sharing one `self.ui` built from main_window.ui.

This module owns the state the mixins share (settings, adapter, debug context, worker
registry, closing guard), the profile selector, the Load from GitLab popup, the
Preferences dialog, the theme switch and the shutdown path.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMainWindow, QMessageBox

from wflash import APP_AUTHOR, __version__
from wflash.core.debug_bundle import DebugContext
from wflash.core.errors import CancelledError, ProfileError
from wflash.core.logging_setup import get_logger, redact, set_verbose
from wflash.core.profile import Profile, list_profiles, load_profile
from wflash.core.settings import AppSettings
from wflash.core.winidea_adapter import WinIDEAAdapter
from wflash.gui.flash_mixin import FlashMixin
from wflash.gui.gitlab_dialog import WORKER_PREFIX, ClientFactory, GitlabDialog, default_client_factory
from wflash.gui.log_panel import LogPanelMixin
from wflash.gui.mapping_table import MappingTableMixin
from wflash.gui.preferences_dialog import PreferencesDialog
from wflash.gui.style import apply_theme, repolish
from wflash.gui.ui_main_window import Ui_MainWindow
from wflash.gui.workers import WorkerRegistry

log = get_logger("ui")

# Bounded wait in closeEvent: long enough for a cancelled flash to roll back, short
# enough that a hung worker cannot freeze the app forever (threading rule 3).
CLOSE_TIMEOUT_S = 15.0


class MainWindow(MappingTableMixin, FlashMixin, LogPanelMixin, QMainWindow):
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
        self.setWindowTitle(f"WFlash v{__version__}")  # the version only exists at runtime
        self.settings = settings
        self.adapter = adapter
        self.log_file = log_file
        self._client_factory = client_factory
        self._settings_path = settings_path
        self.ctx = DebugContext()
        self.profile: Profile | None = None
        self._closing = False
        self._close_in_progress = False  # re-entrancy guard for closeEvent
        self._pool = pool or QThreadPool(self)
        self._workers = WorkerRegistry(self._pool, self)  # main thread, in __init__ (rule 6)

        self._init_log_panel()  # first, so the other parts' start-up is logged
        self._init_mapping_table()
        self._init_flash()
        self._init_status_bar()
        # One dialog for the window's whole life: it is never deleted while one of its
        # workers could still report to it (CLAUDE.md threading rules 1 and 4).
        self._gitlab_dialog = GitlabDialog(self)
        self._gitlab_dialog.firmwareReady.connect(self.on_firmware_ready)
        self.ui.comboBox_profile.currentIndexChanged.connect(self._on_profile_selected)
        self.ui.pushButton_reloadProfiles.clicked.connect(self.reload_profiles)
        self.ui.pushButton_loadFromGitlab.clicked.connect(self.open_gitlab_dialog)
        self.ui.pushButton_preferences.clicked.connect(self.open_preferences)

        self.reload_profiles()
        self.refresh_instances()
        self._update_flash_controls()

    def _init_status_bar(self) -> None:
        # Designer cannot put widgets into a status bar; these two are fixed text.
        self.label_version = QLabel(f"Version: v{__version__}")
        self.label_author = QLabel(f"Author: {APP_AUTHOR}")
        self.statusBar().addWidget(self.label_version)
        self.statusBar().addPermanentWidget(self.label_author)

    # -- shared helpers -------------------------------------------------------------
    def show_error(self, exc: BaseException) -> None:
        text = redact(str(exc))
        hint = getattr(exc, "hint", "")
        if hint:
            text += f"\n\nHint: {redact(hint)}"
        text += "\n\nUse 'Export debug bundle…' in the Information tab to collect logs for support."
        title = "WFlash — rollback failed" if getattr(exc, "rollback_failed", False) else "WFlash error"
        QMessageBox.critical(self, title, text)

    def _save_settings(self) -> None:
        try:
            self.settings.save(self._settings_path)
        except OSError as exc:
            log.warning("Cannot save settings: %s", exc)

    def gitlab_busy(self) -> bool:
        return self._workers.has_running(WORKER_PREFIX)

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
            self._update_flash_controls()
            return
        path = Path(data)
        self.ctx.profile_path = path  # before loading: a bundle after a ProfileError needs the broken file
        try:
            profile = load_profile(path)
        except ProfileError as exc:
            log.error("%s", exc)
            self.ctx.add_error(exc)
            self.show_error(exc)
            self._update_flash_controls()
            return
        self.profile = profile
        self.ui.checkBox_reset.setChecked(profile.post_flash.reset)
        self.ui.checkBox_run.setChecked(profile.post_flash.run)
        self.settings.last_profile = path.name
        self._save_settings()
        log.info("Profile loaded: %s (%s)", profile.name, path)
        self._update_flash_controls()

    # -- Load from GitLab -----------------------------------------------------------
    def open_gitlab_dialog(self, *_args) -> None:
        # Never while flashing: the button is disabled then, this is the second guard.
        if self.flash_active() or self._closing or self.profile is None:
            return
        self._gitlab_dialog.prepare()
        self._gitlab_dialog.open()  # window-modal: Flash cannot be pressed while it is open

    # -- preferences and theme --------------------------------------------------------
    def open_preferences(self, *_args) -> None:
        if self.flash_active() or self.gitlab_busy():
            return
        dialog = PreferencesDialog(self.settings, self)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        if dialog.cache_cleared:
            self.clear_mapping()  # the loaded firmware's files may be gone
        if not accepted:
            return
        dark_before = self.settings.dark_mode
        self.settings = dialog.result_settings()
        set_verbose(self.settings.verbose)
        self._save_settings()
        log.info("Preferences saved")
        if self.settings.dark_mode != dark_before:
            self.apply_dark_mode(self.settings.dark_mode)
        self.reload_profiles()

    def apply_dark_mode(self, dark: bool) -> None:
        """Switch the theme now: application stylesheet plus the colours code paints itself."""
        apply_theme(QApplication.instance(), dark)
        self.refresh_mapping_theme()
        self.refresh_log_theme()
        repolish(self.ui.pushButton_flash)
        repolish(self.ui.progressBar_flash)
        log.info("Theme: %s", "dark" if dark else "light")

    # -- shutdown -------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        if self._close_in_progress:
            event.ignore()  # a nested close() from inside the wait's event pumping
            return
        if self.flash_active() and not self._closing:
            answer = QMessageBox.question(
                self,
                "WFlash",
                "A flash is in progress. Cancel it (the previous workspace paths will be restored) and quit?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        # Threading rule 4: the guards go up before anything is cancelled, so completion
        # signals still queued are settled by the slots instead of starting more work.
        self._closing = True
        self._close_in_progress = True
        self._gitlab_dialog.abort_for_close()
        flash_key = self._flash_key
        # The wait pumps events: lock the UI so no modal dialog (Preferences, file dialogs)
        # can open nested inside it and break the bound.
        self.centralWidget().setEnabled(False)
        self.statusBar().showMessage("Closing — waiting for the flash to cancel and restore paths…")
        self._workers.cancel_all()
        if not self._workers.wait_idle(CLOSE_TIMEOUT_S):
            keys = self._workers.abandon_running()
            log.critical(
                "Workers still running after %.0f s: %s. If a flash was running, check the "
                "winIDEA download/symbol paths before flashing again.",
                CLOSE_TIMEOUT_S,
                keys,
            )
            if flash_key is not None and flash_key in keys:
                QMessageBox.warning(
                    self,
                    "WFlash — flash still running",
                    "The flash did not stop in time. The winIDEA workspace may still point to "
                    "the new files — check the download/symbol file list in winIDEA before "
                    "flashing again.",
                )
        if self._gitlab_dialog.isVisible():
            self._gitlab_dialog.reject()  # its workers were cancelled and waited for above
        exc, self._flash_error_during_close = self._flash_error_during_close, None
        if exc is not None:
            # _on_flash_failed only stored it (no dialogs while closing); record it now.
            self.ctx.add_error(exc)
            if getattr(exc, "rollback_failed", False):
                log.critical("Rollback failed: the winIDEA workspace may still point to the new files")
                self.show_error(exc)
            elif isinstance(exc, CancelledError):
                log.warning("Flash cancelled by closing; previous paths restored")
            else:
                log.error("Flash error while closing: %s", exc)
        self._detach_log_panel()
        super().closeEvent(event)
