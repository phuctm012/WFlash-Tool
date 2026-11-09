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
import random

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# The stress test flashes many times: keep its history out of the real flash_history.csv.
os.environ["WFLASH_HISTORY_FILE"] = os.path.join(__import__("tempfile").mkdtemp(prefix="wflash_stress_"), "flash_history.csv")

import argparse  # noqa: E402
import csv  # noqa: E402
import dataclasses  # noqa: E402
import faulthandler  # noqa: E402
import logging  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
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

from PySide6.QtCore import QEvent, QtMsgType, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QDesktopServices  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from tests.gui_stubs import (  # noqa: E402
    GITLAB_URL,
    JOB_ID,
    PROJECT,
    OLD_APP,
    OLD_CM7_0,
    OLD_CM7_1,
    SOURCE,
    TOKEN,
    FakeGitLabSession,
    SessionClientFactory,
    make_artifact_tree,
    write_profiles,
)
from wflash.core.errors import WinIDEAError  # noqa: E402
from wflash.core.fake_adapter import FakeWinIDEAAdapter  # noqa: E402
from wflash.core.flash_plan import ProgramRow, SymbolRow  # noqa: E402
from wflash.core.flash_workflow import Step  # noqa: E402
from wflash.core.logging_setup import close_file_handler, get_logger, setup_logging  # noqa: E402
from wflash.core.settings import AppSettings  # noqa: E402
from wflash.core.gitlab_url import split_gitlab_url  # noqa: E402
from wflash.gui import gitlab_dialog, main_window, part_controller, workers  # noqa: E402
from wflash.gui.main_window import MainWindow  # noqa: E402
from wflash.gui.style import apply_theme  # noqa: E402
from wflash.gui.theme import THEMES, current_theme_name  # noqa: E402

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
    "different thread",
    "another thread",
    "outside the GUI thread",
)
POLL_S = part_controller.POLL_S
CANCEL_DELAYS_S = (0.0, 0.005, 0.02, 0.06, 0.15, 0.4)
NEW_APP_SUFFIX = "App.s3"
DEV_CAL = "20260623_142557_2018688_CAL_T008_v0_0.sre"
DEV_BM, DEV_FBL = "FBL_M7_LIP_RfeClock_Image.bin", "Radar_SUZ05_Gen7_FBL.bin"
DEV_FFI_JOB = "create_ffi_stingray_3p5mb_no_HTSM"
DEV_URL = f"{GITLAB_URL}/group"  # with a group: the short BM and FBL project names are joined to it


def suz05_rows():
    """The SUZ05 workspace as observed: five download rows (the first unticked), three symbol files."""
    programs = [
        ProgramRow(0, "Radar_SUZ05_Gen7.s3", "Radar_SUZ05_Gen7.s3", False, 0x1AA000),
        ProgramRow(1, "RAD_SUZ05_FFI.s3", "old/RAD_SUZ05_FFI.s3", True, 0),
        ProgramRow(2, DEV_CAL, DEV_CAL, True, 0),
        ProgramRow(3, DEV_BM, f"old/{DEV_BM}", True, 0),
        ProgramRow(4, DEV_FBL, f"old/{DEV_FBL}", True, 0xF1000),
    ]
    symbols = [
        SymbolRow(0, 0, "App_M7/Radar_SUZ05_Gen7.elf", "old/a.elf", True),
        SymbolRow(0, 1, "App_M7/Radar_SUZ05_Gen7_BM.elf", "old/b.elf", True),
        SymbolRow(0, 2, "App_M7/Radar_SUZ05_Gen7_FBL.elf", "old/c.elf", True),
    ]
    return programs, symbols


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
        self.keyring: dict[str, str] = {GITLAB_URL: TOKEN}
        self.opened: list[str] = []  # files and folders the menus asked the desktop to open

    def get_token(self, url: str) -> str | None:
        """Fake keyring lookup like the real one: by host, then by the full URL."""
        if not url:
            return None
        return self.keyring.get(split_gitlab_url(url)[0]) or self.keyring.get(url.rstrip("/"))

    def set_token(self, url: str, token: str) -> None:
        self.keyring[split_gitlab_url(url)[0] or url] = token

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

    def flush_closed_windows(self) -> None:
        """processEvents() never runs deleteLater(): free the windows closed so far, which nothing uses
        any more, or their widgets pile up and every later theme switch restyles all of them."""
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def new_window(self, adapter, session: FakeGitLabSession | None = None, download_s: int | None = None):
        self.flush_closed_windows()
        self._window_count += 1
        folder = self.workdir / f"window{self._window_count}"
        profiles = write_profiles(folder / "profiles", download_s)
        settings = AppSettings(gitlab_url=GITLAB_URL, profiles_dir=str(profiles), cache_dir=str(folder / "cache"))
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
        return self.pump_until(lambda: window.current_step() == text, timeout_s)

    def wait_flash_idle(self, window, timeout_s: float = 10.0) -> bool:
        return self.pump_until(lambda: not window.flash_active(), timeout_s)

    def open_dialog(self, window):
        window.open_gitlab_dialog()
        dialog = window._gitlab_dialog
        self.check(dialog.isVisible(), "dialog: Load from GitLab opened")
        return dialog

    def browse_to_job(self, window, label: str):
        """Open Load from GitLab, load the refs, list the jobs (no download). Returns the dialog."""
        dialog = self.open_dialog(window)
        dialog.load_refs()
        ok = self.pump_until(lambda: not dialog.busy() and dialog.ui.comboBox_ref.count() == 2, 5.0)
        if ok:
            dialog.browse_jobs()
            ok = self.pump_until(lambda: not dialog.busy() and dialog.ui.tableWidget_jobs.rowCount() == 1, 5.0)
        self.check(ok, f"{label}: dialog listed refs and the job")
        return dialog if ok else None

    def load_artifact_via_gitlab(self, window, label: str) -> bool:
        dialog = self.browse_to_job(window, label)
        ok = dialog is not None
        if ok:
            dialog.job_button(0).click()
            ok = self.pump_until(window.mapping_complete, 10.0)
        if ok:
            ok = self.pump_until(lambda: not window.gitlab_busy() and not dialog.isVisible(), 5.0)
        return self.check(ok, f"{label}: dialog download -> mapping complete -> dialog closed")

    def start_slow_download(self, window, label: str):
        """Browse to the job, start its download and prove it is in flight (progress moved)."""
        dialog = self.browse_to_job(window, label)
        if dialog is None:
            return None
        dialog.job_button(0).click()
        started = self.pump_until(
            lambda: dialog.busy() and dialog.ui.progressBar_download.value() > 0, 5.0
        )
        self.check(started, f"{label}: artifact download in flight (worker running, progress > 0)")
        return dialog if started else None

    # -- sections ---------------------------------------------------------------------
    def check_locked_flash(self, label: str) -> None:
        """Like the real adapter: Cancel is locked once programming starts and the run still completes."""
        window = self.new_window(FakeWinIDEAAdapter(download_seconds=0.5, cancellable=False))
        if self.load_artifact_via_gitlab(window, label):
            window.start_flash()
            self.check(self.wait_step(window, Step.DOWNLOAD.value, 5.0), f"{label}: downloading")
            self.pump(0.05)
            self.check(window.flash_locked(), f"{label}: locked while programming")
            self.check(not window.ui.pushButton_flash.isEnabled(), f"{label}: Cancel disabled while programming")
            window.cancel_flash()
            self.check(self.wait_step(window, Step.DONE.value, 10.0), f"{label}: reached Done despite Cancel")
            self.check(self.wait_flash_idle(window), f"{label}: worker released")
            self.check(not window.flash_locked(), f"{label}: unlocked afterwards")
        self.close_window(window, label)

    def check_two_sources(self, label: str) -> None:
        """The .s3 and the ELF from two artifacts: Flash waits for both, and each row sees only its own."""
        adapter = FakeWinIDEAAdapter(download_seconds=0.2)
        window = self.new_window(adapter)
        folder = Path(window.settings.profiles_dir)
        (folder / "two.yaml").write_text(
            "name: Two\ngitlab: {project: group/app}\n"
            "sources:\n  ffi: {label: FFI}\n  m7: {label: M7}\n"
            "programs:\n  - {winidea_entry: App, source: ffi, pattern: '**/*.s3'}\n"
            "applications:\n  - {winidea_app: CM7_0, source: m7, pattern: '**/*cm7_0*.elf'}\n",
            encoding="utf-8",
        )
        window.reload_profiles()
        window.ui.comboBox_profile.setCurrentIndex(window.ui.comboBox_profile.findText("Two"))
        for source_id in ("ffi", "m7"):
            window.source_load_button(source_id).click()
            window._gitlab_dialog.firmwareReady.emit(self.artifact(f"two_{source_id}"), SOURCE)
            window._gitlab_dialog.reject()
            self.pump(0.02)
            self.check(window.mapping_complete() == (source_id == "m7"), f"{label}: complete only after both ({source_id})")
        window.start_flash()
        self.check(self.wait_step(window, Step.DONE.value, 10.0), f"{label}: reached Done")
        self.check(self.wait_flash_idle(window), f"{label}: worker released")
        self.check("two_ffi" in adapter.programs["App"], f"{label}: program file from the FFI artifact")
        self.check("two_m7" in adapter.applications["CM7_0"], f"{label}: symbol file from the M7 artifact")
        self.close_window(window, label)

    # -- developer flow (profile with builds) --------------------------------------------
    def git(self, repo: Path, *args: str) -> None:
        """git, only ever inside the temporary work folder: never in the WFlash repo itself."""
        repo = Path(repo).resolve()
        if not repo.is_relative_to(self.workdir.resolve()) or repo == self.workdir.resolve():
            raise RuntimeError(f"stress test refused to run git outside its work folder: {repo}")
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    def commit_file(self, repo: Path, name: str, text: str) -> None:
        self.git(repo, "rev-parse", "--git-dir")  # checks the path before writing anything
        (Path(repo) / name).write_text(text)
        self.git(repo, "add", name)
        self.git(repo, "commit", "-q", "-m", name)

    def make_repo(self, folder: Path) -> Path:
        folder.mkdir(parents=True)
        for args in (("init", "-q", "-b", "main"), ("config", "user.email", "s@example.com"), ("config", "user.name", "S")):
            self.git(folder, *args)
        self.commit_file(folder, "a.c", "1")
        return folder

    def new_dev_window(self, label: str, session: FakeGitLabSession | None = None, read_repo: bool = True):
        """SUZ05 with the GitLab URL of a group; the App repository typed in the GitLab tab."""
        self.flush_closed_windows()
        self._window_count += 1
        folder = self.workdir / f"dev{self._window_count}"
        profiles = folder / "profiles"
        profiles.mkdir(parents=True)
        text = (REPO / "profiles" / "suz05.yaml").read_text(encoding="utf-8")
        text = text.replace("project: SUZ05_APP_Application_Software-Impl", f"project: {PROJECT}", 1)
        (profiles / "suz05.yaml").write_text(text, encoding="utf-8")
        workspace = folder / "ws"
        workspace.mkdir()
        (workspace / DEV_CAL).write_text("S0")
        adapter = FakeWinIDEAAdapter(download_seconds=0.2, rows=suz05_rows(), workspace=str(workspace / "SUZ_7G5_M7.xjrf"))
        settings = AppSettings(profiles_dir=str(profiles), cache_dir=str(folder / "cache"), last_profile="suz05.yaml",
                               gitlab_urls={"suz05.yaml": DEV_URL}, last_build={"suz05.yaml": "stingray_3p5mb_no_HTSM"})
        window = MainWindow(settings, adapter, client_factory=SessionClientFactory(session or FakeGitLabSession()),
                            log_file=self.log_file, settings_path=folder / "settings.json")
        window.resize(1280, 820)
        window.show()
        self.check(self.pump_until(lambda: window.ui.comboBox_instance.count() == 1, 5.0), f"{label}: instance listed")
        self.check(window.developer_mode(), f"{label}: GitLab tab for a profile with builds")
        app = window.parts["app"]
        app.w_repo.setText(str(self.make_repo(folder / "src")))
        if read_repo:
            app._on_repo_edited()
            self.check(self.pump_until(lambda: app.repo_state is not None, 5.0), f"{label}: App repo read")
            self.check(window.ui.label_appBranch.text() == "main", f"{label}: App branch shown")
        return window, adapter

    def wait_part(self, part, roles, timeout_s: float = 8.0) -> bool:
        return self.pump_until(lambda: set(roles) <= set(part.loaded) and not part.loading(), timeout_s)

    def deliver_manual(self, window, part: str, role: str, job: str) -> None:
        """What Choose Job delivers once its popup has downloaded the artifact."""
        root = self.workdir / f"manual_{role}_{self._window_count}_{job}"
        files = {"ffi": ["out/FFI/RAD_SUZ05_FFI.s3"], "elf": ["out/ELF/Radar_SUZ05_Gen7.elf"],
                 "bm": [f"out/bin/{DEV_BM}", "out/bin/Radar_SUZ05_Gen7_BM.elf"],
                 "fbl": [f"out/bin/{DEV_FBL}", "out/bin/Radar_SUZ05_Gen7_FBL.elf"]}[role]
        for rel in files:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_bytes(b"S0")
        (root / ".complete").write_text("x")
        window._loading_source = f"part:{part}:{role}"
        window.on_firmware_ready(root, dataclasses.replace(SOURCE, job_name=job, commit="41c7a0de"))

    def check_developer_flow(self, label: str) -> None:
        """App by commit -> Advanced Debug off/on -> BM by its commit, FBL manual -> two flashes."""
        window, adapter = self.new_dev_window(label)
        app = window.parts["app"]
        self.check(self.wait_part(app, ("ffi", "elf")), f"{label}: App loaded from its commit")
        # Reload and coming back to the window, hammered: one read and one load at a time.
        downloads = window._client_factory.session.count("/artifacts")
        for n in range(8):
            app.reload() if n % 2 else window.refresh_source_repo_on_activate()
            reads = [k for k in window._workers.running_keys() if k.startswith("part-repo-app")]
            loads = [k for k in window._workers.running_keys() if k.startswith("part-load-app")]
            self.check(len(reads) <= 1 and len(loads) <= 1, f"{label}: one read/load at a time, got {reads + loads}")
        self.check(self.pump_until(lambda: not app.busy(), 5.0), f"{label}: repeated reloads settled")
        self.check(window._client_factory.session.count("/artifacts") == downloads,
                   f"{label}: the same commit is not downloaded again")
        self.check(app.status_text().startswith("FFI: create_ffi_stingray_3p5mb_no_HTSM · main · "),
                   f"{label}: status line {app.status_text()!r}")
        for _ in range(3):
            window.ui.checkBox_advancedDebug.toggle()
            self.pump(0.01)
        self.check(window.advanced_debug(), f"{label}: Advanced Debug on after three toggles")
        window.ui.checkBox_advancedDebug.setChecked(False)
        self.check([r.role for r in window.mapping_rows()] == ["ffi", "cal", "elf"], f"{label}: no BM/FBL rows when off")
        self.check(self.pump_until(window.ui.pushButton_flash.isEnabled, 3.0), f"{label}: Flash enabled without BM/FBL")
        window.start_flash()
        self.check(self.wait_step(window, Step.DONE.value, 10.0), f"{label}: flash (Advanced Debug off) reached Done")
        self.check(self.wait_flash_idle(window), f"{label}: worker released")
        rows = {r.name: r for r in adapter.program_rows}
        self.check(not rows[DEV_BM].enabled and not rows[DEV_FBL].enabled, f"{label}: BM/FBL unticked when off")
        self.check("main" in rows["RAD_SUZ05_FFI.s3"].path, f"{label}: FFI path in the branch folder")

        window.ui.checkBox_advancedDebug.setChecked(True)
        bm = window.parts["bm"]
        bm.w_repo.setText(str(self.make_repo(self.workdir / f"dev{self._window_count}" / "bm")))
        bm._on_repo_edited()
        self.check(self.pump_until(lambda: bm.repo_state is not None, 5.0), f"{label}: BM repo read")
        window.ui.radioButton_bmCommit.setChecked(True)
        self.check(self.wait_part(bm, ("bm",)), f"{label}: BM loaded from its commit")
        window.ui.radioButton_fblManual.setChecked(True)
        self.deliver_manual(window, "fbl", "fbl", "build")
        self.check(window.flash_block_reason() == "", f"{label}: nothing blocks: {window.flash_block_reason()!r}")
        self.check(self.pump_until(window.ui.pushButton_flash.isEnabled, 3.0), f"{label}: Flash enabled with BM/FBL")
        window.start_flash()
        self.check(self.wait_step(window, Step.DONE.value, 10.0), f"{label}: flash (Advanced Debug on) reached Done")
        self.check(self.wait_flash_idle(window), f"{label}: second worker released")
        rows = {r.name: r for r in adapter.program_rows}
        self.check(rows[DEV_BM].enabled and rows[DEV_FBL].enabled, f"{label}: BM/FBL ticked when on")
        self.check(rows[DEV_FBL].path.endswith(DEV_FBL) and "old/" not in rows[DEV_FBL].path, f"{label}: FBL path set")
        symbols = [r for r in adapter.symbol_rows if r.name.endswith("_BM.elf")]
        self.check(symbols and symbols[0].enabled and "old/" not in symbols[0].path, f"{label}: BM ELF ticked and set")
        with open(os.environ["WFLASH_HISTORY_FILE"], encoding="utf-8-sig", newline="") as fh:
            last = list(csv.DictReader(fh))[-1]
        self.check(last["result"] == "Done" and last["advanced_debug"] == "on"
                   and last["fbl_mode"] == "Manual" and last["bm_mode"] == "From commit",
                   f"{label}: flash history line {last}")
        self.check(self.dialogs == [], f"{label}: no error dialog: {self.dialogs}")
        self.close_window(window, label)

    def check_pipeline_wait(self, label: str) -> None:
        """A running pipeline is polled; it finishes during a flash, the load waits; then a close mid-wait."""
        part_controller.POLL_S = 0.05  # every 30 s in the app
        session = FakeGitLabSession()
        session.job_status[DEV_FFI_JOB] = "running"
        window, _adapter = self.new_dev_window(label, session)
        app = window.parts["app"]
        self.check(self.pump_until(app.waiting, 5.0), f"{label}: waiting for the pipeline")
        self.check("is running" in app.status_text(), f"{label}: status says running: {app.status_text()!r}")
        session.job_status.clear()
        self.check(self.wait_part(app, ("ffi", "elf"), 8.0), f"{label}: loaded once the pipeline finished")
        self.check(not app.waiting(), f"{label}: no longer waiting")
        # Waiting again, then the window closes mid-wait and mid-poll.
        session.job_status[DEV_FFI_JOB] = "pending"
        self.commit_file(self.workdir / f"dev{self._window_count}" / "src", "b.c", "2")
        app.refresh_repo()
        self.check(self.pump_until(app.waiting, 5.0), f"{label}: waiting for the new commit's pipeline")
        self.close_window(window, f"{label}: closed while waiting", max_s=3.0)
        self.check(not app.waiting(), f"{label}: wait timer stopped by close")
        part_controller.POLL_S = POLL_S

    def section_flash(self) -> None:
        self.check_developer_flow("flash[developer]")
        self.check_pipeline_wait("flash[pipeline-wait]")
        self.check_locked_flash("flash[locked]")
        self.check_two_sources("flash[two-sources]")
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

            programs_after_first = dict(adapter.programs)
            applications_after_first = dict(adapter.applications)
            adapter.download_seconds = 3.0
            window.start_flash()
            self.check(self.wait_step(window, Step.DOWNLOAD.value, 5.0), f"{label}: second flash downloading")
            window.cancel_flash()
            self.check(self.wait_step(window, "Cancelled", 5.0), f"{label}: cancelled flash settled")
            self.check(self.wait_flash_idle(window), f"{label}: cancelled worker released")
            self.check(adapter.programs == programs_after_first,
                       f"{label}: cancel restored exactly the program paths of the first flash")
            self.check(adapter.applications == applications_after_first,
                       f"{label}: cancel restored exactly the symbol paths of the first flash")
            self.check(adapter.connected_to is None, f"{label}: disconnected after cancel")

            adapter.download_seconds = 1.0
            window.start_flash()
            tabs = window.ui.tabWidget_main
            for n, size in enumerate(((800, 600), (1600, 1000), (1024, 700), (1280, 820))):
                window.resize(*size)
                tabs.setCurrentIndex(n % tabs.count())  # Flash and Setting tabs while flashing
                self.pump(0.05)
            tabs.setCurrentIndex(0)
            self.check(self.wait_step(window, Step.DONE.value, 10.0), f"{label}: flash with resize/tab switch reached Done")
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
            window.on_firmware_ready(self.artifact(name.replace(" ", "_")), SOURCE)
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
        dialog = self.open_dialog(window)
        for _ in range(5):
            dialog.load_refs()  # every click after the first is refused while busy
            self.pump(0.01)
        self.check(self.pump_until(lambda: not dialog.busy(), 5.0), "gitlab: repeated Load branches/tags settled")
        self.check(dialog.ui.comboBox_ref.count() == 2, "gitlab: refs listed once")
        self.check(session.count("/repository/branches") <= 5, "gitlab: no request storm")
        dialog.reject()
        self.check(self.load_artifact_via_gitlab(window, "gitlab"), "gitlab: browse to artifact")

        dialog = self.browse_to_job(window, "gitlab-cached")
        if dialog is not None:
            self.check(dialog.job_button(0).text() == "Cached", "gitlab: the downloaded job is shown as Cached")
            dialog.job_button(0).click()  # same job again: served from the cache
            self.check(self.pump_until(lambda: not dialog.isVisible() and not window.gitlab_busy(), 5.0),
                       "gitlab: cached download settled")
        self.check(session.count(f"/jobs/{JOB_ID}/artifacts") == 1, "gitlab: one network download, then cache")

        self.dialogs.clear()
        dialog = self.open_dialog(window)
        for status, needle in ((401, "expired"), (403, "access"), (404, "expired")):
            session.fail_status = status
            dialog.load_refs()
            ok = self.pump_until(lambda: len(self.dialogs) == 1, 5.0)
            self.check(ok and f"HTTP {status}" in self.dialogs[0][1] and needle in self.dialogs[0][1],
                       f"gitlab: HTTP {status} shows its specific hint")
            self.pump_until(lambda: not dialog.busy(), 5.0)
            self.check(dialog.isVisible(), f"gitlab: dialog stays open after HTTP {status}")
            self.dialogs.clear()
        session.fail_status = None
        session.connection_error = True
        dialog.load_refs()
        ok = self.pump_until(lambda: len(self.dialogs) == 1, 5.0)
        self.check(ok and "Cannot reach GitLab" in self.dialogs[0][1], "gitlab: connection error reported")
        session.connection_error = False
        self.pump_until(lambda: not dialog.busy(), 5.0)
        self.dialogs.clear()
        dialog.reject()
        self.close_window(window, "gitlab")

        # Double-click on an UNCACHED job while the first download is in flight: refused.
        slow_dc = FakeGitLabSession(chunk_delay_s=0.02)
        window = self.new_window(FakeWinIDEAAdapter(), slow_dc)
        dialog = self.start_slow_download(window, "gitlab-double-click")
        if dialog is not None:
            dialog.job_button(0).click()
            dialog.download_selected()
            running = [k for k in window._workers.running_keys() if "download" in k]
            self.check(len(running) == 1, f"gitlab: double-click runs one download worker, got {running}")
            self.check(self.pump_until(window.mapping_complete, 10.0), "gitlab: double-click download finished")
            self.check(self.pump_until(lambda: not window.gitlab_busy(), 5.0), "gitlab: double-click settled")
            self.check(slow_dc.count(f"/jobs/{JOB_ID}/artifacts") == 1,
                       f"gitlab: double-click made exactly one artifact request, got "
                       f"{slow_dc.count(f'/jobs/{JOB_ID}/artifacts')}")
        self.close_window(window, "gitlab-double-click")

        # Stop an artifact download: dialog stays open, nothing loaded afterwards.
        self.dialogs.clear()
        slow = FakeGitLabSession(chunk_delay_s=0.02)
        window = self.new_window(FakeWinIDEAAdapter(), slow)
        dialog = self.start_slow_download(window, "gitlab-stop")
        if dialog is not None:
            dialog.stop()
            self.check(self.pump_until(lambda: not dialog.busy(), 5.0), "gitlab: stopped download settled")
            self.check(dialog.isVisible(), "gitlab: dialog still open after Stop")
            self.check(dialog.ui.label_downloadStatus.text() == "Cancelled", "gitlab: status says Cancelled")
            self.check(not window.mapping_rows(), "gitlab: no artifact loaded after Stop")
            self.check(self.dialogs == [], "gitlab: Stop shows no error dialog")
            dialog.reject()
        self.close_window(window, "gitlab-stop")

        # Dialog closed mid-download at several delays: bounded, nothing loaded.
        for delay in (0.0, 0.05, 0.2):
            dl = FakeGitLabSession(chunk_delay_s=0.02)
            window = self.new_window(FakeWinIDEAAdapter(), dl)
            dialog = self.browse_to_job(window, f"gitlab: dialog-close {delay}s")
            if dialog is not None:
                dialog.job_button(0).click()
                self.check(dialog.busy(), f"gitlab: download in flight before dialog close at {delay}s")
                self.pump(delay)
                t0 = time.monotonic()
                dialog.reject()
                self.check(time.monotonic() - t0 < 3.0, f"gitlab: dialog close at {delay}s is bounded")
                self.check(not dialog.busy() and not window.gitlab_busy(), f"gitlab: no worker after dialog close at {delay}s")
                self.pump(0.1)
                self.check(not window.mapping_rows(), f"gitlab: nothing loaded after dialog close at {delay}s")
            self.close_window(window, f"gitlab: dialog-close {delay}s")

        # Window closed mid-fetch / mid-download at several delays.
        for delay in CANCEL_DELAYS_S[:5]:
            fetch = FakeGitLabSession(delay_s=0.3)
            window = self.new_window(FakeWinIDEAAdapter(), fetch)
            dialog = self.open_dialog(window)
            dialog.load_refs()
            self.pump(delay)
            self.close_window(window, f"gitlab: closed {delay * 1000:.0f} ms into a fetch", max_s=3.0)
            self.check(dialog.ui.comboBox_ref.count() == 0, f"gitlab: nothing shown after close at {delay}s")
            self.check(not dialog.isVisible(), f"gitlab: dialog closed with the window at {delay}s")
        for delay in (0.0, 0.05, 0.2):
            dl = FakeGitLabSession(chunk_delay_s=0.02)
            window = self.new_window(FakeWinIDEAAdapter(), dl)
            dialog = self.browse_to_job(window, f"gitlab: close-in-download {delay}s")
            if dialog is not None:
                dialog.job_button(0).click()
                self.check(dialog.busy(), f"gitlab: download in flight before close at {delay}s")
                self.pump(delay)
            self.close_window(window, f"gitlab: closed {delay * 1000:.0f} ms into a download", max_s=3.0)
            self.check(not window.mapping_rows(), f"gitlab: no artifact loaded after close at {delay}s")
        self.check(self.dialogs == [], f"gitlab: no dialogs from closing windows: {self.dialogs}")

    def section_races(self) -> None:
        adapter = FakeWinIDEAAdapter(download_seconds=0.5)
        window = self.new_window(adapter)
        window.on_firmware_ready(self.artifact("races"), SOURCE)
        self.dialogs.clear()
        for delay in CANCEL_DELAYS_S:
            label = f"races: cancel {delay * 1000:.0f} ms after Flash"
            before = dict(adapter.programs)
            before_apps = dict(adapter.applications)
            window.start_flash()
            self.pump(delay)
            window.cancel_flash()
            window.cancel_flash()  # double Cancel
            self.check(self.wait_flash_idle(window), f"{label}: settled")
            final = window.current_step()
            self.check(final in ("Cancelled", Step.DONE.value), f"{label}: final state {final!r}")
            if final == "Cancelled":
                self.check(adapter.programs == before, f"{label}: program paths restored")
                self.check(adapter.applications == before_apps, f"{label}: symbol paths restored")
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
        self.check(self.wait_flash_idle(window), "races: double-Flash worker released")
        self.check(adapter.calls.count("download") == downloads + 1, "races: exactly one download for double Flash")
        self.close_window(window, "races")

        # Window closed mid-download: rollback finished before close() returns.
        adapter = FakeWinIDEAAdapter(download_seconds=10.0)
        window = self.new_window(adapter)
        window.on_firmware_ready(self.artifact("close"), SOURCE)
        window.start_flash()
        in_flight = self.wait_step(window, Step.DOWNLOAD.value, 5.0) and window.flash_active()
        self.check(in_flight, "races: long flash downloading (worker running) before close")
        self.questions.clear()
        self.close_window(window, "races: closed mid-download", max_s=3.0)
        if in_flight:
            self.check(len(self.questions) == 1, "races: close asked for confirmation once")
            self.check(adapter.programs["App"] == OLD_APP, "races: close rolled back App")
            self.check(adapter.applications == {"CM7_0": OLD_CM7_0, "CM7_1": OLD_CM7_1},
                       "races: close rolled back symbol paths")
            self.check(adapter.connected_to is None, "races: close disconnected")

        # Closed during the GitLab fetch, before any flash worker exists.
        window = self.new_window(FakeWinIDEAAdapter(), FakeGitLabSession(delay_s=0.4))
        self.open_dialog(window).load_refs()
        self.check(self.pump_until(window.gitlab_busy, 2.0), "races: GitLab fetch in flight before close")
        self.check(not window.flash_active(), "races: no flash worker before close")
        self.close_window(window, "races: closed during GitLab fetch", max_s=3.0)

        # Developer flow: closed while a build loads, and while the repo is being read.
        window, _adapter = self.new_dev_window("races[dev-load]", FakeGitLabSession(delay_s=0.4))
        self.check(self.pump_until(window.parts["app"].loading, 3.0), "races: App load in flight before close")
        self.check(window.source_busy(), "races: source busy during the App load")
        self.close_window(window, "races: closed during App load", max_s=3.0)
        window, _adapter = self.new_dev_window("races[dev-repo]", read_repo=False)
        window.parts["app"]._on_repo_edited()
        self.close_window(window, "races: closed during repo read", max_s=3.0)
        # Manual chosen while the commit load runs: the load is dropped, never overwrites the choice.
        window, _adapter = self.new_dev_window("races[dev-mode]", FakeGitLabSession(delay_s=0.3))
        app = window.parts["app"]
        self.check(self.pump_until(app.loading, 3.0), "races: App load in flight before Manual")
        window.ui.radioButton_appManual.setChecked(True)
        self.pump(0.8)
        self.check(not app.loaded and not app.loading(), "races: Manual dropped the running commit load")
        window.ui.radioButton_appCommit.setChecked(True)
        self.check(self.wait_part(app, ("ffi", "elf")), "races: back to the commit, it loads")
        self.close_window(window, "races[dev-mode]")

    def section_theme(self) -> None:
        app = QApplication.instance()
        adapter = FakeWinIDEAAdapter(download_seconds=6.0)
        window = self.new_window(adapter)
        window.on_firmware_ready(self.artifact("theme"), SOURCE)
        self.dialogs.clear()
        window.start_flash()
        self.check(self.wait_step(window, Step.DOWNLOAD.value, 5.0), "theme: flash downloading")
        for dark in (True, False, True):
            t0 = time.monotonic()
            window.apply_dark_mode(dark)
            print(f"   theme switch took {time.monotonic() - t0:.2f} s ({len(app.topLevelWidgets())} top-level widgets)", flush=True)
            name = "dark" if dark else "light"
            self.check(current_theme_name() == name and THEMES[name]["primary"] in app.styleSheet(),
                       f"theme: switched to {name} while flashing")
            self.pump(0.1)
        self.check(window.flash_active() and window.ui.pushButton_flash.property("state") == "flashing",
                   "theme: button still Cancel while flashing")
        self.check(self.wait_step(window, Step.DONE.value, 10.0), "theme: flash reached Done in dark mode")
        self.check(self.wait_flash_idle(window), "theme: flash worker released")
        dialog = self.open_dialog(window)
        window.apply_dark_mode(False)
        self.check(dialog.isVisible() and current_theme_name() == "light", "theme: switched back with the dialog open")
        dialog.reject()
        self.check(self.dialogs == [], f"theme: no error dialogs: {self.dialogs}")
        self.close_window(window, "theme")
        apply_theme(app, False)

    def section_menu(self) -> None:
        """Every menu action, hammered; Tools refused while flashing; a close with a Tools worker running."""
        session = FakeGitLabSession()
        adapter = FakeWinIDEAAdapter(download_seconds=1.0)
        window = self.new_window(adapter, session)
        ui = window.ui
        self.dialogs.clear()
        self.opened.clear()
        for action in (ui.action_openLogFolder, ui.action_openDownloadFolder, ui.action_userGuide):
            action.trigger()
        self.check(len(self.opened) == 3 and all(Path(path).exists() for path in self.opened),
                   f"menu: log folder, download folder and user guide opened: {self.opened}")
        self.check(self.opened[-1].endswith("user_guide.html"), "menu: User Guide is the bundled HTML")
        ui.action_about.trigger()
        self.check(len(self.dialogs) == 1 and "WFlash v" in self.dialogs[0][1], "menu: About shows the version")
        self.dialogs.clear()
        for action, tab in ((ui.action_tabSetting, ui.tab_setting), (ui.action_tabFlash, ui.tab_flash)):
            action.trigger()
            self.check(ui.tabWidget_main.currentWidget() is tab, f"menu: {action.text()} shows its tab")
        ui.action_tabGitlab.trigger()  # hidden for a profile without builds: stays on Flash
        self.check(ui.tabWidget_main.currentWidget() is ui.tab_flash, "menu: hidden GitLab tab not shown")
        for _ in range(4):
            ui.action_darkMode.trigger()
            self.pump(0.01)
        self.check(current_theme_name() == "light" and not window.settings.dark_mode, "menu: dark mode toggled back")

        requests = session.count(f"/projects/{PROJECT}")
        for _ in range(4):
            ui.action_testGitlab.trigger()
            ui.action_checkCores.trigger()
        running = [k for k in window._workers.running_keys() if k.startswith("tools-")]
        self.check(len(running) <= 1, f"menu: one Tools worker at a time, got {running}")
        self.check(self.pump_until(lambda: not window.tools_busy(), 5.0), "menu: Tools settled")
        self.check(session.count(f"/projects/{PROJECT}") == requests + 1, "menu: one Test GitLab request")
        ui.action_checkCores.trigger()
        self.check(self.pump_until(lambda: not window.tools_busy(), 5.0), "menu: Check winIDEA cores settled")
        self.check("core_states" in adapter.calls and adapter.connected_to is None,
                   "menu: cores read, then disconnected")
        self.check(not any(c in adapter.calls for c in ("download", "set_program_path")), "menu: Check cores is read only")
        session.fail_status = 401
        ui.action_testGitlab.trigger()
        self.check(self.pump_until(lambda: not window.tools_busy(), 5.0), "menu: failed Test GitLab settled")
        session.fail_status = None
        self.check(self.dialogs == [], f"menu: Tools failures go to the log, no dialog: {self.dialogs}")

        window.on_firmware_ready(self.artifact("menu"), SOURCE)
        window.start_flash()
        self.check(self.wait_step(window, Step.DOWNLOAD.value, 5.0), "menu: flash downloading")
        cores_before = adapter.calls.count("core_states")
        ui.action_testGitlab.trigger()
        ui.action_checkCores.trigger()
        ui.action_refreshInstances.trigger()
        self.check(not window.tools_busy(), "menu: Tools refused while flashing")
        self.check(not ui.action_checkCores.isEnabled(), "menu: Check cores disabled while flashing")
        self.check(self.wait_step(window, Step.DONE.value, 10.0), "menu: flash reached Done")
        self.check(self.wait_flash_idle(window), "menu: flash worker released")
        self.check(adapter.calls.count("core_states") >= cores_before, "menu: no stray cores read")
        ui.action_openHistory.trigger()
        self.check(self.opened[-1] == os.environ["WFLASH_HISTORY_FILE"], "menu: flash history opened")
        self.close_window(window, "menu")

        # Closed while a Tools request is in flight.
        window = self.new_window(FakeWinIDEAAdapter(), FakeGitLabSession(delay_s=0.4))
        window.ui.action_testGitlab.trigger()
        self.check(window.tools_busy(), "menu: Test GitLab in flight before close")
        self.close_window(window, "menu: closed during Test GitLab", max_s=3.0)
        self.check(self.dialogs == [], f"menu: no dialogs: {self.dialogs}")

    def section_fuzz(self) -> None:
        """Random user actions on the developer window, then a close at a random moment.

        Each seed is reproducible (`--section fuzz --seed N`). Failures are the global ones:
        uncaught exceptions, Qt threading warnings, a slow close, workers left running."""
        part_controller.POLL_S = 0.05
        # Weighted toward Flash: the dangerous mixes are a flash with everything else around it.
        weights = {
            "reload": 3, "activate": 3, "mode_app": 2, "mode_bm": 1, "mode_fbl": 1, "advanced": 2, "build": 1,
            "profile": 1, "flash": 10, "cancel": 3, "tools_gitlab": 2, "tools_cores": 2, "refresh": 2,
            "checkout": 1, "commit": 2, "pipeline": 2, "manual_debug": 4, "manual_app": 3, "theme": 1, "tab": 2, "pump": 6,
        }
        actions, action_weights = list(weights), list(weights.values())
        flashes = 0
        for seed in self.seeds:
            rng = random.Random(seed)
            label = f"fuzz[{seed}]"
            session = FakeGitLabSession(delay_s=rng.choice((0.0, 0.02, 0.1)))
            window, adapter = self.new_dev_window(label, session, read_repo=rng.random() < 0.7)
            adapter.download_seconds = rng.choice((0.1, 0.4, 1.0))
            write_profiles(Path(window.settings.profiles_dir))
            window.reload_profiles()
            app = window.parts["app"]
            repo = self.workdir / f"dev{self._window_count}" / "src"  # fixed: the field may be emptied
            self.answer = QMessageBox.StandardButton.Yes
            done = []
            for step in range(rng.randint(25, 60)):
                action = rng.choices(actions, action_weights)[0]
                done.append(action)
                ui = window.ui
                if action == "reload":
                    rng.choice(list(window.parts.values())).reload()
                elif action == "activate":
                    window.refresh_source_repo_on_activate()
                elif action.startswith("mode_"):
                    part = action[5:]
                    button = getattr(ui, f"radioButton_{part}{rng.choice(('Commit', 'Manual'))}")
                    if button.isEnabled():
                        button.setChecked(True)
                elif action == "advanced" and ui.checkBox_advancedDebug.isEnabled():
                    ui.checkBox_advancedDebug.toggle()
                elif action == "build" and ui.comboBox_appBuild.isEnabled() and ui.comboBox_appBuild.count():
                    ui.comboBox_appBuild.setCurrentIndex(rng.randrange(ui.comboBox_appBuild.count()))
                elif action == "profile" and ui.comboBox_profile.isEnabled():
                    ui.comboBox_profile.setCurrentIndex(rng.randrange(ui.comboBox_profile.count()))
                    if not window.developer_mode() and rng.random() < 0.5:
                        window.on_firmware_ready(self.artifact(f"fuzz{seed}_{step}"), SOURCE)
                elif action == "flash" and ui.pushButton_flash.isEnabled() and not window.flash_active():
                    window.start_flash()
                    flashes += 1
                elif action == "pump":
                    self.pump(rng.uniform(0.1, 0.6))
                elif action == "cancel":
                    window.cancel_flash()
                elif action == "tools_gitlab":
                    ui.action_testGitlab.trigger()
                elif action == "tools_cores":
                    ui.action_checkCores.trigger()
                elif action == "refresh":
                    ui.action_refreshInstances.trigger()
                elif action == "checkout" and window.developer_mode():
                    part = window.parts["app"]
                    if part.w_checkout.isEnabled():
                        part.open_checkout()
                        self.pump(rng.uniform(0, 0.15))
                        window._checkout_dialog.reject()
                elif action == "commit":
                    self.commit_file(repo, f"f{step}.c", str(step))
                elif action == "pipeline":
                    if session.job_status:
                        session.job_status.clear()
                    else:
                        session.job_status[DEV_FFI_JOB] = rng.choice(("running", "pending", "manual", "failed"))
                elif action == "manual_debug" and window.developer_mode() and window.advanced_debug() \
                        and not window.flash_active():
                    for name in ("bm", "fbl"):
                        part = window.parts[name]
                        if part.mode == "manual" and part.jobs():
                            self.deliver_manual(window, name, name, part.jobs()[0])
                elif action == "manual_app" and window.developer_mode() and not window.flash_active():
                    part = window.parts["app"]
                    if part.mode == "manual" and part.jobs():
                        for role, job in zip(part.roles, part.jobs()):
                            self.deliver_manual(window, "app", role, job)
                elif action == "theme":
                    window.apply_dark_mode(rng.random() < 0.5)
                elif action == "tab":
                    ui.tabWidget_main.setCurrentIndex(rng.randrange(ui.tabWidget_main.count()))
                self.pump(rng.choice((0.0, 0.005, 0.03, 0.1)))
            log.info("%s actions: %s", label, " ".join(done))
            closing_during = "flash" if window.flash_active() else ("load" if window.source_busy() else "idle")
            closing_during += f" [dev={window.developer_mode()} adv={window.advanced_debug() if window.developer_mode() else "-"} complete={window.mapping_complete()} block={window.flash_block_reason()!r} app={sorted(app.loaded)} status={app.status_text()[:60]!r}]"
            print(f"   {label}: {len(done)} actions, {flashes} flash(es) started, closed while {closing_during}",
                  flush=True)
            flashes = 0
            self.dialogs.clear()
            self.close_window(window, f"{label} closed after {len(done)} actions", max_s=5.0)
            self.check(not any(part.waiting() for part in window.parts.values()), f"{label}: no wait timer left")
            self.check(adapter.connected_to is None, f"{label}: winIDEA disconnected after close")
        apply_theme(QApplication.instance(), False)
        part_controller.POLL_S = POLL_S

    def section_secrets(self) -> None:
        window = self.new_window(FakeWinIDEAAdapter(download_seconds=0.1))
        log.info("token in a message: %s", TOKEN)
        log.error("request headers {'PRIVATE-TOKEN': '%s'}", TOKEN)
        log.debug("url https://gitlab.example.com/api/v4/projects?private_token=%s", TOKEN)
        window.ctx.add_error(RuntimeError(f"authentication failed for {TOKEN}"))
        self.check(self.pump_until(lambda: "token in a message" in window.log_visible_text(), 3.0),
                   "secrets: log lines reached the panel")
        panel = window.log_visible_text()
        self.check(TOKEN not in panel, "secrets: token absent from the log panel")
        self.check("***" in panel, "secrets: panel shows the masked token")
        for handler in logging.getLogger("wflash").handlers:
            handler.flush()
        file_text = self.log_file.read_text(encoding="utf-8")
        self.check(TOKEN not in file_text, "secrets: token absent from the log file")
        self.check("token in a message: ***" in file_text, "secrets: log file has the masked line")
        self.keyring.clear()
        window.ui.tabWidget_main.setCurrentWidget(window.ui.tab_setting)
        window.ui.lineEdit_token.setText(TOKEN)
        window.ui.lineEdit_token.editingFinished.emit()  # to the (fake) keyring, never to the settings
        dialog = self.open_dialog(window)
        dialog.load_refs()
        self.pump_until(lambda: not dialog.busy(), 5.0)
        dialog._note(logging.INFO, f"PRIVATE-TOKEN: {TOKEN}")
        self.check(TOKEN not in dialog.ui.plainTextEdit_gitlabLog.toPlainText(), "secrets: token absent from the GitLab log")
        dialog.reject()
        settings_file = self.workdir / f"window{self._window_count}" / "settings.json"
        self.check(settings_file.is_file() and TOKEN not in settings_file.read_text(encoding="utf-8"),
                   "secrets: token absent from settings.json")
        self.check(self.get_token(GITLAB_URL) == TOKEN, "secrets: token stored in the keyring")
        bundle = window.export_bundle(self.workdir / "bundle")
        with zipfile.ZipFile(bundle) as zf:
            contents = {name: zf.read(name).decode("utf-8", "replace") for name in zf.namelist()}
        leaked = [name for name, text in contents.items() if TOKEN in text]
        self.check(leaked == [], f"secrets: token absent from every bundle file (leaked in {leaked})")
        self.check("authentication failed for ***" in contents.get("errors.txt", ""), "secrets: bundle errors masked")
        self.close_window(window, "secrets")


SECTIONS = {
    "flash": ("GitLab tab parts by commit/manual + Advanced Debug, pipeline wait; full fetch->map->flash, cancel mid-download, resize + log filter", Stress.section_flash),
    "rollback": ("every failure branch; workspace paths restored, failed rollback shown", Stress.section_rollback),
    "gitlab": ("dialog: CI artifact, 401/403/404/connection, double-click, Stop, close mid-fetch",
               Stress.section_gitlab),
    "races": ("cancel at 0..400 ms, double Flash/Cancel, close mid-download / mid-fetch / App load / repo read, Manual mid-load", Stress.section_races),
    "theme": ("light/dark switched while flashing and with the dialog open", Stress.section_theme),
    "menu": ("every menu action, Tools one at a time and refused while flashing, close mid-request", Stress.section_menu),
    "fuzz": ("random user actions on the GitLab tab, Flash, Tools, profile/theme switches, then close", Stress.section_fuzz),
    "secrets": ("a realistic PAT through panel, log file and debug bundle", Stress.section_secrets),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="list the sections and exit")
    parser.add_argument("--section", action="append", choices=sorted(SECTIONS), help="run only these (repeatable)")
    parser.add_argument("--iterations", type=int, default=2, help="repetitions of the flash section")
    parser.add_argument("--keep", action="store_true", help="keep the temporary work folder")
    parser.add_argument("--seed", type=int, action="append", help="fuzz seeds (repeatable; default 1..12)")
    args = parser.parse_args(argv)
    if args.list:
        for name, (description, _) in SECTIONS.items():
            print(f"{name:<9} {description}")
        return 0

    app = QApplication.instance() or QApplication([sys.argv[0]])
    workdir = Path(tempfile.mkdtemp(prefix="wflash_stress_"))
    log_file = setup_logging(log_dir=workdir / "logs")
    stress = Stress(workdir, log_file, args.iterations)
    stress.seeds = args.seed or list(range(1, 13))

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
    QMessageBox.about = staticmethod(lambda parent, title, text: stress.dialogs.append((title, text)))
    # Keep the real keyring and the desktop (Finder, browser) out of the run.
    gitlab_dialog.get_token = stress.get_token
    main_window.get_token = stress.get_token
    main_window.set_token = stress.set_token
    QDesktopServices.openUrl = staticmethod(lambda url: stress.opened.append(url.toLocalFile()) or True)

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
    close_file_handler()
    del app
    stress.pump(0.0)
    qInstallMessageHandler(previous_handler)  # after teardown, so teardown warnings are seen

    passed = not stress.failures and not stress.qt_problems
    print(f"CHECKPOINTS={stress.checkpoints} FAILED={len(stress.failures)} "
          f"QT_THREADING_WARNINGS={len(stress.qt_problems)} OTHER_QT_WARNINGS={len(stress.qt_other)} "
          f"TIME={time.monotonic() - started:.1f}s")
    for failure in stress.failures:
        print(f"  - {failure.splitlines()[0]}")
    for message in sorted(set(stress.qt_other)):
        print(f"  other Qt warning (not a failure): {message}")
    print(f"STRESS_RESULT={'PASS' if passed else 'FAIL'}")
    if passed and not args.keep:
        shutil.rmtree(workdir, ignore_errors=True)
    else:
        print(f"work folder kept: {workdir}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
