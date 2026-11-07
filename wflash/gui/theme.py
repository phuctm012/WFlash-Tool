"""Teal theme tokens shared by the stylesheets and by code that colours dynamic content.

The .qss files (wflash/resources) style every static widget by objectName and dynamic
property. Colours that code applies at runtime — log lines, red mapping rows, the "#"
column — come from `current_theme()`, so both use the same values. `style.apply_theme()`
switches the current theme together with the application stylesheet.
"""
from __future__ import annotations

THEMES: dict[str, dict[str, str]] = {
    "light": {
        "ground": "#f2f6f6",
        "surface": "#ffffff",
        "panel": "#e3eceb",
        "border": "#d7dde5",
        "line": "#e9edf2",
        "text": "#1a1a1a",
        "muted": "#5a6472",
        "disabled": "#9aa4b2",
        "primary": "#0f6b63",
        "primary_hover": "#1f9488",
        "accent": "#1f9488",
        "head": "#0f6b63",
        "soft": "#e7f3f1",
        "cancel": "#b23b3b",
        "cancel_hover": "#d1574f",
        "done": "#3f8f5f",
        "log_debug": "#8a8a8a",
        "log_warn": "#c77700",
        "log_error": "#d32f2f",
        "missing_bg": "#ffcdd2",
        "missing_border": "#d1574f",
        "banner_bg": "#fdecea",
        "banner_border": "#e6a5a0",
        "banner_text": "#8f1d17",
    },
    "dark": {
        "ground": "#1b2023",
        "surface": "#232a2d",
        "panel": "#262e31",
        "border": "#3a464a",
        "line": "#2e383b",
        "text": "#e4eceb",
        "muted": "#9aaaa8",
        "disabled": "#6b7a7c",
        "primary": "#138277",
        "primary_hover": "#1a988b",
        "accent": "#2bb3a3",
        "head": "#6fd3c6",
        "soft": "#22383a",
        "cancel": "#c24b45",
        "cancel_hover": "#d65c55",
        "done": "#3a8a5c",
        "log_debug": "#7d8b8a",
        "log_warn": "#e0a03b",
        "log_error": "#ef7b74",
        "missing_bg": "#4a2a2c",
        "missing_border": "#c96058",
        "banner_bg": "#3a2324",
        "banner_border": "#7a3a37",
        "banner_text": "#f3b1ac",
    },
}

_current = "light"


def current_theme_name() -> str:
    return _current


def current_theme() -> dict[str, str]:
    return THEMES[_current]


def set_theme_name(name: str) -> None:
    global _current
    if name not in THEMES:
        raise ValueError(f"Unknown theme {name!r}")
    _current = name
