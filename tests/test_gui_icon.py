"""The WFlash icon: in the package, on every window, and embedded in WFlash.exe."""
import logging
import sys
import types
from pathlib import Path

import pytest

from wflash import main as main_module
from wflash.gui import style

pytestmark = pytest.mark.gui
ROOT = Path(__file__).resolve().parents[1]


def test_gui_icon_files_are_in_the_package_resources():
    for suffix in (".svg", ".ico"):
        path = style.ICONS_DIR / f"{style.ICON_NAME}{suffix}"
        assert path.is_file() and path.stat().st_size > 0, path
    assert (style.ICONS_DIR / f"{style.ICON_NAME}.ico").read_bytes()[:4] == b"\x00\x00\x01\x00"  # ICO header


def test_gui_app_icon_is_not_null_and_has_small_and_large_sizes(qapp):
    icon = style.app_icon()
    assert not icon.isNull()
    assert not icon.pixmap(16, 16).isNull() and not icon.pixmap(256, 256).isNull()


def test_gui_missing_icon_files_only_warn(qapp, tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(style, "ICONS_DIR", tmp_path)
    with caplog.at_level(logging.WARNING, logger="wflash.ui.style"):
        icon = style.app_icon()
    assert icon.isNull() and "Icon file missing" in caplog.text


def test_gui_exe_and_package_carry_the_icon():
    spec = (ROOT / "wflash.spec").read_text(encoding="utf-8")
    assert 'icon="wflash/resources/icons/wflash_chip_teal.ico"' in spec
    assert '("wflash/resources", "wflash/resources")' in spec  # the icons ride along with the stylesheets
    assert '"resources/icons/*"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_gui_windows_app_id_is_set_only_on_windows(monkeypatch):
    calls = []
    shell32 = types.SimpleNamespace(SetCurrentProcessExplicitAppUserModelID=calls.append)
    fake_ctypes = types.SimpleNamespace(windll=types.SimpleNamespace(shell32=shell32))
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)
    monkeypatch.setattr(sys, "platform", "darwin")
    main_module.set_windows_app_id()
    assert calls == []
    monkeypatch.setattr(sys, "platform", "win32")
    main_module.set_windows_app_id()
    assert calls == [main_module.APP_USER_MODEL_ID]


def test_gui_windows_app_id_failure_only_warns(monkeypatch, caplog):
    def refuse(_id):
        raise OSError("no shell32")

    shell32 = types.SimpleNamespace(SetCurrentProcessExplicitAppUserModelID=refuse)
    monkeypatch.setitem(sys.modules, "ctypes", types.SimpleNamespace(windll=types.SimpleNamespace(shell32=shell32)))
    monkeypatch.setattr(sys, "platform", "win32")
    with caplog.at_level(logging.WARNING, logger="wflash.main"):
        main_module.set_windows_app_id()
    assert "taskbar identity" in caplog.text
