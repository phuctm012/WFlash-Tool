import logging
import sys

import pytest

from tests.fake_isystem import WORKSPACE, World, install
from wflash.core.errors import WinIDEAError
from wflash.core.winidea_adapter import RealWinIDEAAdapter


@pytest.fixture
def world(monkeypatch):
    world = World()
    install(monkeypatch, world)
    return world


@pytest.fixture
def adapter(world):
    adapter = RealWinIDEAAdapter()
    adapter.list_instances()
    return adapter


@pytest.fixture
def connected(adapter):
    adapter.connect("5315")
    yield adapter
    adapter.disconnect()


def test_list_instances_uses_the_port_as_id_because_winidea_gives_an_empty_id(world):
    [info] = RealWinIDEAAdapter().list_instances()
    assert (info.instance_id, info.workspace, info.tcp_port) == ("5315", WORKSPACE, 5315)
    assert info.label() == "SUZ_7G5_M7.xjrf (5315)"


def test_list_instances_returns_empty_when_the_module_is_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "isystem.connect", None)
    assert RealWinIDEAAdapter().list_instances() == []


def test_connect_reports_the_root_cause_when_the_module_cannot_load(monkeypatch):
    monkeypatch.setitem(sys.modules, "isystem.connect", None)
    with pytest.raises(WinIDEAError) as err:
        RealWinIDEAAdapter().connect("5315")
    assert "isystem.connect" in str(err.value)
    assert "bitness" in err.value.hint
    assert isinstance(err.value.__cause__, ImportError)


def test_connect_refuses_when_winidea_attached_to_another_workspace(adapter, world):
    world.workspace = "C:/other/Other.xjrf"
    with pytest.raises(WinIDEAError) as err:
        adapter.connect("5315")
    assert "Other.xjrf" in str(err.value)
    assert "Close" in err.value.hint
    with pytest.raises(WinIDEAError):
        adapter.get_info()  # the session was dropped


def test_connect_accepts_the_same_workspace_written_with_other_slashes(adapter, world):
    world.workspace = "C:\\WS\\suz_7g5_m7.xjrf"
    adapter.connect("5315")
    assert adapter.get_info()["workspace"] == "C:\\WS\\suz_7g5_m7.xjrf"


def test_connect_fails_when_not_attached(adapter, world):
    world.attached = False
    with pytest.raises(WinIDEAError):
        adapter.connect("5315")


def test_connect_wraps_a_connection_failure(adapter, world):
    world.connect_error = OSError("no winIDEA")
    with pytest.raises(WinIDEAError) as err:
        adapter.connect("5315")
    assert isinstance(err.value.__cause__, OSError)


def test_connect_to_an_unknown_instance_fails(adapter):
    with pytest.raises(WinIDEAError):
        adapter.connect("9999")


def test_get_info_reports_versions(connected):
    info = connected.get_info()
    assert info["winidea_version"] == "9.21.408.1.260751"
    assert info["isystem_connect"] == "9.21.408.1"
    assert info["adapter"] == "real"


def test_version_mismatch_is_a_warning_not_a_block(adapter, world, caplog):
    world.module_version = "9.26.11.2"
    with caplog.at_level(logging.WARNING):
        adapter.connect("5315")
        adapter.get_info()
    assert any("does not match" in r.getMessage() and r.levelno == logging.WARNING for r in caplog.records)


def test_download_is_not_cancellable():
    assert RealWinIDEAAdapter.download_cancellable is False


from tests.fake_isystem import DEVICE
from wflash.core.errors import MappingError

ROW1 = f"{DEVICE}.DownloadFiles[1].Path"
ELF = "/IDE/System.Debug.Applications[0].SymbolFiles.File[0].Path"


def test_read_programs_names_rows_after_their_file(connected):
    assert {e.name: e.path for e in connected.read_programs()} == {
        "Radar_SUZ05_Gen7.s3 (disabled)": "Radar_SUZ05_Gen7.s3",
        "RAD_SUZ05_FFI.s3": "../debug/out/FFI/RAD_SUZ05_FFI.s3",
        "20260623_CAL_T008.sre": "20260623_CAL_T008.sre",
    }


def test_read_programs_does_not_guess_between_two_enabled_rows_with_one_name(connected, world):
    world.options[f"{DEVICE}.DownloadFiles[2].Path"] = "other/RAD_SUZ05_FFI.s3"
    names = [e.name for e in connected.read_programs()]
    assert "RAD_SUZ05_FFI.s3" not in names
    assert "RAD_SUZ05_FFI.s3 #1" in names and "RAD_SUZ05_FFI.s3 #2" in names
    with pytest.raises(WinIDEAError):
        connected.set_program_path("RAD_SUZ05_FFI.s3", "C:/new/RAD_SUZ05_FFI.s3")


@pytest.mark.parametrize("option", ["Enabled", "ProgramAtDownload"])
def test_read_programs_refuses_a_device_that_would_not_be_programmed(connected, world, option):
    world.options[f"{DEVICE}.{option}"] = "false"
    with pytest.raises(WinIDEAError) as err:
        connected.read_programs()
    assert "Configure" in err.value.hint


def test_read_applications_lists_every_symbol_file_and_ends_at_out_of_range(connected):
    assert {e.name: e.path for e in connected.read_applications()} == {
        "App_M7/Radar_SUZ05_Gen7.elf": "../debug/out/bin/Radar_SUZ05_Gen7.elf",
        "App_BBE/BBE_Core_Gen7.elf": "BBE_Core_Gen7.elf",
        "App_A53/RAD_A53_Perception_Core.elf #0": "RAD_A53_Perception_Core.elf",
        "App_A53/RAD_A53_Perception_Core.elf #1": "Y:\\out\\RAD_A53_Perception_Core.elf",
    }


def test_set_program_path_writes_only_that_row_and_reads_back(connected, world):
    connected.read_programs()
    before = dict(world.options)
    connected.set_program_path("RAD_SUZ05_FFI.s3", "C:/new/RAD_SUZ05_FFI.s3")
    changed = {k for k in world.options if world.options[k] != before[k]}
    assert changed == {ROW1}
    assert world.options[ROW1] == "C:/new/RAD_SUZ05_FFI.s3"


def test_set_symbol_path_writes_only_that_file(connected, world):
    connected.read_applications()
    connected.set_symbol_path("App_M7/Radar_SUZ05_Gen7.elf", "C:/new/Radar_SUZ05_Gen7.elf")
    assert world.options[ELF] == "C:/new/Radar_SUZ05_Gen7.elf"
    assert world.options["/IDE/System.Debug.Applications[1].SymbolFiles.File[0].Path"] == "BBE_Core_Gen7.elf"


def test_set_path_refuses_a_file_with_another_name(connected, world):
    connected.read_programs()
    with pytest.raises(MappingError) as err:
        connected.set_program_path("RAD_SUZ05_FFI.s3", "C:/new/Other.s3")
    assert "Other.s3" in str(err.value)
    assert world.options[ROW1] == "../debug/out/FFI/RAD_SUZ05_FFI.s3"


def test_set_path_file_name_check_ignores_case_like_windows(connected, world):
    connected.read_programs()
    connected.set_program_path("RAD_SUZ05_FFI.s3", "C:/new/rad_suz05_ffi.S3")
    assert world.options[ROW1] == "C:/new/rad_suz05_ffi.S3"


def test_set_path_fails_when_the_read_back_differs(connected, world):
    connected.read_programs()
    world.set_stores = "something else"
    with pytest.raises(WinIDEAError):
        connected.set_program_path("RAD_SUZ05_FFI.s3", "C:/new/RAD_SUZ05_FFI.s3")


def test_set_path_for_a_disabled_row_fails(connected):
    connected.read_programs()
    with pytest.raises(WinIDEAError):
        connected.set_program_path("Radar_SUZ05_Gen7.s3 (disabled)", "C:/new/Radar_SUZ05_Gen7.s3")


def test_lost_connection_is_reported_as_such(connected, world):
    world.routing_lost = True
    with pytest.raises(WinIDEAError) as err:
        connected.read_programs()
    assert "lost" in str(err.value)


from wflash.core import winidea_adapter
from wflash.core.cancel import CancelToken
from wflash.core.debug_bundle import DebugContext
from wflash.core.errors import CancelledError, FlashError
from wflash.core.file_matcher import MappingRow
from wflash.core.flash_workflow import FlashRequest, FlashWorkflow, Step


def test_download_calls_begin_program_once(connected, world):
    connected.download(lambda p, m: None, CancelToken(), 600)
    assert world.calls.count("begin_program") == 1


def test_download_ignores_cancel_because_it_cannot_be_stopped_safely(connected, world):
    token = CancelToken()
    token.cancel()
    connected.download(lambda p, m: None, token, 600)
    assert world.calls.count("begin_program") == 1


def test_download_reports_estimated_progress_below_100(connected, world, monkeypatch):
    monkeypatch.setattr(winidea_adapter, "PROGRESS_TICK_S", 0.01)
    monkeypatch.setattr(winidea_adapter, "EXPECTED_PROGRAM_S", 0.02)
    world.begin_program_hook = lambda: __import__("time").sleep(0.1)
    seen = []
    connected.download(lambda p, m: seen.append((p, m)), CancelToken(), 600)
    assert seen and all(0 <= p <= winidea_adapter.MAX_ESTIMATED_PERCENT for p, _m in seen)
    assert "estimated" in seen[0][1]


def test_download_survives_a_failing_progress_callback(connected, world, monkeypatch):
    monkeypatch.setattr(winidea_adapter, "PROGRESS_TICK_S", 0.01)
    world.begin_program_hook = lambda: __import__("time").sleep(0.05)

    def boom(_p, _m):
        raise RuntimeError("signal source deleted")

    connected.download(boom, CancelToken(), 600)
    assert world.calls.count("begin_program") == 1


def test_download_past_the_timeout_warns_and_keeps_waiting(connected, world, monkeypatch, caplog):
    monkeypatch.setattr(winidea_adapter, "PROGRESS_TICK_S", 0.01)
    world.begin_program_hook = lambda: __import__("time").sleep(0.05)
    with caplog.at_level(logging.WARNING):
        connected.download(lambda p, m: None, CancelToken(), 0)
    assert any("cannot be stopped" in r.getMessage() for r in caplog.records)


def test_download_failure_warns_that_the_flash_may_be_erased(connected, world):
    world.begin_program_error = OSError("probe lost")
    with pytest.raises(FlashError) as err:
        connected.download(lambda p, m: None, CancelToken(), 600)
    assert "erased" in err.value.hint
    assert isinstance(err.value.__cause__, OSError)


def test_reset_halts_and_confirms_with_is_stopped(connected, world):
    connected.reset(run=False)
    assert world.calls[-1] == "reset"


def test_reset_with_run_runs(connected, world):
    connected.reset(run=True)
    assert world.calls[-2:] == ["reset", "run"]


def test_reset_fails_when_the_target_does_not_stop(connected, world, monkeypatch):
    monkeypatch.setattr(winidea_adapter, "HALT_WAIT_S", 0.05)
    monkeypatch.setattr(winidea_adapter, "HALT_POLL_S", 0.01)
    world.stopped_after_reset = False
    with pytest.raises(WinIDEAError) as err:
        connected.reset(run=False)
    assert "flash finished" in err.value.hint


def _rows(tmp_path):
    s3 = tmp_path / "RAD_SUZ05_FFI.s3"
    elf = tmp_path / "Radar_SUZ05_Gen7.elf"
    s3.write_text("S0\n")
    elf.write_text("x")
    return [
        MappingRow(kind="program", target="RAD_SUZ05_FFI.s3", pattern="**/RAD_SUZ05_FFI.s3", selected=s3),
        MappingRow(kind="application", target="App_M7/Radar_SUZ05_Gen7.elf", pattern="**/Radar_SUZ05_Gen7.elf", selected=elf),
    ]


def test_workflow_changes_only_the_two_paths_then_programs_once(adapter, world, tmp_path):
    before = dict(world.options)
    rows = _rows(tmp_path)
    FlashWorkflow(adapter, DebugContext()).run(FlashRequest("5315", rows), CancelToken())
    changed = {k for k in world.options if world.options[k] != before[k]}
    assert changed == {ROW1, ELF}
    assert world.options[ROW1] == str(rows[0].selected.resolve())
    assert world.calls.count("begin_program") == 1
    assert world.calls[-1] == "reset"


def test_workflow_rolls_back_both_paths_when_programming_fails(adapter, world, tmp_path):
    before = dict(world.options)
    world.begin_program_error = OSError("probe lost")
    with pytest.raises(FlashError):
        FlashWorkflow(adapter, DebugContext()).run(FlashRequest("5315", _rows(tmp_path)), CancelToken())
    assert world.options == before


def test_workflow_stops_before_programming_when_the_profile_names_a_missing_row(adapter, world, tmp_path):
    rows = _rows(tmp_path)
    rows[0] = MappingRow(kind="program", target="Nope.s3", pattern="*", selected=rows[0].selected)
    with pytest.raises(MappingError):
        FlashWorkflow(adapter, DebugContext()).run(FlashRequest("5315", rows), CancelToken())
    assert "begin_program" not in world.calls


def test_workflow_stops_before_programming_when_the_file_is_named_differently(adapter, world, tmp_path):
    before = dict(world.options)
    other = tmp_path / "Other.s3"
    other.write_text("S0\n")
    rows = _rows(tmp_path)
    rows[0] = MappingRow(kind="program", target="RAD_SUZ05_FFI.s3", pattern="*", selected=other)
    with pytest.raises(MappingError):
        FlashWorkflow(adapter, DebugContext()).run(FlashRequest("5315", rows), CancelToken())
    assert "begin_program" not in world.calls
    assert world.options == before


def _prepare_flash(world, tmp_path, corrupt=False):
    world.workspace_dir = str(tmp_path)
    world.options[f"{DEVICE}.DownloadFiles[1].Path"] = "RAD_SUZ05_FFI.s3"
    world.options[f"{DEVICE}.DownloadFiles[2].Path"] = "CAL.hex"
    (tmp_path / "RAD_SUZ05_FFI.s3").write_text(_s3(0x100, b"\x11" * 16) + "\n")
    world.flash = {0x100 + i: 0x11 for i in range(16)}
    if corrupt:
        world.flash[0x105] = 0xFF


def _s3(address, data):
    body = bytes([4 + len(data) + 1]) + address.to_bytes(4, "big") + data
    return "S3" + body.hex().upper() + f"{(~sum(body)) & 0xFF:02X}"


def test_verify_flash_passes_and_skips_disabled_and_non_srec_rows(connected, world, tmp_path):
    _prepare_flash(world, tmp_path)
    seen = []
    connected.verify_flash(lambda p, m: seen.append(p))
    assert [c for c in world.calls if c.startswith("read")] == ["read 0 0x100 16"]
    assert seen[-1] == 100


def test_verify_flash_reports_the_first_difference(connected, world, tmp_path):
    _prepare_flash(world, tmp_path, corrupt=True)
    with pytest.raises(FlashError) as err:
        connected.verify_flash(lambda p, m: None)
    assert "0x000105" in str(err.value)
    assert "Flash again" in err.value.hint


def test_verify_flash_applies_the_row_offset(connected, world, tmp_path):
    _prepare_flash(world, tmp_path)
    world.options[f"{DEVICE}.DownloadFiles[1].Offset"] = "0x1000"
    world.flash = {0x1100 + i: 0x11 for i in range(16)}
    connected.verify_flash(lambda p, m: None)
    assert "read 0 0x1100 16" in world.calls


def test_verify_flash_read_failure_logs_the_device_error(connected, world, tmp_path, caplog):
    _prepare_flash(world, tmp_path)
    world.read_error = OSError("CUMIController::read failed!")
    with caplog.at_level(logging.ERROR), pytest.raises(WinIDEAError):
        connected.verify_flash(lambda p, m: None)
    assert any("Operation failed" in r.getMessage() for r in caplog.records)


def test_verify_flash_with_a_missing_file_fails(connected, world, tmp_path):
    _prepare_flash(world, tmp_path)
    (tmp_path / "RAD_SUZ05_FFI.s3").unlink()
    with pytest.raises(FlashError):
        connected.verify_flash(lambda p, m: None)


def test_a_cancel_raised_by_the_progress_callback_cannot_stop_programming_or_verify(connected, world, tmp_path, monkeypatch, caplog):
    # WorkerContext.progress raises CancelledError once the token is set, e.g. Cancel just before the lock.
    monkeypatch.setattr(winidea_adapter, "PROGRESS_TICK_S", 0.01)
    world.begin_program_hook = lambda: __import__("time").sleep(0.05)

    def cancelled(_p, _m):
        raise CancelledError("cancelled")

    with caplog.at_level(logging.WARNING):
        connected.download(cancelled, CancelToken(), 600)
    assert world.calls.count("begin_program") == 1
    assert not any("Progress callback failed" in r.getMessage() for r in caplog.records)
    _prepare_flash(world, tmp_path)
    connected.verify_flash(cancelled)


from wflash.core.winidea_adapter import create_adapter


def test_create_adapter_real_builds_without_importing_isystem(monkeypatch):
    monkeypatch.setitem(sys.modules, "isystem.connect", None)
    assert isinstance(create_adapter("real"), RealWinIDEAAdapter)


MONITOR_ERROR = "001 - Operation failed! [fpcErrCode=0x39] [extErrCode=0x0000] [Error loading monitor]"


def test_programming_monitor_failure_advises_a_power_cycle(connected, world):
    world.begin_program_error = OSError("Device 'Program' feature: 'Error loading monitor'")
    with pytest.raises(FlashError) as err:
        connected.download(lambda p, m: None, CancelToken(), 600)
    assert err.value.hint.startswith("Turn the ECU power off and on, then flash again.")
    assert "Error loading monitor" not in str(err.value)


def test_verify_monitor_failure_says_the_flash_finished_and_advises_a_power_cycle(connected, world, tmp_path, caplog):
    _prepare_flash(world, tmp_path)
    world.read_error = OSError("CUMIController::read failed! Error code unknown to isystem.connect facade: 39")
    world.umi_last_error = MONITOR_ERROR
    with caplog.at_level(logging.ERROR), pytest.raises(WinIDEAError) as err:
        connected.verify_flash(lambda p, m: None)
    assert "Error loading monitor" not in str(err.value)
    assert any("Error loading monitor" in r.getMessage() for r in caplog.records)
    assert "power off and on" in err.value.hint
    assert "programming finished" in err.value.hint.lower()


def test_other_verify_read_failure_still_says_the_flash_finished(connected, world, tmp_path):
    _prepare_flash(world, tmp_path)
    world.read_error = OSError("probe lost")
    with pytest.raises(WinIDEAError) as err:
        connected.verify_flash(lambda p, m: None)
    assert "programming finished" in err.value.hint.lower()
    assert "power off and on" not in err.value.hint


def test_download_resets_the_cpu_before_programming(connected, world):
    connected.download(lambda p, m: None, CancelToken(), 600)
    assert world.calls.index("reset") < world.calls.index("begin_program")


def test_download_still_programs_when_the_reset_before_it_fails(connected, world, caplog):
    world.reset_error = OSError("reset refused")
    with caplog.at_level(logging.WARNING):
        connected.download(lambda p, m: None, CancelToken(), 600)
    assert world.calls.count("begin_program") == 1
    assert any("before programming" in r.getMessage() for r in caplog.records)


def test_download_still_programs_when_the_target_does_not_stop_after_the_reset(connected, world, monkeypatch, caplog):
    monkeypatch.setattr(winidea_adapter, "HALT_WAIT_S", 0.05)
    monkeypatch.setattr(winidea_adapter, "HALT_POLL_S", 0.01)
    world.stopped_after_reset = False
    with caplog.at_level(logging.WARNING):
        connected.download(lambda p, m: None, CancelToken(), 600)
    assert world.calls.count("begin_program") == 1
    assert any("before programming" in r.getMessage() for r in caplog.records)


def test_download_confirms_programming_by_reading_the_flash_once(connected, world):
    connected.download(lambda p, m: None, CancelToken(), 600)
    assert world.calls[-2:] == ["begin_program", f"read 0 0x0 {winidea_adapter.PROBE_BYTES}"]


def _silent_monitor_failure(world):
    # Observed: begin_program returns normally after 4.8 s, the next read fails with code 39.
    world.read_error = OSError("CUMIController::read failed! Error code unknown to isystem.connect facade: 39")
    world.umi_last_error = MONITOR_ERROR


def test_download_reports_a_program_that_failed_silently(connected, world, caplog):
    _silent_monitor_failure(world)
    with caplog.at_level(logging.ERROR), pytest.raises(FlashError) as err:
        connected.download(lambda p, m: None, CancelToken(), 600)
    assert str(err.value) == "Flash failed: winIDEA could not start programming."
    assert err.value.hint == "Turn the ECU power off and on, then flash again."
    assert any("Error loading monitor" in r.getMessage() for r in caplog.records)


def test_workflow_restores_the_paths_and_does_not_finish_after_a_silent_failure(adapter, world, tmp_path):
    before = dict(world.options)
    _silent_monitor_failure(world)
    steps = []
    with pytest.raises(FlashError):
        FlashWorkflow(adapter, DebugContext(), on_step=steps.append).run(FlashRequest("5315", _rows(tmp_path)), CancelToken())
    assert world.options == before
    assert Step.DONE not in steps and Step.RESET not in steps


def test_download_logs_the_target_status_after_programming(connected, world, caplog):
    with caplog.at_level(logging.INFO):
        connected.download(lambda p, m: None, CancelToken(), 600)
    assert any("stopped=True" in r.getMessage() for r in caplog.records)


def test_binding_errors_stay_out_of_the_message_and_go_to_the_log(connected, world, caplog):
    world.options.pop("/iOPEN/UMIConfig.Devices.Devices[0].Enabled")
    with caplog.at_level(logging.ERROR), pytest.raises(WinIDEAError) as err:
        connected.read_programs()
    assert "E_INVALIDARG" not in str(err.value)
    assert any("E_INVALIDARG" in r.getMessage() for r in caplog.records)


def test_verify_compares_only_what_a_later_row_did_not_overwrite(connected, world, tmp_path):
    world.workspace_dir = str(tmp_path)
    world.options[f"{DEVICE}.DownloadFiles[1].Path"] = "RAD_SUZ05_FFI.s3"
    world.options[f"{DEVICE}.DownloadFiles[2].Path"] = "BM.bin"
    world.options[f"{DEVICE}.DownloadFiles[2].Offset"] = "0x104"
    (tmp_path / "RAD_SUZ05_FFI.s3").write_text(_s3(0x100, b"\x11" * 16) + "\n")
    (tmp_path / "BM.bin").write_bytes(b"\x22" * 4)
    world.flash = {0x100 + i: 0x11 for i in range(16)}
    world.flash.update({0x104 + i: 0x22 for i in range(4)})
    connected.verify_flash(lambda p, m: None)  # no false difference where BM covers the FFI
    world.flash[0x105] = 0xFF
    with pytest.raises(FlashError) as err:
        connected.verify_flash(lambda p, m: None)
    assert "0x000105" in str(err.value) and "BM.bin" in str(err.value)


def test_read_program_and_symbol_rows(connected, world):
    world.options["/IDE/System.Debug.Applications[0].SymbolFiles.File[0].Load"] = "true"
    world.options["/IDE/System.Debug.Applications[1].SymbolFiles.File[0].Load"] = "false"
    world.options["/IDE/System.Debug.Applications[2].SymbolFiles.File[0].Load"] = "true"
    world.options["/IDE/System.Debug.Applications[2].SymbolFiles.File[1].Load"] = "true"
    rows = connected.read_program_rows()
    assert [(r.index, r.name, r.enabled, r.offset) for r in rows][:2] == [
        (0, "Radar_SUZ05_Gen7.s3", False, 0x1AA000), (1, "RAD_SUZ05_FFI.s3", True, 0)]
    symbols = connected.read_symbol_rows()
    assert (symbols[0].name, symbols[0].enabled) == ("App_M7/Radar_SUZ05_Gen7.elf", True)
    assert symbols[1].enabled is False


def test_set_program_row_writes_path_and_tick_and_reads_back(connected, world):
    connected.set_program_row(1, path="C:/new/RAD_SUZ05_FFI.s3", tick=False)
    assert world.options[f"{DEVICE}.DownloadFiles[1].Path"] == "C:/new/RAD_SUZ05_FFI.s3"
    assert world.options[f"{DEVICE}.DownloadFiles[1].Enabled"] == "false"


def test_set_symbol_row_writes_the_load_field(connected, world):
    world.options["/IDE/System.Debug.Applications[0].SymbolFiles.File[0].Load"] = "false"
    connected.set_symbol_row(0, 0, tick=True)
    assert world.options["/IDE/System.Debug.Applications[0].SymbolFiles.File[0].Load"] == "true"


def test_a_tick_winidea_does_not_keep_is_an_error(connected, world):
    world.set_stores = "true"
    with pytest.raises(WinIDEAError):
        connected.set_program_row(1, tick=False)


INACCESSIBLE = [("M7_0", 2, "STOP"), ("M7_RFE", 3, "RUN"), ("A53", 1, "NOT ACCESSIBLE"),
                ("SPT", 5, "IDLE"), ("BBE32EP", 1, "NOT ACCESSIBLE")]  # spike 16, flashing failed


def test_download_logs_the_core_states_and_programs_when_none_is_inaccessible(connected, world, caplog):
    with caplog.at_level(logging.INFO):
        connected.download(lambda p, m: None, CancelToken(), 600)
    assert world.calls.index("reset") < world.calls.index("get_status") < world.calls.index("begin_program")
    assert any("M7_0 STOP" in r.getMessage() and "BBE32EP RUN" in r.getMessage() for r in caplog.records)


def test_download_resets_again_until_no_core_is_inaccessible(connected, world, monkeypatch, caplog):
    monkeypatch.setattr(winidea_adapter, "CORE_WAIT_S", 0.02)
    monkeypatch.setattr(winidea_adapter, "HALT_POLL_S", 0.01)
    world.cores_after_reset = [INACCESSIBLE, INACCESSIBLE, list(World().cores)]  # the third reset clears it
    with caplog.at_level(logging.INFO):
        connected.download(lambda p, m: None, CancelToken(), 600)
    assert world.calls.count("reset") == 3
    assert world.calls.count("begin_program") == 1
    assert world.calls.index("begin_program") > max(i for i, c in enumerate(world.calls) if c == "reset")
    assert sum("resetting again" in r.getMessage() for r in caplog.records) == 2
    assert any("Cores before programming: M7_0 STOP" in r.getMessage() for r in caplog.records)


def test_download_gives_up_after_the_maximum_resets(connected, world, monkeypatch, caplog):
    monkeypatch.setattr(winidea_adapter, "CORE_WAIT_S", 0.02)
    monkeypatch.setattr(winidea_adapter, "HALT_POLL_S", 0.01)
    world.cores_after_reset = [INACCESSIBLE]
    with caplog.at_level(logging.ERROR), pytest.raises(FlashError) as err:
        connected.download(lambda p, m: None, CancelToken(), 600)
    assert world.calls.count("reset") == 1 + winidea_adapter.MAX_CORE_RESETS
    assert "begin_program" not in world.calls
    assert str(err.value) == "Flash not started: A53, BBE32EP still not accessible after 3 more resets."
    assert "Session Explorer" in err.value.hint and "Nothing was written" in err.value.hint
    assert any("NOT ACCESSIBLE" in r.getMessage() for r in caplog.records)


def test_download_programs_when_the_cores_become_accessible_within_the_grace(connected, world, monkeypatch):
    monkeypatch.setattr(winidea_adapter, "CORE_WAIT_S", 5.0)
    monkeypatch.setattr(winidea_adapter, "HALT_POLL_S", 0.01)
    world.cores_after_reset = [INACCESSIBLE]

    def recover_on_third_read():
        if world.calls.count("get_status") == 3:
            world.cores = [("M7_0", 2, "STOP"), ("A53", 2, "STOP")]

    world.get_status_hook = recover_on_third_read
    connected.download(lambda p, m: None, CancelToken(), 600)
    assert world.calls.count("reset") == 1  # recovered without another reset
    assert world.calls.count("begin_program") == 1


def test_download_programs_anyway_when_the_core_states_cannot_be_read(connected, world, caplog):
    world.core_status_error = OSError("get_status not supported")
    with caplog.at_level(logging.WARNING):
        connected.download(lambda p, m: None, CancelToken(), 600)
    assert world.calls.count("begin_program") == 1
    assert any("Cannot read the core states" in r.getMessage() for r in caplog.records)
