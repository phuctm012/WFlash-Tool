"""A window must never be allowed smaller than its layout needs.

Qt only enforces the layout's minimum size on a top-level widget that has *no* explicit
minimumSize. An explicit minimum below the layout's minimum (e.g. 760x600 while the
native macOS style needs 820 px of height) lets the window open too small, and the layout
then squeezes rows below their size hint (Project/Branch/Job rows were 13 px tall).
"""
import pytest
from PySide6.QtWidgets import QDialog, QMainWindow

from wflash.gui.ui_gitlab_dialog import Ui_GitlabDialog
from wflash.gui.ui_main_window import Ui_MainWindow
from wflash.gui.ui_preferences_dialog import Ui_PreferencesDialog

pytestmark = pytest.mark.gui


@pytest.mark.parametrize(
    "base, ui_class",
    [(QDialog, Ui_GitlabDialog), (QDialog, Ui_PreferencesDialog), (QMainWindow, Ui_MainWindow)],
    ids=["gitlab_dialog", "preferences_dialog", "main_window"],
)
def test_gui_window_minimum_covers_its_layout(qtbot, base, ui_class):
    window = base()
    ui_class().setupUi(window)
    qtbot.addWidget(window)
    window.show()
    needed = window.layout().minimumSize()
    assert window.minimumSize().height() >= needed.height()
    assert window.minimumSize().width() >= needed.width()
    assert window.height() >= needed.height()
