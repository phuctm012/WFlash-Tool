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


def test_list_profiles_sorted(tmp_path):
    write(tmp_path, MINIMAL, "b.yaml")
    write(tmp_path, MINIMAL, "a.yml")
    (tmp_path / "notes.txt").write_text("x")
    assert [p.name for p in list_profiles(tmp_path)] == ["a.yml", "b.yaml"]


def test_list_profiles_missing_dir(tmp_path):
    assert list_profiles(tmp_path / "missing") == []
