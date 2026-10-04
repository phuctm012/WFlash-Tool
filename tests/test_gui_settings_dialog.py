import pytest
from PySide6.QtWidgets import QDialog, QLineEdit, QMessageBox

from wflash.core.artifact_cache import ArtifactCache
from wflash.core.settings import AppSettings
from wflash.gui.settings_dialog import SettingsDialog

pytestmark = pytest.mark.gui


def make(qtbot, **kwargs):
    dialog = SettingsDialog(AppSettings(last_profile="keep.yaml", **kwargs), "old-token")
    qtbot.addWidget(dialog)
    return dialog


def test_gui_fields_loaded_and_token_hidden(qtbot):
    dialog = make(qtbot, gitlab_url="https://gl", max_cached_jobs=7, verbose=True)
    assert dialog.ui.lineEdit_gitlabUrl.text() == "https://gl"
    assert dialog.ui.lineEdit_token.text() == "old-token"
    assert dialog.ui.lineEdit_token.echoMode() == QLineEdit.EchoMode.Password
    assert dialog.ui.spinBox_maxCachedJobs.value() == 7
    assert dialog.ui.checkBox_verbose.isChecked()


def test_gui_accept_returns_new_settings(qtbot, tmp_path):
    dialog = make(qtbot)
    ca = tmp_path / "ca.pem"
    ca.write_text("cert")
    dialog.ui.lineEdit_gitlabUrl.setText("https://gitlab.example.com/ ")
    dialog.ui.lineEdit_token.setText(" glpat-new ")
    dialog.ui.lineEdit_caBundle.setText(str(ca))
    dialog.ui.spinBox_maxCachedJobs.setValue(5)
    dialog.ui.checkBox_verbose.setChecked(True)
    dialog.ok_button().click()
    assert dialog.result() == QDialog.DialogCode.Accepted
    result = dialog.result_settings()
    assert result.gitlab_url == "https://gitlab.example.com"
    assert result.ca_bundle == str(ca)
    assert result.max_cached_jobs == 5
    assert result.verbose is True
    assert result.last_profile == "keep.yaml"
    assert dialog.result_token() == "glpat-new"


def test_gui_invalid_url_blocks_accept(qtbot):
    dialog = make(qtbot)
    dialog.ui.lineEdit_gitlabUrl.setText("gitlab.example.com")
    dialog.ok_button().click()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "http" in dialog.ui.label_error.text()


def test_gui_missing_ca_file_blocks_accept(qtbot, tmp_path):
    dialog = make(qtbot)
    dialog.ui.lineEdit_gitlabUrl.setText("https://gl")
    dialog.ui.lineEdit_caBundle.setText(str(tmp_path / "missing.pem"))
    dialog.ok_button().click()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "CA bundle" in dialog.ui.label_error.text()


def test_gui_clear_cache_after_confirmation(qtbot, tmp_path, monkeypatch):
    root = tmp_path / "cache"
    (root / "42" / "7" / "files").mkdir(parents=True)
    (root / "42" / "7" / ".complete").write_text("x")
    dialog = make(qtbot, cache_dir=str(root))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    dialog.ui.pushButton_clearCache.click()
    assert root.exists() and not dialog.cache_cleared
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    dialog.ui.pushButton_clearCache.click()
    assert not root.exists()
    assert dialog.cache_cleared
    assert ArtifactCache(root).entries() == []
