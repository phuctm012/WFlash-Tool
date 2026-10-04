"""On-disk cache of downloaded firmware: <root>/<project_id>/<job_id>/files.

The same layout caches Package Registry downloads under its own root
(`<cache_dir>/packages`, key = package id). Only digit-named directories belong to a
cache, so the artifact cache never touches the `packages` folder next to its entries.
"""
from __future__ import annotations

import datetime
import os
import shutil
import zipfile
from pathlib import Path
from typing import Callable

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

    def store_file(self, project_id: int, job_id: int, file_path: Path) -> Path:
        """Cache one downloaded file as-is (a package file that is not a zip)."""

        def fill(files_dir: Path) -> None:
            try:
                shutil.copy2(file_path, files_dir / file_path.name)
            except OSError as exc:
                raise ArtifactError(
                    f"Failed to cache file {file_path.name}: {exc}",
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
