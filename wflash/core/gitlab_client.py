"""Minimal GitLab REST v4 client: browse refs → pipelines → jobs and download job artifacts."""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal
from urllib.parse import quote

import requests

from wflash.core.cancel import CancelToken
from wflash.core.errors import GitLabError
from wflash.core.logging_setup import get_logger, register_secret

log = get_logger("gitlab")
CHUNK = 1024 * 1024
DownloadProgress = Callable[[int, int], None]  # (bytes_done, bytes_total or 0 if unknown)

_HINTS = {
    401: "Token is invalid or expired. Create a Personal Access Token with scope read_api and update it in Settings.",
    403: "Your token has no access to this project. Ask for project access or check the token scope.",
    404: "Not found. Check the project path in the profile; the artifact may also have expired.",
}


@dataclass(frozen=True)
class Ref:
    name: str
    kind: Literal["branch", "tag"]


@dataclass(frozen=True)
class Pipeline:
    id: int
    ref: str
    status: str
    sha: str
    created_at: str


@dataclass(frozen=True)
class Job:
    id: int
    name: str
    stage: str
    status: str
    finished_at: str


def _has_archive(job: dict) -> bool:
    if any(a.get("file_type") == "archive" for a in job.get("artifacts") or []):
        return True
    return bool(job.get("artifacts_file"))


class GitLabClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        ca_bundle: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base = base_url.rstrip("/") + "/api/v4"
        self.session = session or requests.Session()
        self.session.headers["PRIVATE-TOKEN"] = token
        self.verify: bool | str = ca_bundle or True
        self.timeout = timeout
        register_secret(token)

    def _get(self, path: str, params: dict | None = None, stream: bool = False) -> requests.Response:
        url = self.base + path
        log.debug("GET %s params=%s", url, params)
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout, verify=self.verify, stream=stream)
        except requests.exceptions.SSLError as exc:
            raise GitLabError(
                f"SSL error connecting to GitLab: {exc}",
                hint="If GitLab uses an internal certificate, set the CA bundle file in Settings.",
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise GitLabError(f"Cannot reach GitLab: {exc}") from exc
        if resp.status_code >= 400:
            raise GitLabError(
                f"GitLab returned HTTP {resp.status_code} for {path}: {resp.text[:200]}",
                hint=_HINTS.get(resp.status_code, ""),
            )
        return resp

    def get_project_id(self, project: str) -> int:
        if project.isdigit():
            return int(project)
        return int(self._get(f"/projects/{quote(project, safe='')}").json()["id"])

    def list_refs(self, project_id: int) -> list[Ref]:
        branches = self._get(f"/projects/{project_id}/repository/branches", {"per_page": 100}).json()
        tags = self._get(f"/projects/{project_id}/repository/tags", {"per_page": 100}).json()
        return [Ref(b["name"], "branch") for b in branches] + [Ref(t["name"], "tag") for t in tags]

    def list_pipelines(self, project_id: int, ref: str, limit: int = 20) -> list[Pipeline]:
        params = {"ref": ref, "per_page": limit, "order_by": "id", "sort": "desc"}
        data = self._get(f"/projects/{project_id}/pipelines", params).json()
        return [
            Pipeline(p["id"], p.get("ref", ""), p.get("status", ""), p.get("sha", ""), p.get("created_at") or "")
            for p in data
        ]

    def list_jobs(self, project_id: int, pipeline_id: int, name_glob: str = "*") -> list[Job]:
        data = self._get(f"/projects/{project_id}/pipelines/{pipeline_id}/jobs", {"per_page": 100}).json()
        jobs = [
            Job(j["id"], j["name"], j.get("stage", ""), j.get("status", ""), j.get("finished_at") or "")
            for j in data
            if _has_archive(j) and fnmatch.fnmatchcase(j["name"], name_glob)
        ]
        return sorted(jobs, key=lambda j: j.name)

    def download_artifacts(
        self,
        project_id: int,
        job_id: int,
        dest: Path,
        progress_cb: DownloadProgress | None = None,
        cancel: CancelToken | None = None,
    ) -> Path:
        resp = self._get(f"/projects/{project_id}/jobs/{job_id}/artifacts", stream=True)
        dest.mkdir(parents=True, exist_ok=True)
        final = dest / f"artifacts_{job_id}.zip"
        part = final.with_suffix(".zip.part")
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        log.info("Downloading artifacts of job #%s (%s bytes)", job_id, total or "unknown")
        try:
            with resp, part.open("wb") as fh:
                for chunk in resp.iter_content(CHUNK):
                    if cancel is not None:
                        cancel.raise_if_cancelled()
                    fh.write(chunk)
                    done += len(chunk)
                    if progress_cb is not None:
                        progress_cb(done, total)
        except requests.exceptions.RequestException as exc:
            part.unlink(missing_ok=True)
            raise GitLabError(f"Artifact download interrupted: {exc}") from exc
        except BaseException:
            part.unlink(missing_ok=True)
            raise
        part.replace(final)
        log.info("Downloaded %.1f MB to %s", done / 1e6, final)
        return final
