#!/usr/bin/env python3
"""Headless end-to-end stress test for WFlash (see .claude/skills/stress-test/SKILL.md).

Drives the real MainWindow against FakeWinIDEAAdapter and a fake GitLab network
(tests/gui_stubs.py), chaining many actions in one process. Fails on its own checkpoints
AND on Qt threading warnings / uncaught exceptions, which raise no Python exception in
the code under test and would otherwise scroll past in stderr.

    ~/.venvs/wflash/bin/python tools/stress_test.py
    ~/.venvs/wflash/bin/python tools/stress_test.py --list
    ~/.venvs/wflash/bin/python tools/stress_test.py --section flash --section races

Prints `STRESS_RESULT=PASS` or `STRESS_RESULT=FAIL` and the checkpoint count; exit code 0/1.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import argparse  # noqa: E402
import faulthandler  # noqa: E402
import logging  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
import zipfile  # noqa: E402
from pathlib import Path  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

faulthandler.enable()  # a hard crash still prints every thread's Python stack

from PySide6.QtCore import QtMsgType, qInstallMessageHandler  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from tests.gui_stubs import (  # noqa: E402
    JOB_ID,
    OLD_APP,
    OLD_CM7_0,
    OLD_CM7_1,
    TOKEN,
    FakeGitLabSession,
    SessionClientFactory,
    make_artifact_tree,
    write_profiles,
)
from wflash.core.errors import WinIDEAError  # noqa: E402
from wflash.core.fake_adapter import FakeWinIDEAAdapter  # noqa: E402
from wflash.core.flash_workflow import Step  # noqa: E402
from wflash.core.logging_setup import close_file_handler, get_logger, setup_logging  # noqa: E402
from wflash.core.settings import AppSettings  # noqa: E402
from wflash.gui import workers  # noqa: E402
from wflash.gui.main_window import MainWindow  # noqa: E402

log = get_logger("stress")

# Qt messages that mean a threading bug. Any of them fails the run.
THREADING_PATTERNS = (
    "QThread: Destroyed while thread",
    "Signal source has been deleted",
    "QObject: Cannot create children for a parent that is in a different thread",
    "QObject::killTimer",
    "QObject::startTimer",
    "Timers cannot be",
    "QBasicTimer",
    "Cannot queue arguments",
    "QSocketNotifier: Socket notifiers cannot be enabled or disabled from another thread",
    "QObject::setParent: Cannot set parent",
    "moveToThread",
)
CANCEL_DELAYS_S = (0.0, 0.005, 0.02, 0.06, 0.15, 0.4)
NEW_APP_SUFFIX = "App.s3"


class DropsMidTransfer(FakeWinIDEAAdapter):
    """Connection drops at 30 % of the download; winIDEA is back for the rollback."""

    def download(self, progress, cancel, timeout_s):
        progress(30, "Programming external flash (fake)")
        raise WinIDEAError("Connection to winIDEA lost during download")


class DropsAndStaysDown(DropsMidTransfer):
    """Connection drops mid-transfer and never comes back: the rollback must fail visibly."""

    lost = False

    def download(self, progress, cancel, timeout_s):
        self.lost = True
        super().download(progress, cancel, timeout_s)

    def set_program_path(self, name, path):
        if self.lost:
            raise WinIDEAError("Connection to winIDEA lost")
        super().set_program_path(name, path)

    def set_symbol_path(self, name, path):
        if self.lost:
            raise WinIDEAError("Connection to winIDEA lost")
        super().set_symbol_path(name, path)


class Stress:
    def __init__(self, workdir: Path, log_file: Path, iterations: int) -> None:
        self.workdir = workdir
        self.log_file = log_file
        self.iterations = iterations
        self.checkpoints = 0
        self.failures: list[str] = []
        self.qt_problems: list[str] = []
        self.qt_other: list[str] = []
        self.dialogs: list[tuple[str, str]] = []
        self.questions: list[str] = []
        self.answer = QMessageBox.StandardButton.Yes
        self._window_count = 0

    # -- infrastructure ---------------------------------------------------------------
    def check(self, condition: bool, label: str) -> bool:
        self.checkpoints += 1
        if not condition:
            self.failures.append(label)
            print(f"  FAIL: {label}", flush=True)
        return condition

    def pump(self, seconds: float) -> None:
        # Never app.quit() to end a wait (stress-test trap 1): just process events.
        deadline = time.monotonic() + seconds
        while True:
            QApplication.processEvents()
            if time.monotonic() >= deadline:
                return
            time.sleep(0.002)

    def pump_until(self, predicate, timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        while not predicate():
            if time.monotonic() >= deadline:
                return False
            QApplication.processEvents()
            time.sleep(0.002)
        return True

    def new_window(self, adapter, session: FakeGitLabSession | None = None, download_s: int | None = None):
        self._window_count += 1
        folder = self.workdir / f"window{self._window_count}"
        profiles = write_profiles(folder / "profiles", download_s)
        settings = AppSettings(profiles_dir=str(profiles), cache_dir=str(folder / "cache"))
        window = MainWindow(
            settings,
            adapter,
            client_factory=SessionClientFactory(session or FakeGitLabSession()),
            log_file=self.log_file,
            settings_path=folder / "settings.json",
        )
        window.resize(1280, 820)
        window.show()
        self.check(
            self.pump_until(lambda: window.ui.comboBox_instance.count() == 1, 5.0),
            f"window{self._window_count}: fake winIDEA instance listed",
        )
        return window

    def artifact(self, name: str) -> Path:
        return make_artifact_tree(self.workdir / f"artifact_{name}")

    def close_window(self, window, label: str, max_s: float = 5.0) -> None:
        t0 = time.monotonic()
        window.close()
        elapsed = time.monotonic() - t0
        self.check(elapsed < max_s, f"{label}: close() took {elapsed:.2f}s (deadlock?)")
        self.check(window._workers.running_keys() == [], f"{label}: no worker left running after close")
        self.check(window.log_handler not in logging.getLogger("wflash").handlers, f"{label}: log handler detached")
        window.deleteLater()
        self.pump(0.05)

    def wait_step(self, window, text: str, timeout_s: float) -> bool:
        return self.pump_until(lambda: window.ui.label_step.text() == text, timeout_s)

    def wait_flash_idle(self, window, timeout_s: float = 10.0) -> bool:
        return self.pump_until(lambda: not window.flash_active(), timeout_s)

    def load_artifact_via_gitlab(self, window, label: str) -> bool:
        window.refresh_gitlab()
        # The refs -> pipelines chain keeps gitlab_busy() true until the list is final.
        ok = self.pump_until(
            lambda: not window.gitlab_busy() and window.ui.listWidget_pipelines.count() == 1, 5.0
        )
        if ok:
            window.ui.listWidget_pipelines.setCurrentRow(0)
            ok = self.pump_until(lambda: window.ui.listWidget_jobs.count() == 1, 5.0)
        if ok:
            window.ui.listWidget_jobs.setCurrentRow(0)
            window.download_selected_artifact()
            ok = self.pump_until(window.mapping_complete, 10.0)
        if ok:
            ok = self.pump_until(lambda: not window.gitlab_busy(), 5.0)
        return self.check(ok, f"{label}: GitLab browse -> download -> mapping complete")

    # -- sections ---------------------------------------------------------------------
    def section_flash(self) -> None:
        for i in range(self.iterations):
            label = f"flash[{i}]"
            adapter = FakeWinIDEAAdapter(download_seconds=0.3)
            window = self.new_window(adapter)
            if not self.load_artifact_via_gitlab(window, label):
                self.close_window(window, label)
                continue
            self.dialogs.clear()

            window.start_flash()
            self.check(self.wait_step(window, Step.DONE.value, 10.0), f"{label}: flash reached Done")
            self.check(self.wait_flash_idle(window), f"{label}: flash worker released")
            self.check(adapter.programs["App"].endswith(NEW_APP_SUFFIX) and adapter.programs["App"] != OLD_APP,
                       f"{label}: App path points to the artifact")
            self.check(adapter.target_state == "halted", f"{label}: target halted after reset")

            adapter.download_seconds = 3.0
            window.start_flash()
            self.check(self.wait_step(window, Step.DOWNLOAD.value, 5.0), f"{label}: second flash downloading")
            window.cancel_flash()
            self.check(self.wait_step(window, "Cancelled", 5.0), f"{label}: cancelled flash settled")
            self.check(self.wait_flash_idle(window), f"{label}: cancelled worker released")
            self.check(adapter.programs["App"] != OLD_APP,
                       f"{label}: cancel restored the paths of before this flash (the first flash's)")
            self.check(adapter.connected_to is None, f"{label}: disconnected after cancel")

            adapter.download_seconds = 1.0
            window.start_flash()
            levels = window.ui.comboBox_logLevel
            for n, size in enumerate(((800, 600), (1600, 1000), (1024, 700), (1280, 820))):
                window.resize(*size)
                levels.setCurrentIndex(n % levels.count())
                self.pump(0.05)
            self.check(self.wait_step(window, Step.DONE.value, 10.0), f"{label}: flash with resize/filter reached Done")
            self.check(self.wait_flash_idle(window), f"{label}: third worker released")
            self.check(self.dialogs == [], f"{label}: no error dialog in the happy paths: {self.dialogs}")
            self.close_window(window, label)

    def section_rollback(self) -> None:
        originals_programs = {"App": OLD_APP}
        originals_apps = {"CM7_0": OLD_CM7_0, "CM7_1": OLD_CM7_1}
        cases = [
            # label, adapter, profile download_s, expected rollback_failed
            ("missing entry", FakeWinIDEAAdapter(download_seconds=0.2, programs={"Other": OLD_APP}), None, False),
            ("set path refused", FakeWinIDEAAdapter(download_seconds=0.2, fail_on={"set_path"}), None, True),
            ("download fails at 50%", FakeWinIDEAAdapter(download_seconds=0.4, fail_on={"download"}), None, False),
            ("download timeout", FakeWinIDEAAdapter(download_seconds=3.0), 1, False),
            ("connection dropped mid-transfer", DropsMidTransfer(download_seconds=0.2), None, False),
            ("connection dropped for good", DropsAndStaysDown(download_seconds=0.2), None, True),
        ]
        for name, adapter, download_s, rollback_failed in cases:
            label = f"rollback[{name}]"
            programs_before = dict(adapter.programs)
            window = self.new_window(adapter, download_s=download_s)
            window.on_artifact_ready(self.artifact(name.replace(" ", "_")), f"job #{JOB_ID}")
            self.dialogs.clear()
            window.start_flash()
            self.check(self.wait_step(window, "Failed", 10.0), f"{label}: flash failed")
            self.check(self.wait_flash_idle(window), f"{label}: worker released")
            self.check(len(self.dialogs) == 1, f"{label}: exactly one error dialog, got {len(self.dialogs)}")
            self.check(adapter.connected_to is None, f"{label}: disconnected")
            warning_shown = window.ui.label_rollbackWarning.isVisibleTo(window)
            self.check(warning_shown == rollback_failed, f"{label}: rollback warning shown={warning_shown}")
            if rollback_failed and self.dialogs:
                self.check("ROLLBACK FAILED" in self.dialogs[0][1], f"{label}: dialog says ROLLBACK FAILED")
            if name == "connection dropped for good":
                self.check(adapter.programs["App"] != OLD_APP, f"{label}: (expected) App still points to the new file")
            else:
                self.check(adapter.programs == programs_before, f"{label}: program paths back to the originals")
                if name != "missing entry":
                    self.check(adapter.programs == originals_programs, f"{label}: App == original")
                self.check(adapter.applications == originals_apps, f"{label}: symbol paths back to the originals")
            self.close_window(window, label)

    def section_gitlab(self) -> None:
        session = FakeGitLabSession()
        window = self.new_window(FakeWinIDEAAdapter(), session)
        for i in range(5):
            window.refresh_gitlab()
            self.pump(0.01)
        self.check(self.pump_until(lambda: not window.gitlab_busy(), 5.0), "gitlab: repeated refreshes settled")
        self.check(window.ui.comboBox_ref.count() == 2, "gitlab: refs listed once (stale results dropped)")
        self.check(self.load_artifact_via_gitlab(window, "gitlab"), "gitlab: browse to artifact")

        window.download_selected_artifact()
        window.download_selected_artifact()  # double-click: second refused
        self.check(self.pump_until(lambda: not window.gitlab_busy(), 5.0), "gitlab: cached download settled")
        self.check(session.count(f"/jobs/{JOB_ID}/artifacts") == 1, "gitlab: one network download, then cache")

        self.dialogs.clear()
        for status, needle in ((401, "expired"), (403, "access"), (404, "expired")):
            session.fail_status = status
            window.refresh_gitlab()
            ok = self.pump_until(lambda: len(self.dialogs) == 1, 5.0)
            self.check(ok and f"HTTP {status}" in self.dialogs[0][1] and needle in self.dialogs[0][1],
                       f"gitlab: HTTP {status} shows its specific hint")
            self.pump_until(lambda: not window.gitlab_busy(), 5.0)
            self.dialogs.clear()
        session.fail_status = None
        session.connection_error = True
        window.refresh_gitlab()
        ok = self.pump_until(lambda: len(self.dialogs) == 1, 5.0)
        self.check(ok and "Cannot reach GitLab" in self.dialogs[0][1], "gitlab: connection error reported")
        session.connection_error = False
        self.pump_until(lambda: not window.gitlab_busy(), 5.0)
        self.dialogs.clear()
        self.close_window(window, "gitlab")

        # Cancel an artifact download: nothing loaded afterwards.
        slow = FakeGitLabSession(chunk_delay_s=0.02)
        window = self.new_window(FakeWinIDEAAdapter(), slow)
        window.refresh_gitlab()
        self.pump_until(lambda: window.ui.listWidget_pipelines.count() == 1, 5.0)
        window.ui.listWidget_pipelines.setCurrentRow(0)
        self.pump_until(lambda: window.ui.listWidget_jobs.count() == 1, 5.0)
        window.ui.listWidget_jobs.setCurrentRow(0)
        window.download_selected_artifact()
        self.pump_until(lambda: window.ui.progressBar_artifact.value() > 0, 5.0)
        window.cancel_artifact_download()
        self.check(self.pump_until(lambda: not window.gitlab_busy(), 5.0), "gitlab: cancelled download settled")
        self.check(not window.mapping_rows(), "gitlab: no artifact loaded after cancel")
        self.check(self.dialogs == [], "gitlab: cancel shows no error dialog")
        self.close_window(window, "gitlab-cancel")

        # Window closed mid-fetch / mid-download at several delays.
        for delay in CANCEL_DELAYS_S[:5]:
            fetch = FakeGitLabSession(delay_s=0.3)
            window = self.new_window(FakeWinIDEAAdapter(), fetch)
            window.refresh_gitlab()
            self.pump(delay)
            self.close_window(window, f"gitlab: closed {delay * 1000:.0f} ms into a fetch", max_s=3.0)
            self.check(window.ui.comboBox_ref.count() == 0, f"gitlab: nothing shown after close at {delay}s")
        for delay in (0.0, 0.05, 0.2):
            dl = FakeGitLabSession(chunk_delay_s=0.02)
            window = self.new_window(FakeWinIDEAAdapter(), dl)
            window.refresh_gitlab()
            self.pump_until(lambda: window.ui.listWidget_pipelines.count() == 1, 5.0)
            window.ui.listWidget_pipelines.setCurrentRow(0)
            self.pump_until(lambda: window.ui.listWidget_jobs.count() == 1, 5.0)
            window.ui.listWidget_jobs.setCurrentRow(0)
            window.download_selected_artifact()
            self.pump(delay)
            self.close_window(window, f"gitlab: closed {delay * 1000:.0f} ms into a download", max_s=3.0)
            self.check(not window.mapping_rows(), f"gitlab: no artifact loaded after close at {delay}s")
        self.check(self.dialogs == [], f"gitlab: no dialogs from closing windows: {self.dialogs}")

    def section_races(self) -> None:
        adapter = FakeWinIDEAAdapter(download_seconds=0.5)
        window = self.new_window(adapter)
        window.on_artifact_ready(self.artifact("races"), f"job #{JOB_ID}")
        self.dialogs.clear()
        for delay in CANCEL_DELAYS_S:
            label = f"races: cancel {delay * 1000:.0f} ms after Flash"
            before = dict(adapter.programs)
            window.start_flash()
            self.pump(delay)
            window.cancel_flash()
            window.cancel_flash()  # double Cancel
            self.check(self.wait_flash_idle(window), f"{label}: settled")
            final = window.ui.label_step.text()
            self.check(final in ("Cancelled", Step.DONE.value), f"{label}: final state {final!r}")
            if final == "Cancelled":
                self.check(adapter.programs == before, f"{label}: paths restored")
            self.check(adapter.connected_to is None, f"{label}: disconnected")
        self.check(self.dialogs == [], f"races: cancels show no error dialog: {self.dialogs}")

        downloads = adapter.calls.count("download")
        window.start_flash()
        window.start_flash()  # double Flash
        running = [k for k in window._workers.running_keys() if k.startswith("flash")]
        self.check(len(running) == 1, f"races: double Flash runs one worker, got {running}")
        try:
            window.export_bundle(self.workdir / "bundle_during_flash")
            refused = False
        except RuntimeError:
            refused = True
        self.check(refused, "races: debug bundle export refused while flashing")
        self.check(self.wait_step(window, Step.DONE.value, 10.0), "races: double-Flash run completed")
        self.wait_flash_idle(window)
        self.check(adapter.calls.count("download") == downloads + 1, "races: exactly one download for double Flash")
        self.close_window(window, "races")

        # Window closed mid-download: rollback finished before close() returns.
        adapter = FakeWinIDEAAdapter(download_seconds=10.0)
        window = self.new_window(adapter)
        window.on_artifact_ready(self.artifact("close"), f"job #{JOB_ID}")
        window.start_flash()
        self.check(self.wait_step(window, Step.DOWNLOAD.value, 5.0), "races: long flash downloading")
        self.questions.clear()
        self.close_window(window, "races: closed mid-download", max_s=3.0)
        self.check(len(self.questions) == 1, "races: close asked for confirmation once")
        self.check(adapter.programs["App"] == OLD_APP, "races: close rolled back App")
        self.check(adapter.connected_to is None, "races: close disconnected")

        # Closed during the GitLab fetch, before any flash worker exists.
        window = self.new_window(FakeWinIDEAAdapter(), FakeGitLabSession(delay_s=0.4))
        window.refresh_gitlab()
        self.pump(0.05)
        self.check(not window.flash_active(), "races: no flash worker before close")
        self.close_window(window, "races: closed during GitLab fetch", max_s=3.0)

    def section_secrets(self) -> None:
        window = self.new_window(FakeWinIDEAAdapter(download_seconds=0.1))
        window.ui.comboBox_logLevel.setCurrentIndex(0)  # DEBUG: show everything
        log.info("token in a message: %s", TOKEN)
        log.error("request headers {'PRIVATE-TOKEN': '%s'}", TOKEN)
        log.debug("url https://gitlab.example.com/api/v4/projects?private_token=%s", TOKEN)
        window.ctx.add_error(RuntimeError(f"authentication failed for {TOKEN}"))
        self.pump(0.2)
        panel = window.log_visible_text()
        self.check(TOKEN not in panel, "secrets: token absent from the log panel")
        self.check("***" in panel, "secrets: panel shows the masked token")
        for handler in logging.getLogger("wflash").handlers:
            handler.flush()
        file_text = self.log_file.read_text(encoding="utf-8")
        self.check(TOKEN not in file_text, "secrets: token absent from the log file")
        self.check("token in a message: ***" in file_text, "secrets: log file has the masked line")
        bundle = window.export_bundle(self.workdir / "bundle")
        with zipfile.ZipFile(bundle) as zf:
            contents = {name: zf.read(name).decode("utf-8", "replace") for name in zf.namelist()}
        leaked = [name for name, text in contents.items() if TOKEN in text]
        self.check(leaked == [], f"secrets: token absent from every bundle file (leaked in {leaked})")
        self.check("authentication failed for ***" in contents.get("errors.txt", ""), "secrets: bundle errors masked")
        self.close_window(window, "secrets")


SECTIONS = {
    "flash": ("full fetch->map->flash, cancel mid-download, resize + log filter while live", Stress.section_flash),
    "rollback": ("every failure branch; workspace paths restored, failed rollback shown", Stress.section_rollback),
    "gitlab": ("refresh storms, 401/403/404/connection, double-click, cancel, close mid-fetch", Stress.section_gitlab),
    "races": ("cancel at 0..400 ms, double Flash/Cancel, close mid-download / mid-fetch", Stress.section_races),
    "secrets": ("a realistic PAT through panel, log file and debug bundle", Stress.section_secrets),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="list the sections and exit")
    parser.add_argument("--section", action="append", choices=sorted(SECTIONS), help="run only these (repeatable)")
    parser.add_argument("--iterations", type=int, default=2, help="repetitions of the flash section")
    parser.add_argument("--keep", action="store_true", help="keep the temporary work folder")
    args = parser.parse_args(argv)
    if args.list:
        for name, (description, _) in SECTIONS.items():
            print(f"{name:<9} {description}")
        return 0

    app = QApplication.instance() or QApplication([sys.argv[0]])
    workdir = Path(tempfile.mkdtemp(prefix="wflash_stress_"))
    log_file = setup_logging(log_dir=workdir / "logs")
    stress = Stress(workdir, log_file, args.iterations)

    def qt_handler(mode, context, message) -> None:
        if mode in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            if any(pattern in message for pattern in THREADING_PATTERNS):
                stress.qt_problems.append(message)
                print(f"  QT THREADING WARNING: {message}", flush=True)
            else:
                stress.qt_other.append(message)

    def excepthook(exc_type, exc, tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        stress.failures.append(f"uncaught exception: {text}")
        print(f"  UNCAUGHT: {text}", flush=True)

    def thread_excepthook(hook_args) -> None:
        excepthook(hook_args.exc_type, hook_args.exc_value, hook_args.exc_traceback)

    def unraisablehook(unraisable) -> None:
        stress.failures.append(f"unraisable: {unraisable.exc_value!r} in {unraisable.object!r}")

    previous_handler = qInstallMessageHandler(qt_handler)
    sys.excepthook = excepthook
    threading.excepthook = thread_excepthook
    sys.unraisablehook = unraisablehook

    def critical(parent, title, text, *rest):
        stress.dialogs.append((title, text))
        return QMessageBox.StandardButton.Ok

    def question(parent, title, text, *rest):
        stress.questions.append(text)
        return stress.answer

    QMessageBox.critical = staticmethod(critical)
    QMessageBox.warning = staticmethod(critical)
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(question)

    selected = args.section or list(SECTIONS)
    started = time.monotonic()
    for name in selected:
        print(f"== {name}: {SECTIONS[name][0]}", flush=True)
        t0 = time.monotonic()
        try:
            SECTIONS[name][1](stress)
        except Exception:
            stress.failures.append(f"section {name} raised:\n{traceback.format_exc()}")
            print(traceback.format_exc(), flush=True)
        print(f"   {name} done in {time.monotonic() - t0:.1f}s", flush=True)

    stress.pump(0.3)  # let late queued signals arrive while the handlers still listen
    stress.check(workers._ABANDONED == [], f"no worker was abandoned: {[w.key for w in workers._ABANDONED]}")
    stray = [t.name for t in threading.enumerate()
             if t is not threading.main_thread() and not isinstance(t, threading._DummyThread)]
    stress.check(stray == [], f"no Python worker threads left: {stray}")
    qInstallMessageHandler(previous_handler)
    close_file_handler()
    del app

    passed = not stress.failures and not stress.qt_problems
    print(f"CHECKPOINTS={stress.checkpoints} FAILED={len(stress.failures)} "
          f"QT_THREADING_WARNINGS={len(stress.qt_problems)} OTHER_QT_WARNINGS={len(stress.qt_other)} "
          f"TIME={time.monotonic() - started:.1f}s")
    for failure in stress.failures:
        print(f"  - {failure.splitlines()[0]}")
    for message in sorted(set(stress.qt_other))[:5]:
        print(f"  other Qt warning (not a failure): {message}")
    print(f"STRESS_RESULT={'PASS' if passed else 'FAIL'}")
    if passed and not args.keep:
        shutil.rmtree(workdir, ignore_errors=True)
    else:
        print(f"work folder kept: {workdir}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
