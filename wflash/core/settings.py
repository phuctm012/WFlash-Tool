"""User settings stored as JSON in the user config dir; GitLab token stored in the OS keyring."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import keyring
import keyring.errors

from wflash.core.errors import GitLabError
from wflash.core.logging_setup import get_logger

KEYRING_SERVICE = "WFlash-GitLab"
PACKAGES_SUBDIR = "packages"  # Package Registry downloads are cached in <cache_dir>/packages
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


@dataclass
class AppSettings:
    gitlab_url: str = ""
    ca_bundle: str = ""
    cache_dir: str = ""
    max_cached_jobs: int = 10
    profiles_dir: str = ""
    last_profile: str = ""
    verbose: bool = False
    verify_tls: bool = True
    dark_mode: bool = False
    # Profile file name (e.g. "saf.yaml") -> CI project typed in Load from GitLab.
    ci_project_overrides: dict[str, str] = field(default_factory=dict)
    ci_job_name: str = ""
    package_project: str = ""
    package_name: str = ""

    def resolved_cache_dir(self) -> Path:
        return Path(self.cache_dir) if self.cache_dir else default_cache_dir()

    def resolved_package_cache_dir(self) -> Path:
        return self.resolved_cache_dir() / PACKAGES_SUBDIR

    def resolved_profiles_dir(self) -> Path:
        return Path(self.profiles_dir) if self.profiles_dir else bundled_profiles_dir()

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
            if f.name not in data:
                continue
            value, default = data[f.name], getattr(defaults, f.name)
            if _same_type(value, default):
                values[f.name] = value
            else:
                log.warning("Ignoring setting %r: expected %s, got %r", f.name, _type_name(default), value)
        return cls(**values)

    def save(self, path: Path | None = None) -> None:
        path = path or settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


def get_token(gitlab_url: str) -> str | None:
    if not gitlab_url:
        return None
    try:
        return keyring.get_password(KEYRING_SERVICE, gitlab_url)
    except keyring.errors.KeyringError as exc:
        log.warning("Cannot read GitLab token from keyring: %s", exc)
        return None


def set_token(gitlab_url: str, token: str) -> None:
    try:
        keyring.set_password(KEYRING_SERVICE, gitlab_url, token)
    except keyring.errors.KeyringError as exc:
        raise GitLabError(
            "Cannot store the GitLab token",
            hint="The system keyring is unavailable or locked. Unlock it (Windows Credential Manager) and try again.",
        ) from exc
