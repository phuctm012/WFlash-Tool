from pathlib import Path

from wflash.core.file_matcher import build_mapping, candidates_for_kind, match_pattern
from wflash.core.profile import load_profile

EXAMPLE = Path(__file__).resolve().parents[1] / "profiles" / "saf85xx_example.yaml"


def make_tree(root: Path, files: list[str]) -> None:
    for rel in files:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")


def test_match_pattern_rules():
    assert match_pattern("out/bin/App.s3", "**/*App*.s3")
    assert match_pattern("App.s3", "**/*App*.s3")
    assert match_pattern("OUT/APP.S3", "**/*app*.s3")
    assert match_pattern("out/App.s3", "*.s3")
    assert not match_pattern("out/App.elf", "**/*App*.s3")


def test_single_candidate_is_selected(tmp_path):
    make_tree(tmp_path, ["out/SAF_App.s3", "out/saf_cm7_0.elf", "out/saf_cm7_1.elf", "out/readme.txt"])
    rows = build_mapping(load_profile(EXAMPLE), tmp_path)
    assert [(r.kind, r.target) for r in rows] == [
        ("program", "App"),
        ("application", "CM7_0"),
        ("application", "CM7_1"),
    ]
    assert all(r.ok for r in rows)
    assert rows[0].selected == tmp_path / "out" / "SAF_App.s3"


def test_multiple_candidates_not_selected(tmp_path):
    make_tree(tmp_path, ["a/App.s3", "b/App.s3", "x_cm7_0.elf", "x_cm7_1.elf"])
    rows = build_mapping(load_profile(EXAMPLE), tmp_path)
    program = rows[0]
    assert program.selected is None and not program.ok
    assert program.candidates == [tmp_path / "a" / "App.s3", tmp_path / "b" / "App.s3"]


def test_zero_candidates(tmp_path):
    make_tree(tmp_path, ["App.s3", "x_cm7_0.elf"])
    rows = build_mapping(load_profile(EXAMPLE), tmp_path)
    cm7_1 = rows[2]
    assert cm7_1.candidates == [] and cm7_1.selected is None


def test_candidates_for_kind(tmp_path):
    make_tree(tmp_path, ["a.s3", "b.SREC", "c.elf", "d.map"])
    assert [p.name for p in candidates_for_kind(tmp_path, "program")] == ["a.s3", "b.SREC"]
    assert [p.name for p in candidates_for_kind(tmp_path, "application")] == ["c.elf"]


def test_to_dict(tmp_path):
    make_tree(tmp_path, ["App.s3", "x_cm7_0.elf", "x_cm7_1.elf"])
    data = build_mapping(load_profile(EXAMPLE), tmp_path)[0].to_dict()
    assert data == {
        "kind": "program",
        "target": "App",
        "pattern": "**/*App*.s3",
        "candidates": [str(tmp_path / "App.s3")],
        "selected": str(tmp_path / "App.s3"),
    }
