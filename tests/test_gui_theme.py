"""Teal theme: tokens, stylesheet files, loader, and theme-driven log colours."""
import logging

import pytest
from PySide6.QtWidgets import QApplication

from tests.gui_stubs import HostWindow
from wflash.gui import style
from wflash.gui.log_panel import LogPanelMixin, level_color
from wflash.gui.style import apply_theme, load_stylesheet, stylesheet_path
from wflash.gui.theme import THEMES, current_theme, current_theme_name, set_theme_name

pytestmark = pytest.mark.gui


@pytest.fixture
def light_after(qapp):
    yield qapp
    apply_theme(qapp, False)
    qapp.setStyleSheet("")


def contrast(fg: str, bg: str) -> float:
    def luminance(color: str) -> float:
        channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    hi, lo = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_gui_both_themes_define_the_same_tokens():
    assert set(THEMES) == {"light", "dark"}
    assert set(THEMES["light"]) == set(THEMES["dark"])


@pytest.mark.parametrize("name", ["light", "dark"])
def test_gui_white_text_on_primary_and_cancel_is_readable(name):
    assert contrast("#ffffff", THEMES[name]["primary"]) >= 4.5
    assert contrast("#ffffff", THEMES[name]["cancel"]) >= 4.5


@pytest.mark.parametrize("dark, name", [(False, "light"), (True, "dark")])
def test_gui_stylesheet_files_use_their_own_tokens(dark, name):
    text = load_stylesheet(dark)
    assert text, f"{stylesheet_path(dark)} is missing or empty"
    tokens = THEMES[name]
    for token in ("ground", "surface", "primary", "cancel", "accent", "head", "soft", "banner_bg"):
        assert tokens[token] in text, f"{token} {tokens[token]} not used in {name} stylesheet"
    other = THEMES["dark" if name == "light" else "light"]
    assert other["primary"] not in text and other["ground"] not in text
    for selector in (
        "#pushButton_flash",
        '#pushButton_flash[state="flashing"]',
        "#pushButton_loadFromGitlab",
        '#progressBar_flash[state="done"]',
        "#label_rollbackWarning",
        "#frame_sourceCard",
        "#label_settingHeader",
    ):
        assert selector in text


def test_gui_missing_stylesheet_returns_empty_and_warns(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(style, "RESOURCES_DIR", tmp_path)
    with caplog.at_level(logging.WARNING, logger="wflash.ui.style"):
        assert load_stylesheet(False) == ""
    assert "default Qt style" in caplog.text


def test_gui_apply_theme_switches_tokens_and_app_stylesheet(light_after):
    app = light_after
    apply_theme(app, True)
    assert current_theme_name() == "dark"
    assert current_theme()["primary"] == THEMES["dark"]["primary"]
    assert THEMES["dark"]["primary"] in app.styleSheet()
    apply_theme(app, False)
    assert current_theme_name() == "light"
    assert THEMES["light"]["primary"] in app.styleSheet()


def test_gui_unknown_theme_name_is_refused():
    with pytest.raises(ValueError):
        set_theme_name("purple")


class LogHost(LogPanelMixin, HostWindow):
    def __init__(self, tmp):
        super().__init__(tmp)
        self._init_log_panel()

    def flash_active(self):
        return False


def first_line_color(w) -> str:
    block = w.ui.plainTextEdit_log.document().firstBlock()
    return block.begin().fragment().charFormat().foreground().color().name()


def test_gui_log_colours_follow_the_theme(qtbot, tmp_path, light_after):
    w = LogHost(tmp_path)
    qtbot.addWidget(w)
    assert level_color(logging.INFO) is None
    logging.getLogger("wflash.test_theme").warning("careful")
    qtbot.waitUntil(lambda: "careful" in w.log_visible_text(), timeout=1000)
    assert first_line_color(w) == THEMES["light"]["log_warn"]
    apply_theme(QApplication.instance(), True)
    w.refresh_log_theme()
    assert first_line_color(w) == THEMES["dark"]["log_warn"]
    assert level_color(logging.ERROR) == THEMES["dark"]["log_error"]
