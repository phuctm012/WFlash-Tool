import json
import zipfile
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

from tests.gui_stubs import (
    OLD_APP,
    TOKEN,
    FakeGitLabSession,
    SessionClientFactory,
    make_artifact_tree,
    write_profiles,
)
from wflash.core.errors import GitLabError, WinIDEAError
from wflash.core.fake_adapter import FakeWinIDEAAdapter
from wflash.core.flash_workflow import Step
from wflash.core.settings import AppSettings
from wflash.gui import main_window as main_window_module
from wflash.gui.flash_mixin import FlashMixin
from wflash.gui.gitlab_browser import GitlabBrowserMixin
from wflash.gui.log_panel import LogPanelMixin
from wflash.gui.main_window import MainWindow
from wflash.gui.mapping_table import MappingTableMixin

pytestmark = pytest.mark.gui


@pytest.fixture
def env(qtbot, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda parent, title, text: shown.append((title, text)))
    monkeypatch.setattr(main_window_module, "get_token", lambda url: None)
    profiles = write_profiles(tmp_path / "profiles")
    settings = AppSettings(profiles_dir=str(profiles), cache_dir=str(tmp_path / "cache"))
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
    return SimpleNamespace(window=window, adapter=adapter, session=session, shown=shown, tmp=tmp_path)


def test_gui_main_window_is_composed_from_the_four_mixins():
    for mixin in (GitlabBrowserMixin, MappingTableMixin, FlashMixin, LogPanelMixin):
        assert issubclass(MainWindow, mixin)


def test_gui_profile_loaded_on_start(env):
    w = env.window
    assert w.profile.name == "SAF85xx_Radar"
    assert json.loads((env.tmp / "settings.json").read_text())["last_profile"] == "saf.yaml"
    assert "group/saf85xx-sw" in w.ui.label_project.text()
    assert not w.ui.pushButton_flash.isEnabled()
    assert w.ui.checkBox_reset.isChecked() and not w.ui.checkBox_run.isChecked()


def test_gui_full_chain_gitlab_to_flash(env, qtbot):
    w = env.window
    qtbot.mouseClick(w.ui.pushButton_refreshRefs, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: w.ui.listWidget_pipelines.count() == 1, timeout=3000)
    w.ui.listWidget_pipelines.setCurrentRow(0)
    qtbot.waitUntil(lambda: w.ui.listWidget_jobs.count() == 1, timeout=3000)
    w.ui.listWidget_jobs.setCurrentRow(0)
    qtbot.mouseClick(w.ui.pushButton_downloadArtifact, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(w.mapping_complete, timeout=5000)
    qtbot.waitUntil(w.ui.pushButton_flash.isEnabled, timeout=3000)
    qtbot.mouseClick(w.ui.pushButton_flash, Qt.MouseButton.LeftButton)
    assert not w.ui.pushButton_settings.isEnabled() and not w.ui.groupBox_gitlab.isEnabled()
    qtbot.waitUntil(lambda: w.ui.label_step.text() == Step.DONE.value, timeout=5000)
    qtbot.waitUntil(w.ui.pushButton_flash.isEnabled, timeout=3000)
    assert env.adapter.programs["App"].endswith("App.s3") and env.adapter.programs["App"] != OLD_APP
    assert env.adapter.target_state == "halted"
    assert env.shown == []
    assert "Flash completed successfully" in w.log_visible_text()


def test_gui_ambiguous_mapping_blocks_flash(env):
    root = make_artifact_tree(env.tmp / "art")
    (root / "out" / "y_cm7_0.elf").write_bytes(b"x")
    env.window.on_artifact_ready(root, "job #7")
    assert not env.window.ui.pushButton_flash.isEnabled()


def test_gui_failure_shows_hint_and_bundle_has_rollback(env, qtbot):
    env.adapter.fail_on = {"download"}
    w = env.window
    w.on_artifact_ready(make_artifact_tree(env.tmp / "art"), "job #7")
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


def test_gui_rollback_failure_uses_its_own_title(env, qtbot):
    class RestoreFails(FakeWinIDEAAdapter):
        def set_program_path(self, name, path):
            if path == OLD_APP:
                raise WinIDEAError("restore App failed")
            super().set_program_path(name, path)

    w = env.window
    w.adapter = RestoreFails(download_seconds=0.1, fail_on={"download"})
    w.on_artifact_ready(make_artifact_tree(env.tmp / "art"), "job #7")
    w.start_flash()
    qtbot.waitUntil(lambda: bool(env.shown), timeout=5000)
    assert env.shown[0][0] == "WFlash — rollback failed"
    assert "ROLLBACK FAILED" in env.shown[0][1]
    assert w.ui.label_rollbackWarning.isVisibleTo(w)


def test_gui_bad_profile_shows_error(qtbot, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda parent, title, text: shown.append(text))
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "bad.yaml").write_text("name: [unclosed", encoding="utf-8")
    w = MainWindow(AppSettings(profiles_dir=str(profiles)), FakeWinIDEAAdapter(), settings_path=tmp_path / "s.json")
    qtbot.addWidget(w)
    assert w.profile is None
    assert shown and "Invalid YAML" in shown[0]
    assert not w.ui.pushButton_refreshRefs.isEnabled()


def test_gui_settings_saved_token_stored_and_redacted(env, monkeypatch, qtbot):
    stored = {}
    monkeypatch.setattr(main_window_module, "set_token", lambda url, token: stored.update({url: token}))

    class AcceptingDialog:
        def __init__(self, settings, token, parent):
            self.cache_cleared = False
            self._settings = settings

        def exec(self):
            return QDialog.DialogCode.Accepted

        def result_settings(self):
            return AppSettings(
                gitlab_url="https://gitlab.example.com",
                profiles_dir=self._settings.profiles_dir,
                cache_dir=self._settings.cache_dir,
                verbose=True,
            )

        def result_token(self):
            return TOKEN

    monkeypatch.setattr(main_window_module, "SettingsDialog", AcceptingDialog)
    w = env.window
    w.open_settings()
    assert stored == {"https://gitlab.example.com": TOKEN}
    assert w.settings.verbose is True
    saved = json.loads((env.tmp / "settings.json").read_text())
    assert saved["gitlab_url"] == "https://gitlab.example.com"
    assert TOKEN not in (env.tmp / "settings.json").read_text()
    main_window_module.log.info("echo %s", TOKEN)
    qtbot.waitUntil(lambda: "echo ***" in w.log_visible_text(), timeout=1000)
    assert TOKEN not in w.log_visible_text()


def test_gui_keyring_failure_is_reported(env, monkeypatch):
    def refuse(url, token):
        raise GitLabError("Cannot store the GitLab token", hint="Unlock the keyring")

    monkeypatch.setattr(main_window_module, "set_token", refuse)

    class AcceptingDialog:
        def __init__(self, settings, token, parent):
            self.cache_cleared = False

        def exec(self):
            return QDialog.DialogCode.Accepted

        def result_settings(self):
            return AppSettings(gitlab_url="https://gl", profiles_dir=env.window.settings.profiles_dir)

        def result_token(self):
            return TOKEN

    monkeypatch.setattr(main_window_module, "SettingsDialog", AcceptingDialog)
    env.window.open_settings()
    assert any("Cannot store the GitLab token" in text for _, text in env.shown)
