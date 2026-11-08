from pathlib import Path

import pytest

from wflash.core.errors import MappingError
from wflash.core.flash_plan import ProgramRow, SymbolRow, find_cal_files, make_plan
from wflash.core.profile import load_profile

PROFILE = load_profile(Path(__file__).resolve().parents[1] / "profiles" / "suz05_m7_ffi.yaml")
CAL = "20260623_142557_2018688_CAL_T008_v0_0.sre"
BM, FBL = "FBL_M7_LIP_RfeClock_Image.bin", "Radar_SUZ05_Gen7_FBL.bin"


def rows(**over):
    data = [
        ProgramRow(0, "Radar_SUZ05_Gen7.s3", "Radar_SUZ05_Gen7.s3", False, 0x1AA000),
        ProgramRow(1, "RAD_SUZ05_FFI.s3", "old/RAD_SUZ05_FFI.s3", True, 0),
        ProgramRow(2, CAL, CAL, True, 0),
        ProgramRow(3, BM, f"old/{BM}", False, over.get("bm_offset", 0)),
        ProgramRow(4, FBL, f"old/{FBL}", False, 0xF1000),
    ]
    return data


def symbols():
    return [
        SymbolRow(0, 0, "App_M7/Radar_SUZ05_Gen7.elf", "old/a.elf", True),
        SymbolRow(0, 1, "App_M7/Radar_SUZ05_Gen7_BM.elf", "old/b.elf", False),
        SymbolRow(0, 2, "App_M7/Radar_SUZ05_Gen7_FBL.elf", "old/c.elf", False),
    ]


FILES = {
    "RAD_SUZ05_FFI.s3": Path("c/RAD_SUZ05_FFI.s3"),
    "App_M7/Radar_SUZ05_Gen7.elf": Path("c/Radar_SUZ05_Gen7.elf"),
    BM: Path(f"c/{BM}"),
    FBL: Path(f"c/{FBL}"),
    "App_M7/Radar_SUZ05_Gen7_BM.elf": Path("c/Radar_SUZ05_Gen7_BM.elf"),
    "App_M7/Radar_SUZ05_Gen7_FBL.elf": Path("c/Radar_SUZ05_Gen7_FBL.elf"),
}


def ticks(changes):
    return {c.row.name: c.tick for c in changes}


def test_advanced_on_ticks_and_replaces_everything():
    plan = make_plan(PROFILE, True, rows(), symbols(), FILES, CAL)
    assert ticks(plan.programs) == {"RAD_SUZ05_FFI.s3": True, CAL: True, BM: True, FBL: True}
    assert all(ticks(plan.symbols).values())
    assert next(c for c in plan.programs if c.row.name == BM).new_path == str(FILES[BM])


def test_advanced_off_unticks_bm_and_fbl_and_leaves_their_paths():
    plan = make_plan(PROFILE, False, rows(), symbols(), FILES, CAL)
    assert ticks(plan.programs)[BM] is False and ticks(plan.symbols)["App_M7/Radar_SUZ05_Gen7_BM.elf"] is False
    assert next(c for c in plan.programs if c.row.name == BM).new_path is None


def test_missing_row_names_the_file_and_the_offset():
    data = [r for r in rows() if r.name != FBL]
    with pytest.raises(MappingError) as err:
        make_plan(PROFILE, False, data, symbols(), FILES, CAL)
    assert FBL in str(err.value) and "0xF1000" in err.value.hint


def test_wrong_order_is_refused():
    data = rows()
    data[3], data[4] = ProgramRow(3, FBL, FBL, False, 0xF1000), ProgramRow(4, BM, BM, False, 0)
    with pytest.raises(MappingError, match="order"):
        make_plan(PROFILE, False, data, symbols(), FILES, CAL)


def test_wrong_offset_is_refused():
    with pytest.raises(MappingError, match="offset"):
        make_plan(PROFILE, False, rows(bm_offset=0x1000), symbols(), FILES, CAL)


def test_another_ticked_row_is_refused():
    data = rows()
    data[0] = ProgramRow(0, "Radar_SUZ05_Gen7.s3", "Radar_SUZ05_Gen7.s3", True, 0x1AA000)
    with pytest.raises(MappingError, match="Radar_SUZ05_Gen7.s3"):
        make_plan(PROFILE, False, data, symbols(), FILES, CAL)


def test_a_new_cal_replaces_the_old_row_with_a_relative_name():
    data = rows()
    data[2] = ProgramRow(2, "20250101_CAL_T008_v0.sre", "20250101_CAL_T008_v0.sre", True, 0)
    plan = make_plan(PROFILE, False, data, symbols(), FILES, CAL)
    assert next(c for c in plan.programs if c.row.index == 2).new_path == CAL


def test_missing_cal_is_refused():
    with pytest.raises(MappingError, match="CAL"):
        make_plan(PROFILE, False, rows(), symbols(), FILES, "")


def test_find_cal_files_looks_only_next_to_the_workspace(tmp_path):
    (tmp_path / CAL).write_text("x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "1_CAL_T008_x.sre").write_text("x")
    assert find_cal_files(tmp_path, "*_CAL_T008_*.sre") == [tmp_path / CAL]
