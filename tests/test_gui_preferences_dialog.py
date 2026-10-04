import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from wflash.core.artifact_cache import ArtifactCache
from wflash.core.errors import ArtifactError
from wflash.core.settings import AppSettings
from wflash.gui.preferences_dialog import PreferencesDialog

pytestmark = pytest.mark.gui


def make(qtbot, **kwargs):
    settings = AppSettings(last_profile="keep.yaml", gitlab_url="https://gl", package_name="fw", **kwargs)
    dialog = PreferencesDialog(settings)
    qtbot.addWidget(dialog)
    return dialog


def test_gui_fields_loaded(qtbot):
    dialog = make(qtbot, max_cached_jobs=7, verbose=True, dark_mode=True, cache_dir="/c")
    assert dialog.ui.lineEdit_cacheDir.text() == "/c"
    assert dialog.ui.spinBox_maxCachedJobs.value() == 7
    assert dialog.ui.checkBox_verbose.isChecked()
    assert dialog.ui.checkBox_darkMode.isChecked()


def test_gui_preferences_has_no_gitlab_fields(qtbot):
    dialog = make(qtbot)
    names = set(vars(dialog.ui))
    assert not {"lineEdit_gitlabUrl", "lineEdit_token", "lineEdit_caBundle"} & names


def test_gui_accept_returns_new_settings_and_keeps_the_rest(qtbot, tmp_path):
    dialog = make(qtbot)
    dialog.ui.lineEdit_cacheDir.setText(f" {tmp_path / 'cache'} ")
    dialog.ui.lineEdit_profilesDir.setText(str(tmp_path))
    dialog.ui.spinBox_maxCachedJobs.setValue(5)
    dialog.ui.checkBox_verbose.setChecked(True)
    dialog.ui.checkBox_darkMode.setChecked(True)
    dialog.ok_button().click()
    assert dialog.result() == QDialog.DialogCode.Accepted
    result = dialog.result_settings()
    assert result.cache_dir == str(tmp_path / "cache")
    assert result.profiles_dir == str(tmp_path)
    assert result.max_cached_jobs == 5
    assert result.verbose is True and result.dark_mode is True
    # Fields edited elsewhere are carried over untouched.
    assert (result.last_profile, result.gitlab_url, result.package_name) == ("keep.yaml", "https://gl", "fw")


def test_gui_missing_profiles_folder_blocks_accept(qtbot, tmp_path):
    dialog = make(qtbot)
    dialog.ui.lineEdit_profilesDir.setText(str(tmp_path / "missing"))
    dialog.ok_button().click()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "Profiles folder not found" in dialog.ui.label_error.text()


def test_gui_clear_cache_clears_artifacts_and_packages_after_confirmation(qtbot, tmp_path, monkeypatch):
    root = tmp_path / "cache"
    for base in (root, root / "packages"):
        (base / "42" / "7" / "files").mkdir(parents=True)
        (base / "42" / "7" / ".complete").write_text("x")
    dialog = make(qtbot, cache_dir=str(root))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    dialog.ui.pushButton_clearCache.click()
    assert ArtifactCache(root).entries() and not dialog.cache_cleared
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    dialog.ui.pushButton_clearCache.click()
    assert ArtifactCache(root).entries() == []
    assert ArtifactCache(root / "packages").entries() == []
    assert root.exists()  # the root itself is never deleted
    assert dialog.cache_cleared


def test_gui_clear_cache_failure_is_shown(qtbot, tmp_path, monkeypatch):
    dialog = make(qtbot, cache_dir=str(tmp_path / "cache"))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)

    def boom(self):
        raise ArtifactError("Could not clear 2 cached artifact(s)", hint="Close programs holding files.")

    monkeypatch.setattr(ArtifactCache, "clear", boom)
    dialog.ui.pushButton_clearCache.click()
    assert "Could not clear 2" in dialog.ui.label_error.text()
    assert "Close programs" in dialog.ui.label_error.text()
    assert dialog.cache_cleared  # a partial clear may still have removed the loaded files
