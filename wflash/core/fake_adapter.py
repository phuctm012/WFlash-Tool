"""In-memory winIDEA stand-in for development on macOS and for tests.

Failures can be injected per operation (constructor `fail_on`, or env
WFLASH_FAKE_FAIL="download,reset"):
  list_instances   - list_instances() returns [] (no winIDEA instance found)
  connect          - connect() raises WinIDEAError
  connection_lost  - connect() succeeds, every later call needing a connection
                     raises WinIDEAError("Connection to winIDEA lost");
                     disconnect() still works
  read_programs, read_applications, set_path, reset - raise WinIDEAError
  download         - FlashError half way through (progress stops below 100)
"""
from __future__ import annotations

import logging
import os
import time
from typing import Iterable

from wflash.core.cancel import CancelToken
from wflash.core.errors import FlashError, WinIDEAError
from wflash.core.logging_setup import CALLS_LOGGER
from wflash.core.winidea_adapter import FileEntry, InstanceInfo, ProgressCallback

calls_log = logging.getLogger(CALLS_LOGGER)
INSTANCE_ID = "fake-1"
# Ops whose injection is handled by the method itself rather than in _call.
_NON_RAISING = {"download", "list_instances", "connection_lost"}
WORKSPACE = r"C:\fake\SAF85xx\SAF85xx.xjrf"


class FakeWinIDEAAdapter:
    def __init__(
        self,
        programs: dict[str, str] | None = None,
        applications: dict[str, str] | None = None,
        download_seconds: float = 3.0,
        fail_on: Iterable[str] = (),
    ) -> None:
        self.programs = dict(programs if programs is not None else {"App": r"C:\fake\old\App.s3"})
        self.applications = dict(
            applications
            if applications is not None
            else {"CM7_0": r"C:\fake\old\cm7_0.elf", "CM7_1": r"C:\fake\old\cm7_1.elf"}
        )
        self.download_seconds = download_seconds
        self.fail_on = set(fail_on)
        self.connected_to: str | None = None
        self.target_state = "unknown"
        self.calls: list[str] = []

    @classmethod
    def from_env(cls) -> "FakeWinIDEAAdapter":
        fail = [f.strip() for f in os.environ.get("WFLASH_FAKE_FAIL", "").split(",") if f.strip()]
        seconds = float(os.environ.get("WFLASH_FAKE_DOWNLOAD_S", "3"))
        return cls(download_seconds=seconds, fail_on=fail)

    def _call(self, op: str, detail: str = "") -> None:
        self.calls.append(op)
        calls_log.debug("fake.%s %s", op, detail)
        if op in self.fail_on and op not in _NON_RAISING:
            raise WinIDEAError(f"Fake failure injected in '{op}'")

    def _require_connected(self) -> None:
        if self.connected_to is None:
            raise WinIDEAError("Not connected to winIDEA")
        if "connection_lost" in self.fail_on:
            raise WinIDEAError("Connection to winIDEA lost")

    def list_instances(self) -> list[InstanceInfo]:
        self._call("list_instances")
        if "list_instances" in self.fail_on:
            return []
        return [InstanceInfo(INSTANCE_ID, WORKSPACE, 5313)]

    def connect(self, instance_id: str) -> None:
        self._call("connect", instance_id)
        if instance_id != INSTANCE_ID:
            raise WinIDEAError(f"No winIDEA instance with id {instance_id!r}")
        self.connected_to = instance_id

    def disconnect(self) -> None:
        self._call("disconnect")
        self.connected_to = None

    def get_info(self) -> dict[str, str]:
        self._require_connected()
        return {"winidea_version": "9.21.0 (fake)", "workspace": WORKSPACE, "adapter": "fake"}

    def read_programs(self) -> list[FileEntry]:
        self._require_connected()
        self._call("read_programs")
        return [FileEntry(k, v) for k, v in self.programs.items()]

    def read_applications(self) -> list[FileEntry]:
        self._require_connected()
        self._call("read_applications")
        return [FileEntry(k, v) for k, v in self.applications.items()]

    def set_program_path(self, name: str, path: str) -> None:
        self._require_connected()
        self._call("set_path", f"program {name}={path}")
        if name not in self.programs:
            raise WinIDEAError(f"Unknown program entry {name!r}")
        self.programs[name] = path

    def set_symbol_path(self, name: str, path: str) -> None:
        self._require_connected()
        self._call("set_path", f"application {name}={path}")
        if name not in self.applications:
            raise WinIDEAError(f"Unknown application {name!r}")
        self.applications[name] = path

    def download(self, progress: ProgressCallback, cancel: CancelToken, timeout_s: int) -> None:
        self._require_connected()
        self._call("download")
        steps = 20
        start = time.monotonic()
        for i in range(1, steps + 1):
            if cancel.wait(self.download_seconds / steps):
                cancel.raise_if_cancelled()
            if time.monotonic() - start > timeout_s:
                raise FlashError(f"Download timed out after {timeout_s}s")
            if "download" in self.fail_on and i == steps // 2:
                raise FlashError("Fake failure injected in 'download'")
            progress(i * 100 // steps, "Programming external flash (fake)")
        self.target_state = "downloaded"

    def reset(self, run: bool) -> None:
        self._require_connected()
        self._call("reset", f"run={run}")
        self.target_state = "running" if run else "halted"
