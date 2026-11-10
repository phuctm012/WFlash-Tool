"""GitLab tab: App, Boot Manager and Flash Bootloader, from the checked-out commit or manual."""
import csv
import os
import subprocess
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from tests.gui_stubs import (
    BM_BIN,
    FBL_BIN,
    GITLAB_URL,
    PROJECT,
    TOKEN,
    FakeGitLabSession,
    SessionClientFactory,
    patch_keyring,
)
from wflash.core.fake_adapter import FakeWinIDEAAdapter
from wflash.core.firmware_source import FirmwareSource
from wflash.core.flash_plan import ProgramRow, SymbolRow
from wflash.core.flash_workflow import Step
from wflash.core.settings import AppSettings
from wflash.core.source_repo import read_state
from wflash.gui import part_controller
from wflash.gui.main_window import MainWindow

pytestmark = pytest.mark.gui

ROOT = Path(__file__).resolve().parents[1]
CAL = "20260623_142557_2018688_CAL_T008_v0_0.sre"
URL = f"{GITLAB_URL}/group"  # with a group: the short BM and FBL project names are joined to it


def git(path, *args):
    subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)


def make_repo(path: Path) -> Path:
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "t@example.com")
    git(path, "config", "user.name", "T")
    (path / "a.c").write_text("1")
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", "first")
    return path


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path / "src")


def suz05_rows():
    programs = [
        ProgramRow(0, "Radar_SUZ05_Gen7.s3", "Radar_SUZ05_Gen7.s3", False, 0x1AA000),
        ProgramRow(1, "RAD_SUZ05_FFI.s3", "old/RAD_SUZ05_FFI.s3", True, 0),
        ProgramRow(2, CAL, CAL, True, 0),
        ProgramRow(3, BM_BIN, f"old/{BM_BIN}", True, 0),
        ProgramRow(4, FBL_BIN, f"old/{FBL_BIN}", True, 0xF1000),
    ]
    symbols = [
        SymbolRow(0, 0, "App_M7/Radar_SUZ05_Gen7.elf", "old/a.elf", True),
        SymbolRow(0, 1, "App_M7/Radar_SUZ05_Gen7_BM.elf", "old/b.elf", True),
        SymbolRow(0, 2, "App_M7/Radar_SUZ05_Gen7_FBL.elf", "old/c.elf", True),
    ]
    return programs, symbols


class Env:
    def __init__(self, window, adapter, session, workspace):
        self.window, self.adapter, self.session, self.workspace = window, adapter, session, workspace


@pytest.fixture
def env(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: None)
    patch_keyring(monkeypatch, {URL: TOKEN})
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    text = (ROOT / "profiles" / "suz05.yaml").read_text(encoding="utf-8")
    text = text.replace("project: SUZ05_APP_Application_Software-Impl", f"project: {PROJECT}", 1)
    (profiles / "suz05.yaml").write_text(text, encoding="utf-8")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / CAL).write_text("S0")
    adapter = FakeWinIDEAAdapter(download_seconds=0.05, rows=suz05_rows(), workspace=str(workspace / "SUZ_7G5_M7.xjrf"))
    session = FakeGitLabSession()
    settings = AppSettings(
        profiles_dir=str(profiles), cache_dir=str(tmp_path / "cache"), last_profile="suz05.yaml",
        gitlab_urls={"suz05.yaml": URL}, last_build={"suz05.yaml": "stingray_3p5mb_no_HTSM"},
    )
    window = MainWindow(settings, adapter, client_factory=SessionClientFactory(session),
                        settings_path=tmp_path / "settings.json")
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: window.ui.comboBox_instance.count() == 1, timeout=3000)
    return Env(window, adapter, session, workspace)


def set_repo(qtbot, window, name: str, repo: Path) -> None:
    part = window.parts[name]
    part.w_repo.setText(str(repo))
    part._on_repo_edited()
    qtbot.waitUntil(lambda: part.repo_state is not None, timeout=5000)


def wait_loaded(qtbot, part, roles, timeout=8000):
    qtbot.waitUntil(lambda: set(roles) <= set(part.loaded) and not part.loading(), timeout=timeout)


def test_gui_gitlab_tab_shows_three_parts_for_a_profile_with_builds(env):
    w = env.window
    ui = w.ui
    assert ui.tabWidget_main.isTabVisible(ui.tabWidget_main.indexOf(ui.tab_gitlab))
    assert ui.lineEdit_appProject.text() == PROJECT
    assert ui.lineEdit_bmProject.text() == "SUZ05_BM_Boot_Manager-Impl"
    assert w.parts["bm"].full_project() == "group/SUZ05_BM_Boot_Manager-Impl"
    assert ui.label_bmBuild.text() == "build_STINGRAY_3P5MB" and ui.label_fblBuild.text() == "build"
    assert ui.radioButton_bmManual.isChecked() and not ui.radioButton_bmCommit.isEnabled()  # no repository
    assert ui.radioButton_appCommit.isChecked()
    assert ui.frame_firmwareSummary.isVisibleTo(w) and not ui.frame_gitlabSource.isVisibleTo(w)


def test_gui_app_from_the_checked_out_commit_loads_ffi_and_elf_and_flashes(env, qtbot, repo):
    w = env.window
    set_repo(qtbot, w, "app", repo)
    app = w.parts["app"]
    wait_loaded(qtbot, app, ("ffi", "elf"))
    commit = read_state(repo).commit[:8]
    assert app.status_text().splitlines()[0] == f"FFI: create_ffi_stingray_3p5mb_no_HTSM · main · {commit} · Downloaded"
    assert [r.role for r in w.mapping_rows()] == ["ffi", "cal", "elf"] and w.mapping_complete()
    assert "From commit" in w.ui.label_summaryApp.text() and commit in w.ui.label_summaryApp.text()
    assert "background" not in w.ui.label_summaryApp.text()  # no white box on the card (user report)
    qtbot.waitUntil(w.ui.pushButton_flash.isEnabled, timeout=3000)
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DONE.value, timeout=8000)
    rows = {r.name: r for r in env.adapter.program_rows}
    assert rows[BM_BIN].enabled is False and "main" in rows["RAD_SUZ05_FFI.s3"].path
    with open(os.environ["WFLASH_HISTORY_FILE"], encoding="utf-8-sig", newline="") as fh:
        last = list(csv.DictReader(fh))[-1]
    assert last["profile"] == "SUZ05" and commit in last["app"] and last["app_mode"] == "From commit"
    assert last["result"] == "Done" and last["tries"] == "1"


def test_gui_the_same_commit_is_not_downloaded_twice(env, qtbot, repo):
    w = env.window
    set_repo(qtbot, w, "app", repo)
    wait_loaded(qtbot, w.parts["app"], ("ffi", "elf"))
    calls = env.session.count("/artifacts")
    w.parts["app"].reload()
    qtbot.waitUntil(lambda: not w.parts["app"].busy(), timeout=5000)
    assert env.session.count("/artifacts") == calls


def test_gui_a_new_commit_found_when_coming_back_to_the_window_loads_again(env, qtbot, repo, monkeypatch):
    w = env.window
    set_repo(qtbot, w, "app", repo)
    app = w.parts["app"]
    wait_loaded(qtbot, app, ("ffi", "elf"))
    (repo / "b.c").write_text("2")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "second")
    commit = read_state(repo).commit[:8]
    monkeypatch.setattr(w, "isActiveWindow", lambda: True)
    QApplication.sendEvent(w, QEvent(QEvent.Type.ActivationChange))
    qtbot.waitUntil(lambda: app.loaded["ffi"][1].commit.startswith(commit) and not app.loading(), timeout=8000)
    assert w.ui.label_appCommit.text().startswith(commit)


def test_gui_manual_keeps_its_choice_when_the_commit_moves(env, qtbot, repo, tmp_path):
    w = env.window
    set_repo(qtbot, w, "app", repo)
    app = w.parts["app"]
    w.ui.radioButton_appManual.setChecked(True)  # the commit load still running is cancelled
    qtbot.waitUntil(w.ui.pushButton_appChooseJob.isEnabled, timeout=5000)
    path = tmp_path / "manual"
    (path / "out" / "FFI").mkdir(parents=True)
    (path / "out" / "FFI" / "RAD_SUZ05_FFI.s3").write_bytes(b"S0")
    (path / ".complete").write_text("x")
    w._loading_source = "part:app:ffi"
    source = FirmwareSource("ci", PROJECT, "CI artifact · job #9 create_ffi_x", f"{PROJECT} · dev · pipeline #1",
                            "Cached · 1 file", "1234567890", "create_ffi_x")
    w.on_firmware_ready(path, source)
    assert app.loaded["ffi"][0] == path and "Manual" in w.ui.label_summaryApp.text()
    app.refresh_repo()
    qtbot.waitUntil(lambda: not app.busy(), timeout=5000)
    assert app.loaded["ffi"][0] == path  # a manual choice is not replaced by the commit
    assert "suz05.yaml#app" in w.settings.part_manual


def test_gui_boot_manager_with_a_repository_follows_its_commit_and_the_app_build(env, qtbot, repo, tmp_path):
    w = env.window
    w.ui.checkBox_advancedDebug.setChecked(True)
    bm_repo = make_repo(tmp_path / "bm")
    set_repo(qtbot, w, "bm", bm_repo)
    bm = w.parts["bm"]
    assert w.ui.radioButton_bmCommit.isEnabled()
    w.ui.radioButton_bmCommit.setChecked(True)
    wait_loaded(qtbot, bm, ("bm",))
    assert bm.status_text().startswith("BM: build_STINGRAY_3P5MB · development · ")
    assert "Boot Manager" in w.ui.label_summaryBm.text()
    roles = [r.role for r in w.mapping_rows()]
    assert roles.count("bm") == 2


def test_gui_advanced_debug_off_hides_boot_manager_and_flash_bootloader(env, qtbot):
    w = env.window
    w.ui.checkBox_advancedDebug.setChecked(True)
    assert w.ui.widget_debugParts.isVisibleTo(w.ui.tab_gitlab)
    assert [r.role for r in w.mapping_rows()] == ["ffi", "cal", "bm", "fbl", "elf", "bm", "fbl"]
    w.ui.checkBox_advancedDebug.setChecked(False)
    assert not w.ui.widget_debugParts.isVisibleTo(w.ui.tab_gitlab)
    assert [r.role for r in w.mapping_rows()] == ["ffi", "cal", "elf"]
    assert w.settings.advanced_debug is False


def test_gui_a_running_pipeline_is_waited_for_and_loaded_when_it_finishes(env, qtbot, repo, monkeypatch):
    monkeypatch.setattr(part_controller, "POLL_S", 0.05)
    notified = []
    monkeypatch.setattr(env.window, "notify", notified.append)
    env.session.job_status["create_ffi_stingray_3p5mb_no_HTSM"] = "running"
    w = env.window
    set_repo(qtbot, w, "app", repo)
    app = w.parts["app"]
    qtbot.waitUntil(lambda: app.waiting(), timeout=5000)
    assert "Waiting for pipeline: create_ffi_stingray_3p5mb_no_HTSM is running" in app.status_text()
    env.session.job_status.clear()
    wait_loaded(qtbot, app, ("ffi", "elf"))
    assert not app.waiting()
    assert notified and notified[-1].startswith("Firmware ready: App")


def test_gui_a_job_nobody_started_is_reported_once_and_not_retried_until_reload(env, qtbot, repo, monkeypatch):
    env.session.job_status["create_ffi_stingray_3p5mb_no_HTSM"] = "manual"
    w = env.window
    set_repo(qtbot, w, "app", repo)
    app = w.parts["app"]
    qtbot.waitUntil(lambda: "is manual" in app.status_text() and not app.busy(), timeout=5000)
    assert not app.waiting()
    lookups = env.session.count("/pipelines")
    monkeypatch.setattr(w, "isActiveWindow", lambda: True)
    QApplication.sendEvent(w, QEvent(QEvent.Type.ActivationChange))
    qtbot.waitUntil(lambda: not app.busy(), timeout=5000)
    assert env.session.count("/pipelines") == lookups  # no new lookup for the same commit
    env.session.job_status.clear()
    app.reload()
    wait_loaded(qtbot, app, ("ffi", "elf"))


def test_gui_closing_while_waiting_and_loading_stops_everything(env, qtbot, repo, monkeypatch):
    monkeypatch.setattr(part_controller, "POLL_S", 0.05)
    env.session.job_status["create_ffi_stingray_3p5mb_no_HTSM"] = "running"
    w = env.window
    set_repo(qtbot, w, "app", repo)
    qtbot.waitUntil(lambda: w.parts["app"].waiting(), timeout=5000)
    w.close()
    assert not w.parts["app"].waiting()
    assert not w._workers.has_running("part-")


def test_gui_no_load_starts_while_flashing_it_waits_for_the_end(env, qtbot, repo):
    w = env.window
    set_repo(qtbot, w, "app", repo)
    app = w.parts["app"]
    wait_loaded(qtbot, app, ("ffi", "elf"))
    env.adapter.download_seconds = 0.6
    w.start_flash()
    assert w.flash_active()
    (repo / "b.c").write_text("2")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "second")
    app.refresh_repo()
    qtbot.waitUntil(lambda: not w._workers.is_running(app._repo_key), timeout=5000)
    assert not app.loading()  # deferred
    qtbot.waitUntil(lambda: not w.flash_active(), timeout=8000)
    commit = read_state(repo).commit
    qtbot.waitUntil(lambda: app.loaded["ffi"][1].commit == commit and not app.loading(), timeout=8000)
    qtbot.waitUntil(lambda: w.current_step() == Step.DONE.value, timeout=3000)  # the flash's result comes back


def test_gui_missing_cal_blocks_flash(env, qtbot, repo):
    w = env.window
    (env.workspace / CAL).unlink()
    w.ui.comboBox_instance.currentIndexChanged.emit(0)
    set_repo(qtbot, w, "app", repo)
    wait_loaded(qtbot, w.parts["app"], ("ffi", "elf"))
    assert "CAL" in w.flash_block_reason()
    assert not w.ui.pushButton_flash.isEnabled()


def test_gui_checkout_of_a_part_switches_its_branch(env, qtbot, repo):
    w = env.window
    git(repo, "branch", "feature")
    set_repo(qtbot, w, "app", repo)
    wait_loaded(qtbot, w.parts["app"], ("ffi", "elf"))
    w.ui.pushButton_appCheckout.click()
    dialog = w._checkout_dialog
    assert dialog.windowTitle().endswith("Application")
    qtbot.waitUntil(lambda: dialog.isVisible() and not dialog.busy() and dialog.ui.comboBox_branch.count() == 2, timeout=5000)
    dialog.ui.comboBox_branch.setCurrentIndex(dialog.ui.comboBox_branch.findText("feature"))
    qtbot.waitUntil(lambda: not dialog.busy() and dialog.ui.tableWidget_commits.rowCount() == 1, timeout=5000)
    dialog.ui.tableWidget_commits.selectRow(0)
    dialog.ui.pushButton_checkout.click()
    qtbot.waitUntil(lambda: w.ui.label_appBranch.text() == "feature", timeout=5000)
    assert not dialog.isVisible()


def test_gui_settings_of_each_part_survive_a_restart(env, qtbot, repo, tmp_path):
    w = env.window
    set_repo(qtbot, w, "app", repo)
    wait_loaded(qtbot, w.parts["app"], ("ffi", "elf"))
    w.ui.checkBox_advancedDebug.setChecked(True)
    w.ui.radioButton_fblManual.setChecked(True)
    w.ui.tabWidget_main.setCurrentIndex(1)
    w.close()
    settings = AppSettings.load(tmp_path / "settings.json")
    settings.profiles_dir = w.settings.profiles_dir  # never saved: the test points at its own profiles again
    assert settings.part_repos["suz05.yaml#app"] == str(repo)
    assert settings.advanced_debug is True and settings.last_tab == 1 and settings.window_geometry
    again = MainWindow(settings, FakeWinIDEAAdapter(download_seconds=0.05, rows=suz05_rows(),
                                                    workspace=str(env.workspace / "SUZ_7G5_M7.xjrf")),
                       client_factory=SessionClientFactory(FakeGitLabSession()), settings_path=tmp_path / "s2.json")
    qtbot.addWidget(again)
    assert again.ui.tabWidget_main.currentIndex() == 1
    assert again.ui.lineEdit_appRepo.text() == str(repo) and again.ui.checkBox_advancedDebug.isChecked()
    wait_loaded(qtbot, again.parts["app"], ("ffi", "elf"))  # from the cache, by itself
    assert "Cached" in again.parts["app"].status_text()


def test_gui_switching_mode_never_keeps_the_other_modes_firmware(env, qtbot, repo, tmp_path):
    """Manual job chosen, then back to From commit on the same commit: the commit's firmware
    comes back (from the cache), not the manual job labelled 'From commit'; and the other way."""
    w = env.window
    set_repo(qtbot, w, "app", repo)
    app = w.parts["app"]
    wait_loaded(qtbot, app, ("ffi", "elf"))
    commit = read_state(repo).commit
    commit_ffi = app.loaded["ffi"][0]
    w.ui.radioButton_appManual.setChecked(True)
    assert app.loaded == {} and "Press Choose Job" in app.status_text()
    assert not w.mapping_complete()  # the commit's firmware is not flashed as "Manual"
    manual = tmp_path / "manual"
    (manual / "out" / "FFI").mkdir(parents=True)
    (manual / "out" / "FFI" / "RAD_SUZ05_FFI.s3").write_bytes(b"S0")
    (manual / ".complete").write_text("x")
    w._loading_source = "part:app:ffi"
    w.on_firmware_ready(manual, FirmwareSource("ci", PROJECT, "CI artifact · job #9 create_ffi_x",
                                               f"{PROJECT} · dev · pipeline #1", "Cached · 1 file", "1234567890",
                                               "create_ffi_x"))
    calls = env.session.count("/artifacts")
    w.ui.radioButton_appCommit.setChecked(True)
    wait_loaded(qtbot, app, ("ffi", "elf"))
    assert app.loaded["ffi"][0] == commit_ffi and app.loaded["ffi"][1].commit == commit
    assert env.session.count("/artifacts") == calls  # from the cache
    assert "From commit" in w.ui.label_summaryApp.text() and commit[:8] in w.ui.label_summaryApp.text()
    w.ui.radioButton_appManual.setChecked(True)
    assert app.loaded["ffi"][0] == manual and "elf" not in app.loaded  # the remembered manual job
    assert "1234567890"[:8] in w.ui.label_summaryApp.text()


def test_gui_firmware_of_an_older_commit_blocks_flash_until_the_new_one_loads(env, qtbot, repo):
    """From commit never flashes another commit's firmware (CLAUDE.md): the repo moved on and the
    new commit's job cannot be loaded, so the old firmware stays visible but Flash is blocked."""
    w = env.window
    set_repo(qtbot, w, "app", repo)
    app = w.parts["app"]
    wait_loaded(qtbot, app, ("ffi", "elf"))
    qtbot.waitUntil(w.ui.pushButton_flash.isEnabled, timeout=3000)
    old = read_state(repo).commit[:8]
    env.session.job_status["create_ffi_stingray_3p5mb_no_HTSM"] = "manual"
    (repo / "b.c").write_text("2")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "second")
    new = read_state(repo).commit[:8]
    app.reload()
    qtbot.waitUntil(lambda: "is manual" in app.status_text() and not app.busy(), timeout=5000)
    reason = w.flash_block_reason()
    assert f"commit {old}" in reason and f"at {new}" in reason
    assert not w.ui.pushButton_flash.isEnabled() and w.ui.label_flashBlocked.isVisibleTo(w)
    env.session.job_status.clear()
    app.reload()
    qtbot.waitUntil(lambda: app.loaded["ffi"][1].commit.startswith(new) and not app.loading(), timeout=8000)
    assert w.flash_block_reason() == ""
    qtbot.waitUntil(w.ui.pushButton_flash.isEnabled, timeout=3000)


def test_gui_manual_firmware_is_not_blocked_by_the_repository_commit(env, qtbot, repo):
    w = env.window
    set_repo(qtbot, w, "app", repo)
    wait_loaded(qtbot, w.parts["app"], ("ffi", "elf"))
    w.ui.radioButton_appManual.setChecked(True)
    (repo / "b.c").write_text("2")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "second")
    w.parts["app"].refresh_repo()
    qtbot.waitUntil(lambda: not w.parts["app"].busy(), timeout=5000)
    assert w.parts["app"].stale_reason() == ""


def test_gui_new_commit_loads_ffi_and_elf_together_without_a_mismatch_warning(env, qtbot, repo, caplog):
    """A load hands FFI and ELF over one at a time: the check must wait for both (user report:
    a warning named the new FFI commit and the old ELF commit while the ELF was already loaded)."""
    w = env.window
    set_repo(qtbot, w, "app", repo)
    app = w.parts["app"]
    wait_loaded(qtbot, app, ("ffi", "elf"))
    (repo / "b.c").write_text("2")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "second")
    new = read_state(repo).commit[:8]
    caplog.clear()
    app.reload()
    qtbot.waitUntil(lambda: app.loaded["elf"][1].commit.startswith(new) and not app.loading(), timeout=8000)
    assert not any("different commits" in r.getMessage() for r in caplog.records)
    assert not w.ui.label_commitWarning.isVisibleTo(w)


def test_gui_build_whose_job_is_manual_says_why_and_shows_the_held_build(env, qtbot, repo, caplog):
    """User report: Build changed to one whose FFI job is manual. Flash stays off (right), but the
    red line, the summary card and the mapping hint must say what is held and why."""
    w = env.window
    set_repo(qtbot, w, "app", repo)
    app = w.parts["app"]
    wait_loaded(qtbot, app, ("ffi", "elf"))
    caplog.clear()
    w.ui.comboBox_appBuild.setCurrentText("stingray_3p5mb")
    qtbot.waitUntil(lambda: "is manual" in app.status_text() and not app.busy(), timeout=5000)
    reason = w.flash_block_reason()
    assert "create_ffi_stingray_3p5mb_no_HTSM" in reason and "is manual" in reason
    assert w.ui.label_flashBlocked.text() == reason and not w.ui.pushButton_flash.isEnabled()
    summary = w.ui.label_summaryApp.text()
    assert "stingray_3p5mb_no_HTSM" in summary and "Out of date" in summary
    assert "Flash enabled" not in w.ui.label_mappingHint.text()
    assert not [r for r in caplog.records if r.levelname == "ERROR"]  # a manual job is a state, not an error
