import pytest
from PySide6.QtCore import Qt

from tests.gui_stubs import EXAMPLE_PROFILE, OLD_APP, OLD_CM7_0, HostWindow, make_artifact_tree
from wflash.core.errors import FlashError, MappingError, WinIDEAError
from wflash.core.fake_adapter import FakeWinIDEAAdapter
from wflash.core.flash_workflow import Step
from wflash.core.profile import load_profile
from wflash.gui.flash_mixin import FlashMixin, safe_list_instances
from wflash.gui.mapping_table import MappingTableMixin

pytestmark = pytest.mark.gui


class FlashHost(FlashMixin, MappingTableMixin, HostWindow):
    def __init__(self, tmp, adapter):
        super().__init__(tmp, adapter=adapter)
        self._init_mapping_table()
        self._init_flash()
        self.profile = load_profile(EXAMPLE_PROFILE)
        self.refresh_instances()


class RestoreFails(FakeWinIDEAAdapter):
    """Download fails, and writing the old App path back fails too: rollback_failed."""

    def set_program_path(self, name, path):
        if path == OLD_APP:
            raise WinIDEAError("restore App failed")
        super().set_program_path(name, path)


def make_host(qtbot, tmp_path, adapter):
    w = FlashHost(tmp_path, adapter)
    qtbot.addWidget(w)
    qtbot.waitUntil(lambda: w.ui.comboBox_instance.count() == 1, timeout=3000)
    w.on_artifact_ready(make_artifact_tree(tmp_path / "art"), "job #7")
    return w


def wait_idle(w, qtbot):
    qtbot.waitUntil(lambda: not w.flash_active() and w.ui.pushButton_flash.isEnabled(), timeout=10000)


def test_gui_instance_combo_holds_a_dict(qtbot, tmp_path):
    w = make_host(qtbot, tmp_path, FakeWinIDEAAdapter(download_seconds=0.1))
    data = w.ui.comboBox_instance.currentData()
    assert data == {"instance_id": "fake-1", "workspace": r"C:\fake\SAF85xx\SAF85xx.xjrf", "tcp_port": 5313}
    assert w.selected_instance()["instance_id"] == "fake-1"


def test_gui_no_instance_keeps_flash_disabled(qtbot, tmp_path):
    w = FlashHost(tmp_path, FakeWinIDEAAdapter(fail_on={"list_instances"}))
    qtbot.addWidget(w)
    qtbot.waitUntil(lambda: not w._workers.running_keys(), timeout=3000)
    w.on_artifact_ready(make_artifact_tree(tmp_path / "art"), "job #7")
    assert w.ui.comboBox_instance.count() == 0
    assert not w.ui.pushButton_flash.isEnabled()


def test_gui_list_instances_failure_returns_empty_list():
    class Broken(FakeWinIDEAAdapter):
        def list_instances(self):
            raise OSError("isystem.connect not loadable")

    assert safe_list_instances(Broken()) == []


def test_gui_flash_happy_path(qtbot, tmp_path):
    adapter = FakeWinIDEAAdapter(download_seconds=0.2)
    w = make_host(qtbot, tmp_path, adapter)
    assert w.ui.pushButton_flash.isEnabled()
    qtbot.mouseClick(w.ui.pushButton_flash, Qt.MouseButton.LeftButton)
    assert w.flash_active()
    assert not w.ui.pushButton_flash.isEnabled() and w.ui.pushButton_cancelFlash.isEnabled()
    assert not w.ui.tableWidget_mapping.isEnabled() and not w.ui.pushButton_exportBundle.isEnabled()
    qtbot.waitUntil(lambda: w.ui.label_step.text() == Step.DONE.value, timeout=5000)
    wait_idle(w, qtbot)
    assert adapter.programs["App"] == str((tmp_path / "art" / "out" / "App.s3").resolve())
    assert adapter.target_state == "halted"
    assert w.ui.progressBar_flash.value() == 100
    assert w.errors_shown == []
    assert not w.ui.label_rollbackWarning.isVisibleTo(w)


def test_gui_flash_run_after_reset(qtbot, tmp_path):
    adapter = FakeWinIDEAAdapter(download_seconds=0.05)
    w = make_host(qtbot, tmp_path, adapter)
    w.ui.checkBox_run.setChecked(True)
    w.start_flash()
    qtbot.waitUntil(lambda: w.ui.label_step.text() == Step.DONE.value, timeout=5000)
    assert adapter.target_state == "running"


def test_gui_flash_download_failure_rolls_back_and_shows_error(qtbot, tmp_path):
    adapter = FakeWinIDEAAdapter(download_seconds=0.1, fail_on={"download"})
    w = make_host(qtbot, tmp_path, adapter)
    w.start_flash()
    qtbot.waitUntil(lambda: w.ui.label_step.text() == "Failed", timeout=5000)
    wait_idle(w, qtbot)
    assert isinstance(w.errors_shown[0], FlashError)
    assert adapter.programs["App"] == OLD_APP
    assert adapter.applications["CM7_0"] == OLD_CM7_0
    assert not w.ui.label_rollbackWarning.isVisibleTo(w)
    assert any("Fake failure" in e for e in w.ctx.errors)
    assert "after_rollback" in w.ctx.snapshots


def test_gui_missing_workspace_entry_is_a_mapping_error(qtbot, tmp_path):
    adapter = FakeWinIDEAAdapter(download_seconds=0.1, programs={"Other": r"C:\x.s3"})
    w = make_host(qtbot, tmp_path, adapter)
    w.start_flash()
    qtbot.waitUntil(lambda: w.ui.label_step.text() == "Failed", timeout=5000)
    assert isinstance(w.errors_shown[0], MappingError)
    assert "Other" in w.errors_shown[0].hint


def test_gui_flash_rollback_failure_is_shown_to_the_user(qtbot, tmp_path):
    adapter = RestoreFails(download_seconds=0.1, fail_on={"download"})
    w = make_host(qtbot, tmp_path, adapter)
    w.start_flash()
    qtbot.waitUntil(lambda: w.ui.label_step.text() == "Failed", timeout=5000)
    wait_idle(w, qtbot)
    assert w.ui.label_rollbackWarning.isVisibleTo(w)
    exc = w.errors_shown[0]
    assert getattr(exc, "rollback_failed", False) is True
    assert exc.hint.startswith("ROLLBACK FAILED")
    # The next flash hides the warning again until a new failure.
    adapter.fail_on = set()
    w.start_flash()
    assert not w.ui.label_rollbackWarning.isVisibleTo(w)
    qtbot.waitUntil(lambda: w.ui.label_step.text() == Step.DONE.value, timeout=5000)


def test_gui_thread_cancel_flash_mid_download_rolls_back(qtbot, tmp_path):
    adapter = FakeWinIDEAAdapter(download_seconds=5)
    w = make_host(qtbot, tmp_path, adapter)
    w.start_flash()
    qtbot.waitUntil(lambda: w.ui.label_step.text() == Step.DOWNLOAD.value, timeout=3000)
    qtbot.mouseClick(w.ui.pushButton_cancelFlash, Qt.MouseButton.LeftButton)
    w.cancel_flash()  # a second cancel is harmless
    qtbot.waitUntil(lambda: w.ui.label_step.text() == "Cancelled", timeout=3000)
    wait_idle(w, qtbot)
    assert adapter.programs["App"] == OLD_APP
    assert adapter.connected_to is None
    assert w.errors_shown == []


def test_gui_thread_double_flash_starts_one_worker(qtbot, tmp_path):
    adapter = FakeWinIDEAAdapter(download_seconds=0.3)
    w = make_host(qtbot, tmp_path, adapter)
    w.start_flash()
    w.start_flash()
    assert [k for k in w._workers.running_keys() if k.startswith("flash")] == [w._flash_key]
    qtbot.waitUntil(lambda: w.ui.label_step.text() == Step.DONE.value, timeout=5000)
    assert adapter.calls.count("download") == 1


def test_gui_incomplete_mapping_blocks_flash(qtbot, tmp_path):
    w = make_host(qtbot, tmp_path, FakeWinIDEAAdapter(download_seconds=0.1))
    combo = w.mapping_combo(0)
    combo.setCurrentIndex(0)
    assert not w.ui.pushButton_flash.isEnabled()
    w.start_flash()
    assert not w.flash_active()
