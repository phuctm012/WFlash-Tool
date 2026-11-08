"""What a flash will change in the workspace, decided before anything is changed. No winIDEA here."""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

from wflash.core.errors import MappingError
from wflash.core.profile import Profile

DEBUG_ROLES = {"bm", "fbl"}


@dataclass(frozen=True)
class ProgramRow:
    index: int
    name: str
    path: str
    enabled: bool
    offset: int


@dataclass(frozen=True)
class SymbolRow:
    app_index: int
    file_index: int
    name: str
    path: str
    enabled: bool


@dataclass(frozen=True)
class RowChange:
    row: ProgramRow | SymbolRow
    new_path: str | None  # None: the path stays
    tick: bool


@dataclass(frozen=True)
class FlashPlan:
    programs: list[RowChange]
    symbols: list[RowChange]


def find_cal_files(workspace_dir: Path, pattern: str) -> list[Path]:
    return sorted(p for p in workspace_dir.glob(pattern) if p.is_file())


def _find_program(rows, spec) -> ProgramRow:
    if spec.role == "cal":
        found = [r for r in rows if fnmatch.fnmatch(r.name.lower(), spec.pattern.lower())]
        label = spec.pattern
    else:
        found = [r for r in rows if r.name.casefold() == spec.winidea_entry.casefold()]
        label = spec.winidea_entry
    if len(found) != 1:
        where = f" at offset 0x{spec.offset:X}" if spec.offset is not None else ""
        raise MappingError(
            f"The workspace needs exactly one Download Files row for {label}; it has {len(found)}.",
            hint=f"Fix it in Hardware > (your flash device) > Configure…: {label}{where}, in flash order.",
        )
    return found[0]


def _file(files: dict[str, Path], target: str, role: str | None) -> str:
    path = files.get(target)
    if path is None:
        raise MappingError(f"{target} is not loaded.", hint=f"Load the {str(role).upper()} firmware first.")
    return str(path)


def make_plan(profile: Profile, advanced: bool, program_rows, symbol_rows, files: dict[str, Path], cal_file: str) -> FlashPlan:
    programs: list[RowChange] = []
    last_index = -1
    for spec in profile.programs:
        row = _find_program(program_rows, spec)
        if row.index < last_index:
            order = " > ".join(str(p.role).upper() for p in profile.programs)
            raise MappingError(f"Download Files are in the wrong order; WFlash needs {order}.", hint="Reorder the rows in winIDEA.")
        last_index = row.index
        if spec.offset is not None and row.offset != spec.offset:
            raise MappingError(
                f"{row.name} has offset 0x{row.offset:X}, but it must be 0x{spec.offset:X}.",
                hint="Correct the offset in winIDEA.",
            )
        off = spec.role in DEBUG_ROLES and not advanced
        if spec.role == "cal":
            if not cal_file:
                raise MappingError("No CAL file was found next to the workspace.", hint=f"Copy a {spec.pattern} file there.")
            new_path = None if row.path == cal_file else cal_file
        else:
            new_path = None if off else _file(files, spec.winidea_entry, spec.role)
        programs.append(RowChange(row, new_path, not off))

    managed = {change.row.index for change in programs}
    extra = [r.name for r in program_rows if r.enabled and r.index not in managed]
    if extra:
        raise MappingError(
            f"Other rows are ticked and would be flashed too: {', '.join(extra)}.",
            hint="Untick them in winIDEA, or add them to the profile.",
        )

    symbols: list[RowChange] = []
    by_name = {r.name: r for r in symbol_rows}
    for spec in profile.applications:
        off = spec.role in DEBUG_ROLES and not advanced
        row = by_name.get(spec.winidea_app)
        if row is None:
            if off:
                continue  # nothing to untick
            raise MappingError(f"Symbol Files has no {spec.winidea_app}.", hint="Add it in Debug > Configure Session.")
        symbols.append(RowChange(row, None if off else _file(files, spec.winidea_app, spec.role), not off))
    return FlashPlan(programs, symbols)
