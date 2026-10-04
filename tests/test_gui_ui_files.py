"""Designer files: meaningful names, generated modules in sync, every self.ui.<name> exists."""
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

pytestmark = pytest.mark.gui

GUI = Path(__file__).resolve().parents[1] / "wflash" / "gui"
UI_FILES = {
    "main_window.ui": "ui_main_window.py",
    "settings_dialog.ui": "ui_settings_dialog.py",
    "preferences_dialog.ui": "ui_preferences_dialog.py",
    "gitlab_dialog.ui": "ui_gitlab_dialog.py",
}
TOP_LEVEL = {"MainWindow", "SettingsDialog", "PreferencesDialog", "GitlabDialog"}
# <kind>_<what>, e.g. verticalLayout_gitlabBrowser, tableWidget_mapping.
MEANINGFUL = re.compile(r"^[a-z][A-Za-z]*_[a-z][A-Za-z0-9]*$")


def ui_names(ui_file: Path) -> list[str]:
    root = ET.parse(ui_file).getroot()
    return [el.get("name") for el in root.iter() if el.tag in ("widget", "layout", "spacer")]


def without_uic_version(text: str) -> str:
    # The header names the uic version; a PySide6 upgrade alone must not fail the build.
    return "\n".join(line for line in text.splitlines() if "User Interface Compiler version" not in line)


def uic_executable() -> str | None:
    folder = Path(sys.executable).parent
    for candidate in (folder / "pyside6-uic", folder / "pyside6-uic.exe"):
        if candidate.is_file():
            return str(candidate)
    return shutil.which("pyside6-uic")


@pytest.mark.parametrize("ui_name", sorted(UI_FILES))
def test_gui_every_widget_and_layout_has_a_meaningful_name(ui_name):
    names = ui_names(GUI / ui_name)
    assert names, f"no widgets parsed from {ui_name}"
    bad = [n for n in names if n not in TOP_LEVEL and not (n and MEANINGFUL.match(n))]
    assert bad == [], f"Designer default or unclear names in {ui_name}: {bad}"
    assert len(names) == len(set(names)), "duplicate object names"


@pytest.mark.parametrize("ui_name", sorted(UI_FILES))
def test_gui_generated_module_matches_ui_file(ui_name, tmp_path):
    uic = uic_executable()
    if uic is None:
        pytest.skip("pyside6-uic not found next to the interpreter")
    out = tmp_path / UI_FILES[ui_name]
    subprocess.run([uic, str(GUI / ui_name), "-o", str(out)], check=True)
    committed = (GUI / UI_FILES[ui_name]).read_text(encoding="utf-8")
    assert without_uic_version(committed) == without_uic_version(out.read_text(encoding="utf-8")), (
        f"{UI_FILES[ui_name]} is out of date or hand-edited; run "
        f"pyside6-uic wflash/gui/{ui_name} -o wflash/gui/{UI_FILES[ui_name]}"
    )


def test_gui_every_self_ui_reference_exists_in_a_ui_file():
    known = set()
    for ui_name in UI_FILES:
        known.update(ui_names(GUI / ui_name))
    referenced = set()
    for py in GUI.glob("*.py"):
        if py.name.startswith("ui_"):
            continue
        referenced.update(re.findall(r"self\.ui\.([A-Za-z_][A-Za-z0-9_]*)", py.read_text(encoding="utf-8")))
    referenced -= {"setupUi", "retranslateUi"}  # methods of the generated Ui_ class
    assert sorted(referenced - known) == []


def test_gui_generated_modules_import(qapp):
    from PySide6.QtWidgets import QDialog, QMainWindow

    from wflash.gui.ui_gitlab_dialog import Ui_GitlabDialog
    from wflash.gui.ui_main_window import Ui_MainWindow
    from wflash.gui.ui_preferences_dialog import Ui_PreferencesDialog
    from wflash.gui.ui_settings_dialog import Ui_SettingsDialog

    window = QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(window)
    assert ui.tableWidget_mapping.columnCount() == 4
    assert ui.comboBox_logLevel.currentText() == "INFO"
    assert ui.label_rollbackWarning.isHidden()
    dialog = QDialog()
    Ui_SettingsDialog().setupUi(dialog)
    preferences = QDialog()
    Ui_PreferencesDialog().setupUi(preferences)
    gitlab = QDialog()
    gitlab_ui = Ui_GitlabDialog()
    gitlab_ui.setupUi(gitlab)
    assert gitlab_ui.tableWidget_jobs.columnCount() == 6
    assert gitlab_ui.tableWidget_versions.columnCount() == 3
    assert gitlab_ui.tabWidget_source.count() == 2
    assert gitlab_ui.checkBox_verifyTls.isChecked()
    window.deleteLater()
    dialog.deleteLater()
    preferences.deleteLater()
    gitlab.deleteLater()
