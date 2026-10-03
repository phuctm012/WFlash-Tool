"""Collect everything needed to debug a session remotely into one redacted zip file."""
from __future__ import annotations

import datetime
import importlib.metadata
import json
import platform
import sys
import traceback
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from wflash import __version__
from wflash.core.logging_setup import redact
from wflash.core.winidea_adapter import FileEntry


@dataclass
class DebugContext:
    profile_path: Path | None = None
    mapping: list[dict] = field(default_factory=list)
    adapter_info: dict[str, str] = field(default_factory=dict)
    snapshots: dict[str, dict] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def snapshot(self, label: str, programs: list[FileEntry], applications: list[FileEntry]) -> None:
        self.snapshots[label] = {
            "programs": [asdict(e) for e in programs],
            "applications": [asdict(e) for e in applications],
        }

    def add_error(self, exc: BaseException) -> None:
        self.errors.append("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


def _dist_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def collect_env_info() -> dict[str, str]:
    return {
        "wflash": __version__,
        "python": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "executable": sys.executable,
        "frozen": str(bool(getattr(sys, "frozen", False))),
        "PySide6": _dist_version("PySide6"),
        "isystem.connect": _dist_version("isystem.connect"),
    }


def create_debug_bundle(ctx: DebugContext, dest_dir: Path, log_file: Path | None) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = dest_dir / f"wflash_debug_{stamp}.zip"
    env = {**collect_env_info(), **{f"winidea.{k}": v for k, v in ctx.adapter_info.items()}}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        if log_file is not None and log_file.is_file():
            zf.writestr("log.txt", redact(log_file.read_text(encoding="utf-8", errors="replace")))
        zf.writestr("environment.json", redact(json.dumps(env, indent=2)))
        if ctx.profile_path is not None and ctx.profile_path.is_file():
            zf.writestr("profile.yaml", redact(ctx.profile_path.read_text(encoding="utf-8", errors="replace")))
        zf.writestr("mapping.json", redact(json.dumps(ctx.mapping, indent=2)))
        zf.writestr("workspace_snapshots.json", redact(json.dumps(ctx.snapshots, indent=2)))
        zf.writestr("errors.txt", redact("\n\n".join(ctx.errors) or "(no errors recorded)"))
    return path
