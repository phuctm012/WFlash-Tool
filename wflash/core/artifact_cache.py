"""On-disk cache of downloaded firmware.

ArtifactCache: <root>/<project_id>/<job_id>/files, for firmware loaded by hand. Only digit-named
directories belong to it. NamedArtifactCache: <root>/<branch>/<commit>_<build>/<part>, for firmware
loaded by commit; the name says what is being debugged. Anything else in the root is left alone.
"""
from __future__ import annotations

import datetime
import hashlib
import os
import re
import shutil
import zipfile
from pathlib import Path, PurePath
from typing import Callable, Iterable

from wflash.core.errors import ArtifactError
from wflash.core.logging_setup import get_logger

MARKER = ".complete"
log = get_logger("cache")


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    dest_resolved = dest.resolve()
    for info in zf.infolist():
        target = (dest / info.filename).resolve()
        if not target.is_relative_to(dest_resolved):
            raise ArtifactError(
                f"Unsafe path in artifact zip: {info.filename}",
                hint="The artifact contains unsafe file paths; do not use it — check the CI job output."
            )
    zf.extractall(dest)


def _is_cache_dir(path: Path) -> bool:
    return path.name.isdigit() and path.is_dir() and not path.is_symlink()


class ArtifactCache:
    def __init__(self, root: Path, max_jobs: int = 10) -> None:
        self.root = root
        self.max_jobs = max_jobs

    def job_dir(self, project_id: int, job_id: int) -> Path:
        return self.root / str(project_id) / str(job_id)

    def has(self, project_id: int, job_id: int) -> bool:
        """Like get() but without marking the entry as recently used (for "Cached" labels)."""
        return (self.job_dir(project_id, job_id) / MARKER).is_file()

    def get(self, project_id: int, job_id: int) -> Path | None:
        job = self.job_dir(project_id, job_id)
        marker = job / MARKER
        if not marker.is_file():
            return None
        os.utime(marker)
        return job / "files"

    def store_zip(self, project_id: int, job_id: int, zip_path: Path) -> Path:
        def fill(files_dir: Path) -> None:
            try:
                with zipfile.ZipFile(zip_path) as zf:
                    _safe_extract(zf, files_dir)
            except zipfile.BadZipFile as exc:
                raise ArtifactError(
                    f"Artifact is not a valid zip file: {exc}",
                    hint="Download the artifact again; it may be corrupt."
                ) from exc
            except OSError as exc:
                raise ArtifactError(
                    f"Failed to extract artifact: {exc}",
                    hint="Check free disk space and path length, then retry."
                ) from exc

        return self._store(project_id, job_id, fill)

    def _store(self, project_id: int, job_id: int, fill: Callable[[Path], None]) -> Path:
        final = self.job_dir(project_id, job_id)
        tmp = final.with_name(final.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        files_dir = tmp / "files"
        try:
            files_dir.mkdir(parents=True)
            fill(files_dir)
            (tmp / MARKER).write_text(datetime.datetime.now().isoformat(), encoding="utf-8")
            shutil.rmtree(final, ignore_errors=True)
            try:
                tmp.rename(final)
            except OSError as exc:
                raise ArtifactError(
                    f"Failed to cache artifact (file may be locked): {exc}",
                    hint="Close programs that may hold files in the cache folder (winIDEA, Explorer), "
                         "then retry or clear the cache."
                ) from exc
        except ArtifactError:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        except Exception as exc:
            shutil.rmtree(tmp, ignore_errors=True)
            raise ArtifactError(f"Unexpected error while caching artifact: {exc}") from exc
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        log.info("Cached artifact for project %s job %s at %s", project_id, job_id, final)
        self.prune()
        return final / "files"

    def _project_dirs(self) -> list[Path]:
        if not self.root.is_dir():
            return []
        return [p for p in self.root.iterdir() if _is_cache_dir(p)]

    def entries(self) -> list[Path]:
        return [
            m.parent
            for project in self._project_dirs()
            for m in project.glob(f"*/{MARKER}")
            if m.parent.name.isdigit()
        ]

    def prune(self) -> None:
        jobs = sorted(self.entries(), key=lambda d: (d / MARKER).stat().st_mtime, reverse=True)
        for old in jobs[self.max_jobs:]:
            log.info("Pruning cached artifact %s", old)
            shutil.rmtree(old, ignore_errors=True)
        for project in self._project_dirs():
            for tmp_dir in project.glob("*.tmp"):
                log.info("Cleaning leftover temporary directory %s", tmp_dir)
                shutil.rmtree(tmp_dir, ignore_errors=True)
            for job_dir in project.iterdir():
                if job_dir.is_dir() and job_dir.name.isdigit() and not (job_dir / MARKER).exists():
                    log.info("Cleaning incomplete job directory %s", job_dir)
                    shutil.rmtree(job_dir, ignore_errors=True)

    def clear(self) -> None:
        """Delete only cache-layout entries (<root>/<digits>/<digits>[.tmp]); never root or anything else."""
        log.info("Clearing artifact cache %s", self.root)
        failures: list[OSError] = []
        for project in self._project_dirs():
            for entry in project.iterdir():
                name = entry.name.removesuffix(".tmp")
                if not (name.isdigit() and entry.is_dir() and not entry.is_symlink()):
                    continue
                try:
                    shutil.rmtree(entry)
                except OSError as exc:
                    log.warning("Cannot remove cache entry %s: %s", entry, exc)
                    failures.append(exc)
            try:
                project.rmdir()  # only succeeds when it is now empty
            except OSError:
                pass
        if failures:
            raise ArtifactError(
                f"Could not clear {len(failures)} cached artifact(s)",
                hint="Close programs that may hold files in the cache folder (winIDEA, Explorer), then try again.",
            ) from failures[0]


BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MAX_SEGMENT = 60


def safe_segment(text: str) -> str:
    cleaned = BAD_CHARS.sub("_", text).strip(" .") or "_"
    if len(cleaned) > MAX_SEGMENT:  # Windows limits the whole path
        digest = hashlib.sha1(cleaned.encode("utf-8")).hexdigest()[:8]
        cleaned = f"{cleaned[:MAX_SEGMENT - 9]}_{digest}"
    return cleaned


def build_cache_path(branch: str, commit: str, build: str, part: str) -> PurePath:
    return PurePath(safe_segment(branch or "detached"), safe_segment(f"{commit[:8]}_{build}"), part)


def debug_cache_path(role: str, ref: str, commit: str, job: str) -> PurePath:
    return PurePath(role.upper(), safe_segment(ref), safe_segment(f"{commit[:8]}_{job}"))


class NamedArtifactCache:
    """<root>/<rel>/ holds the extracted files and a marker; the name says what is in it."""

    def __init__(self, root: Path, max_entries: int = 10) -> None:
        self.root = root
        self.max_entries = max_entries

    def has(self, rel: PurePath) -> bool:
        return (self.root / rel / MARKER).is_file()

    def get(self, rel: PurePath) -> Path | None:
        if not self.has(rel):
            return None
        os.utime(self.root / rel / MARKER)
        return self.root / rel

    def store_zip(self, rel: PurePath, zip_path: Path, keep: Iterable[PurePath] = ()) -> Path:
        final = self.root / rel
        tmp = final.with_name(final.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            tmp.mkdir(parents=True)
            with zipfile.ZipFile(zip_path) as zf:
                _safe_extract(zf, tmp)
            (tmp / MARKER).write_text(datetime.datetime.now().isoformat(), encoding="utf-8")
            shutil.rmtree(final, ignore_errors=True)
            tmp.rename(final)
        except zipfile.BadZipFile as exc:
            shutil.rmtree(tmp, ignore_errors=True)
            raise ArtifactError("The artifact is not a valid zip file.", hint="Download it again.") from exc
        except OSError as exc:
            shutil.rmtree(tmp, ignore_errors=True)
            log.error("Failed to cache %s: %s", rel, exc)
            raise ArtifactError(
                "Failed to store the artifact.",
                hint="Check free disk space, and close programs that hold files in the cache folder.",
            ) from exc
        self.prune(keep=[rel, *keep])
        return final

    def entries(self) -> list[Path]:
        return [marker.parent for marker in self.root.rglob(MARKER)] if self.root.is_dir() else []

    def prune(self, keep: Iterable[PurePath] = ()) -> None:
        kept = {self.root / rel for rel in keep}
        ordered = sorted(self.entries(), key=lambda d: (d / MARKER).stat().st_mtime, reverse=True)
        for old in ordered[self.max_entries:]:
            if old not in kept:
                log.info("Pruning cached artifact %s", old)
                shutil.rmtree(old, ignore_errors=True)

    def clear(self) -> None:
        """Remove every entry, then the folders left empty. Anything else in the root stays."""
        for entry in self.entries():
            shutil.rmtree(entry, ignore_errors=True)
        ArtifactCache(self.root).clear()
        for folder in sorted((p for p in self.root.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
            if not any(folder.iterdir()):
                folder.rmdir()
