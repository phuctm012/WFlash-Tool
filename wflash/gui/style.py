"""Load and apply the Teal stylesheets (wflash/resources/style.qss, style_dark.qss).

`load_stylesheet()` never raises: a missing or unreadable file logs a WARNING and returns
"", so the app runs with Qt's default look instead of crashing (spec §8). The resources
folder sits inside the package, so the same path works from source and from the
PyInstaller build (wflash.spec copies wflash/resources to the same relative place).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget

from wflash.core.logging_setup import get_logger
from wflash.gui.theme import set_theme_name

log = get_logger("ui.style")

RESOURCES_DIR = Path(__file__).resolve().parents[1] / "resources"


def stylesheet_path(dark: bool) -> Path:
    return RESOURCES_DIR / ("style_dark.qss" if dark else "style.qss")


def load_stylesheet(dark: bool) -> str:
    path = stylesheet_path(dark)
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        log.warning("Theme file %s cannot be read (%s); using the default Qt style", path, exc)
        return ""


def apply_theme(app: QApplication, dark: bool) -> None:
    """Switch the token table and the application stylesheet together."""
    set_theme_name("dark" if dark else "light")
    app.setStyleSheet(load_stylesheet(dark))


def repolish(widget: QWidget) -> None:
    """Re-evaluate the stylesheet after a dynamic property changed (e.g. state="flashing")."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
