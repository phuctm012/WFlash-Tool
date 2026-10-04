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
from wflash.core.gitlab_client import GitLabClient
from wflash.core.settings import AppSettings
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
OLD_APP = r"C:\fake\old\App.s3"
OLD_CM7_0 = r"C:\fake\old\cm7_0.elf"
OLD_CM7_1 = r"C:\fake\old\cm7_1.elf"
ARTIFACT_FILES = {"out/App.s3": b"S0", "out/x_cm7_0.elf": b"E0", "out/x_cm7_1.elf": b"E1"}


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
            resp = requests.Response()
            resp.status_code = 200
            resp.url = url
            resp.headers = CaseInsensitiveDict({"Content-Length": str(len(self.zip_bytes))})
            resp.raw = _SlowRaw(self.zip_bytes, 4096, self.chunk_delay_s)
            return resp
        return self._response(404, {"message": "404 Not Found"})

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

    Provides exactly the host contract the mixins document: ui, settings, adapter, ctx,
    profile, log_file, _workers, _closing, _client_factory, show_error(), plus no-op
    versions of the cross-mixin hooks that a mixin under test may call.
    """

    def __init__(self, tmp: Path, adapter=None, client_factory=None) -> None:
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.settings = AppSettings(cache_dir=str(tmp / "cache"), profiles_dir=str(tmp / "profiles"))
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
        self.flash_control_updates = 0

    def show_error(self, exc: BaseException) -> None:
        self.errors_shown.append(exc)

    # Cross-mixin hooks; the real mixin wins over these when it is in the MRO first.
    def _update_flash_controls(self) -> None:
        self.flash_control_updates += 1

    def on_artifact_ready(self, path: Path, label: str) -> None:
        self.artifacts_loaded.append((path, label))

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
