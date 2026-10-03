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
