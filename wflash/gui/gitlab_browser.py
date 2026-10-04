"""GitLab browser mixin: ref -> pipeline -> job, then download (or reuse the cached) artifact.

Every GitLab call runs in a worker named "gitlab-*"; the GUI thread never touches the
network. List results carry the generation they were requested for, so a result that
arrives after a newer refresh (or a profile change) is dropped instead of shown; a
downloaded artifact is dropped only if the profile changed meanwhile.

Host contract: `self.ui`, `self.settings`, `self.profile`, `self.ctx`, `self._workers`
(WorkerRegistry), `self._closing`, `self._client_factory`, `self.show_error()`,
`self.flash_active()`, `self.on_artifact_ready()` (MappingTableMixin),
`self._update_flash_controls()` (FlashMixin).
"""
from __future__ import annotations

import dataclasses
import tempfile
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem

from wflash.core.artifact_cache import ArtifactCache
from wflash.core.errors import CancelledError, GitLabError
from wflash.core.gitlab_client import GitLabClient
from wflash.core.logging_setup import get_logger
from wflash.core.profile import Profile
from wflash.core.settings import AppSettings, get_token
from wflash.gui.workers import WorkerContext

log = get_logger("ui.gitlab")
ROLE = Qt.ItemDataRole.UserRole
ClientFactory = Callable[[AppSettings], GitLabClient]


def default_client_factory(settings: AppSettings) -> GitLabClient:
    """Called on a worker thread: builds a client from the settings and the keyring token."""
    token = get_token(settings.gitlab_url)
    if not settings.gitlab_url or not token:
        raise GitLabError(
            "GitLab URL or token is not configured",
            hint="Open Settings… and enter the GitLab URL and a Personal Access Token (scope read_api).",
        )
    return GitLabClient(settings.gitlab_url, token, ca_bundle=settings.ca_bundle or None)


class GitlabBrowserMixin:
    def _init_gitlab_browser(self) -> None:
        self._gl_project_id: int | None = None
        self._gl_generation = 0  # bumped by every refresh: drops stale list results
        self._gl_profile_generation = 0  # bumped by a profile change: drops a stale download
        self._gl_download_key: str | None = None
        self._gl_download_cancel_requested = False
        self._gl_key_generation: dict[str, int] = {}  # listing worker key -> generation at start
        self.ui.progressBar_artifact.setRange(0, 100)
        self.ui.progressBar_artifact.setValue(0)
        self.ui.pushButton_refreshRefs.clicked.connect(self.refresh_gitlab)
        self.ui.comboBox_ref.currentIndexChanged.connect(self._on_ref_changed)
        self.ui.listWidget_pipelines.currentItemChanged.connect(self._on_pipeline_changed)
        self.ui.listWidget_jobs.currentItemChanged.connect(self._update_gitlab_controls)
        self.ui.pushButton_downloadArtifact.clicked.connect(self.download_selected_artifact)
        self.ui.pushButton_cancelArtifact.clicked.connect(self.cancel_artifact_download)
        self._update_gitlab_controls()

    # -- state ----------------------------------------------------------------------
    def gitlab_busy(self) -> bool:
        return self._workers.has_running("gitlab-")

    def artifact_downloading(self) -> bool:
        return self._workers.is_running(self._gl_download_key)

    def _update_gitlab_controls(self, *_args) -> None:
        downloading = self.artifact_downloading()
        self.ui.pushButton_refreshRefs.setEnabled(self.profile is not None and not downloading)
        self.ui.pushButton_downloadArtifact.setEnabled(
            self.ui.listWidget_jobs.currentItem() is not None and not downloading
        )
        self.ui.pushButton_cancelArtifact.setEnabled(downloading)

    def _start_gitlab(self, name: str, fn: Callable[[WorkerContext], object], on_succeeded, on_progress=None) -> str:
        key = self._workers.start(
            f"gitlab-{name}",
            fn,
            on_succeeded=on_succeeded,
            on_failed=self._on_gitlab_failed,
            on_finished=self._on_gitlab_finished,
            on_progress=on_progress,
        )
        self._gl_key_generation[key] = self._gl_generation
        # A running GitLab worker disables Flash and the browser controls.
        self._update_gitlab_controls()
        self._update_flash_controls()
        return key

    def _settings_snapshot(self) -> AppSettings:
        # Workers get their own copy; the GUI thread may keep editing self.settings.
        return dataclasses.replace(self.settings)

    # -- profile ----------------------------------------------------------------------
    def set_gitlab_profile(self, profile: Profile | None) -> None:
        self.cancel_artifact_download()
        self._gl_generation += 1
        self._gl_profile_generation += 1
        self._gl_project_id = None
        if profile is None:
            self.ui.label_project.setText("No profile")
        else:
            self.ui.label_project.setText(
                f"Project: {profile.gitlab.project}  (jobs: {profile.gitlab.job_filter})"
            )
        self.ui.comboBox_ref.blockSignals(True)
        self.ui.comboBox_ref.clear()
        self.ui.comboBox_ref.blockSignals(False)
        self.ui.listWidget_pipelines.clear()
        self.ui.listWidget_jobs.clear()
        self._update_gitlab_controls()

    # -- browsing ---------------------------------------------------------------------
    def refresh_gitlab(self, *_args) -> None:
        if self.profile is None or self._closing or self.flash_active():
            return
        self._gl_generation += 1
        generation = self._gl_generation
        project = self.profile.gitlab.project
        factory, settings = self._client_factory, self._settings_snapshot()

        def job(ctx: WorkerContext):
            client = factory(settings)
            project_id = client.get_project_id(project)
            return generation, project_id, client.list_refs(project_id)

        self._start_gitlab("refs", job, self._on_refs_loaded)

    def _on_refs_loaded(self, _key: str, result) -> None:
        if self._closing:
            return
        generation, project_id, refs = result
        if generation != self._gl_generation:
            return
        self._gl_project_id = project_id
        combo = self.ui.comboBox_ref
        combo.blockSignals(True)
        combo.clear()
        for ref in refs:
            combo.addItem(ref.name + (" (tag)" if ref.kind == "tag" else ""), ref.name)
        combo.blockSignals(False)
        log.info("Loaded %d branches/tags", len(refs))
        self._on_ref_changed()

    def _on_ref_changed(self, *_args) -> None:
        self.ui.listWidget_pipelines.clear()
        self.ui.listWidget_jobs.clear()
        ref = self.ui.comboBox_ref.currentData()
        if ref is None or self._gl_project_id is None or self._closing or self.flash_active():
            return
        generation, project_id = self._gl_generation, self._gl_project_id
        factory, settings = self._client_factory, self._settings_snapshot()

        def job(ctx: WorkerContext):
            client = factory(settings)
            return generation, ref, client.list_pipelines(project_id, ref)

        self._start_gitlab("pipelines", job, self._on_pipelines_loaded)

    def _on_pipelines_loaded(self, _key: str, result) -> None:
        if self._closing:
            return
        generation, ref, pipelines = result
        if generation != self._gl_generation or ref != self.ui.comboBox_ref.currentData():
            return
        self.ui.listWidget_pipelines.clear()
        for p in pipelines:
            created = p.created_at[:16].replace("T", " ")
            item = QListWidgetItem(f"#{p.id}   {p.status:<9} {created}   {p.sha[:8]}")
            item.setData(ROLE, p.id)
            self.ui.listWidget_pipelines.addItem(item)

    def _on_pipeline_changed(self, *_args) -> None:
        self.ui.listWidget_jobs.clear()
        current = self.ui.listWidget_pipelines.currentItem()
        if (
            current is None
            or self._gl_project_id is None
            or self.profile is None
            or self._closing
            or self.flash_active()
        ):
            self._update_gitlab_controls()
            return
        generation, project_id = self._gl_generation, self._gl_project_id
        pipeline_id = current.data(ROLE)
        job_filter = self.profile.gitlab.job_filter
        factory, settings = self._client_factory, self._settings_snapshot()

        def job(ctx: WorkerContext):
            client = factory(settings)
            return generation, pipeline_id, client.list_jobs(project_id, pipeline_id, job_filter)

        self._start_gitlab("jobs", job, self._on_jobs_loaded)

    def _on_jobs_loaded(self, _key: str, result) -> None:
        if self._closing:
            return
        generation, pipeline_id, jobs = result
        current = self.ui.listWidget_pipelines.currentItem()
        if generation != self._gl_generation or current is None or current.data(ROLE) != pipeline_id:
            return
        self.ui.listWidget_jobs.clear()
        for j in jobs:
            item = QListWidgetItem(f"{j.name}   [{j.stage}]   {j.status}")
            item.setData(ROLE, {"id": j.id, "name": j.name})
            self.ui.listWidget_jobs.addItem(item)
        if not jobs:
            log.warning("Pipeline #%s has no jobs with artifacts matching the profile filter", pipeline_id)
        self._update_gitlab_controls()

    # -- download ---------------------------------------------------------------------
    def download_selected_artifact(self, *_args) -> None:
        item = self.ui.listWidget_jobs.currentItem()
        if (
            item is None
            or self._gl_project_id is None
            or self.profile is None
            or self.artifact_downloading()  # a second click while downloading is refused
            or self.flash_active()
            or self._closing
        ):
            return
        job_info = item.data(ROLE)
        job_id, job_name = job_info["id"], job_info["name"]
        project_id, generation = self._gl_project_id, self._gl_profile_generation
        label = f"{self.profile.gitlab.project}  job #{job_id} ({job_name})"
        factory, settings = self._client_factory, self._settings_snapshot()
        cache_root, max_jobs = settings.resolved_cache_dir(), settings.max_cached_jobs

        def job(ctx: WorkerContext):
            cache = ArtifactCache(cache_root, max_jobs)
            cached = cache.get(project_id, job_id)
            if cached is not None:
                log.info("Using cached artifact for job #%s: %s", job_id, cached)
                return generation, label, cached
            client = factory(settings)

            def on_bytes(done: int, total: int) -> None:
                ctx.progress(int(done * 100 / total) if total else None, f"{done / 1e6:.1f} MB")

            with tempfile.TemporaryDirectory(prefix="wflash_dl_") as tmp:
                zip_path = client.download_artifacts(project_id, job_id, Path(tmp), on_bytes, ctx.cancel)
                ctx.progress(None, "Extracting")
                return generation, label, cache.store_zip(project_id, job_id, zip_path)

        self._gl_download_cancel_requested = False
        self.ui.progressBar_artifact.setRange(0, 100)
        self.ui.progressBar_artifact.setValue(0)
        self.ui.progressBar_artifact.setFormat("%p%")
        self._gl_download_key = self._start_gitlab(
            "download", job, self._on_artifact_downloaded, on_progress=self._on_artifact_progress
        )
        self._update_gitlab_controls()
        self._update_flash_controls()

    def cancel_artifact_download(self, *_args) -> None:
        if not self.artifact_downloading():
            return
        # Threading rule 4: the guard is set before cancelling, so a completion already
        # queued is dropped by _on_artifact_downloaded instead of loading the artifact.
        self._gl_download_cancel_requested = True
        log.warning("Artifact download cancel requested")
        self._workers.cancel(self._gl_download_key)

    def _on_artifact_progress(self, percent, message: str) -> None:
        if self._closing:
            return
        bar = self.ui.progressBar_artifact
        if percent is None:
            bar.setRange(0, 0)
        else:
            bar.setRange(0, 100)
            bar.setValue(percent)
        bar.setFormat(message)

    def _on_artifact_downloaded(self, _key: str, result) -> None:
        if self._closing or self._gl_download_cancel_requested:
            log.info("Artifact download completed after cancel; not loading it")
            self._reset_progress_cancelled()
            return
        generation, label, path = result
        if generation != self._gl_profile_generation:
            log.info("Profile changed during download; not loading %s", label)
            self._reset_progress_cancelled()
            return
        bar = self.ui.progressBar_artifact
        bar.setRange(0, 100)
        bar.setValue(100)
        bar.setFormat("Ready")
        self.on_artifact_ready(path, label)

    def _reset_progress_cancelled(self) -> None:
        if self._closing:
            return
        bar = self.ui.progressBar_artifact
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setFormat("Cancelled")

    def _on_gitlab_failed(self, key: str, exc: BaseException) -> None:
        if self._closing:
            return
        started_gen = self._gl_key_generation.get(key)
        if key != self._gl_download_key and started_gen is not None and started_gen != self._gl_generation:
            log.warning("Dropping failure of outdated GitLab request %s: %s", key, exc)
            return
        if key == self._gl_download_key:
            self.ui.progressBar_artifact.setRange(0, 100)
            self.ui.progressBar_artifact.setValue(0)
            self.ui.progressBar_artifact.setFormat("Cancelled" if isinstance(exc, CancelledError) else "Failed")
        if isinstance(exc, CancelledError):
            return
        self.ctx.add_error(exc)  # no flash runs while a GitLab worker exists
        self.show_error(exc)

    def _on_gitlab_finished(self, key: str) -> None:
        self._gl_key_generation.pop(key, None)
        if key == self._gl_download_key:
            self._gl_download_key = None
        if self._closing:
            return
        self._update_gitlab_controls()
        self._update_flash_controls()
