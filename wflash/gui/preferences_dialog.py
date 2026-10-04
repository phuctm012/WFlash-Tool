"""Preferences dialog (layout in preferences_dialog.ui): cache, profiles, verbose, dark mode.

GitLab URL, token and TLS options live in the Load from GitLab popup. The dialog only
edits a copy: `result_settings()` returns a new AppSettings and the main window decides
what to apply (theme, verbose logging) and saves it.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFileDialog, QMessageBox, QWidget

from wflash.core.artifact_cache import ArtifactCache
from wflash.core.errors import ArtifactError
from wflash.core.logging_setup import get_logger
from wflash.core.settings import PACKAGES_SUBDIR, AppSettings, bundled_profiles_dir, default_cache_dir
from wflash.gui.ui_preferences_dialog import Ui_PreferencesDialog

log = get_logger("ui.preferences")


class PreferencesDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ui = Ui_PreferencesDialog()
        self.ui.setupUi(self)
        self._settings = settings
        self.cache_cleared = False

        self.ui.lineEdit_cacheDir.setText(settings.cache_dir)
        # Placeholders show the platform defaults, which only exist at runtime.
        self.ui.lineEdit_cacheDir.setPlaceholderText(str(default_cache_dir()))
        self.ui.spinBox_maxCachedJobs.setValue(settings.max_cached_jobs)
        self.ui.lineEdit_profilesDir.setText(settings.profiles_dir)
        self.ui.lineEdit_profilesDir.setPlaceholderText(str(bundled_profiles_dir()))
        self.ui.checkBox_verbose.setChecked(settings.verbose)
        self.ui.checkBox_darkMode.setChecked(settings.dark_mode)

        self.ui.buttonBox_preferences.accepted.connect(self._on_accept)
        self.ui.buttonBox_preferences.rejected.connect(self.reject)
        self.ui.pushButton_browseCacheDir.clicked.connect(self._browse_cache_dir)
        self.ui.pushButton_browseProfilesDir.clicked.connect(self._browse_profiles_dir)
        self.ui.pushButton_clearCache.clicked.connect(self._clear_cache)

    def ok_button(self):
        return self.ui.buttonBox_preferences.button(QDialogButtonBox.StandardButton.Ok)

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
        answer = QMessageBox.question(
            self, "Clear cache", f"Delete every cached artifact and package in\n{root}?"
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        errors: list[ArtifactError] = []
        for cache_root in (root, root / PACKAGES_SUBDIR):
            try:
                ArtifactCache(cache_root).clear()
            except ArtifactError as exc:
                log.error("Cannot clear the cache %s: %s", cache_root, exc)
                errors.append(exc)
        # Whatever was removed is gone: the loaded firmware may point into it.
        self.cache_cleared = True
        if errors:
            self.ui.label_error.setText(f"{errors[0]}\n{errors[0].hint}")
            return
        self.ui.label_error.setText("")
        log.info("Cache cleared: %s", root)

    def _on_accept(self) -> None:
        profiles = self.ui.lineEdit_profilesDir.text().strip()
        if profiles and not Path(profiles).is_dir():
            self.ui.label_error.setText(f"Profiles folder not found: {profiles}")
            return
        self.ui.label_error.clear()
        self.accept()

    def result_settings(self) -> AppSettings:
        return replace(
            self._settings,
            cache_dir=self.ui.lineEdit_cacheDir.text().strip(),
            max_cached_jobs=self.ui.spinBox_maxCachedJobs.value(),
            profiles_dir=self.ui.lineEdit_profilesDir.text().strip(),
            verbose=self.ui.checkBox_verbose.isChecked(),
            dark_mode=self.ui.checkBox_darkMode.isChecked(),
        )
