from pathlib import Path

import pytest

from wflash.core.cancel import CancelToken
from wflash.core.debug_bundle import DebugContext
from wflash.core.errors import CancelledError, FlashError, MappingError, WinIDEAError
from wflash.core.fake_adapter import FakeWinIDEAAdapter
from wflash.core.file_matcher import build_mapping
from wflash.core.flash_workflow import FlashRequest, FlashWorkflow, Step
from wflash.core.profile import load_profile

EXAMPLE = Path(__file__).resolve().parents[1] / "profiles" / "saf85xx_example.yaml"
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
    assert steps == [Step.CONNECT, Step.VALIDATE, Step.SET_PATHS, Step.DOWNLOAD, Step.RESET, Step.DONE]
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
        def download(self, progress, cancel, timeout_s):
            raise RuntimeError("COM error")

    adapter = Broken()
    error = run(adapter, rows)[3]
    assert isinstance(error, FlashError)
    assert "RuntimeError: COM error" in str(error)
    assert adapter.programs["App"] == OLD_APP


def test_rollback_failure_recorded(rows):
    adapter = FakeWinIDEAAdapter(fail_on={"set_path"})
    ctx, _, _, error = run(adapter, rows)
    assert isinstance(error, WinIDEAError)
    assert len(ctx.errors) == 1 and "set_path" in ctx.errors[0]


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

        def download(self, progress, cancel, timeout_s):
            self.lost = True
            raise WinIDEAError("Connection to winIDEA lost")

        def set_program_path(self, name, path):
            if self.lost:
                raise WinIDEAError("Connection to winIDEA lost")
            super().set_program_path(name, path)

        def set_symbol_path(self, name, path):
            if self.lost:
                raise WinIDEAError("Connection to winIDEA lost")
            super().set_symbol_path(name, path)

    adapter = Dropping(download_seconds=0.02)
    ctx, _, _, error = run(adapter, rows)
    assert isinstance(error, WinIDEAError) and "Connection to winIDEA lost" in str(error)
    assert len(ctx.errors) == 1
    assert adapter.connected_to is None
