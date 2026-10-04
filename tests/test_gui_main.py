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
