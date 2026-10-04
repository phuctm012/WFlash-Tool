"""Where the loaded firmware came from: shown on the source card and written to the debug bundle."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

SourceKind = Literal["ci", "package"]


@dataclass(frozen=True)
class FirmwareSource:
    kind: SourceKind
    project: str  # GitLab project path (or id) the firmware was downloaded from
    title: str  # "CI artifact · job #7 build_app" / "Package · saf85xx-firmware 1.4.0"
    detail: str  # "group/saf85xx-sw · main · pipeline #100" / "group/pkgs · 2026-10-04 09:20"
    cache_note: str  # "Cached · 3 files" / "Downloaded · 3 files"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def files_note(from_cache: bool, count: int) -> str:
    """`files_note(True, 3)` -> "Cached · 3 files"; `files_note(False, 1)` -> "Downloaded · 1 file"."""
    origin = "Cached" if from_cache else "Downloaded"
    return f"{origin} · {count} file{'' if count == 1 else 's'}"


def short_timestamp(iso: str) -> str:
    """'2026-10-04T09:20:11.123Z' -> '2026-10-04 09:20'; anything unexpected is returned unchanged."""
    text = str(iso or "")
    if len(text) >= 16 and text[10] == "T":
        return text[:10] + " " + text[11:16]
    return text
