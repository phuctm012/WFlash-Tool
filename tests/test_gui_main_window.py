import json
import zipfile
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from tests.gui_stubs import (
    GITLAB_URL,
    OLD_APP,
    PKG_NAME,
    PKG_PROJECT,
    SOURCE,
    TOKEN,
    FakeGitLabSession,
    SessionClientFactory,
    make_artifact_tree,
    patch_keyring,
    write_profiles,
)
from wflash import APP_AUTHOR, __version__
from wflash.core.errors import GitLabError, WinIDEAError
from wflash.core.fake_adapter import FakeWinIDEAAdapter
from wflash.core.flash_workflow import Step
from wflash.core.settings import AppSettings
from wflash.gui import main_window as main_window_module
from wflash.gui.flash_mixin import FlashMixin
from wflash.gui.log_panel import LogPanelMixin
from wflash.gui.main_window import MainWindow
from wflash.gui.mapping_table import NO_FIRMWARE_TITLE, MappingTableMixin
from wflash.gui.style import apply_theme
from wflash.gui.theme import THEMES, current_theme_name

pytestmark = pytest.mark.gui


@pytest.fixture
def env(qtbot, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda parent, title, text: shown.append((title, text)))
    patch_keyring(monkeypatch)
    profiles = write_profiles(tmp_path / "profiles")
    settings = AppSettings(gitlab_url=GITLAB_URL, profiles_dir=str(profiles), cache_dir=str(tmp_path / "cache"))
    adapter = FakeWinIDEAAdapter(download_seconds=0.2)
    session = FakeGitLabSession()
    window = MainWindow(
        settings,
        adapter,
        client_factory=SessionClientFactory(session),
        settings_path=tmp_path / "settings.json",
    )
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: window.ui.comboBox_instance.count() == 1, timeout=3000)
    yield SimpleNamespace(window=window, adapter=adapter, session=session, shown=shown, tmp=tmp_path)
    apply_theme(QApplication.instance(), False)
    QApplication.instance().setStyleSheet("")


class FakePreferences:
    """Stands in for PreferencesDialog: accepts with the settings given to `result`."""

    result = None
    cache_cleared = False

    def __init__(self, settings, parent):
        self._settings = settings

    def exec(self):
        return QDialog.DialogCode.Accepted

    def result_settings(self):
        return FakePreferences.result(self._settings)


def test_gui_main_window_is_composed_from_three_mixins():
    for mixin in (MappingTableMixin, FlashMixin, LogPanelMixin):
        assert issubclass(MainWindow, mixin)
    assert not hasattr(main_window_module, "GitlabBrowserMixin")


def test_gui_profile_loaded_on_start(env):
    w = env.window
    assert w.profile.name == "SAF85xx_Radar"
    assert json.loads((env.tmp / "settings.json").read_text())["last_profile"] == "saf.yaml"
    assert w.ui.pushButton_loadFromGitlab.isEnabled()
    assert not w.ui.pushButton_flash.isEnabled()
    assert w.ui.checkBox_reset.isChecked() and not w.ui.checkBox_run.isChecked()
    assert w.ui.label_sourceTitle.text() == NO_FIRMWARE_TITLE


def test_gui_title_and_status_bar_show_version_and_author(env):
    w = env.window
    assert w.windowTitle() == f"WFlash v{__version__}"
    assert w.label_version.text() == f"Version: v{__version__}"
    assert w.label_author.text() == f"Author: {APP_AUTHOR}"


def test_gui_full_chain_gitlab_dialog_to_flash(env, qtbot):
    w = env.window
    qtbot.mouseClick(w.ui.pushButton_loadFromGitlab, Qt.MouseButton.LeftButton)
    dialog = w._gitlab_dialog
    assert dialog.isVisible() and dialog.isModal()
    dialog.load_refs()
    qtbot.waitUntil(lambda: not dialog.busy(), timeout=3000)
    dialog.browse_jobs()
    qtbot.waitUntil(lambda: dialog.ui.tableWidget_jobs.rowCount() == 1, timeout=3000)
    qtbot.waitUntil(lambda: not dialog.busy(), timeout=3000)
    qtbot.mouseClick(dialog.job_button(0), Qt.MouseButton.LeftButton)
    qtbot.waitUntil(w.mapping_complete, timeout=5000)
    assert not dialog.isVisible()
    assert w.ui.label_sourceTitle.text().endswith("job #7 build_app")
    qtbot.waitUntil(w.ui.pushButton_flash.isEnabled, timeout=3000)
    qtbot.mouseClick(w.ui.pushButton_flash, Qt.MouseButton.LeftButton)
    assert not w.ui.pushButton_preferences.isEnabled() and not w.ui.pushButton_loadFromGitlab.isEnabled()
    w.open_gitlab_dialog()  # refused while flashing
    assert not dialog.isVisible()
    qtbot.waitUntil(lambda: w.current_step() == Step.DONE.value, timeout=5000)
    qtbot.waitUntil(lambda: w.ui.pushButton_flash.text() == "Flash", timeout=3000)
    assert env.adapter.programs["App"].endswith("App.s3") and env.adapter.programs["App"] != OLD_APP
    assert env.adapter.target_state == "halted"
    assert env.shown == []
    assert "Flash completed successfully" in w.log_visible_text()


def test_gui_package_registry_firmware_fills_the_mapping(env, qtbot):
    w = env.window
    w.open_gitlab_dialog()
    dialog = w._gitlab_dialog
    dialog.ui.lineEdit_pkgProject.setText(PKG_PROJECT)
    dialog.ui.lineEdit_packageName.setText(PKG_NAME)
    dialog.fetch_latest()
    qtbot.waitUntil(w.mapping_complete, timeout=5000)
    assert w.ui.label_sourceTitle.text() == f"Package · {PKG_NAME} 1.4.0"
    assert w.ctx.source["kind"] == "package"


def test_gui_ambiguous_mapping_blocks_flash(env):
    root = make_artifact_tree(env.tmp / "art")
    (root / "out" / "y_cm7_0.elf").write_bytes(b"x")
    env.window.on_firmware_ready(root, SOURCE)
    assert not env.window.ui.pushButton_flash.isEnabled()


def test_gui_failure_shows_hint_and_bundle_has_rollback_and_source(env, qtbot):
    env.adapter.fail_on = {"download"}
    w = env.window
    w.on_firmware_ready(make_artifact_tree(env.tmp / "art"), SOURCE)
    w.start_flash()
    qtbot.waitUntil(lambda: bool(env.shown), timeout=5000)
    title, text = env.shown[0]
    assert title == "WFlash error"
    assert "Fake failure" in text and "Hint:" in text and "Export debug bundle" in text
    qtbot.waitUntil(w.ui.pushButton_flash.isEnabled, timeout=3000)
    assert env.adapter.programs["App"] == OLD_APP
    bundle = w.export_bundle(env.tmp / "bundle")
    with zipfile.ZipFile(bundle) as zf:
        assert "Fake failure" in zf.read("errors.txt").decode()
        assert "after_rollback" in zf.read("workspace_snapshots.json").decode()
        assert json.loads(zf.read("source.json"))["title"] == SOURCE.title


def test_gui_rollback_failure_uses_its_own_title(env, qtbot):
    class RestoreFails(FakeWinIDEAAdapter):
        def set_program_path(self, name, path):
            if path == OLD_APP:
                raise WinIDEAError("restore App failed")
            super().set_program_path(name, path)

    w = env.window
    w.adapter = RestoreFails(download_seconds=0.1, fail_on={"download"})
    w.on_firmware_ready(make_artifact_tree(env.tmp / "art"), SOURCE)
    w.start_flash()
    qtbot.waitUntil(lambda: bool(env.shown), timeout=5000)
    assert env.shown[0][0] == "WFlash — rollback failed"
    assert "ROLLBACK FAILED" in env.shown[0][1]
    assert w.ui.label_rollbackWarning.isVisibleTo(w)


def test_gui_bad_profile_shows_error_and_disables_load(qtbot, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda parent, title, text: shown.append(text))
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "bad.yaml").write_text("name: [unclosed", encoding="utf-8")
    w = MainWindow(AppSettings(profiles_dir=str(profiles)), FakeWinIDEAAdapter(), settings_path=tmp_path / "s.json")
    qtbot.addWidget(w)
    assert w.profile is None
    assert shown and "Invalid YAML" in shown[0]
    assert not w.ui.pushButton_loadFromGitlab.isEnabled()
    w.open_gitlab_dialog()
    assert not w._gitlab_dialog.isVisible()


def test_gui_preferences_saved_without_any_token(env, monkeypatch, qtbot):
    from dataclasses import replace

    FakePreferences.result = staticmethod(lambda s: replace(s, verbose=True, max_cached_jobs=3))
    monkeypatch.setattr(main_window_module, "PreferencesDialog", FakePreferences)
    w = env.window
    w.open_preferences()
    assert w.settings.verbose is True and w.settings.max_cached_jobs == 3
    saved = json.loads((env.tmp / "settings.json").read_text())
    assert saved["verbose"] is True and saved["gitlab_url"] == GITLAB_URL
    assert TOKEN not in (env.tmp / "settings.json").read_text()
    main_window_module.log.info("echo %s", TOKEN)
    qtbot.waitUntil(lambda: "echo ***" in w.log_visible_text(), timeout=1000)
    assert TOKEN not in w.log_visible_text()


def test_gui_dark_mode_applies_immediately_and_is_saved(env, monkeypatch, qtbot):
    from dataclasses import replace

    w = env.window
    w.on_firmware_ready(make_artifact_tree(env.tmp / "art", {"x_cm7_0.elf": b"3"}), SOURCE)
    FakePreferences.result = staticmethod(lambda s: replace(s, dark_mode=True))
    monkeypatch.setattr(main_window_module, "PreferencesDialog", FakePreferences)
    w.open_preferences()
    assert current_theme_name() == "dark"
    assert THEMES["dark"]["primary"] in QApplication.instance().styleSheet()
    assert json.loads((env.tmp / "settings.json").read_text())["dark_mode"] is True
    assert "Theme: dark" in w.log_visible_text()
    FakePreferences.result = staticmethod(lambda s: replace(s, dark_mode=False))
    w.open_preferences()
    assert current_theme_name() == "light"
    assert THEMES["light"]["primary"] in QApplication.instance().styleSheet()


def test_gui_preferences_cache_cleared_unloads_the_firmware(env, monkeypatch):
    class ClearingPreferences(FakePreferences):
        cache_cleared = True

        def exec(self):
            return QDialog.DialogCode.Rejected

    w = env.window
    w.on_firmware_ready(make_artifact_tree(env.tmp / "art"), SOURCE)
    monkeypatch.setattr(main_window_module, "PreferencesDialog", ClearingPreferences)
    w.open_preferences()
    assert w.mapping_rows() == [] and w.ui.label_sourceTitle.text() == NO_FIRMWARE_TITLE


def test_gui_show_error_redacts_unregistered_token(env):
    token = "glpat-" + "Ab3dEf6hIj9kLm2nOp5q"
    env.shown.clear()
    env.window.show_error(GitLabError(f"401 for {token}", hint=f"retry with {token}"))
    title, text = env.shown[0]
    assert "***" in text and token not in text


def test_gui_profile_path_recorded_even_when_profile_is_broken(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    bad = profiles / "bad.yaml"
    bad.write_text("name: [unclosed", encoding="utf-8")
    w = MainWindow(AppSettings(profiles_dir=str(profiles)), FakeWinIDEAAdapter(), settings_path=tmp_path / "s.json")
    qtbot.addWidget(w)
    assert w.profile is None
    assert w.ctx.profile_path == bad
