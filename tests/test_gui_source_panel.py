"""Developer panel: source repo, build loading by commit, Advanced Debug, CAL and the planned flash."""
import subprocess
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from tests.gui_stubs import GITLAB_URL, PROJECT, FakeGitLabSession, SessionClientFactory, patch_keyring
from wflash.core.fake_adapter import FakeWinIDEAAdapter
from wflash.core.firmware_source import FirmwareSource
from wflash.core.flash_plan import ProgramRow, SymbolRow
from wflash.core.flash_workflow import Step
from wflash.core.settings import AppSettings
from wflash.core.source_repo import read_state
from wflash.gui.main_window import MainWindow

pytestmark = pytest.mark.gui

ROOT = Path(__file__).resolve().parents[1]
CAL = "20260623_142557_2018688_CAL_T008_v0_0.sre"
BM_BIN, FBL_BIN = "FBL_M7_LIP_RfeClock_Image.bin", "Radar_SUZ05_Gen7_FBL.bin"


def git(path, *args):
    subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "src"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "t@example.com")
    git(path, "config", "user.name", "T")
    (path / "a.c").write_text("1")
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", "first")
    return path


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


@pytest.fixture
def env(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: None)
    patch_keyring(monkeypatch)
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    text = (ROOT / "profiles" / "suz05.yaml").read_text(encoding="utf-8")
    project = text.split("project: ", 1)[1].split("\n", 1)[0]
    (profiles / "suz05.yaml").write_text(text.replace(project, PROJECT, 1), encoding="utf-8")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / CAL).write_text("S0")
    adapter = FakeWinIDEAAdapter(download_seconds=0.05, rows=suz05_rows(), workspace=str(workspace / "SUZ_7G5_M7.xjrf"))
    session = FakeGitLabSession()
    window = MainWindow(
        AppSettings(gitlab_url=GITLAB_URL, profiles_dir=str(profiles), cache_dir=str(tmp_path / "cache")),
        adapter,
        client_factory=SessionClientFactory(session),
        settings_path=tmp_path / "settings.json",
    )
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: window.ui.comboBox_instance.count() == 1, timeout=3000)
    window.ui.comboBox_build.setCurrentText("stingray_3p5mb_no_HTSM")
    return window, adapter, session, workspace


def use_repo(qtbot, window, repo):
    window.ui.lineEdit_sourceRepo.setText(str(repo))
    window._on_repo_edited()
    qtbot.waitUntil(lambda: window.ui.label_repoBranch.text() == "Branch: main", timeout=5000)


def load_build(qtbot, window):
    window.load_build_firmware()
    qtbot.waitUntil(lambda: window.ui.label_loadStatus.text().startswith("FFI:"), timeout=8000)


def deliver(window, role, tmp_path, job, files):
    root = tmp_path / f"art_{role}_{job}"
    for rel, data in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    window._loading_source = f"debug:{role}"
    source = FirmwareSource("ci", "p", f"CI artifact · job #1 {job}", "p · develop · pipeline #1", "Cached · 2 files", "41c7a0de", job)
    window.on_firmware_ready(root, source)


def test_gui_profile_with_builds_shows_the_developer_panel(env):
    window, *_ = env
    assert window.ui.frame_developer.isVisibleTo(window)
    assert not window.ui.pushButton_loadFromGitlab.isVisibleTo(window)
    assert window.ui.comboBox_build.count() == 4


def test_gui_developer_parts_are_split_between_the_flash_and_setting_tabs(env):
    window, *_ = env
    ui = window.ui
    assert ui.frame_developer.isVisibleTo(ui.tab_flash)
    assert not ui.frame_gitlabSource.isVisibleTo(ui.tab_flash)
    assert ui.frame_sourceRepoSetting.isVisibleTo(ui.tab_setting)
    assert ui.tab_setting.isAncestorOf(ui.lineEdit_sourceRepo) and ui.tab_setting.isAncestorOf(ui.pushButton_checkout)


def test_gui_reload_button_reads_the_repo_again(env, qtbot, repo):
    window, *_ = env
    use_repo(qtbot, window, repo)
    (repo / "b.c").write_text("2")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "second")
    commit = read_state(repo).commit[:8]
    window.ui.pushButton_reloadRepo.click()
    qtbot.waitUntil(lambda: window.ui.label_repoCommit.text() == f"Commit: {commit}", timeout=5000)
    assert window.ui.label_repoSummary.text() == f"Branch: main · Commit: {commit} · No local changes."


def test_gui_coming_back_to_the_window_reads_the_repo_again(env, qtbot, repo, monkeypatch):
    window, *_ = env
    use_repo(qtbot, window, repo)
    git(repo, "checkout", "-q", "-b", "elsewhere")
    monkeypatch.setattr(window, "isActiveWindow", lambda: True)
    QApplication.sendEvent(window, QEvent(QEvent.Type.ActivationChange))
    qtbot.waitUntil(lambda: window.ui.label_repoBranch.text() == "Branch: elsewhere", timeout=5000)
    assert "Branch: elsewhere" in window.ui.label_repoSummary.text()


def test_gui_repo_shows_branch_commit_and_the_button_names_the_commit(env, qtbot, repo):
    window, *_ = env
    use_repo(qtbot, window, repo)
    commit = read_state(repo).commit[:8]
    assert window.ui.pushButton_loadBuild.text() == f"Load firmware for {commit}"
    assert "No local changes" in window.ui.label_repoChanges.text()


def test_gui_local_changes_warn_but_do_not_block(env, qtbot, repo):
    window, *_ = env
    (repo / "a.c").write_text("mine")
    use_repo(qtbot, window, repo)
    assert "local changes" in window.ui.label_repoChanges.text()
    load_build(qtbot, window)


def test_gui_load_build_fills_ffi_cal_and_elf_and_enables_flash(env, qtbot, repo):
    window, adapter, _session, _ws = env
    use_repo(qtbot, window, repo)
    load_build(qtbot, window)
    assert [r.role for r in window.mapping_rows()] == ["ffi", "cal", "elf"]
    assert window.mapping_complete()
    assert "main" in str(window.mapping_rows()[0].selected)
    qtbot.waitUntil(window.ui.pushButton_flash.isEnabled, timeout=3000)
    window.start_flash()
    qtbot.waitUntil(lambda: window.current_step() == Step.DONE.value, timeout=8000)
    rows = {r.name: r for r in adapter.program_rows}
    assert rows[BM_BIN].enabled is False and rows[FBL_BIN].enabled is False  # Advanced Debug is off
    assert rows["RAD_SUZ05_FFI.s3"].path.endswith("RAD_SUZ05_FFI.s3") and "main" in rows["RAD_SUZ05_FFI.s3"].path


def test_gui_commit_without_a_pipeline_shows_the_reason(env, qtbot, repo):
    window, _adapter, session, _ws = env
    session.commit_has_pipeline = False
    use_repo(qtbot, window, repo)
    window.load_build_firmware()
    qtbot.waitUntil(lambda: "no pipeline" in window.ui.label_loadStatus.text().lower(), timeout=8000)
    assert not window.mapping_complete()


def test_gui_advanced_debug_adds_bm_and_fbl_rows(env, qtbot, repo):
    window, *_ = env
    use_repo(qtbot, window, repo)
    load_build(qtbot, window)
    window.ui.checkBox_advancedDebug.setChecked(True)
    assert [r.role for r in window.mapping_rows()] == ["ffi", "cal", "bm", "fbl", "elf", "bm", "fbl"]
    assert not window.mapping_complete()
    window.ui.checkBox_advancedDebug.setChecked(False)
    assert [r.role for r in window.mapping_rows()] == ["ffi", "cal", "elf"]


def test_gui_wrong_bm_job_blocks_flash_and_the_right_one_frees_it(env, qtbot, repo, tmp_path):
    window, *_ = env
    use_repo(qtbot, window, repo)
    load_build(qtbot, window)
    window.ui.checkBox_advancedDebug.setChecked(True)
    bm_files = {f"out/bin/{BM_BIN}": b"B", "out/bin/Radar_SUZ05_Gen7_BM.elf": b"E"}
    deliver(window, "fbl", tmp_path, "build", {f"out/bin/{FBL_BIN}": b"F", "out/bin/Radar_SUZ05_Gen7_FBL.elf": b"E"})
    deliver(window, "bm", tmp_path, "build_STRX_3P5MB", bm_files)
    assert window.mapping_complete()
    assert "build_STINGRAY_3P5MB" in window.flash_block_reason()
    assert window.ui.label_flashBlocked.isVisibleTo(window)
    assert not window.ui.pushButton_flash.isEnabled()
    deliver(window, "bm", tmp_path, "build_STINGRAY_3P5MB", bm_files)
    assert window.flash_block_reason() == ""
    qtbot.waitUntil(window.ui.pushButton_flash.isEnabled, timeout=3000)


def test_gui_missing_cal_blocks_flash(env, qtbot, repo):
    window, _adapter, _session, workspace = env
    (workspace / CAL).unlink()
    window.ui.comboBox_instance.currentIndexChanged.emit(0)
    use_repo(qtbot, window, repo)
    load_build(qtbot, window)
    assert "CAL" in window.flash_block_reason()
    assert not window.ui.pushButton_flash.isEnabled()


def test_gui_checkout_button_switches_branch_and_refreshes_the_panel(env, qtbot, repo):
    window, *_ = env
    git(repo, "branch", "feature")
    use_repo(qtbot, window, repo)
    load_build(qtbot, window)
    window.ui.pushButton_checkout.click()
    dialog = window._checkout_dialog
    qtbot.waitUntil(lambda: dialog.isVisible() and not dialog.busy() and dialog.ui.comboBox_branch.count() == 2, timeout=5000)
    dialog.ui.comboBox_branch.setCurrentIndex(dialog.ui.comboBox_branch.findText("feature"))
    qtbot.waitUntil(lambda: not dialog.busy() and dialog.ui.tableWidget_commits.rowCount() == 1, timeout=5000)
    dialog.ui.tableWidget_commits.selectRow(0)
    dialog.ui.pushButton_checkout.click()
    qtbot.waitUntil(lambda: window.ui.label_repoBranch.text() == "Branch: feature", timeout=5000)
    assert not dialog.isVisible()
