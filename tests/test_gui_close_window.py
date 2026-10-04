"""closeEvent while work is running: bounded, no deadlock, rollback finished before close returns."""
import logging
import threading
import time
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMessageBox

from tests.gui_stubs import (
    GITLAB_URL,
    OLD_APP,
    OLD_CM7_0,
    SOURCE,
    FakeGitLabSession,
    SessionClientFactory,
    make_artifact_tree,
    patch_keyring,
    write_profiles,
)
from wflash.core.errors import WinIDEAError
from wflash.core.fake_adapter import FakeWinIDEAAdapter
from wflash.core.flash_workflow import Step
from wflash.core.settings import AppSettings
from wflash.gui import main_window as main_window_module
from wflash.gui.main_window import MainWindow

pytestmark = pytest.mark.gui

THREADING_WARNINGS = ("QThread: Destroyed", "Signal source has been deleted", "QObject::", "Cannot queue")


@pytest.fixture
def make(qtbot, tmp_path, monkeypatch):
    shown, questions = [], []
    monkeypatch.setattr(QMessageBox, "critical", lambda parent, title, text: shown.append((title, text)))

    def question(parent, title, text, *args):
        questions.append(text)
        return env.answer

    monkeypatch.setattr(QMessageBox, "question", question)
    patch_keyring(monkeypatch)
    env = SimpleNamespace(shown=shown, questions=questions, answer=QMessageBox.StandardButton.Yes)

    def factory(adapter, session=None):
        profiles = write_profiles(tmp_path / "profiles")
        window = MainWindow(
            AppSettings(gitlab_url=GITLAB_URL, profiles_dir=str(profiles), cache_dir=str(tmp_path / "cache")),
            adapter,
            client_factory=SessionClientFactory(session or FakeGitLabSession()),
            settings_path=tmp_path / "settings.json",
        )
        qtbot.addWidget(window)
        qtbot.waitUntil(lambda: window.ui.comboBox_instance.count() == 1, timeout=3000)
        window.on_firmware_ready(make_artifact_tree(tmp_path / "art"), SOURCE)
        env.window = window
        return window

    env.factory = factory
    return env


def no_threading_warnings(qtlog):
    return [r.message for r in qtlog.records if any(p in r.message for p in THREADING_WARNINGS)] == []


def test_gui_thread_close_during_flash_cancels_and_rolls_back_before_returning(make, qtbot, qtlog):
    adapter = FakeWinIDEAAdapter(download_seconds=10)
    w = make.factory(adapter)
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DOWNLOAD.value, timeout=3000)
    t0 = time.monotonic()
    w.close()
    elapsed = time.monotonic() - t0
    assert elapsed < 3.0, f"close took {elapsed:.1f}s (deadlock?)"
    assert make.questions and "flash is in progress" in make.questions[0]
    assert w._closing
    # Rollback ran to completion before close() returned.
    assert adapter.programs["App"] == OLD_APP and adapter.applications["CM7_0"] == OLD_CM7_0
    assert adapter.connected_to is None
    assert w._workers.running_keys() == []
    assert make.shown == []  # no dialogs from completion slots while closing
    assert w.log_handler not in logging.getLogger("wflash").handlers
    assert no_threading_warnings(qtlog)


def test_gui_thread_close_declined_keeps_flashing(make, qtbot):
    adapter = FakeWinIDEAAdapter(download_seconds=0.5)
    w = make.factory(adapter)
    make.answer = QMessageBox.StandardButton.No
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DOWNLOAD.value, timeout=3000)
    w.close()
    assert not w._closing and w.flash_active()
    qtbot.waitUntil(lambda: w.current_step() == Step.DONE.value, timeout=5000)
    assert adapter.programs["App"] != OLD_APP
    make.answer = QMessageBox.StandardButton.Yes


def test_gui_thread_close_during_gitlab_fetch_before_any_flash(make, qtbot, qtlog):
    session = FakeGitLabSession(delay_s=0.5)
    w = make.factory(FakeWinIDEAAdapter(), session)
    w.clear_mapping()
    w.open_gitlab_dialog()
    dialog = w._gitlab_dialog
    dialog.load_refs()
    assert w.gitlab_busy() and not w.flash_active()
    t0 = time.monotonic()
    w.close()
    assert time.monotonic() - t0 < 3.0
    assert make.questions == []  # nothing to confirm without a flash
    assert w._workers.running_keys() == []
    assert dialog.ui.comboBox_ref.count() == 0  # the late refs result was settled, not shown
    assert not dialog.isVisible()
    assert make.shown == []
    assert no_threading_warnings(qtlog)


def test_gui_thread_close_during_dialog_download_loads_nothing(make, qtbot, qtlog):
    session = FakeGitLabSession(chunk_delay_s=0.02)
    w = make.factory(FakeWinIDEAAdapter(), session)
    w.clear_mapping()
    w.open_gitlab_dialog()
    dialog = w._gitlab_dialog
    dialog.ui.comboBox_ref.setEditText("main")
    dialog.download_selected()
    qtbot.waitUntil(lambda: dialog.ui.progressBar_download.value() > 0, timeout=3000)
    t0 = time.monotonic()
    w.close()
    assert time.monotonic() - t0 < 3.0
    assert w._workers.running_keys() == []
    assert w.mapping_rows() == []
    assert not dialog.isVisible()
    assert make.shown == []
    assert no_threading_warnings(qtlog)


def test_gui_thread_close_reports_rollback_failure_after_the_wait(make, qtbot):
    class RestoreFails(FakeWinIDEAAdapter):
        def set_program_path(self, name, path):
            if path == OLD_APP:
                raise WinIDEAError("restore App failed")
            super().set_program_path(name, path)

    w = make.factory(RestoreFails(download_seconds=10))
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DOWNLOAD.value, timeout=3000)
    w.close()
    assert len(make.shown) == 1
    assert make.shown[0][0] == "WFlash — rollback failed"


def test_gui_thread_close_wait_is_bounded_when_a_worker_ignores_cancel(make, qtbot, monkeypatch, caplog):
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: warnings.append((title, text)))
    release = threading.Event()

    class Stuck(FakeWinIDEAAdapter):
        def download(self, progress, cancel, timeout_s):
            release.wait(5)  # ignores the cancel token on purpose

    monkeypatch.setattr(main_window_module, "CLOSE_TIMEOUT_S", 0.5)
    w = make.factory(Stuck())
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DOWNLOAD.value, timeout=3000)
    worker = w._workers.worker(w._flash_key)
    w._flash_key_for_test = w._flash_key
    t0 = time.monotonic()
    with caplog.at_level(logging.CRITICAL, logger="wflash"):
        w.close()
    assert time.monotonic() - t0 < 2.0
    assert w._workers.running_keys() == []  # parked in workers._ABANDONED, not dropped
    assert any(r.levelno == logging.CRITICAL and w._flash_key_for_test in r.message for r in caplog.records)
    assert len(warnings) == 1 and warnings[0][0] == "WFlash — flash still running"
    assert "winIDEA" in warnings[0][1]
    release.set()
    assert worker.done.wait(5)


def test_gui_thread_close_logs_rollback_failure_critical_and_records_it(make, qtbot, caplog):
    class RestoreFails(FakeWinIDEAAdapter):
        def set_program_path(self, name, path):
            if path == OLD_APP:
                raise WinIDEAError("restore App failed")
            super().set_program_path(name, path)

    w = make.factory(RestoreFails(download_seconds=10))
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DOWNLOAD.value, timeout=3000)
    with caplog.at_level(logging.CRITICAL, logger="wflash"):
        w.close()
    assert any(r.levelno == logging.CRITICAL and "Rollback failed" in r.message for r in caplog.records)
    assert any("restore App failed" in e for e in w.ctx.errors)


def test_gui_thread_close_records_non_rollback_error_without_dialog(make, qtbot):
    w = make.factory(FakeWinIDEAAdapter())
    w._closing = True
    w._flash_error_during_close = WinIDEAError("boom")
    w.close()
    assert make.shown == []
    assert w._flash_error_during_close is None
    assert any("boom" in e for e in w.ctx.errors)


def test_gui_thread_close_disables_ui_and_ignores_reentrant_close_during_wait(make, qtbot):
    class SlowToStop(FakeWinIDEAAdapter):
        def download(self, progress, cancel, timeout_s):
            time.sleep(0.5)  # keeps the close wait open long enough for the probe
            super().download(progress, cancel, timeout_s)

    w = make.factory(SlowToStop(download_seconds=10))
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DOWNLOAD.value, timeout=3000)
    seen = {}

    def probe():
        seen["enabled"] = w.centralWidget().isEnabled()
        seen["status"] = w.statusBar().currentMessage()
        nested = QCloseEvent()  # Qt's own close() guard hides re-entry, so call closeEvent directly
        w.closeEvent(nested)
        seen["nested_accepted"] = nested.isAccepted()

    QTimer.singleShot(50, probe)
    w.close()
    assert seen["enabled"] is False
    assert "Closing" in seen["status"]
    assert seen["nested_accepted"] is False
    assert make.questions.count(make.questions[0]) == 1  # the nested close did not ask again


def test_gui_thread_close_after_confirmed_cancel_logs_warning_not_error(make, qtbot, caplog):
    w = make.factory(FakeWinIDEAAdapter(download_seconds=10))
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DOWNLOAD.value, timeout=3000)
    with caplog.at_level(logging.INFO, logger="wflash"):
        w.close()
    assert any(r.levelno == logging.WARNING and "cancelled by closing" in r.message for r in caplog.records)
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []
    assert any("Cancelled" in e for e in w.ctx.errors)
    assert make.shown == []
