"""On-disk cache of extracted GitLab job artifacts: <root>/<project_id>/<job_id>/files."""
from __future__ import annotations

import datetime
import os
import shutil
import zipfile
from pathlib import Path

from wflash.core.errors import ArtifactError
from wflash.core.logging_setup import get_logger

MARKER = ".complete"
log = get_logger("cache")


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    dest_resolved = dest.resolve()
    for info in zf.infolist():
        target = (dest / info.filename).resolve()
        if not target.is_relative_to(dest_resolved):
            raise ArtifactError(f"Unsafe path in artifact zip: {info.filename}")
    zf.extractall(dest)


class ArtifactCache:
    def __init__(self, root: Path, max_jobs: int = 10) -> None:
        self.root = root
        self.max_jobs = max_jobs

    def job_dir(self, project_id: int, job_id: int) -> Path:
        return self.root / str(project_id) / str(job_id)

    def get(self, project_id: int, job_id: int) -> Path | None:
        job = self.job_dir(project_id, job_id)
        marker = job / MARKER
        if not marker.is_file():
            return None
        os.utime(marker)
        return job / "files"

    def store_zip(self, project_id: int, job_id: int, zip_path: Path) -> Path:
        final = self.job_dir(project_id, job_id)
        tmp = final.with_name(final.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        files_dir = tmp / "files"
        files_dir.mkdir(parents=True)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                _safe_extract(zf, files_dir)
        except zipfile.BadZipFile as exc:
            shutil.rmtree(tmp, ignore_errors=True)
            raise ArtifactError(f"Artifact is not a valid zip file: {exc}") from exc
        except ArtifactError:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        (tmp / MARKER).write_text(datetime.datetime.now().isoformat(), encoding="utf-8")
        shutil.rmtree(final, ignore_errors=True)
        tmp.rename(final)
        log.info("Cached artifact for project %s job %s at %s", project_id, job_id, final)
        self.prune()
        return final / "files"

    def entries(self) -> list[Path]:
        if not self.root.is_dir():
            return []
        return [m.parent for m in self.root.glob(f"*/*/{MARKER}")]

    def prune(self) -> None:
        jobs = sorted(self.entries(), key=lambda d: (d / MARKER).stat().st_mtime, reverse=True)
        for old in jobs[self.max_jobs:]:
            log.info("Pruning cached artifact %s", old)
            shutil.rmtree(old, ignore_errors=True)

    def clear(self) -> None:
        log.info("Clearing artifact cache %s", self.root)
        shutil.rmtree(self.root, ignore_errors=True)
