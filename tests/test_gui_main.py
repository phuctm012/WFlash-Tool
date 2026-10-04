import logging
import sys
import threading

import pytest
from PySide6.QtWidgets import QMessageBox

from wflash.main import install_excepthooks, parse_args

pytestmark = pytest.mark.gui


def test_gui_default_adapter_depends_on_platform(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert parse_args([]).adapter == "real"
    monkeypatch.setattr(sys, "platform", "darwin")
    assert parse_args([]).adapter == "fake"


def test_gui_flags():
    args = parse_args(["--adapter", "fake", "--verbose", "--smoke"])
    assert (args.adapter, args.verbose, args.smoke) == ("fake", True, True)


def test_gui_excepthooks_log_and_show_dialog_on_gui_thread_only(qapp, monkeypatch, caplog):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: shown.append(a))
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    caplog.set_level(logging.DEBUG, logger="wflash")
    install_excepthooks()

    try:
        raise RuntimeError("kaboom")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    assert "kaboom" in caplog.text
    assert len(shown) == 1

    def crash():
        raise ZeroDivisionError("bad thread")

    thread = threading.Thread(target=crash, name="bad-thread")
    thread.start()
    thread.join()
    assert "ZeroDivisionError" in caplog.text and "bad-thread" in caplog.text
    assert len(shown) == 1  # no dialog from a non-GUI thread


def test_gui_main_log_dir_fallback_and_warning(qapp, monkeypatch, tmp_path):
    import tempfile
    from pathlib import Path

    from wflash import main as main_module

    calls = []
    fallback_file = tmp_path / "fb.log"

    def fake_setup(log_dir=None, **kw):
        calls.append(log_dir)
        if log_dir is None:
            raise OSError("read-only")
        return fallback_file

    monkeypatch.setattr(main_module, "setup_logging", fake_setup)
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    result, fallback = main_module.init_logging(verbose=False)
    assert result == fallback_file
    assert fallback == Path(tmp_path) / "WFlash" / "logs"
    assert calls == [None, fallback]


def test_gui_main_log_dir_total_failure_continues_without_file(monkeypatch):
    from wflash import main as main_module

    def always_fail(log_dir=None, **kw):
        raise OSError("nope")

    monkeypatch.setattr(main_module, "setup_logging", always_fail)
    result, fallback = main_module.init_logging(verbose=False)
    assert result is None and fallback is not None


def test_gui_excepthook_dialog_is_redacted(qapp, monkeypatch):
    token = "glpat-" + "Ab3dEf6hIj9kLm2nOp5q"
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: shown.append(a))
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    install_excepthooks()
    try:
        raise RuntimeError(f"failed with {token}")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    assert "***" in shown[0][2] and token not in shown[0][2]
