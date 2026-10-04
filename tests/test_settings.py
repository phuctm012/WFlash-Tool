import json
import keyring
import pytest

from wflash.core import settings as st
from wflash.core.errors import GitLabError
from wflash.core.settings import AppSettings


def test_round_trip(tmp_path):
    path = tmp_path / "s.json"
    AppSettings(gitlab_url="https://gl", max_cached_jobs=3, verbose=True).save(path)
    loaded = AppSettings.load(path)
    assert loaded.gitlab_url == "https://gl"
    assert loaded.max_cached_jobs == 3
    assert loaded.verbose is True


def test_missing_file_gives_defaults(tmp_path):
    assert AppSettings.load(tmp_path / "missing.json") == AppSettings()


def test_corrupt_file_gives_defaults(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{not json", encoding="utf-8")
    assert AppSettings.load(path) == AppSettings()


def test_unknown_keys_ignored(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"gitlab_url": "https://gl", "old_option": 1}), encoding="utf-8")
    assert AppSettings.load(path).gitlab_url == "https://gl"


def test_resolved_dirs(tmp_path):
    assert AppSettings(cache_dir=str(tmp_path)).resolved_cache_dir() == tmp_path
    assert AppSettings().resolved_cache_dir() == st.default_cache_dir()
    bundled = AppSettings().resolved_profiles_dir()
    assert bundled == st.bundled_profiles_dir()
    assert (bundled / "saf85xx_example.yaml").is_file()


def test_token_roundtrip_via_keyring(monkeypatch):
    store = {}
    monkeypatch.setattr(keyring, "set_password", lambda s, u, p: store.__setitem__((s, u), p))
    monkeypatch.setattr(keyring, "get_password", lambda s, u: store.get((s, u)))
    st.set_token("https://gl", "glpat-1")
    assert st.get_token("https://gl") == "glpat-1"
    assert store == {(st.KEYRING_SERVICE, "https://gl"): "glpat-1"}
    assert st.get_token("") is None


def test_get_token_keyring_error_returns_none(monkeypatch):
    def boom(service, user):
        raise keyring.errors.KeyringError("locked")

    monkeypatch.setattr(keyring, "get_password", boom)
    assert st.get_token("https://gl") is None


def test_wrong_typed_values_fall_back_to_defaults(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(
        json.dumps({"max_cached_jobs": "abc", "cache_dir": 5, "verbose": 1, "gitlab_url": None, "last_profile": "p"}),
        encoding="utf-8",
    )
    loaded = AppSettings.load(path)
    assert loaded.max_cached_jobs == 10
    assert loaded.cache_dir == ""
    assert loaded.verbose is False
    assert loaded.gitlab_url == ""
    assert loaded.last_profile == "p"


def test_bool_not_accepted_as_int(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"max_cached_jobs": True}), encoding="utf-8")
    assert AppSettings.load(path).max_cached_jobs == 10


def test_set_token_keyring_error_raises_gitlab_error(monkeypatch):
    def boom(service, user, pw):
        raise keyring.errors.KeyringError("locked")

    monkeypatch.setattr(keyring, "set_password", boom)
    with pytest.raises(GitLabError) as info:
        st.set_token("https://gl", "t")
    assert "keyring" in info.value.hint


def test_new_fields_default_values():
    s = AppSettings()
    assert s.verify_tls is True and s.dark_mode is False
    assert s.ci_project_overrides == {}
    assert (s.ci_job_name, s.package_project, s.package_name) == ("", "", "")


def test_new_fields_round_trip(tmp_path):
    path = tmp_path / "s.json"
    AppSettings(
        verify_tls=False,
        dark_mode=True,
        ci_project_overrides={"saf.yaml": "group/other"},
        ci_job_name="build_app",
        package_project="group/pkgs",
        package_name="saf85xx-firmware",
    ).save(path)
    loaded = AppSettings.load(path)
    assert loaded.verify_tls is False and loaded.dark_mode is True
    assert loaded.ci_project_overrides == {"saf.yaml": "group/other"}
    assert loaded.ci_job_name == "build_app"
    assert (loaded.package_project, loaded.package_name) == ("group/pkgs", "saf85xx-firmware")


def test_overrides_default_is_not_shared_between_instances():
    a, b = AppSettings(), AppSettings()
    a.ci_project_overrides["x.yaml"] = "g/p"
    assert b.ci_project_overrides == {}


@pytest.mark.parametrize(
    "bad",
    [["saf.yaml", "group/x"], "group/x", {"saf.yaml": 5}, {"saf.yaml": None}],
)
def test_wrong_typed_overrides_fall_back_to_default(tmp_path, caplog, bad):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"ci_project_overrides": bad, "dark_mode": True}), encoding="utf-8")
    with caplog.at_level("WARNING", logger="wflash.settings"):
        loaded = AppSettings.load(path)
    assert loaded.ci_project_overrides == {}
    assert loaded.dark_mode is True
    assert "ci_project_overrides" in caplog.text and "dict[str, str]" in caplog.text


def test_wrong_typed_bool_flags_fall_back(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"verify_tls": "no", "dark_mode": 1}), encoding="utf-8")
    loaded = AppSettings.load(path)
    assert loaded.verify_tls is True and loaded.dark_mode is False


def test_package_cache_sits_inside_the_cache_dir(tmp_path):
    assert AppSettings(cache_dir=str(tmp_path)).resolved_package_cache_dir() == tmp_path / "packages"
    assert AppSettings().resolved_package_cache_dir() == st.default_cache_dir() / st.PACKAGES_SUBDIR
