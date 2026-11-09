"""Menu bar mixin: File, View, Tools, Help (spec 2026-11-09, 3.1 and 4.7), and notifications.

The menus and actions live in main_window.ui; this mixin connects them. Tools run on the
worker pool like everything that talks to GitLab or winIDEA, and never while a flash runs.
Check winIDEA cores is read only: connect, `core_states()`, disconnect.

Notifications (spec 4.9): a tray message and a flashing taskbar entry, only when the
window is not the active one. The tray icon is built on the GUI thread in `_init_menu`
and shown only for the message.

Host contract: `self.ui`, `self.settings`, `self.adapter`, `self.profile`, `self._workers`,
`self._closing`, `self.flash_active()`, `self.selected_instance()`, `self.gitlab_settings()`,
`self.parts`, `self.export_bundle`, `self.apply_dark_mode()`, `self.refresh_instances()`,
`self.log_file`, `self._client_factory`, `self._save_settings()`.
"""
from __future__ import annotations

import sys
from functools import partial
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from wflash import APP_AUTHOR, __version__
from wflash.core.debug_bundle import collect_env_info
from wflash.core.errors import GitLabError
from wflash.core.flash_history import history_path
from wflash.core.gitlab_url import project_path, split_gitlab_url
from wflash.core.logging_setup import default_log_dir, get_logger
from wflash.gui.style import RESOURCES_DIR, app_icon
from wflash.gui.workers import WorkerContext

log = get_logger("ui.menu")

USER_GUIDE = RESOURCES_DIR / "help" / "user_guide.html"
TOOLS_PREFIX = "tools-"


class MenuActionsMixin:
    def _init_menu(self) -> None:
        ui = self.ui
        ui.action_exportBundle.triggered.connect(self._on_export_bundle_clicked)
        ui.action_openHistory.triggered.connect(self.open_flash_history)
        ui.action_openLogFolder.triggered.connect(self.open_log_folder)
        ui.action_openDownloadFolder.triggered.connect(self.open_download_folder)
        ui.action_exit.triggered.connect(self.close)  # the normal closeEvent: asks while flashing
        ui.action_darkMode.toggled.connect(self._on_dark_mode_toggled)
        for action, tab in ((ui.action_tabFlash, ui.tab_flash), (ui.action_tabGitlab, ui.tab_gitlab),
                            (ui.action_tabSetting, ui.tab_setting)):
            action.triggered.connect(partial(self._show_tab, tab))
        ui.action_testGitlab.triggered.connect(self.test_gitlab_connection)
        ui.action_checkCores.triggered.connect(self.check_winidea_cores)
        ui.action_refreshInstances.triggered.connect(self.refresh_instances)
        ui.action_userGuide.triggered.connect(self.open_user_guide)
        ui.action_about.triggered.connect(self.show_about)
        self._tray: QSystemTrayIcon | None = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray = QSystemTrayIcon(app_icon(), self)

    def lock_menus(self) -> None:
        """Closing: every menu action off for good (Exit included: closeEvent ignores nested closes)."""
        self.ui.menuBar_main.setEnabled(False)
        for action in self.findChildren(QAction):
            action.setEnabled(False)

    # -- File --------------------------------------------------------------------------
    def _open(self, path: Path, what: str) -> bool:
        if not path.exists():
            log.warning("%s not found: %s", what, path)
            return False
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        return True

    def open_flash_history(self, *_args) -> None:
        if not self._open(history_path(), "Flash history"):
            log.info("No flash history yet: it is written after the first flash.")

    def open_log_folder(self, *_args) -> None:
        folder = Path(self.log_file).parent if self.log_file else default_log_dir()
        self._open(folder, "Log folder")

    def open_download_folder(self, *_args) -> None:
        folder = self.settings.resolved_cache_dir()
        folder.mkdir(parents=True, exist_ok=True)
        self._open(folder, "Download folder")

    # -- View --------------------------------------------------------------------------
    def _on_dark_mode_toggled(self, checked: bool) -> None:
        if checked == self.settings.dark_mode:
            return
        self.settings.dark_mode = checked
        self._save_settings()
        self.apply_dark_mode(checked)

    def _show_tab(self, tab, *_args) -> None:
        tabs = self.ui.tabWidget_main
        index = tabs.indexOf(tab)
        if tabs.isTabVisible(index):
            tabs.setCurrentIndex(index)

    # -- Tools -------------------------------------------------------------------------
    def tools_busy(self) -> bool:
        return self._workers.has_running(TOOLS_PREFIX)

    def test_gitlab_connection(self, *_args) -> None:
        if self.flash_active() or self._closing or self.tools_busy():
            return
        settings = self.gitlab_settings()
        project = ""
        if self.profile is not None:
            project = project_path(split_gitlab_url(settings.gitlab_url)[1], self.parts["app"].w_project.text().strip()
                                   or self.profile.gitlab.project)
        log.info("Testing the GitLab connection to %s…", split_gitlab_url(settings.gitlab_url)[0] or "(no URL)")
        self._workers.start(
            f"{TOOLS_PREFIX}gitlab", partial(_test_gitlab, self._client_factory, settings, project),
            on_succeeded=self._on_gitlab_tested, on_failed=self._on_tool_failed, on_finished=self._on_tool_finished,
        )

    def _on_gitlab_tested(self, _key: str, text: str) -> None:
        if not self._closing:
            log.info("GitLab connection works: %s", text)

    def check_winidea_cores(self, *_args) -> None:
        if self.flash_active() or self._closing or self.tools_busy() or self._workers.is_running(self._instances_key):
            return  # one caller of the adapter at a time
        instance = self.selected_instance()
        if instance is None:
            log.warning("Check winIDEA cores: no winIDEA instance selected (Setting tab)")
            return
        self._workers.start(
            f"{TOOLS_PREFIX}cores", partial(_check_cores, self.adapter, instance["instance_id"]),
            on_succeeded=self._on_cores_checked, on_failed=self._on_tool_failed, on_finished=self._on_tool_finished,
        )
        self._update_flash_controls()

    def _on_cores_checked(self, _key: str, states) -> None:
        if self._closing:
            return
        summary = ", ".join(f"{name} {text}" for name, text in states)
        if any(text.upper() == "NOT ACCESSIBLE" for _name, text in states):
            log.warning("winIDEA cores: %s. WFlash resets the ECU before flashing; power-cycle it if that is not enough.", summary)
        else:
            log.info("winIDEA cores: %s", summary)

    def _on_tool_failed(self, _key: str, exc: BaseException) -> None:
        if self._closing:
            return
        hint = getattr(exc, "hint", "")
        log.error("%s%s", exc, f" (hint: {hint})" if hint else "")

    def _on_tool_finished(self, _key: str) -> None:
        if not self._closing:
            self._update_flash_controls()

    # -- Help --------------------------------------------------------------------------
    def open_user_guide(self, *_args) -> None:
        if not self._open(USER_GUIDE, "User guide"):
            log.error("The user guide is missing from this installation: %s", USER_GUIDE)

    def show_about(self, *_args) -> None:
        env = collect_env_info()
        info = getattr(self, "ctx", None)
        winidea = info.adapter_info.get("winidea_version", "-") if info is not None else "-"
        QMessageBox.about(
            self, "About WFlash",
            f"<b>WFlash v{__version__}</b><br>Flashes SAF85xx firmware from GitLab CI through winIDEA.<br><br>"
            f"isystem.connect: {env.get('isystem.connect', '-')}<br>winIDEA: {winidea}<br>"
            f"Python: {sys.version.split()[0]}<br>PySide6: {env.get('PySide6', '-')}<br><br>Author: {APP_AUTHOR}",
        )

    # -- notifications -----------------------------------------------------------------
    def notify(self, text: str) -> None:
        """Tell the user something finished, only when they are looking elsewhere (spec 4.9)."""
        if self._closing or self.isActiveWindow():
            return
        QApplication.alert(self)
        if self._tray is not None:
            self._tray.show()
            self._tray.showMessage("WFlash", text, app_icon(), 8000)
        log.info("Notified: %s", text)

    def hide_tray(self) -> None:
        if getattr(self, "_tray", None) is not None:
            self._tray.hide()


def _test_gitlab(client_factory, settings, project: str, _ctx: WorkerContext) -> str:
    """One read-only API call with the URL and token of the Setting tab: the profile's project."""
    if not project:
        raise GitLabError("No project to test with.", hint="Select a profile in the Setting tab first.")
    client = client_factory(settings)
    project_id = client.get_project_id(project)
    return f"project {project} (id {project_id})"


def _check_cores(adapter, instance_id: str, _ctx: WorkerContext):
    """Read only: connect, read the core states, disconnect."""
    adapter.connect(instance_id)
    try:
        return adapter.core_states()
    finally:
        adapter.disconnect()
