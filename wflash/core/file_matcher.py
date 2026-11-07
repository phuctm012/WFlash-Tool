"""Match files from an extracted artifact to the winIDEA entries declared in a profile."""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from wflash.core.profile import Profile

Kind = Literal["program", "application"]
PROGRAM_SUFFIXES = (".s3", ".srec", ".s19", ".mot")
SYMBOL_SUFFIXES = (".elf",)


@dataclass
class MappingRow:
    kind: Kind
    target: str
    pattern: str
    candidates: list[Path] = field(default_factory=list)
    selected: Path | None = None
    source: str | None = None  # the profile's source id, when it declares sources
    root: Path | None = None  # that source's folder; files are shown relative to it

    @property
    def ok(self) -> bool:
        return self.selected is not None

    def to_dict(self) -> dict:
        data = {
            "kind": self.kind,
            "target": self.target,
            "pattern": self.pattern,
            "candidates": [str(p) for p in self.candidates],
            "selected": str(self.selected) if self.selected else None,
        }
        if self.source is not None:
            data["source"] = self.source
        return data


def match_pattern(rel_posix: str, pattern: str) -> bool:
    rel = rel_posix.lower()
    pat = pattern.lower()
    if fnmatch.fnmatchcase(rel, pat):
        return True
    return pat.startswith("**/") and fnmatch.fnmatchcase(rel, pat[3:])


def _files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


def _row(kind: Kind, target: str, pattern: str, root: Path, files: list[Path]) -> MappingRow:
    candidates = [p for p in files if match_pattern(p.relative_to(root).as_posix(), pattern)]
    selected = candidates[0] if len(candidates) == 1 else None
    return MappingRow(kind, target, pattern, candidates, selected)


def build_mapping(profile: Profile, root: Path) -> list[MappingRow]:
    files = _files(root)
    rows = [_row("program", s.winidea_entry, s.pattern, root, files) for s in profile.programs if s.winidea_entry]
    rows += [_row("application", s.winidea_app, s.pattern, root, files) for s in profile.applications]
    return rows


def _targets(profile: Profile) -> list[tuple[Kind, str, str, str | None]]:
    return [("program", s.winidea_entry, s.pattern, s.source) for s in profile.programs if s.winidea_entry] + [
        ("application", s.winidea_app, s.pattern, s.source) for s in profile.applications
    ]


def build_mapping_for_source(profile: Profile, source_id: str, root: Path) -> list[MappingRow]:
    """Only that source's rows, matched only against its own files: same names elsewhere cannot match."""
    files = _files(root)
    rows = []
    for kind, target, pattern, source in _targets(profile):
        if source == source_id:
            row = _row(kind, target, pattern, root, files)
            row.source, row.root = source_id, root
            rows.append(row)
    return rows


def pending_rows(profile: Profile) -> list[MappingRow]:
    """Every target in profile order with no file yet, for sources that are not loaded."""
    return [MappingRow(kind, target, pattern, source=source) for kind, target, pattern, source in _targets(profile)]


def candidates_for_kind(root: Path, kind: str) -> list[Path]:
    suffixes = PROGRAM_SUFFIXES if kind == "program" else SYMBOL_SUFFIXES
    return [p for p in _files(root) if p.suffix.lower() in suffixes]
