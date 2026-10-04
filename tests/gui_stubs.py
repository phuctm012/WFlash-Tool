"""Test doubles shared by the GUI tests and tools/stress_test.py.

`FakeGitLabSession` replaces `requests.Session` *under* the real `GitLabClient`, so the
client's own pagination, error classification (401/403/404, connection errors) and
streaming download run unchanged — only the network is fake.
"""
from __future__ import annotations

import io
import json
import threading
import time
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QMainWindow
from requests.structures import CaseInsensitiveDict

from wflash.core.debug_bundle import DebugContext
from wflash.core.firmware_source import FirmwareSource
from wflash.core.gitlab_client import GitLabClient
from wflash.core.settings import AppSettings
from wflash.gui import gitlab_dialog
from wflash.gui.ui_main_window import Ui_MainWindow
from wflash.gui.workers import WorkerRegistry

REPO = Path(__file__).resolve().parents[1]
EXAMPLE_PROFILE = REPO / "profiles" / "saf85xx_example.yaml"
GITLAB_URL = "https://gitlab.example.com"
# Realistic PAT shape (glpat- + 20 chars) so the redaction is tested on the real thing.
# Built by concatenation so push-protection secret scanners do not flag a fake token.
TOKEN = "glpat-" + "Zx9Qw3Er5Ty7Ui1Op2As"
PROJECT = "group/saf85xx-sw"
PROJECT_ID = 42
PIPELINE_ID = 100
JOB_ID = 7
PKG_PROJECT = "group/saf85xx-packages"
PKG_PROJECT_ID = 43
PKG_NAME = "saf85xx-firmware"
PKG_ZIP_ID = 502  # version 1.4.0: one zip with the usual artifact files
PKG_RAW_ID = 501  # version 1.3.0: one plain .s3 file (not a zip)
OLD_APP = r"C:\fake\old\App.s3"
OLD_CM7_0 = r"C:\fake\old\cm7_0.elf"
OLD_CM7_1 = r"C:\fake\old\cm7_1.elf"
ARTIFACT_FILES = {"out/App.s3": b"S0", "out/x_cm7_0.elf": b"E0", "out/x_cm7_1.elf": b"E1"}


# What a CI download of JOB_ID reports; tests that load a local tree use it as the source.
SOURCE = FirmwareSource(
    kind="ci",
    project=PROJECT,
    title=f"CI artifact \u00b7 job #{JOB_ID} build_app",
    detail=f"{PROJECT} \u00b7 main \u00b7 pipeline #{PIPELINE_ID}",
    cache_note="Downloaded \u00b7 3 files",
)


def patch_keyring(monkeypatch, store: dict | None = None) -> dict:
    """Keep the GitLab dialog away from the real system keyring; returns the fake store."""
    store = {} if store is None else store
    monkeypatch.setattr(gitlab_dialog, "get_token", lambda url: store.get(url))
    monkeypatch.setattr(gitlab_dialog, "set_token", lambda url, token: store.__setitem__(url, token))
    return store


def artifact_zip_bytes(files: dict[str, bytes] = ARTIFACT_FILES, padding: int = 64 * 1024) -> bytes:
    """Zip of the artifact. `padding` bytes of stored data make the stream span many chunks."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
        if padding:
            zf.writestr("out/padding.bin", b"\0" * padding)
    return buf.getvalue()


def make_artifact_tree(root: Path, files: dict[str, bytes] = ARTIFACT_FILES) -> Path:
    for rel, data in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return root


def write_profiles(folder: Path, download_s: int | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    text = EXAMPLE_PROFILE.read_text(encoding="utf-8")
    if download_s is not None:
        text = text.replace("download_s: 600", f"download_s: {download_s}")
    (folder / "saf.yaml").write_text(text, encoding="utf-8")
    return folder


class _SlowRaw(io.BytesIO):
    """Response body that hands out small chunks with a delay, like a slow network."""

    def __init__(self, data: bytes, chunk: int, delay_s: float) -> None:
        super().__init__(data)
        self._chunk = chunk
        self._delay_s = delay_s

    def read(self, size: int | None = -1) -> bytes:
        if self._delay_s:
            time.sleep(self._delay_s)
        limit = self._chunk if size is None or size < 0 else min(size, self._chunk)
        return super().read(limit)


class FakeGitLabSession:
    """Answers the GitLab REST v4 calls GitLabClient makes. Thread-safe."""

    def __init__(
        self,
        delay_s: float = 0.0,
        fail_status: int | None = None,
        connection_error: bool = False,
        chunk_delay_s: float = 0.0,
    ) -> None:
        self.headers = CaseInsensitiveDict()
        self.delay_s = delay_s
        self.fail_status = fail_status
        self.connection_error = connection_error
        self.chunk_delay_s = chunk_delay_s
        self.zip_bytes = artifact_zip_bytes()
        self.package_versions = [
            {"id": PKG_ZIP_ID, "name": PKG_NAME, "version": "1.4.0", "created_at": "2026-10-04T09:20:00Z"},
            {"id": 503, "name": PKG_NAME + "-debug", "version": "9.9.9", "created_at": "2026-10-03T08:00:00Z"},
            {"id": PKG_RAW_ID, "name": PKG_NAME, "version": "1.3.0", "created_at": "2026-10-01T07:00:00Z"},
        ]
        self.package_files = {PKG_ZIP_ID: f"{PKG_NAME}-1.4.0.zip", PKG_RAW_ID: "App.s3"}
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def count(self, suffix: str) -> int:
        with self._lock:
            return sum(1 for path in self.calls if path.endswith(suffix))

    def get(self, url, params=None, timeout=None, verify=None, stream=False):
        path = unquote(urlparse(url).path).removeprefix("/api/v4")
        with self._lock:
            self.calls.append(path)
        if self.delay_s:
            time.sleep(self.delay_s)  # like a real request: not interruptible by cancel
        if self.connection_error:
            raise requests.exceptions.ConnectionError(f"Failed to establish a new connection to {url}")
        if self.fail_status is not None:
            return self._response(self.fail_status, {"message": f"{self.fail_status} error"})
        if path == f"/projects/{PROJECT}":
            return self._response(200, {"id": PROJECT_ID})
        if path == f"/projects/{PROJECT_ID}/repository/branches":
            return self._response(200, [{"name": "main"}])
        if path == f"/projects/{PROJECT_ID}/repository/tags":
            return self._response(200, [{"name": "v1.0"}])
        if path == f"/projects/{PROJECT_ID}/pipelines":
            ref = (params or {}).get("ref", "main")
            return self._response(
                200,
                [{"id": PIPELINE_ID, "ref": ref, "status": "success", "sha": "abcdef1234567",
                  "created_at": "2026-10-01T10:00:00Z"}],
            )
        if path == f"/projects/{PROJECT_ID}/pipelines/{PIPELINE_ID}/jobs":
            return self._response(
                200,
                [{"id": JOB_ID, "name": "build_app", "stage": "build", "status": "success",
                  "finished_at": "2026-10-01T10:05:00Z", "artifacts": [{"file_type": "archive"}]},
                 {"id": 8, "name": "lint", "stage": "test", "status": "success", "artifacts": []}],
            )
        if path == f"/projects/{PROJECT_ID}/jobs/{JOB_ID}/artifacts":
            return self._stream(url, self.zip_bytes)
        if path == f"/projects/{PKG_PROJECT}":
            return self._response(200, {"id": PKG_PROJECT_ID})
        if path == f"/projects/{PKG_PROJECT_ID}/packages":
            name = (params or {}).get("package_name", "")
            return self._response(200, [p for p in self.package_versions if p["name"].startswith(name)])
        for package_id, file_name in self.package_files.items():
            if path == f"/projects/{PKG_PROJECT_ID}/packages/{package_id}/package_files":
                return self._response(200, [{"id": 1, "file_name": file_name}])
            version = next((p["version"] for p in self.package_versions if p["id"] == package_id), None)
            if path == f"/projects/{PKG_PROJECT_ID}/packages/generic/{PKG_NAME}/{version}/{file_name}":
                return self._stream(url, self.zip_bytes if file_name.endswith(".zip") else b"S0 raw")
        return self._response(404, {"message": "404 Not Found"})

    def _stream(self, url: str, data: bytes) -> requests.Response:
        resp = requests.Response()
        resp.status_code = 200
        resp.url = url
        resp.headers = CaseInsensitiveDict({"Content-Length": str(len(data))})
        resp.raw = _SlowRaw(data, 4096, self.chunk_delay_s)
        return resp

    @staticmethod
    def _response(status: int, payload) -> requests.Response:
        resp = requests.Response()
        resp.status_code = status
        resp._content = json.dumps(payload).encode()
        resp.headers = CaseInsensitiveDict({"Content-Type": "application/json"})
        return resp


class SessionClientFactory:
    """`client_factory` for MainWindow: a real GitLabClient over a FakeGitLabSession."""

    def __init__(self, session: FakeGitLabSession) -> None:
        self.session = session

    def __call__(self, settings: AppSettings) -> GitLabClient:
        return GitLabClient(GITLAB_URL, TOKEN, session=self.session)


class HostWindow(QMainWindow):
    """Minimal stand-in for MainWindow's shared state, to test one mixin at a time.

    Provides exactly the host contract the mixins and GitlabDialog document: ui, settings,
    adapter, ctx, profile, log_file, _workers, _closing, _client_factory, show_error(),
    _save_settings(), plus no-op versions of the cross-mixin hooks a part under test may call.
    """

    def __init__(self, tmp: Path, adapter=None, client_factory=None) -> None:
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.settings = AppSettings(
            gitlab_url=GITLAB_URL, cache_dir=str(tmp / "cache"), profiles_dir=str(tmp / "profiles")
        )
        self.adapter = adapter
        self.ctx = DebugContext()
        self.profile = None
        self.log_file = None
        self._closing = False
        self._client_factory = client_factory
        self._pool = QThreadPool(self)
        self._workers = WorkerRegistry(self._pool, self)
        self.errors_shown: list[BaseException] = []
        self.artifacts_loaded: list[tuple[Path, str]] = []
        self.firmware_loaded: list[tuple[Path, FirmwareSource]] = []
        self.flash_control_updates = 0
        self.settings_saved = 0

    def show_error(self, exc: BaseException) -> None:
        self.errors_shown.append(exc)

    def _save_settings(self) -> None:
        self.settings_saved += 1

    # Cross-mixin hooks; the real mixin wins over these when it is in the MRO first.
    def _update_flash_controls(self) -> None:
        self.flash_control_updates += 1

    def on_artifact_ready(self, path: Path, label: str) -> None:
        self.artifacts_loaded.append((path, label))

    def on_firmware_ready(self, path: Path, source: FirmwareSource) -> None:
        self.firmware_loaded.append((path, source))

    def flash_active(self) -> bool:
        return False

    def gitlab_busy(self) -> bool:
        return False

    def closeEvent(self, event) -> None:
        self._closing = True
        self._workers.cancel_all()
        if not self._workers.wait_idle(10.0):
            self._workers.abandon_running()
        if hasattr(self, "log_handler"):
            self._detach_log_panel()
        super().closeEvent(event)
