"""User settings stored as JSON in the user config dir; GitLab token stored in the OS keyring."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import keyring
import keyring.errors

from wflash.core.bench_switch import DEFAULT_BENCH, DEFAULT_ECU, BenchConfig
from wflash.core.errors import GitLabError
from wflash.core.gitlab_url import split_gitlab_url
from wflash.core.logging_setup import get_logger

KEYRING_SERVICE = "WFlash-GitLab"
# The SUZ05 profile was renamed (2026-11-09); settings saved under the old file name move over.
RENAMED_PROFILES = ("suz05_m7_ffi.yaml", "suz05.yaml")
log = get_logger("settings")


def config_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "WFlash"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "WFlash"
    return Path.home() / ".config" / "wflash"


def default_cache_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "WFlash" / "cache"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "WFlash"
    return Path.home() / ".cache" / "wflash"


def bundled_profiles_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "profiles"
    return Path(__file__).resolve().parents[2] / "profiles"


def settings_path() -> Path:
    return config_dir() / "settings.json"


def _same_type(value: object, default: object) -> bool:
    # bool is a subclass of int, so require the exact type; a dict must map str -> str.
    if type(value) is not type(default):
        return False
    if isinstance(default, dict):
        return all(isinstance(k, str) and isinstance(v, str) for k, v in value.items())
    return True


def _type_name(default: object) -> str:
    return "dict[str, str]" if isinstance(default, dict) else type(default).__name__


NOT_LOADED = {"profiles_dir"}  # an old file may still hold a folder chosen before it left the Setting tab


@dataclass
class AppSettings:
    gitlab_url: str = ""
    ca_bundle: str = ""  # no longer used (2026-11-09): the system certificate store is; kept so old files load
    cache_dir: str = ""
    max_cached_jobs: int = 10
    # Not saved or loaded: the app always uses its bundled profiles (user decision, 2026-11-10).
    # Only tests and the stress test set it, to point at profiles of their own.
    profiles_dir: str = ""
    last_profile: str = ""
    verbose: bool = False
    verify_tls: bool = True
    dark_mode: bool = False
    # Profile file name (e.g. "saf.yaml") -> CI project typed in Load from GitLab.
    ci_project_overrides: dict[str, str] = field(default_factory=dict)
    ci_job_name: str = ""
    # Profile file name -> the developer's source repo folder, and the last build chosen.
    source_repos: dict[str, str] = field(default_factory=dict)
    last_build: dict[str, str] = field(default_factory=dict)
    # GitLab tab (2026-11-09). Keys "<profile file>#<part>", part = app | bm | fbl.
    gitlab_urls: dict[str, str] = field(default_factory=dict)  # profile file -> URL typed in Setting
    part_repos: dict[str, str] = field(default_factory=dict)
    part_projects: dict[str, str] = field(default_factory=dict)  # only when it differs from the profile
    part_modes: dict[str, str] = field(default_factory=dict)  # "commit" | "manual"
    part_manual: dict[str, str] = field(default_factory=dict)  # JSON of the job chosen by hand
    reset_target: bool = True
    run_after_reset: bool = False
    verify_samples: bool = False
    advanced_debug: bool = False
    window_geometry: str = ""  # base64 of QWidget.saveGeometry()
    last_tab: int = 0
    # Bench power and JTAG through Switch Debugger (2026-11-11). Off unless the user turns it on.
    # Address, port, power-off and boot times are fixed since 2026-11-12; older files' values are ignored.
    bench_enabled: bool = False
    bench_name: str = DEFAULT_BENCH  # a key of bench_switch.BENCHES
    bench_ecu: int = DEFAULT_ECU

    def bench_config(self) -> BenchConfig:
        return BenchConfig.for_ecu(self.bench_ecu, self.bench_name)

    def resolved_cache_dir(self) -> Path:
        return Path(self.cache_dir) if self.cache_dir else default_cache_dir()

    def resolved_profiles_dir(self) -> Path:
        return Path(self.profiles_dir) if self.profiles_dir else bundled_profiles_dir()

    def gitlab_url_for(self, profile_file: str, profile_url: str | None) -> str:
        """The URL typed for this profile, else the profile's own, else the one of older versions."""
        return self.gitlab_urls.get(profile_file, "") or (profile_url or "") or self.gitlab_url

    def migrate(self) -> None:
        """Bring settings of older versions forward; never overwrites a value already set."""
        old, new = RENAMED_PROFILES
        for mapping in (self.source_repos, self.last_build, self.ci_project_overrides):
            if old in mapping and new not in mapping:
                mapping[new] = mapping[old]
        if self.last_profile == old:
            self.last_profile = new
        for profile_file, repo in self.source_repos.items():
            self.part_repos.setdefault(f"{profile_file}#app", repo)

    @classmethod
    def load(cls, path: Path | None = None) -> "AppSettings":
        path = path or settings_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError) as exc:
            log.warning("Ignoring unreadable settings file %s: %s", path, exc)
            return cls()
        if not isinstance(data, dict):
            log.warning("Ignoring settings file %s: not a JSON object", path)
            return cls()
        defaults = cls()
        values = {}
        for f in fields(cls):
            if f.name not in data or f.name in NOT_LOADED:
                continue
            value, default = data[f.name], getattr(defaults, f.name)
            if _same_type(value, default):
                values[f.name] = value
            else:
                log.warning("Ignoring setting %r: expected %s, got %r", f.name, _type_name(default), value)
        loaded = cls(**values)
        loaded.migrate()
        return loaded

    def save(self, path: Path | None = None) -> None:
        path = path or settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {key: value for key, value in asdict(self).items() if key not in NOT_LOADED}
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_token(gitlab_url: str) -> str | None:
    """Token of the GitLab host of `gitlab_url`; older versions stored it under the full URL."""
    if not gitlab_url:
        return None
    host = split_gitlab_url(gitlab_url)[0]
    try:
        for key in dict.fromkeys((host, gitlab_url.strip().rstrip("/"), gitlab_url)):
            if key:
                token = keyring.get_password(KEYRING_SERVICE, key)
                if token:
                    return token
        return None
    except keyring.errors.KeyringError as exc:
        log.warning("Cannot read GitLab token from keyring: %s", exc)
        return None


def set_token(gitlab_url: str, token: str) -> None:
    """Stored under the host, so changing the group in the URL keeps the token."""
    try:
        keyring.set_password(KEYRING_SERVICE, split_gitlab_url(gitlab_url)[0] or gitlab_url, token)
    except keyring.errors.KeyringError as exc:
        raise GitLabError(
            "Cannot store the GitLab token",
            hint="The system keyring is unavailable or locked. Unlock it (Windows Credential Manager) and try again.",
        ) from exc
