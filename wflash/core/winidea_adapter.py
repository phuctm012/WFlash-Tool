"""Interface between the flash workflow and winIDEA. Only adapters talk to isystem.connect."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Callable, Protocol

from wflash.core.cancel import CancelToken
from wflash.core.errors import FlashError, MappingError, WinIDEAError
from wflash.core.logging_setup import CALLS_LOGGER, get_logger
from wflash.core.srec import is_srec_file, parse_srec, sample_ranges

log = get_logger("winidea")
calls_log = logging.getLogger(CALLS_LOGGER)

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
    download_cancellable: bool

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

    def verify_flash(self, progress: ProgressCallback) -> None:
        """Compare samples of the flash with the enabled files; raises FlashError on a difference."""
        ...

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


DEVICES = "/iOPEN/UMIConfig.Devices.Devices"
DEVICE = f"{DEVICES}[0]"
DOWNLOAD_FILES = f"{DEVICE}.DownloadFiles"
APPLICATIONS = "/IDE/System.Debug.Applications"
BITNESS_HINT = (
    "Install isystem.connect from the winIDEA installation, and use Python with the same bitness "
    "as winIDEA. Meanwhile start WFlash with --adapter fake."
)


def _same_workspace(a: str, b: str) -> bool:
    return str(PureWindowsPath(a)).casefold() == str(PureWindowsPath(b)).casefold()


def _major_minor(version: str) -> tuple[str, ...]:
    return tuple(version.split(".")[:2])


def _is_out_of_range(exc: Exception) -> bool:
    return isinstance(exc, ValueError) and "out of range" in str(exc)


class RealWinIDEAAdapter:
    """winIDEA through isystem.connect. Every call traces to docs/winidea_api_notes.md."""

    # begin_program() blocks for about 100 s and stopping it mid-erase could leave an empty ECU.
    download_cancellable = False

    def __init__(self) -> None:
        self._ic = None
        self._cmgr = None
        self._ide = None
        self._workspaces: dict[str, str] = {}
        self._program_rows: dict[str, int] = {}
        self._symbol_files: dict[str, tuple[int, int]] = {}

    def _load_module(self):
        try:
            import isystem.connect as ic
        except Exception as exc:  # a wrong-bitness DLL raises ImportError or OSError
            raise WinIDEAError(f"Cannot load isystem.connect: {exc}", hint=BITNESS_HINT) from exc
        return ic

    def list_instances(self) -> list[InstanceInfo]:
        try:
            ic = self._load_module()
            found = ic.VectorWinIDEAInstanceInfo()
            ic.ConnectionMgr().enumerateWinIDEAInstances("", ic.CConnectionConfig(), found)
            instances = [
                InstanceInfo(str(item.getTcpPort()), item.getWorkspace(), item.getTcpPort()) for item in found
            ]
        except Exception as exc:
            log.warning("Listing winIDEA instances failed: %s", exc)
            return []
        self._workspaces = {info.instance_id: info.workspace for info in instances}
        return instances

    def connect(self, instance_id: str) -> None:
        ic = self._load_module()  # first: a missing module is the root cause of an empty instance list
        expected = self._workspaces.get(instance_id)
        if expected is None:
            raise WinIDEAError(
                f"No winIDEA instance {instance_id!r} in the last list",
                hint="Click Refresh next to the winIDEA instance list and select it again.",
            )
        try:
            cmgr = ic.ConnectionMgr()
            # cmgr.connect() attaches to the most recent winIDEA; selecting by id is unverified
            # because getInstanceId() returned ''. The workspace check below catches a wrong one.
            cmgr.connect()
            attached = cmgr.isAttached()
            ide = ic.CIDEController(cmgr)
            actual = ide.getPath(ic.CIDEController.WORKSPACE_FILE_NAME) if attached else ""
        except Exception as exc:
            raise WinIDEAError(f"Cannot connect to winIDEA: {exc}") from exc
        if not attached:
            raise WinIDEAError("isystem.connect did not attach to winIDEA")
        if not _same_workspace(actual, expected):
            raise WinIDEAError(
                f"winIDEA attached to {actual}, not the selected workspace {expected}",
                hint="Close the other winIDEA windows so that only the selected workspace is open.",
            )
        self._ic, self._cmgr, self._ide = ic, cmgr, ide
        self._program_rows, self._symbol_files = {}, {}

    def disconnect(self) -> None:
        # Only drops the references, as every spike process did on exit. ConnectionMgr.disconnect
        # was never observed and might end the debug session.
        self._ic = self._cmgr = self._ide = None

    def _session(self):
        if self._ide is None:
            raise WinIDEAError("Not connected to winIDEA")
        return self._ic, self._cmgr, self._ide

    def _fail(self, action: str, exc: Exception) -> WinIDEAError:
        text = str(exc)
        if "ICONNECT_E_ROUTING" in text:
            return WinIDEAError(f"Connection to winIDEA lost while {action}: {text}")
        return WinIDEAError(f"winIDEA failed while {action}: {text}")

    def get_info(self) -> dict[str, str]:
        ic, _cmgr, ide = self._session()
        try:
            winidea = str(ide.getWinIDEAVersion().toString())
            module = str(ic.getModuleVersion())
            workspace = ide.getPath(ic.CIDEController.WORKSPACE_FILE_NAME)
        except Exception as exc:
            raise self._fail("reading version information", exc) from exc
        if _major_minor(winidea) != _major_minor(module):
            log.warning("isystem.connect %s does not match winIDEA %s", module, winidea)
        return {"winidea_version": winidea, "isystem_connect": module, "workspace": workspace, "adapter": "real"}
