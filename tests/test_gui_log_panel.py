import logging
import threading
import zipfile

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from tests.gui_stubs import TOKEN, HostWindow
from wflash.core.logging_setup import clear_secrets, register_secret
from wflash.gui.log_panel import LogPanelMixin

pytestmark = pytest.mark.gui


class LogHost(LogPanelMixin, HostWindow):
    def __init__(self, tmp):
        super().__init__(tmp)
        self.flashing = False
        self._init_log_panel()

    def flash_active(self):
        return self.flashing


@pytest.fixture
def host(qtbot, tmp_path):
    window = LogHost(tmp_path)
    qtbot.addWidget(window)
    yield window, logging.getLogger("wflash.test_gui_panel")
    clear_secrets()


def test_gui_info_filter_hides_debug_until_changed(host, qtbot):
    w, log = host
    log.debug("dbg-line")
    log.info("info-line")
    qtbot.waitUntil(lambda: "info-line" in w.log_visible_text(), timeout=1000)
    assert "dbg-line" not in w.log_visible_text()
    w.ui.comboBox_logLevel.setCurrentIndex(w.ui.comboBox_logLevel.findText("DEBUG"))
    assert "dbg-line" in w.log_visible_text()
    w.ui.comboBox_logLevel.setCurrentIndex(w.ui.comboBox_logLevel.findText("ERROR"))
    assert w.log_visible_text() == ""


def test_gui_error_keeps_traceback_and_flags_status_bar(host, qtbot):
    w, log = host
    try:
        raise ValueError("broken value")
    except ValueError:
        log.exception("operation failed")
    qtbot.waitUntil(lambda: "operation failed" in w.log_visible_text(), timeout=1000)
    assert "ValueError: broken value" in w.log_visible_text()
    assert "Error" in w.statusBar().currentMessage()


def test_gui_secret_redacted_in_panel(host, qtbot):
    w, log = host
    register_secret(TOKEN)
    log.info("token %s and header PRIVATE-TOKEN: %s", TOKEN, TOKEN)
    qtbot.waitUntil(lambda: "token ***" in w.log_visible_text(), timeout=1000)
    assert TOKEN not in w.log_visible_text()


def test_gui_copy_and_clear(host, qtbot):
    w, log = host
    log.info("copy me")
    qtbot.waitUntil(lambda: "copy me" in w.log_visible_text(), timeout=1000)
    qtbot.mouseClick(w.ui.pushButton_copyLog, Qt.MouseButton.LeftButton)
    assert "copy me" in QGuiApplication.clipboard().text()
    qtbot.mouseClick(w.ui.pushButton_clearLog, Qt.MouseButton.LeftButton)
    assert w.log_visible_text() == ""
    w.ui.comboBox_logLevel.setCurrentIndex(0)
    assert w.log_visible_text() == ""  # cleared records do not come back on refilter


def test_gui_thread_log_record_from_worker_thread_reaches_panel(host, qtbot):
    w, log = host
    thread = threading.Thread(target=log.info, args=("from-thread",))
    thread.start()
    thread.join()
    qtbot.waitUntil(lambda: "from-thread" in w.log_visible_text(), timeout=1000)


def test_gui_export_bundle_and_refused_during_flash(host, tmp_path, qtbot):
    w, log = host
    w.ctx.add_error(RuntimeError(f"failed with {TOKEN}"))
    bundle = w.export_bundle(tmp_path / "out")
    with zipfile.ZipFile(bundle) as zf:
        errors = zf.read("errors.txt").decode()
    assert "failed with ***" in errors and TOKEN not in errors
    w.flashing = True
    with pytest.raises(RuntimeError, match="while a flash is running"):
        w.export_bundle(tmp_path / "out2")


def test_gui_close_detaches_handler(qtbot, tmp_path):
    w = LogHost(tmp_path)
    qtbot.addWidget(w)
    assert w.log_handler in logging.getLogger("wflash").handlers
    w.close()
    assert w.log_handler not in logging.getLogger("wflash").handlers
