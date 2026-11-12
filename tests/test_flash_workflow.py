from pathlib import Path

import pytest

from wflash.core.cancel import CancelToken
from wflash.core.debug_bundle import DebugContext
from wflash.core.errors import CancelledError, FlashError, MappingError, WinIDEAError
from wflash.core.fake_adapter import FakeWinIDEAAdapter
from wflash.core.file_matcher import build_mapping
from wflash.core.flash_workflow import FlashRequest, FlashWorkflow, Step
from wflash.core.profile import load_profile

EXAMPLE = Path(__file__).resolve().parent / "fixtures" / "saf85xx_example.yaml"
OLD_APP = r"C:\fake\old\App.s3"


@pytest.fixture
def rows(tmp_path):
    for name in ("App.s3", "x_cm7_0.elf", "x_cm7_1.elf"):
        (tmp_path / name).write_bytes(b"x")
    return build_mapping(load_profile(EXAMPLE), tmp_path)


def run(adapter, rows, cancel=None, **req_kwargs):
    ctx = DebugContext()
    steps, progress = [], []
    wf = FlashWorkflow(adapter, ctx, on_step=steps.append, on_progress=lambda p, m: progress.append(p))
    error = None
    try:
        wf.run(FlashRequest("fake-1", rows, **req_kwargs), cancel or CancelToken())
    except Exception as exc:  # returned for assertions
        error = exc
    return ctx, steps, progress, error


def test_happy_path(rows, tmp_path):
    adapter = FakeWinIDEAAdapter(download_seconds=0.02)
    ctx, steps, progress, error = run(adapter, rows)
    assert error is None
    assert adapter.programs["App"] == str((tmp_path / "App.s3").resolve())
    assert adapter.applications["CM7_1"] == str((tmp_path / "x_cm7_1.elf").resolve())
    assert adapter.target_state == "halted"
    assert steps == [Step.CONNECT, Step.VALIDATE, Step.SET_PATHS, Step.DOWNLOAD, Step.PROGRAM, Step.RESET, Step.DONE]
    assert progress[-1] == 100
    assert adapter.connected_to is None
    assert set(ctx.snapshots) == {"before", "after_set"}
    assert ctx.adapter_info["adapter"] == "fake"
    assert ctx.mapping[0]["target"] == "App"


def test_run_after_reset(rows):
    adapter = FakeWinIDEAAdapter(download_seconds=0.02)
    assert run(adapter, rows, run=True)[3] is None
    assert adapter.target_state == "running"


def test_no_reset(rows):
    adapter = FakeWinIDEAAdapter(download_seconds=0.02)
    _, steps, _, error = run(adapter, rows, reset=False)
    assert error is None
    assert "reset" not in adapter.calls
    assert Step.RESET not in steps


def test_unmapped_row_rejected_before_connect(rows):
    rows[0].selected = None
    adapter = FakeWinIDEAAdapter()
    error = run(adapter, rows)[3]
    assert isinstance(error, MappingError) and "App" in str(error)
    assert "connect" not in adapter.calls


def test_missing_workspace_entry(rows):
    adapter = FakeWinIDEAAdapter(programs={"Other": "o.s3"}, download_seconds=0.02)
    error = run(adapter, rows)[3]
    assert isinstance(error, MappingError)
    assert "program 'App'" in str(error)
    assert "Other" in error.hint
    assert adapter.programs == {"Other": "o.s3"}
    assert adapter.connected_to is None


def test_download_failure_rolls_back(rows):
    adapter = FakeWinIDEAAdapter(download_seconds=0.02, fail_on={"download"})
    ctx, steps, _, error = run(adapter, rows)
    assert isinstance(error, FlashError)
    assert adapter.programs["App"] == OLD_APP
    assert Step.ROLLBACK in steps and Step.DONE not in steps
    assert "after_rollback" in ctx.snapshots


def test_inaccessible_core_refuses_programming_and_rolls_back(rows):
    adapter = FakeWinIDEAAdapter(download_seconds=0.02, fail_on={"core_inaccessible"})
    _ctx, steps, _, error = run(adapter, rows)
    assert isinstance(error, FlashError)
    assert "A53, BBE32EP still not accessible" in str(error)
    assert "Nothing was written" in error.hint
    assert adapter.programs["App"] == OLD_APP
    assert Step.ROLLBACK in steps and Step.DONE not in steps


def test_cancel_during_download_rolls_back(rows):
    adapter = FakeWinIDEAAdapter(download_seconds=0.5)
    token = CancelToken()
    ctx = DebugContext()
    wf = FlashWorkflow(adapter, ctx, on_progress=lambda p, m: token.cancel())
    with pytest.raises(CancelledError):
        wf.run(FlashRequest("fake-1", rows), token)
    assert adapter.programs["App"] == OLD_APP


def test_unexpected_exception_wrapped(rows):
    class Broken(FakeWinIDEAAdapter):
        def download(self, progress, cancel, timeout_s, **_kwargs):
            raise RuntimeError("COM error")

    adapter = Broken()
    error = run(adapter, rows)[3]
    assert isinstance(error, FlashError)
    assert "RuntimeError: COM error" in str(error)
    assert adapter.programs["App"] == OLD_APP


def test_rollback_failure_recorded(rows):
    adapter = FakeWinIDEAAdapter(fail_on={"set_path"})
    ctx, _, _, error = run(adapter, rows)
    assert isinstance(error, WinIDEAError) and "set_path" in str(error)
    assert len(ctx.errors) == 1  # the failed set is restored too, and that restore failed as well
    assert error.rollback_failed is True


def test_second_path_failure_restores_first(rows):
    class FailSecond(FakeWinIDEAAdapter):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.symbol_calls = 0

        def set_symbol_path(self, name, path):
            self.symbol_calls += 1
            if self.symbol_calls == 1:
                raise WinIDEAError("cannot set symbol path")
            super().set_symbol_path(name, path)

    adapter = FailSecond(download_seconds=0.02)
    ctx, steps, _, error = run(adapter, rows)
    assert isinstance(error, WinIDEAError) and "cannot set symbol path" in str(error)
    assert adapter.programs["App"] == OLD_APP
    assert adapter.applications["CM7_0"] == r"C:\fake\old\cm7_0.elf"
    assert Step.ROLLBACK in steps
    assert ctx.errors == []


def test_download_timeout_rolls_back(rows):
    adapter = FakeWinIDEAAdapter(download_seconds=0.5)
    ctx, steps, _, error = run(adapter, rows, timeout_s=0)
    assert isinstance(error, FlashError) and "timed out" in str(error)
    assert adapter.programs["App"] == OLD_APP
    assert Step.ROLLBACK in steps and Step.DONE not in steps
    assert "after_rollback" in ctx.snapshots


def test_connection_lost_during_download(rows):
    class Dropping(FakeWinIDEAAdapter):
        lost = False

        def download(self, progress, cancel, timeout_s, **_kwargs):
            self.lost = True
            raise WinIDEAError("Connection to winIDEA lost during download")

        def set_program_path(self, name, path):
            if self.lost:
                raise WinIDEAError("Connection to winIDEA lost")
            super().set_program_path(name, path)

        def set_symbol_path(self, name, path):
            if self.lost:
                raise WinIDEAError("Connection to winIDEA lost")
            super().set_symbol_path(name, path)

    adapter = Dropping(download_seconds=0.02)
    ctx, steps, _, error = run(adapter, rows)
    assert isinstance(error, WinIDEAError) and "during download" in str(error)
    assert Step.ROLLBACK in steps
    assert len(ctx.errors) == 3  # every written entry's restore failed and was recorded
    assert adapter.connected_to is None
    assert error.rollback_failed is True


class RestoreFailsOnce(FakeWinIDEAAdapter):
    """Restoring program 'App' to its old path fails (the first set is the new path)."""

    def set_program_path(self, name, path):
        if path == OLD_APP:
            raise WinIDEAError("restore App failed")
        super().set_program_path(name, path)


def test_rollback_continues_after_failed_restore(rows):
    adapter = RestoreFailsOnce(download_seconds=0.02, fail_on={"download"})
    ctx, _, _, error = run(adapter, rows)
    assert isinstance(error, FlashError) and "Fake failure" in str(error)
    assert adapter.applications["CM7_0"] == r"C:\fake\old\cm7_0.elf"
    assert adapter.applications["CM7_1"] == r"C:\fake\old\cm7_1.elf"
    assert adapter.programs["App"] != OLD_APP
    assert len(ctx.errors) == 1 and "restore App failed" in ctx.errors[0]
    assert error.rollback_failed is True
    assert error.hint.startswith("ROLLBACK FAILED")


def test_unwritten_entry_not_touched_on_rollback(rows):
    class FailSecondSet(FakeWinIDEAAdapter):
        sets = 0
        touched: list[str] = []

        def set_symbol_path(self, name, path):
            self.touched.append(name)
            self.sets += 1
            if self.sets == 1:
                raise WinIDEAError("second set failed")
            super().set_symbol_path(name, path)

    adapter = FailSecondSet(download_seconds=0.02)
    adapter.touched = []
    error = run(adapter, rows)[3]
    assert isinstance(error, WinIDEAError)
    assert adapter.touched == ["CM7_0", "CM7_0"]  # failed set is restored too; CM7_1 never touched
    assert adapter.programs["App"] == OLD_APP
    assert error.rollback_failed is False


def test_raising_rollback_callback_does_not_break_restore(rows):
    adapter = FakeWinIDEAAdapter(download_seconds=0.02, fail_on={"download"})

    def on_step(step):
        if step is Step.ROLLBACK:
            raise RuntimeError("signal emit failed")

    wf = FlashWorkflow(adapter, DebugContext(), on_step=on_step)
    with pytest.raises(FlashError, match="Fake failure"):
        wf.run(FlashRequest("fake-1", rows), CancelToken())
    assert adapter.programs["App"] == OLD_APP


def test_rollback_flag_false_on_success_and_clean_rollback(rows):
    adapter = FakeWinIDEAAdapter(download_seconds=0.02, fail_on={"download"})
    error = run(adapter, rows)[3]
    assert error.rollback_failed is False
    assert not error.hint.startswith("ROLLBACK FAILED")


def test_wrapped_unexpected_error_recorded_in_ctx(rows):
    class Broken(FakeWinIDEAAdapter):
        def download(self, progress, cancel, timeout_s, **_kwargs):
            raise RuntimeError("COM error")

    ctx, _, _, error = run(Broken(), rows)
    assert isinstance(error, FlashError)
    assert len(ctx.errors) == 1 and "RuntimeError: COM error" in ctx.errors[0]


def test_snapshot_failure_after_rollback_not_reported_as_rollback_failure(rows):
    class SnapFails(FakeWinIDEAAdapter):
        reads = 0

        def read_programs(self):
            self.reads += 1
            if self.reads == 3:  # before, after_set, after_rollback
                raise WinIDEAError("snapshot read failed")
            return super().read_programs()

    adapter = SnapFails(download_seconds=0.02, fail_on={"download"})
    ctx, _, _, error = run(adapter, rows)
    assert isinstance(error, FlashError)
    assert adapter.programs["App"] == OLD_APP
    assert error.rollback_failed is False


def test_set_that_raises_after_applying_is_restored(rows):
    class WritesThenRaises(FakeWinIDEAAdapter):
        sets = 0

        def set_symbol_path(self, name, path):
            self.sets += 1
            if self.sets == 1:
                self.applications[name] = path
                raise WinIDEAError("Connection lost after write")
            super().set_symbol_path(name, path)

    adapter = WritesThenRaises(download_seconds=0.02)
    error = run(adapter, rows)[3]
    assert isinstance(error, WinIDEAError) and "after write" in str(error)
    assert adapter.applications["CM7_0"] == r"C:\fake\old\cm7_0.elf"
    assert adapter.programs["App"] == OLD_APP
    assert error.rollback_failed is False


def test_selected_file_deleted_before_flash_raises_with_no_adapter_calls(rows):
    for row in rows:
        row.selected.unlink()
    adapter = FakeWinIDEAAdapter(download_seconds=0.02)
    ctx, steps, progress, error = run(adapter, rows)
    assert isinstance(error, MappingError)
    assert "no longer exists" in str(error) and "App.s3" in str(error)
    assert "Download the artifact again" in error.hint
    assert adapter.calls == []
    assert steps == []


from wflash.core.cancel import CancelToken as _Token
from wflash.core.debug_bundle import DebugContext as _Ctx
from wflash.core.errors import FlashError as _FlashError
from wflash.core.fake_adapter import INSTANCE_ID as _ID, FakeWinIDEAAdapter as _Fake
from wflash.core.file_matcher import MappingRow as _Row
from wflash.core.flash_workflow import FlashRequest as _Req, FlashWorkflow as _Flow, Step as _Step


def _verify_setup(tmp_path, fail_on=()):
    adapter = _Fake(download_seconds=0.01, fail_on=fail_on)
    s3 = tmp_path / "App.s3"
    s3.write_text("S0\n")
    steps = []
    flow = _Flow(adapter, _Ctx(), on_step=steps.append)
    req = lambda verify: _Req(_ID, [_Row(kind="program", target="App", pattern="*", selected=s3)], verify=verify)
    return adapter, flow, req, steps, s3


def test_verify_runs_between_download_and_reset_when_requested(tmp_path):
    _adapter, flow, req, steps, _s3 = _verify_setup(tmp_path)
    flow.run(req(True), _Token())
    assert steps.index(_Step.DOWNLOAD) < steps.index(_Step.VERIFY) < steps.index(_Step.RESET)


def test_verify_is_skipped_by_default(tmp_path):
    _adapter, flow, req, steps, _s3 = _verify_setup(tmp_path)
    flow.run(req(False), _Token())
    assert _Step.VERIFY not in steps


def test_verify_failure_does_not_roll_back_the_paths(tmp_path):
    adapter, flow, req, steps, s3 = _verify_setup(tmp_path, fail_on=["verify"])
    with pytest.raises(_FlashError):
        flow.run(req(True), _Token())
    assert _Step.ROLLBACK not in steps
    assert adapter.programs["App"] == str(s3.resolve())


# -- planned flash (profiles with builds) ----------------------------------------------
import dataclasses as _dc

from wflash.core.fake_adapter import INSTANCE_ID as _INSTANCE
from wflash.core.file_matcher import MappingRow as _MRow
from wflash.core.flash_plan import ProgramRow, SymbolRow

SUZ05 = Path(__file__).resolve().parents[1] / "profiles" / "suz05.yaml"
CAL = "20260623_142557_2018688_CAL_T008_v0_0.sre"
BM_BIN, FBL_BIN = "FBL_M7_LIP_RfeClock_Image.bin", "Radar_SUZ05_Gen7_FBL.bin"


def suz05_rows():
    programs = [
        ProgramRow(0, "Radar_SUZ05_Gen7.s3", "Radar_SUZ05_Gen7.s3", False, 0x1AA000),
        ProgramRow(1, "RAD_SUZ05_FFI.s3", "old/RAD_SUZ05_FFI.s3", True, 0),
        ProgramRow(2, CAL, CAL, True, 0),
        ProgramRow(3, BM_BIN, f"old/{BM_BIN}", False, 0),
        ProgramRow(4, FBL_BIN, f"old/{FBL_BIN}", False, 0xF1000),
    ]
    symbols = [
        SymbolRow(0, 0, "App_M7/Radar_SUZ05_Gen7.elf", "old/a.elf", True),
        SymbolRow(0, 1, "App_M7/Radar_SUZ05_Gen7_BM.elf", "old/b.elf", False),
        SymbolRow(0, 2, "App_M7/Radar_SUZ05_Gen7_FBL.elf", "old/c.elf", False),
    ]
    return programs, symbols


def suz05_mapping(tmp_path):
    files = {
        "RAD_SUZ05_FFI.s3": ("program", "RAD_SUZ05_FFI.s3"),
        BM_BIN: ("program", BM_BIN),
        FBL_BIN: ("program", FBL_BIN),
        "App_M7/Radar_SUZ05_Gen7.elf": ("application", "Radar_SUZ05_Gen7.elf"),
        "App_M7/Radar_SUZ05_Gen7_BM.elf": ("application", "Radar_SUZ05_Gen7_BM.elf"),
        "App_M7/Radar_SUZ05_Gen7_FBL.elf": ("application", "Radar_SUZ05_Gen7_FBL.elf"),
    }
    rows = []
    for target, (kind, name) in files.items():
        path = tmp_path / name
        path.write_bytes(b"x")
        rows.append(_MRow(kind, target, "*", [path], path))
    return rows


def planned(tmp_path, advanced=False, fail_on=()):
    adapter = FakeWinIDEAAdapter(download_seconds=0.01, fail_on=fail_on, rows=suz05_rows())
    req = FlashRequest(_INSTANCE, suz05_mapping(tmp_path), profile=load_profile(SUZ05), advanced=advanced, cal_file=CAL)
    return adapter, FlashWorkflow(adapter, DebugContext()), req


def test_planned_flash_with_advanced_off_unticks_bm_and_fbl_and_keeps_it(tmp_path):
    adapter, flow, req = planned(tmp_path)
    adapter.program_rows[3] = _dc.replace(adapter.program_rows[3], enabled=True)
    flow.run(req, CancelToken())
    assert adapter.program_rows[3].enabled is False
    assert adapter.program_rows[3].path == f"old/{BM_BIN}"
    assert adapter.program_rows[1].path == str((tmp_path / "RAD_SUZ05_FFI.s3").resolve())


def test_planned_flash_with_advanced_on_ticks_and_replaces(tmp_path):
    adapter, flow, req = planned(tmp_path, advanced=True)
    flow.run(req, CancelToken())
    assert adapter.program_rows[3].enabled and adapter.program_rows[3].path.endswith(BM_BIN)
    assert adapter.symbol_rows[1].enabled and adapter.symbol_rows[1].path.endswith("Radar_SUZ05_Gen7_BM.elf")


def test_planned_check_failure_changes_nothing(tmp_path):
    adapter, flow, req = planned(tmp_path)
    adapter.program_rows.pop(4)
    before = list(adapter.program_rows)
    with pytest.raises(MappingError):
        flow.run(req, CancelToken())
    assert adapter.program_rows == before and "download" not in adapter.calls


def test_failed_flash_restores_paths_but_keeps_ticks(tmp_path):
    adapter, flow, req = planned(tmp_path, advanced=True, fail_on=["download"])
    with pytest.raises(FlashError):
        flow.run(req, CancelToken())
    assert adapter.program_rows[3].path == f"old/{BM_BIN}"
    assert adapter.program_rows[3].enabled is True
    assert adapter.symbol_rows[1].path == "old/b.elf" and adapter.symbol_rows[1].enabled is True


def test_planned_flash_without_a_loaded_bm_refuses(tmp_path):
    adapter, flow, req = planned(tmp_path, advanced=True)
    req.mapping = [r for r in req.mapping if r.target != BM_BIN]
    with pytest.raises(MappingError, match="BM|FBL_M7"):
        flow.run(req, CancelToken())
    assert "download" not in adapter.calls


# B1 (user, 2026-11-12): with Switch Debugger on, the adapter power-cycles the ECU instead of resetting it.
def test_power_cycle_reaches_the_adapter_when_the_cores_run(rows):
    adapter = FakeWinIDEAAdapter(download_seconds=0.02, fail_on={"cores_running"})
    cycles = []
    _ctx, steps, _, error = run(adapter, rows, power_cycle=lambda: cycles.append(1))
    assert error is None and Step.DONE in steps
    assert cycles == [1] and adapter.program_stats["power_cycles"] == 1


def test_no_power_cycle_without_switch_debugger(rows):
    adapter = FakeWinIDEAAdapter(download_seconds=0.02, fail_on={"cores_running"})
    _ctx, steps, _, error = run(adapter, rows)
    assert error is None and adapter.program_stats["power_cycles"] == 0


def test_failed_power_cycle_writes_nothing_and_rolls_back(rows):
    from wflash.core.errors import BenchSwitchError

    def refuse():
        raise BenchSwitchError("refused", hint="Open Switch Debugger and press Start in its TCP/IP box, then try again.")

    adapter = FakeWinIDEAAdapter(download_seconds=0.02, fail_on={"cores_running"})
    _ctx, steps, _, error = run(adapter, rows, power_cycle=refuse)
    assert isinstance(error, FlashError) and str(error) == "Flash not started: the ECU power cycle failed."
    assert "Nothing was written" in error.hint and "press Start" in error.hint
    assert adapter.programs["App"] == OLD_APP
    assert Step.ROLLBACK in steps and Step.DONE not in steps
