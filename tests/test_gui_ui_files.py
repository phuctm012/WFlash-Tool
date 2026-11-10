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
    "gitlab_dialog.ui": "ui_gitlab_dialog.py",
    "checkout_dialog.ui": "ui_checkout_dialog.py",
}
TOP_LEVEL = {"MainWindow", "GitlabDialog", "CheckoutDialog"}
# <kind>_<what>, e.g. verticalLayout_gitlabBrowser, tableWidget_mapping.
MEANINGFUL = re.compile(r"^[a-z][A-Za-z]*_[a-z][A-Za-z0-9]*$")


def ui_names(ui_file: Path) -> list[str]:
    root = ET.parse(ui_file).getroot()
    return [el.get("name") for el in root.iter() if el.tag in ("widget", "layout", "spacer", "action")]


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


def test_gui_old_widgets_are_gone():
    names = set(ui_names(GUI / "main_window.ui"))
    gone = {
        "comboBox_ref", "listWidget_pipelines", "listWidget_jobs",
        "pushButton_downloadArtifact", "progressBar_artifact", "pushButton_settings",
        "pushButton_cancelFlash", "splitter_mainVertical", "splitter_upperHorizontal",
        # replaced by the GitLab tab and the Setting tab (2026-11-09)
        "frame_developer", "lineEdit_sourceRepo", "comboBox_build", "pushButton_loadBuild", "pushButton_preferences",
        "comboBox_logLevel",
    }
    assert names & gone == set()
    for old in ("settings_dialog.ui", "gitlab_browser.py", "preferences_dialog.ui", "source_panel.py"):
        assert not (GUI / old).exists(), old


def test_gui_every_part_widget_exists_for_app_boot_manager_and_flash_bootloader():
    # part_controller.py binds these by name with getattr, which the self.ui scan cannot see.
    names = set(ui_names(GUI / "main_window.ui"))
    for part in ("app", "bm", "fbl"):
        for pattern in ("groupBox_{}", "lineEdit_{}Project", "lineEdit_{}Repo", "pushButton_{}Browse", "label_{}Branch",
                        "pushButton_{}Checkout", "label_{}Commit", "pushButton_{}Reload", "radioButton_{}Commit",
                        "radioButton_{}Manual", "pushButton_{}ChooseJob", "label_{}Status"):
            assert pattern.format(part) in names, pattern.format(part)
    assert {"comboBox_appBuild", "label_bmBuild", "label_fblBuild"} <= names


def test_gui_generated_modules_import(qapp):
    from PySide6.QtWidgets import QDialog, QMainWindow

    from wflash.gui.ui_gitlab_dialog import Ui_GitlabDialog
    from wflash.gui.ui_main_window import Ui_MainWindow

    window = QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(window)
    assert ui.tableWidget_programFiles.columnCount() == ui.tableWidget_symbolFiles.columnCount() == 4
    assert ui.tableWidget_programFiles.horizontalHeaderItem(0).text() == "#"
    assert ui.label_flashBlocked.isHidden()
    assert ui.tabWidget_output.count() == 1 and ui.tabWidget_output.tabText(0) == "Information"
    assert [ui.tabWidget_main.tabText(i) for i in range(ui.tabWidget_main.count())] == ["Flash", "GitLab", "Setting"]
    assert ui.tabWidget_main.currentIndex() == 0
    assert [m.title() for m in (ui.menu_file, ui.menu_view, ui.menu_tools, ui.menu_help)] == ["&File", "&View", "&Tools", "&Help"]
    assert ui.action_userGuide.shortcut().toString() == "F1" and ui.action_darkMode.isCheckable()
    assert ui.label_rollbackWarning.isHidden()
    assert ui.label_step.text() == "Step: Idle"
    assert ui.pushButton_flash.minimumSize().width() == 90 and ui.pushButton_flash.maximumSize().height() == 70
    assert not ui.progressBar_flash.isTextVisible()
    assert ui.frame_flashPanel.maximumWidth() == 360
    for tab, names in (
        (ui.tab_flash, ("frame_firmwareSummary", "frame_gitlabSource", "tableWidget_programFiles", "tableWidget_symbolFiles")),
        (ui.tab_gitlab, ("groupBox_app", "checkBox_advancedDebug", "groupBox_bm", "groupBox_fbl")),
        (ui.tab_setting, ("comboBox_profile", "lineEdit_profilesDir", "lineEdit_downloadDir", "lineEdit_gitlabUrl",
                          "lineEdit_token", "comboBox_instance", "checkBox_reset", "checkBox_verifyFlash")),
    ):
        for name in names:
            assert tab.isAncestorOf(getattr(ui, name)), name
    gitlab = QDialog()
    gitlab_ui = Ui_GitlabDialog()
    gitlab_ui.setupUi(gitlab)
    assert gitlab_ui.tableWidget_jobs.columnCount() == 6
    assert gitlab_ui.tabWidget_source.count() == 1
    window.deleteLater()
    gitlab.deleteLater()


def test_every_tab_scroll_area_is_transparent_in_both_themes():
    """A scroll area left out of the stylesheet paints Qt's own grey (user report: GitLab tab)."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    names = re.findall(r'class="QScrollArea" name="(\w+)"', (root / "wflash/gui/main_window.ui").read_text())
    assert names
    for qss in ("style.qss", "style_dark.qss"):
        text = (root / "wflash/resources" / qss).read_text()
        for name in names:
            contents = name.replace("scrollArea_", "scrollAreaWidgetContents_")
            assert f"QScrollArea#{name}" in text and f"QWidget#{contents}" in text, (qss, name)
