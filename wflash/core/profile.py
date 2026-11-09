"""Project profile: which GitLab project to browse and how artifact files map to winIDEA entries."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from wflash.core.errors import ProfileError


Role = Literal["ffi", "cal", "bm", "fbl", "elf"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GitLabSpec(_Strict):
    project: str = Field(min_length=1)
    url: str | None = None  # default GitLab URL, may include the group of the projects
    job_filter: str = "*"


class SourceSpec(_Strict):
    """One artifact the firmware files come from; it has its own Load button."""

    label: str = Field(min_length=1)
    job_filter: str | None = None


class BuildSpec(_Strict):
    """Which CI jobs make up one build configuration of the application."""

    name: str = Field(min_length=1)
    ffi_job: str = Field(min_length=1)
    elf_job: str = Field(min_length=1)
    bm_job: str = Field(min_length=1)


class DebugSourceSpec(_Strict):
    """A repo of its own, for files that are flashed only with Advanced Debug."""

    project: str = Field(min_length=1)
    job: str | None = None


class ProgramSpec(_Strict):
    winidea_entry: str | None = Field(default=None, min_length=1)
    pattern: str = Field(min_length=1)
    source: str | None = None
    role: Role | None = None
    offset: int | None = Field(default=None, ge=0)


class ApplicationSpec(_Strict):
    winidea_app: str = Field(min_length=1)
    pattern: str = Field(min_length=1)
    source: str | None = None
    role: Role | None = None


class PostFlash(_Strict):
    reset: bool = True
    run: bool = False


class Timeouts(_Strict):
    download_s: int = Field(default=600, gt=0)


class Profile(_Strict):
    name: str = Field(min_length=1)
    gitlab: GitLabSpec
    sources: dict[str, SourceSpec] = Field(default_factory=dict)
    builds: list[BuildSpec] = Field(default_factory=list)
    debug_sources: dict[str, DebugSourceSpec] = Field(default_factory=dict)
    programs: list[ProgramSpec] = Field(min_length=1)
    applications: list[ApplicationSpec] = Field(default_factory=list)
    post_flash: PostFlash = Field(default_factory=PostFlash)
    timeouts: Timeouts = Field(default_factory=Timeouts)

    @model_validator(mode="after")
    def _unique_targets(self) -> "Profile":
        for label, names in (
            ("program entry", [p.winidea_entry for p in self.programs if p.winidea_entry]),
            ("application", [a.winidea_app for a in self.applications]),
        ):
            dupes = sorted({n for n in names if names.count(n) > 1})
            if dupes:
                raise ValueError(f"Duplicate {label}: {', '.join(dupes)}")
        return self

    @model_validator(mode="after")
    def _consistent_sources(self) -> "Profile":
        targets = [*self.programs, *self.applications]
        for target in targets:
            name = getattr(target, "winidea_entry", None) or getattr(target, "winidea_app", target.pattern)
            if target.source is None:
                if self.sources:
                    raise ValueError(f"Target '{name}' needs a source: the profile declares sources")
            elif target.source not in self.sources:
                raise ValueError(f"Target '{name}' names an unknown source '{target.source}'")
        unused = sorted(set(self.sources) - {t.source for t in targets})
        if unused:
            raise ValueError(f"Source with no target: {', '.join(unused)}")
        return self

    @model_validator(mode="after")
    def _consistent_builds(self) -> "Profile":
        for program in self.programs:
            if program.winidea_entry is None and program.role != "cal":
                raise ValueError("Only a cal row may omit winidea_entry")
        if self.builds:
            roles = {p.role for p in self.programs} | {a.role for a in self.applications}
            missing = {"ffi", "cal", "elf"} - roles
            if missing:
                raise ValueError(f"A profile with builds needs the roles: {', '.join(sorted(missing))}")
        return self

    def build(self, name: str) -> BuildSpec:
        for build in self.builds:
            if build.name == name:
                return build
        raise ProfileError(f"Unknown build '{name}' in profile {self.name}")

    def job_filter_for(self, source_id: str | None) -> str:
        spec = self.sources.get(source_id) if source_id else None
        return (spec.job_filter if spec else None) or self.gitlab.job_filter


def load_profile(path: Path) -> Profile:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise ProfileError(f"Cannot read profile {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ProfileError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileError(f"Profile {path} must be a mapping at the top level")
    try:
        return Profile.model_validate(data)
    except ValidationError as exc:
        raise ProfileError(f"Invalid profile {path}:\n{exc}") from exc


def list_profiles(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted([*directory.glob("*.yaml"), *directory.glob("*.yml")], key=lambda p: p.name)
