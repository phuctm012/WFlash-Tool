"""Interface between the flash workflow and winIDEA. Only adapters talk to isystem.connect."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Callable, Protocol

from wflash.core.cancel import CancelToken
from wflash.core.errors import WinIDEAError

ProgressCallback = Callable[[int | None, str], None]


@dataclass(frozen=True)
class InstanceInfo:
    instance_id: str
    workspace: str
    tcp_port: int | None = None

    def label(self) -> str:
        name = PureWindowsPath(self.workspace).name or self.workspace
        return f"{name} ({self.instance_id})"


@dataclass(frozen=True)
class FileEntry:
    """A download (program) or symbol (application) file entry in the winIDEA workspace."""

    name: str
    path: str


class WinIDEAAdapter(Protocol):
    def list_instances(self) -> list[InstanceInfo]: ...

    def connect(self, instance_id: str) -> None: ...

    def disconnect(self) -> None: ...

    def get_info(self) -> dict[str, str]:
        """winIDEA version, workspace path and adapter name, for logs and the debug bundle."""
        ...

    def read_programs(self) -> list[FileEntry]: ...

    def read_applications(self) -> list[FileEntry]: ...

    def set_program_path(self, name: str, path: str) -> None:
        """Replace only the file path of an existing download entry; keep its other options."""
        ...

    def set_symbol_path(self, name: str, path: str) -> None:
        """Replace only the symbol file path of an existing application."""
        ...

    def download(self, progress: ProgressCallback, cancel: CancelToken, timeout_s: int) -> None: ...

    def reset(self, run: bool) -> None: ...


def create_adapter(kind: str) -> WinIDEAAdapter:
    if kind == "fake":
        from wflash.core.fake_adapter import FakeWinIDEAAdapter

        return FakeWinIDEAAdapter.from_env()
    if kind == "real":
        raise WinIDEAError(
            "The real winIDEA adapter is not available in this build yet.",
            hint="Run the spike scripts (spike/README.md) and send the results. Meanwhile start WFlash with --adapter fake.",
        )
    raise ValueError(f"Unknown adapter kind: {kind}")
