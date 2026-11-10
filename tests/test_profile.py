from pathlib import Path

import pytest

from wflash.core.errors import ProfileError
from wflash.core.profile import list_profiles, load_profile

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "profiles" / "saf85xx_example.yaml"

MINIMAL = """
name: P
gitlab: {project: g/p}
programs:
  - {winidea_entry: App, pattern: "*.s3"}
"""


def write(tmp_path, text, name="p.yaml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_example_profile_loads():
    profile = load_profile(EXAMPLE)
    assert profile.name == "SAF85xx_Radar"
    assert profile.gitlab.project == "group/saf85xx-sw"
    assert [p.winidea_entry for p in profile.programs] == ["App"]
    assert [a.winidea_app for a in profile.applications] == ["CM7_0", "CM7_1"]
    assert profile.post_flash.reset is True and profile.post_flash.run is False
    assert profile.timeouts.download_s == 600


def test_defaults_applied(tmp_path):
    profile = load_profile(write(tmp_path, MINIMAL))
    assert profile.gitlab.job_filter == "*"
    assert profile.applications == []
    assert profile.post_flash.reset is True
    assert profile.timeouts.download_s == 600


def test_missing_programs_rejected(tmp_path):
    with pytest.raises(ProfileError, match="programs"):
        load_profile(write(tmp_path, "name: P\ngitlab: {project: g/p}\n"))


def test_unknown_key_rejected(tmp_path):
    with pytest.raises(ProfileError, match="typo_key"):
        load_profile(write(tmp_path, MINIMAL + "typo_key: 1\n"))


def test_duplicate_targets_rejected(tmp_path):
    text = MINIMAL + '  - {winidea_entry: App, pattern: "*.s3"}\n'
    with pytest.raises(ProfileError, match="Duplicate"):
        load_profile(write(tmp_path, text))


def test_invalid_yaml_rejected(tmp_path):
    with pytest.raises(ProfileError, match="Invalid YAML"):
        load_profile(write(tmp_path, "name: [unclosed"))


def test_non_mapping_rejected(tmp_path):
    with pytest.raises(ProfileError, match="mapping"):
        load_profile(write(tmp_path, "- a\n- b\n"))


def test_missing_file_rejected(tmp_path):
    with pytest.raises(ProfileError, match="Cannot read"):
        load_profile(tmp_path / "nope.yaml")


def test_non_utf8_file_rejected(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(ProfileError, match="Cannot read"):
        load_profile(path)


def test_list_profiles_sorted(tmp_path):
    write(tmp_path, MINIMAL, "b.yaml")
    write(tmp_path, MINIMAL, "a.yml")
    (tmp_path / "notes.txt").write_text("x")
    assert [p.name for p in list_profiles(tmp_path)] == ["a.yml", "b.yaml"]


def test_list_profiles_missing_dir(tmp_path):
    assert list_profiles(tmp_path / "missing") == []




MULTI = """
name: multi
gitlab: {project: group/app}
sources:
  ffi: {label: "FFI (.s3)", job_filter: "build_ffi*"}
  m7: {label: "M7 (.elf)"}
programs:
  - {winidea_entry: "a.s3", source: ffi, pattern: "**/a.s3"}
applications:
  - {winidea_app: "App_M7/b.elf", source: m7, pattern: "**/b.elf"}
"""


def _load(tmp_path, text):
    path = tmp_path / "p.yaml"
    path.write_text(text, encoding="utf-8")
    return load_profile(path)


def test_profile_sources_are_optional(tmp_path):
    profile = _load(tmp_path, "name: x\ngitlab: {project: g/a}\nprograms:\n  - {winidea_entry: a, pattern: '*'}\n")
    assert profile.sources == {} and profile.programs[0].source is None


def test_profile_declares_sources_and_targets_name_them(tmp_path):
    profile = _load(tmp_path, MULTI)
    assert profile.sources["ffi"].label == "FFI (.s3)"
    assert profile.job_filter_for("ffi") == "build_ffi*"
    assert profile.job_filter_for("m7") == "*"
    assert profile.programs[0].source == "ffi"


@pytest.mark.parametrize(
    "old, new, message",
    [
        ("source: m7, pattern", "source: nope, pattern", "unknown source"),
        ("source: m7, pattern", "pattern", "needs a source"),
        ("  m7: {label: \"M7 (.elf)\"}\n", "  m7: {label: \"M7 (.elf)\"}\n  x: {label: X}\n", "no target"),
    ],
)
def test_profile_rejects_inconsistent_sources(tmp_path, old, new, message):
    with pytest.raises(ProfileError, match=message):
        _load(tmp_path, MULTI.replace(old, new))


def test_profile_rejects_a_target_source_without_sources(tmp_path):
    text = "name: x\ngitlab: {project: g/a}\nprograms:\n  - {winidea_entry: a, source: s, pattern: '*'}\n"
    with pytest.raises(ProfileError, match="unknown source"):
        _load(tmp_path, text)


def test_suz05_profile_declares_builds_in_flash_order():
    profile = load_profile(ROOT / "profiles" / "suz05.yaml")
    assert [p.role for p in profile.programs] == ["ffi", "cal", "bm", "fbl"]
    assert profile.programs[3].offset == 0xF1000
    assert profile.build("strx_3p5mb_no_HTSM").bm_job == "build_STRX_3P5MB"
    assert profile.build("stingray_uds27_bypass").elf_job == "build_STINGRAY_3P5MB_UDS27_BYPASS"
    assert profile.debug_sources["fbl"].job == "build"
    assert len(profile.builds) == 4


BUILDS = """
name: b
gitlab: {project: g/a}
builds:
  - {name: one, ffi_job: f, elf_job: e, bm_job: m}
programs:
  - {role: ffi, winidea_entry: a.s3, pattern: "**/a.s3"}
  - {role: cal, pattern: "*_CAL_*.sre"}
applications:
  - {role: elf, winidea_app: "App/b.elf", pattern: "**/b.elf"}
"""


def test_only_a_cal_row_may_omit_its_entry(tmp_path):
    with pytest.raises(ProfileError, match="winidea_entry"):
        _load(tmp_path, BUILDS.replace('winidea_entry: a.s3, ', ""))


def test_builds_require_ffi_cal_and_elf_roles(tmp_path):
    with pytest.raises(ProfileError, match="cal"):
        _load(tmp_path, BUILDS.replace('  - {role: cal, pattern: "*_CAL_*.sre"}\n', ""))


def test_unknown_build_is_a_profile_error(tmp_path):
    with pytest.raises(ProfileError):
        _load(tmp_path, BUILDS).build("nope")


def test_suz05_profile_has_the_gitlab_url_with_its_group_and_short_project_names():
    profile = load_profile(ROOT / "profiles" / "suz05.yaml")
    assert profile.name == "SUZ05"
    assert profile.gitlab.url == "https://gitlab.hella.com/alm/projects_group/e-ad_group/e-ad_radar_cust_suz05_group"
    assert profile.gitlab.project == "SUZ05_APP_Application_Software-Impl"
    assert profile.debug_sources["bm"].project == "SUZ05_BM_Boot_Manager-Impl"
    assert profile.debug_sources["fbl"].job == "build"


def test_suz05_default_build_is_stingray_3p5mb_no_htsm():
    """The first build is selected when none was saved (user decision, 2026-11-10)."""
    profile = load_profile(Path(__file__).resolve().parents[1] / "profiles" / "suz05.yaml")
    assert profile.builds[0].name == "stingray_3p5mb_no_HTSM"
