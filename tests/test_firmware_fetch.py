"""Core firmware lookups against a duck-typed client (no network, no Qt)."""
import io
import zipfile

import pytest

from wflash.core.artifact_cache import ArtifactCache
from wflash.core.cancel import CancelToken
from wflash.core.errors import CancelledError, GitLabError
from wflash.core.firmware_fetch import (
    JobRow,
    browse_jobs,
    fetch_ci_artifact,
    find_latest_job,
)
from wflash.core.gitlab_client import Job, Pipeline

FILES = {"out/App.s3": b"S0", "out/x_cm7_0.elf": b"E0", "out/x_cm7_1.elf": b"E1"}


def zip_bytes(files=FILES) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


class StubClient:
    """Answers the GitLabClient calls firmware_fetch makes; records them."""

    def __init__(self, pipelines=None, jobs=None):
        self.pipelines = pipelines if pipelines is not None else [
            Pipeline(101, "main", "success", "b" * 8, "2026-10-04T09:00:00Z"),
            Pipeline(100, "main", "success", "a" * 8, "2026-10-03T09:00:00Z"),
        ]
        self.jobs = jobs if jobs is not None else {
            101: [Job(9, "build_app", "build", "failed", "2026-10-04T09:05:00Z")],
            100: [Job(7, "build_app", "build", "success", "2026-10-03T09:05:00Z"),
                  Job(8, "build_boot", "build", "success", "")],
        }
        self.calls = []

    def list_pipelines(self, project_id, ref, limit=20):
        self.calls.append(("pipelines", ref, limit))
        return self.pipelines[:limit]

    def list_jobs(self, project_id, pipeline_id, name_glob="*"):
        self.calls.append(("jobs", pipeline_id, name_glob))
        return [j for j in self.jobs.get(pipeline_id, []) if name_glob == "*" or j.name.startswith(name_glob.rstrip("*"))]

    def download_artifacts(self, project_id, job_id, dest, progress_cb=None, cancel=None):
        self.calls.append(("artifacts", job_id))
        data = zip_bytes()
        if progress_cb:
            progress_cb(len(data), len(data))
        if cancel is not None:
            cancel.raise_if_cancelled()
        path = dest / f"artifacts_{job_id}.zip"
        path.write_bytes(data)
        return path


def test_browse_jobs_lists_every_pipeline_newest_first():
    client = StubClient()
    rows = browse_jobs(client, 42, "main", "build_*")
    assert [(r.pipeline_id, r.job_id, r.job_name, r.status) for r in rows] == [
        (100, 7, "build_app", "success"),
        (100, 8, "build_boot", "success"),
    ]
    assert rows[0].when == "2026-10-03 09:05"
    assert rows[1].when == "2026-10-03 09:00"  # no finished_at: pipeline creation time
    assert client.calls[0] == ("pipelines", "main", 10)


def test_browse_jobs_filters_by_job_name():
    rows = browse_jobs(StubClient(), 42, "main", "*", job_name="build_boot")
    assert [r.job_id for r in rows] == [8]


def test_browse_jobs_honours_cancel_between_pipelines():
    token = CancelToken()
    token.cancel()
    with pytest.raises(CancelledError):
        browse_jobs(StubClient(), 42, "main", cancel=token)


def test_latest_job_skips_failed_pipeline_and_matches_name():
    row = find_latest_job(StubClient(), 42, "main", "*", job_name="build_app")
    assert (row.pipeline_id, row.job_id, row.job_name, row.ref) == (100, 7, "build_app", "main")


def test_latest_job_with_several_candidates_and_no_name_is_an_error():
    with pytest.raises(GitLabError, match="2 successful jobs") as info:
        find_latest_job(StubClient(), 42, "main", "*")
    assert "job name" in info.value.hint


def test_latest_job_none_found_is_an_error():
    with pytest.raises(GitLabError, match="No successful job 'flash_x' with artifacts on 'main'") as info:
        find_latest_job(StubClient(), 42, "main", "*", job_name="flash_x", pipelines=5)
    assert "Browse jobs" in info.value.hint


def test_fetch_ci_artifact_downloads_then_uses_cache(tmp_path):
    client = StubClient()
    cache = ArtifactCache(tmp_path / "cache")
    job = JobRow(100, 7, "build_app", "main", "success", "2026-10-03 09:05")
    seen = []
    path, source = fetch_ci_artifact(client, "group/sw", 42, job, cache, progress=lambda d, t: seen.append(d))
    assert (path / "out" / "App.s3").read_bytes() == b"S0"
    assert seen
    assert source.kind == "ci" and source.project == "group/sw"
    assert source.title == "CI artifact · job #7 build_app"
    assert source.detail == "group/sw · main · pipeline #100"
    assert source.cache_note == "Downloaded · 3 files"
    path2, source2 = fetch_ci_artifact(client, "group/sw", 42, job, cache)
    assert path2 == path and source2.cache_note == "Cached · 3 files"
    assert [c for c in client.calls if c[0] == "artifacts"] == [("artifacts", 7)]


def test_fetch_ci_artifact_cancel_leaves_no_cache_entry(tmp_path):
    token = CancelToken()
    token.cancel()
    cache = ArtifactCache(tmp_path / "cache")
    with pytest.raises(CancelledError):
        fetch_ci_artifact(StubClient(), "g/p", 42, JobRow(1, 7, "b", "main", "success", ""), cache, cancel=token)
    assert cache.entries() == []


def test_browse_jobs_carries_the_pipeline_commit():
    rows = browse_jobs(StubClient(), 42, "main")
    assert rows[0].commit == "a" * 8


def test_browse_jobs_lists_only_successful_jobs():
    jobs = {
        100: [
            Job(7, "build_app", "build", "failed", ""),
            Job(8, "build_ok", "build", "success", ""),
            Job(9, "build_manual", "build", "manual", ""),
        ]
    }
    client = StubClient(pipelines=[Pipeline(100, "main", "success", "a" * 8, "2026-10-03T09:00:00Z")], jobs=jobs)
    assert [row.job_name for row in browse_jobs(client, 42, "main")] == ["build_ok"]


def test_ci_source_records_the_pipeline_commit(tmp_path):
    from wflash.core.firmware_source import FirmwareSource

    assert FirmwareSource("ci", "p", "t", "d", "c").commit == ""
    assert FirmwareSource("ci", "p", "t", "d", "c", commit="abc").to_dict()["commit"] == "abc"
    assert JobRow(1, 2, "n", "r", "s", "w").commit == ""
