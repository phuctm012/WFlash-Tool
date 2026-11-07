"""Find and download firmware for Load from GitLab: CI job artifacts.

Plain blocking calls (no Qt): the GUI runs them on a worker thread and passes the
worker's CancelToken and a byte-progress callback. Everything that is downloaded goes
through an ArtifactCache, and the result says where it came from (FirmwareSource).
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Iterable

from wflash.core.artifact_cache import ArtifactCache, NamedArtifactCache
from wflash.core.cancel import CancelToken
from wflash.core.errors import GitLabError
from wflash.core.firmware_source import FirmwareSource, files_note, short_timestamp
from wflash.core.gitlab_client import DownloadProgress, GitLabClient
from wflash.core.logging_setup import get_logger

log = get_logger("gitlab.fetch")
BROWSE_PIPELINES = 10  # "Browse jobs…" looks at the newest 10 pipelines of the ref
LATEST_PIPELINES = 5  # "Download Selected Artifact" without a row searches the newest 5


@dataclass(frozen=True)
class JobRow:
    pipeline_id: int
    job_id: int
    job_name: str
    ref: str
    status: str
    when: str  # "2026-10-04 09:20" (job finished, else pipeline created)
    commit: str = ""  # the pipeline's commit


def _check(cancel: CancelToken | None) -> None:
    if cancel is not None:
        cancel.raise_if_cancelled()


def count_files(root: Path) -> int:
    return sum(1 for p in root.rglob("*") if p.is_file())


def browse_jobs(
    client: GitLabClient,
    project_id: int,
    ref: str,
    job_filter: str = "*",
    job_name: str = "",
    pipelines: int = BROWSE_PIPELINES,
    cancel: CancelToken | None = None,
) -> list[JobRow]:
    """Successful jobs with an artifact archive in the newest pipelines of `ref`, newest pipeline first.

    A failed job can still have artifacts; they must not be offered for flashing.
    """
    rows: list[JobRow] = []
    for pipeline in client.list_pipelines(project_id, ref, limit=pipelines):
        _check(cancel)
        for job in client.list_jobs(project_id, pipeline.id, job_filter):
            if job.status != "success" or (job_name and job.name != job_name):
                continue
            when = short_timestamp(job.finished_at or pipeline.created_at)
            rows.append(JobRow(pipeline.id, job.id, job.name, pipeline.ref or ref, job.status, when, pipeline.sha))
    return rows


def find_latest_job(
    client: GitLabClient,
    project_id: int,
    ref: str,
    job_filter: str = "*",
    job_name: str = "",
    pipelines: int = LATEST_PIPELINES,
    cancel: CancelToken | None = None,
) -> JobRow:
    """The newest *successful* job of `ref` matching the filter and (if given) the job name.

    Several matching jobs in the newest pipeline that has any is an error, never a guess:
    flashing the wrong binary is the worst thing this tool can do.
    """
    for pipeline in client.list_pipelines(project_id, ref, limit=pipelines):
        _check(cancel)
        jobs = [
            job
            for job in client.list_jobs(project_id, pipeline.id, job_filter)
            if job.status == "success" and (not job_name or job.name == job_name)
        ]
        if len(jobs) > 1:
            names = ", ".join(sorted(job.name for job in jobs))
            raise GitLabError(
                f"Pipeline #{pipeline.id} has {len(jobs)} successful jobs with artifacts: {names}",
                hint="Enter the job name to download, or use Browse jobs… and pick a row.",
            )
        if jobs:
            job = jobs[0]
            when = short_timestamp(job.finished_at or pipeline.created_at)
            return JobRow(pipeline.id, job.id, job.name, pipeline.ref or ref, job.status, when, pipeline.sha)
    wanted = f"'{job_name}' " if job_name else ""
    raise GitLabError(
        f"No successful job {wanted}with artifacts on '{ref}' in the newest {pipelines} pipelines",
        hint="Check the branch/tag and the job name, or use Browse jobs… to pick a job.",
    )


def find_build_jobs(
    client: GitLabClient,
    project_id: int,
    sha: str,
    ffi_job: str,
    elf_job: str,
    cancel: CancelToken | None = None,
) -> tuple[JobRow, JobRow]:
    """The FFI and ELF jobs of the newest pipeline of `sha` where both succeeded. Never another commit."""
    pipelines = client.list_pipelines_for_commit(project_id, sha)
    if not pipelines:
        raise GitLabError(
            f"Commit {sha[:8]} has no pipeline.",
            hint="Push the commit and wait for its pipeline, or use Choose job in GitLab…",
        )
    problems: list[str] = []
    for pipeline in pipelines:
        _check(cancel)
        jobs = {job.name: job for job in client.list_jobs(project_id, pipeline.id, archived_only=False)}
        wanted = [jobs.get(ffi_job), jobs.get(elf_job)]
        if all(job is not None and job.status == "success" for job in wanted):
            return tuple(_job_row(pipeline, job) for job in wanted)
        if not problems:
            for name, job in zip((ffi_job, elf_job), wanted):
                if job is None or job.status != "success":
                    problems.append(f"{name}: {job.status if job else 'not in the pipeline'}")
    raise GitLabError(
        f"Commit {sha[:8]} has no finished build: {'; '.join(problems)}.",
        hint="Run the job in GitLab, then load again.",
    )


def _job_row(pipeline, job) -> JobRow:
    when = short_timestamp(job.finished_at or pipeline.created_at)
    return JobRow(pipeline.id, job.id, job.name, pipeline.ref, job.status, when, pipeline.sha)


def fetch_ci_artifact(
    client: GitLabClient,
    project: str,
    project_id: int,
    job: JobRow,
    cache: ArtifactCache,
    progress: DownloadProgress | None = None,
    cancel: CancelToken | None = None,
) -> tuple[Path, FirmwareSource]:
    """Extracted artifact of `job` (from the cache when it is there) and its source description."""
    path = cache.get(project_id, job.job_id)
    from_cache = path is not None
    if path is None:
        with tempfile.TemporaryDirectory(prefix="wflash_dl_") as tmp:
            zip_path = client.download_artifacts(project_id, job.job_id, Path(tmp), progress, cancel)
            _check(cancel)
            path = cache.store_zip(project_id, job.job_id, zip_path)
    else:
        log.info("Using cached artifact of job #%s: %s", job.job_id, path)
    source = FirmwareSource(
        kind="ci",
        project=project,
        title=f"CI artifact · job #{job.job_id} {job.job_name}",
        detail=f"{project} · {job.ref} · pipeline #{job.pipeline_id}",
        cache_note=files_note(from_cache, count_files(path)),
        commit=job.commit,
    )
    return path, source


def fetch_named_artifact(
    client: GitLabClient,
    project: str,
    project_id: int,
    job: JobRow,
    cache: NamedArtifactCache,
    rel: PurePath,
    progress: DownloadProgress | None = None,
    cancel: CancelToken | None = None,
    keep: Iterable[PurePath] = (),
) -> tuple[Path, FirmwareSource]:
    """Extracted artifact of `job` in a folder named after what it is, from the cache when it is there."""
    path = cache.get(rel)
    from_cache = path is not None
    if path is None:
        with tempfile.TemporaryDirectory(prefix="wflash_dl_") as tmp:
            zip_path = client.download_artifacts(project_id, job.job_id, Path(tmp), progress, cancel)
            _check(cancel)
            path = cache.store_zip(rel, zip_path, keep=keep)
    else:
        log.info("Using cached artifact of job #%s: %s", job.job_id, path)
    source = FirmwareSource(
        kind="ci",
        project=project,
        title=f"CI artifact · job #{job.job_id} {job.job_name}",
        detail=f"{project} · {job.ref} · pipeline #{job.pipeline_id}",
        cache_note=files_note(from_cache, count_files(path) - 1),  # without the marker
        commit=job.commit,
    )
    return path, source
