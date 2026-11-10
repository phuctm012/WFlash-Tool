"""Main window: composed from the mixins, all sharing one `self.ui` built from main_window.ui.

This module owns the state the mixins share (settings, adapter, debug context, worker
registry, closing guard), the Setting tab (profile, folders, GitLab connection, winIDEA),
the Load from GitLab popup, the theme, restoring the last session and the shutdown path.
"""
from __future__ import annotations

import base64
import dataclasses
from pathlib import Path

from PySide6.QtCore import QByteArray, QEvent, QThreadPool
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QMainWindow, QMessageBox

from wflash import APP_AUTHOR, DISPLAY_VERSION
from wflash.core.debug_bundle import DebugContext
from wflash.core.errors import CancelledError, ProfileError, WFlashError
from wflash.core.logging_setup import get_logger, redact, register_secret
from wflash.core.profile import Profile, list_profiles, load_profile
from wflash.core.settings import AppSettings, default_cache_dir, get_token, set_token
from wflash.core.winidea_adapter import WinIDEAAdapter
from wflash.gui.flash_mixin import FlashMixin
from wflash.gui.gitlab_dialog import WORKER_PREFIX, ClientFactory, GitlabDialog, default_client_factory
from wflash.gui.gitlab_tab import GitlabTabMixin
from wflash.gui.log_panel import LogPanelMixin
from wflash.gui.mapping_table import MappingTableMixin
from wflash.gui.menu_actions import MenuActionsMixin
from wflash.gui.style import apply_theme, repolish
from wflash.gui.ui_main_window import Ui_MainWindow
from wflash.gui.workers import WorkerRegistry

log = get_logger("ui")

# Bounded wait in closeEvent: long enough for a cancelled flash to roll back, short
# enough that a hung worker cannot freeze the app forever (threading rule 3).
CLOSE_TIMEOUT_S = 15.0


class MainWindow(GitlabTabMixin, MappingTableMixin, FlashMixin, LogPanelMixin, MenuActionsMixin, QMainWindow):
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
        self.setWindowTitle(f"WFlash v{DISPLAY_VERSION}")  # the version only exists at runtime
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
        self._init_gitlab_tab()
        self._init_status_bar()
        self._init_menu()
        # One dialog for the window's whole life: it is never deleted while one of its
        # workers could still report to it (CLAUDE.md threading rules 1 and 4).
        self._gitlab_dialog = GitlabDialog(self)
        self._gitlab_dialog.firmwareReady.connect(self.on_firmware_ready)
        self.ui.comboBox_profile.currentIndexChanged.connect(self._on_profile_selected)
        self.ui.pushButton_reloadProfiles.clicked.connect(self.reload_profiles)
        self.ui.pushButton_loadFromGitlab.clicked.connect(self.open_gitlab_dialog)
        self._init_setting_tab()

        self._restore_window()
        self.reload_profiles()
        self.refresh_instances()
        self._update_flash_controls()

    def _init_status_bar(self) -> None:
        # Designer cannot put widgets into a status bar; these two are fixed text.
        self.label_version = QLabel(f"Version: v{DISPLAY_VERSION}")
        self.label_author = QLabel(f"Author: {APP_AUTHOR}")
        self.statusBar().addWidget(self.label_version)
        self.statusBar().addPermanentWidget(self.label_author)

    # -- shared helpers -------------------------------------------------------------
    def show_error(self, exc: BaseException) -> None:
        text = redact(str(exc))
        hint = getattr(exc, "hint", "")
        if hint:
            text += f"\n\n{redact(hint)}"  # the detail is in the log and the debug bundle
        title = "WFlash — rollback failed" if getattr(exc, "rollback_failed", False) else "WFlash error"
        QMessageBox.critical(self, title, text)

    def _save_settings(self) -> None:
        try:
            self.settings.save(self._settings_path)
        except OSError as exc:
            log.warning("Cannot save settings: %s", exc)

    def gitlab_busy(self) -> bool:
        return self._workers.has_running(WORKER_PREFIX)

    def gitlab_settings(self) -> AppSettings:
        """A copy for a worker, carrying the effective GitLab URL of the current profile."""
        return dataclasses.replace(self.settings, gitlab_url=self.gitlab_url())

    # -- Setting tab ------------------------------------------------------------------
    def _init_setting_tab(self) -> None:
        """Every field saves when it is left (no OK button); the checkboxes save on toggle."""
        ui = self.ui
        s = self.settings
        ui.lineEdit_downloadDir.setText(s.cache_dir)
        ui.lineEdit_downloadDir.setPlaceholderText(f"Default: {default_cache_dir()}")
        ui.label_settingError.setVisible(False)
        ui.lineEdit_downloadDir.editingFinished.connect(self._on_download_dir_edited)
        ui.pushButton_browseDownloadDir.clicked.connect(self._browse_download_dir)
        ui.lineEdit_gitlabUrl.editingFinished.connect(self._on_gitlab_url_edited)
        ui.lineEdit_token.editingFinished.connect(self._on_token_edited)
        for box, name in ((ui.checkBox_reset, "reset_target"), (ui.checkBox_run, "run_after_reset"),
                          (ui.checkBox_verifyFlash, "verify_samples")):
            box.setChecked(getattr(s, name))
            box.toggled.connect(self._on_after_flash_toggled)

    def _setting_error(self, text: str) -> None:
        self.ui.label_settingError.setText(text)
        self.ui.label_settingError.setVisible(bool(text))

    def _on_download_dir_edited(self, *_args) -> None:
        text = self.ui.lineEdit_downloadDir.text().strip()
        if text and not Path(text).is_dir():
            self._setting_error(f"Download folder not found: {text}")
            return
        self._setting_error("")
        if text != self.settings.cache_dir:
            self.settings.cache_dir = text
            self._save_settings()
            log.info("Download folder: %s", self.settings.resolved_cache_dir())

    def _browse_download_dir(self, *_args) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Download folder", str(self.settings.resolved_cache_dir()))
        if folder:
            self.ui.lineEdit_downloadDir.setText(folder)
            self._on_download_dir_edited()

    def _show_gitlab_connection(self) -> None:
        url = self.gitlab_url()
        self.ui.lineEdit_gitlabUrl.setText(url)
        self.ui.lineEdit_token.setText(get_token(url) or "" if url else "")

    def _on_gitlab_url_edited(self, *_args) -> None:
        text = self.ui.lineEdit_gitlabUrl.text().strip().rstrip("/")
        if text and not text.startswith(("http://", "https://")):
            self._setting_error("Enter the GitLab URL with https://")
            return
        self._setting_error("")
        profile_file = self.settings.last_profile
        default = (self.profile.gitlab.url or "") if self.profile is not None else ""
        urls = self.settings.gitlab_urls
        if not text or text == default.rstrip("/"):
            urls.pop(profile_file, None)
        else:
            urls[profile_file] = text
        self._save_settings()
        self._show_gitlab_connection()
        self.retry_parts()

    def _on_token_edited(self, *_args) -> None:
        token = self.ui.lineEdit_token.text().strip()
        url = self.gitlab_url()
        if not token or not url or token == (get_token(url) or ""):
            return
        register_secret(token)
        try:
            set_token(url, token)
        except WFlashError as exc:
            self.show_error(exc)
            return
        log.info("Token stored in the system keyring")
        self.retry_parts()

    def _on_after_flash_toggled(self, *_args) -> None:
        ui = self.ui
        self.settings.reset_target = ui.checkBox_reset.isChecked()
        self.settings.run_after_reset = ui.checkBox_run.isChecked()
        self.settings.verify_samples = ui.checkBox_verifyFlash.isChecked()
        self._save_settings()

    # -- last session ----------------------------------------------------------------
    def _restore_window(self) -> None:
        if self.settings.window_geometry:
            try:
                self.restoreGeometry(QByteArray(base64.b64decode(self.settings.window_geometry)))
            except (ValueError, TypeError):
                log.warning("Ignoring a saved window geometry that cannot be read")
        tabs = self.ui.tabWidget_main
        if 0 <= self.settings.last_tab < tabs.count():
            tabs.setCurrentIndex(self.settings.last_tab)
        self.ui.action_darkMode.setChecked(self.settings.dark_mode)

    def _remember_window(self) -> None:
        self.settings.window_geometry = base64.b64encode(bytes(self.saveGeometry())).decode("ascii")
        self.settings.last_tab = self.ui.tabWidget_main.currentIndex()
        self._save_settings()

    # -- profiles -------------------------------------------------------------------
    def reload_profiles(self, *_args) -> None:
        directory = self.settings.resolved_profiles_dir()
        paths = list_profiles(directory)
        combo = self.ui.comboBox_profile
        combo.blockSignals(True)
        combo.clear()
        names = {path: _display_name(path) for path in paths}
        for path in paths:
            name = names[path]
            if list(names.values()).count(name) > 1:
                name = f"{name} ({path.name})"
            combo.addItem(name, str(path))
        if paths:
            index = next((i for i, p in enumerate(paths) if p.name == self.settings.last_profile), 0)
            combo.setCurrentIndex(index)
        combo.blockSignals(False)
        # One profile (SUZ05 today): nothing to choose, so the row is hidden; it comes back with a second one.
        for widget in (self.ui.label_profile, combo, self.ui.pushButton_reloadProfiles):
            widget.setVisible(len(paths) != 1)
        if not paths:
            log.warning("No profiles found in %s", directory)
        self._on_profile_selected()

    def _on_profile_selected(self, *_args) -> None:
        data = self.ui.comboBox_profile.currentData()
        self.profile = None
        self.clear_mapping()
        self.update_developer_panel()
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
        self.settings.last_profile = path.name
        self._save_settings()
        self.rebuild_source_slots()
        self.update_developer_panel()
        self._show_gitlab_connection()
        log.info("Profile loaded: %s (%s)", profile.name, path)
        self._update_flash_controls()

    # -- Load from GitLab -----------------------------------------------------------
    def open_gitlab_dialog(self, *_args) -> None:
        # Never while flashing: the button is disabled then, this is the second guard.
        if self.flash_active() or self._closing or self.profile is None:
            return
        self._loading_source = None
        self._gitlab_dialog.prepare()
        self._gitlab_dialog.open()  # window-modal: Flash cannot be pressed while it is open

    def open_gitlab_dialog_for(self, source_id: str) -> None:
        if self.flash_active() or self._closing or self.profile is None:
            return
        self._loading_source = source_id
        spec = self.profile.sources[source_id]
        self._gitlab_dialog.prepare(spec.label, self.profile.job_filter_for(source_id))
        self._gitlab_dialog.open()

    # -- theme ------------------------------------------------------------------------
    def apply_dark_mode(self, dark: bool) -> None:
        """Switch the theme now: application stylesheet plus the colours code paints itself."""
        apply_theme(QApplication.instance(), dark)
        self.refresh_mapping_theme()
        self.refresh_log_theme()
        repolish(self.ui.pushButton_flash)
        repolish(self.ui.progressBar_flash)
        self.render_summary()
        log.info("Theme: %s", "dark" if dark else "light")

    def changeEvent(self, event) -> None:
        # Coming back to WFlash (from a terminal or an IDE): read the source repo again.
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            self.refresh_source_repo_on_activate()
        super().changeEvent(event)

    # -- shutdown -------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        if self._close_in_progress:
            event.ignore()  # a nested close() from inside the wait's event pumping
            return
        if self.flash_active() and not self._closing:
            text = (
                "The flash is being programmed and cannot be interrupted. Quitting now could leave "
                "the ECU with erased flash. Quit anyway?"
                if self.flash_locked()
                else "A flash is in progress. Cancel it (the previous workspace paths will be restored) and quit?"
            )
            answer = QMessageBox.question(self, "WFlash", text)
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        # Threading rule 4: the guards go up before anything is cancelled, so completion
        # signals still queued are settled by the slots instead of starting more work.
        self._closing = True
        self._close_in_progress = True
        # The wait below pumps events and the menu bar is outside the central widget: no
        # shortcut (Ctrl+E file dialog, F5, Tools…) may start anything while it runs.
        self.lock_menus()
        self._remember_window()
        self.abort_parts()
        self._gitlab_dialog.abort_for_close()
        self._checkout_dialog.abort_for_close()
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
        self.hide_tray()
        super().closeEvent(event)


def _display_name(path: Path) -> str:
    """The profile's own name for the Profile list; the file name if it cannot be read."""
    try:
        return load_profile(path).name
    except ProfileError:
        return path.stem
