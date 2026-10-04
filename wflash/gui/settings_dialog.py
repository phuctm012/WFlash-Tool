"""Settings dialog (layout in settings_dialog.ui): GitLab URL/token, CA bundle, cache, profiles, verbose."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFileDialog, QMessageBox, QWidget

from wflash.core.artifact_cache import ArtifactCache
from wflash.core.errors import ArtifactError
from wflash.core.logging_setup import get_logger
from wflash.core.settings import AppSettings, bundled_profiles_dir, default_cache_dir
from wflash.gui.ui_settings_dialog import Ui_SettingsDialog

log = get_logger("ui.settings")


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, token: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ui = Ui_SettingsDialog()
        self.ui.setupUi(self)
        self._settings = settings
        self.cache_cleared = False

        self.ui.lineEdit_gitlabUrl.setText(settings.gitlab_url)
        self.ui.lineEdit_token.setText(token)
        self.ui.lineEdit_caBundle.setText(settings.ca_bundle)
        self.ui.lineEdit_cacheDir.setText(settings.cache_dir)
        # Placeholders show the platform defaults, which only exist at runtime.
        self.ui.lineEdit_cacheDir.setPlaceholderText(str(default_cache_dir()))
        self.ui.spinBox_maxCachedJobs.setValue(settings.max_cached_jobs)
        self.ui.lineEdit_profilesDir.setText(settings.profiles_dir)
        self.ui.lineEdit_profilesDir.setPlaceholderText(str(bundled_profiles_dir()))
        self.ui.checkBox_verbose.setChecked(settings.verbose)

        self.ui.buttonBox_settings.accepted.connect(self._on_accept)
        self.ui.buttonBox_settings.rejected.connect(self.reject)
        self.ui.pushButton_browseCaBundle.clicked.connect(self._browse_ca_bundle)
        self.ui.pushButton_browseCacheDir.clicked.connect(self._browse_cache_dir)
        self.ui.pushButton_browseProfilesDir.clicked.connect(self._browse_profiles_dir)
        self.ui.pushButton_clearCache.clicked.connect(self._clear_cache)

    def ok_button(self):
        return self.ui.buttonBox_settings.button(QDialogButtonBox.StandardButton.Ok)

    def _browse_ca_bundle(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CA bundle", self.ui.lineEdit_caBundle.text(), "Certificates (*.pem *.crt *.cer);;All files (*)"
        )
        if path:
            self.ui.lineEdit_caBundle.setText(path)

    def _browse_cache_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select cache folder", self.ui.lineEdit_cacheDir.text())
        if path:
            self.ui.lineEdit_cacheDir.setText(path)

    def _browse_profiles_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select profiles folder", self.ui.lineEdit_profilesDir.text())
        if path:
            self.ui.lineEdit_profilesDir.setText(path)

    def _cache_root(self) -> Path:
        text = self.ui.lineEdit_cacheDir.text().strip()
        return Path(text) if text else default_cache_dir()

    def _clear_cache(self) -> None:
        root = self._cache_root()
        answer = QMessageBox.question(self, "Clear cache", f"Delete every cached artifact in\n{root}?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            ArtifactCache(root).clear()
        except ArtifactError as exc:
            self.ui.label_error.setText(f"{exc}\n{exc.hint}")
            log.error("Cannot clear the artifact cache %s: %s", root, exc)
            return
        self.cache_cleared = True
        self.ui.label_error.setText("")
        log.info("Artifact cache cleared: %s", root)

    def _on_accept(self) -> None:
        url = self.ui.lineEdit_gitlabUrl.text().strip()
        if url and not url.startswith(("http://", "https://")):
            self.ui.label_error.setText("GitLab URL must start with http:// or https://")
            return
        ca = self.ui.lineEdit_caBundle.text().strip()
        if ca and not Path(ca).is_file():
            self.ui.label_error.setText(f"CA bundle file not found: {ca}")
            return
        self.ui.label_error.clear()
        self.accept()

    def result_settings(self) -> AppSettings:
        return replace(
            self._settings,
            gitlab_url=self.ui.lineEdit_gitlabUrl.text().strip().rstrip("/"),
            ca_bundle=self.ui.lineEdit_caBundle.text().strip(),
            cache_dir=self.ui.lineEdit_cacheDir.text().strip(),
            max_cached_jobs=self.ui.spinBox_maxCachedJobs.value(),
            profiles_dir=self.ui.lineEdit_profilesDir.text().strip(),
            verbose=self.ui.checkBox_verbose.isChecked(),
        )

    def result_token(self) -> str:
        return self.ui.lineEdit_token.text().strip()
