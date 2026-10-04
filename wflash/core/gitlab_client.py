"""Minimal GitLab REST v4 client: browse refs → pipelines → jobs and download job artifacts."""
from __future__ import annotations

import fnmatch
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Literal
from urllib.parse import quote

import requests

from wflash.core.cancel import CancelToken
from wflash.core.errors import ArtifactError, GitLabError
from wflash.core.logging_setup import get_logger, register_secret

log = get_logger("gitlab")
CHUNK = 1024 * 1024
DownloadProgress = Callable[[int, int], None]  # (bytes_done, bytes_total or 0 if unknown)

_HINTS = {
    401: "Token is invalid or expired. Create a Personal Access Token with scope read_api and update it in Settings.",
    403: "Your token has no access to this project. Ask for project access or check the token scope.",
    404: "Not found. Check the project path in the profile; the artifact may also have expired.",
}


_BAD_RESPONSE_HINT = (
    "GitLab returned something that is not its API (a proxy or login page?). "
    "Check the GitLab URL in Settings and that you can open it in a browser."
)


@contextmanager
def _parsing(path: str) -> Iterator[None]:
    try:
        yield
    except (ValueError, KeyError, TypeError) as exc:
        raise GitLabError(f"Unexpected response from GitLab for {path}", hint=_BAD_RESPONSE_HINT) from exc


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

    def _get_all(self, path: str, params: dict | None = None) -> list:
        """Fetch every page of a list endpoint by following the X-Next-Page header."""
        items: list = []
        page = "1"
        while page:
            resp = self._get(path, {**(params or {}), "per_page": 100, "page": page})
            with _parsing(path):
                data = resp.json()
                if not isinstance(data, list):
                    raise TypeError("expected a JSON list")
            items.extend(data)
            page = resp.headers.get("X-Next-Page", "")
        return items

    def get_project_id(self, project: str) -> int:
        if project.isdigit():
            return int(project)
        path = f"/projects/{quote(project, safe='')}"
        resp = self._get(path)
        with _parsing(path):
            return int(resp.json()["id"])

    def list_refs(self, project_id: int) -> list[Ref]:
        base = f"/projects/{project_id}/repository"
        branches = self._get_all(f"{base}/branches")
        tags = self._get_all(f"{base}/tags")
        with _parsing(base):
            return [Ref(b["name"], "branch") for b in branches] + [Ref(t["name"], "tag") for t in tags]

    def list_pipelines(self, project_id: int, ref: str, limit: int = 20) -> list[Pipeline]:
        """Latest pipelines of `ref`, newest first. `limit` is clamped to 1..100 (one GitLab page)."""
        path = f"/projects/{project_id}/pipelines"
        params = {"ref": ref, "per_page": max(1, min(limit, 100)), "order_by": "id", "sort": "desc"}
        resp = self._get(path, params)
        with _parsing(path):
            return [
                Pipeline(p["id"], p.get("ref", ""), p.get("status", ""), p.get("sha", ""), p.get("created_at") or "")
                for p in resp.json()
            ]

    def list_jobs(self, project_id: int, pipeline_id: int, name_glob: str = "*") -> list[Job]:
        path = f"/projects/{project_id}/pipelines/{pipeline_id}/jobs"
        data = self._get_all(path)
        with _parsing(path):
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
        final = dest / f"artifacts_{job_id}.zip"
        part = final.with_suffix(".zip.part")
        try:
            total = int(resp.headers.get("Content-Length") or 0)
        except ValueError:
            total = 0  # malformed header: size unknown
        done = 0
        log.info("Downloading artifacts of job #%s (%s bytes)", job_id, total or "unknown")
        try:
            with resp:
                dest.mkdir(parents=True, exist_ok=True)
                with part.open("wb") as fh:
                    for chunk in resp.iter_content(CHUNK):
                        if cancel is not None:
                            cancel.raise_if_cancelled()
                        fh.write(chunk)
                        done += len(chunk)
                        if progress_cb is not None:
                            progress_cb(done, total)
                part.replace(final)
        except BaseException as exc:
            try:
                part.unlink(missing_ok=True)
            except OSError:
                pass
            if isinstance(exc, requests.exceptions.RequestException):
                raise GitLabError(f"Artifact download interrupted: {exc}") from exc
            if isinstance(exc, OSError):
                raise ArtifactError(
                    f"Cannot write artifact to {dest}: {exc}",
                    hint="Cannot write the downloaded artifact. Check free disk space and folder permissions, then retry.",
                ) from exc
            raise
        log.info("Downloaded %.1f MB to %s", done / 1e6, final)
        return final
