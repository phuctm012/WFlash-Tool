"""closeEvent while work is running: bounded, no deadlock, rollback finished before close returns."""
import logging
import threading
import time
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QMessageBox

from tests.gui_stubs import OLD_APP, OLD_CM7_0, FakeGitLabSession, SessionClientFactory, make_artifact_tree, write_profiles
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
    monkeypatch.setattr(main_window_module, "get_token", lambda url: None)
    env = SimpleNamespace(shown=shown, questions=questions, answer=QMessageBox.StandardButton.Yes)

    def factory(adapter, session=None):
        profiles = write_profiles(tmp_path / "profiles")
        window = MainWindow(
            AppSettings(profiles_dir=str(profiles), cache_dir=str(tmp_path / "cache")),
            adapter,
            client_factory=SessionClientFactory(session or FakeGitLabSession()),
            settings_path=tmp_path / "settings.json",
        )
        qtbot.addWidget(window)
        qtbot.waitUntil(lambda: window.ui.comboBox_instance.count() == 1, timeout=3000)
        window.on_artifact_ready(make_artifact_tree(tmp_path / "art"), "job #7")
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
    qtbot.waitUntil(lambda: w.ui.label_step.text() == Step.DOWNLOAD.value, timeout=3000)
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
    qtbot.waitUntil(lambda: w.ui.label_step.text() == Step.DOWNLOAD.value, timeout=3000)
    w.close()
    assert not w._closing and w.flash_active()
    qtbot.waitUntil(lambda: w.ui.label_step.text() == Step.DONE.value, timeout=5000)
    assert adapter.programs["App"] != OLD_APP
    make.answer = QMessageBox.StandardButton.Yes


def test_gui_thread_close_during_gitlab_fetch_before_any_flash(make, qtbot, qtlog):
    session = FakeGitLabSession(delay_s=0.5)
    w = make.factory(FakeWinIDEAAdapter(), session)
    w.clear_mapping()
    w.refresh_gitlab()
    assert w.gitlab_busy() and not w.flash_active()
    t0 = time.monotonic()
    w.close()
    assert time.monotonic() - t0 < 3.0
    assert make.questions == []  # nothing to confirm without a flash
    assert w._workers.running_keys() == []
    assert w.ui.comboBox_ref.count() == 0  # the late refs result was settled, not shown
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
    qtbot.waitUntil(lambda: w.ui.label_step.text() == Step.DOWNLOAD.value, timeout=3000)
    w.close()
    assert len(make.shown) == 1
    assert make.shown[0][0] == "WFlash — rollback failed"


def test_gui_thread_close_wait_is_bounded_when_a_worker_ignores_cancel(make, qtbot, monkeypatch):
    release = threading.Event()

    class Stuck(FakeWinIDEAAdapter):
        def download(self, progress, cancel, timeout_s):
            release.wait(5)  # ignores the cancel token on purpose

    monkeypatch.setattr(main_window_module, "CLOSE_TIMEOUT_S", 0.5)
    w = make.factory(Stuck())
    w.start_flash()
    qtbot.waitUntil(lambda: w.ui.label_step.text() == Step.DOWNLOAD.value, timeout=3000)
    worker = w._workers.worker(w._flash_key)
    t0 = time.monotonic()
    w.close()
    assert time.monotonic() - t0 < 2.0
    assert w._workers.running_keys() == []  # parked in workers._ABANDONED, not dropped
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
    qtbot.waitUntil(lambda: w.ui.label_step.text() == Step.DOWNLOAD.value, timeout=3000)
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
