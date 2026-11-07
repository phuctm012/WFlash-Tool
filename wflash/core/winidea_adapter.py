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
EXPECTED_PROGRAM_S = 100  # observed 98.8 s and 99.0 s; only for the estimated progress
MAX_ESTIMATED_PERCENT = 95
PROGRESS_TICK_S = 1.0
HALT_WAIT_S = 5.0
HALT_POLL_S = 0.2
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

    def _read(self, url: str) -> str:
        calls_log.debug("getOptionStr %s", url)
        return self._session()[2].getOptionStr(url)

    def _check_device(self) -> None:
        ide = self._session()[2]
        calls_log.debug("getDynamicOptionSize %s", DEVICES)
        if ide.getDynamicOptionSize(DEVICES) != 1:
            raise WinIDEAError(
                "Expected exactly one external flash device in the workspace",
                hint="Check Hardware > Options in winIDEA; WFlash supports one device.",
            )
        for option, label in (("Enabled", "enabled"), ("ProgramAtDownload", "'Program at download'")):
            if self._read(f"{DEVICE}.{option}") != "true":
                raise WinIDEAError(
                    f"The external flash device does not have {label} set, so a download would not program it",
                    hint="Set it in Hardware > (your flash device) > Configure… in winIDEA.",
                )

    def read_programs(self) -> list[FileEntry]:
        try:
            self._check_device()
            ide = self._session()[2]
            calls_log.debug("getDynamicOptionSize %s", DOWNLOAD_FILES)
            rows = []
            for i in range(ide.getDynamicOptionSize(DOWNLOAD_FILES)):
                path = self._read(f"{DOWNLOAD_FILES}[{i}].Path")
                rows.append((i, path, self._read(f"{DOWNLOAD_FILES}[{i}].Enabled") == "true"))
        except WinIDEAError:
            raise
        except Exception as exc:
            raise self._fail("reading the download files", exc) from exc
        enabled = [PureWindowsPath(path).name for _i, path, on in rows if on]
        entries = []
        self._program_rows = {}
        for i, path, on in rows:
            base = PureWindowsPath(path).name
            if not on:
                entries.append(FileEntry(f"{base} (disabled)", path))
            elif enabled.count(base) > 1:
                entries.append(FileEntry(f"{base} #{i}", path))  # never matches a profile target
            else:
                entries.append(FileEntry(base, path))
                self._program_rows[base] = i
        return entries

    def read_applications(self) -> list[FileEntry]:
        try:
            apps = []
            for i in range(1000):
                try:
                    # UNVERIFIED: the out-of-range error is observed for File[1] and DownloadFiles[3],
                    # not yet for Applications[i].
                    name = self._read(f"{APPLICATIONS}[{i}].Name")
                except ValueError as exc:
                    if _is_out_of_range(exc):
                        break
                    raise
                apps.append((i, name, self._read_symbol_paths(i)))
        except WinIDEAError:
            raise
        except Exception as exc:
            raise self._fail("reading the applications", exc) from exc
        entries = []
        self._symbol_files = {}
        for i, app, paths in apps:
            bases = [PureWindowsPath(path).name for path in paths]
            for j, path in enumerate(paths):
                name = f"{app}/{bases[j]}"
                if bases.count(bases[j]) > 1:
                    entries.append(FileEntry(f"{name} #{j}", path))  # never matches a profile target
                else:
                    entries.append(FileEntry(name, path))
                    self._symbol_files[name] = (i, j)
        return entries

    def _read_symbol_paths(self, app_index: int) -> list[str]:
        paths: list[str] = []
        for j in range(1000):
            try:
                paths.append(self._read(f"{APPLICATIONS}[{app_index}].SymbolFiles.File[{j}].Path"))
            except ValueError as exc:
                if _is_out_of_range(exc):
                    break
                raise
        return paths

    def _write_path(self, url: str, name: str, path: str) -> None:
        expected = name.rsplit("/", 1)[-1]
        if PureWindowsPath(path).name.casefold() != expected.casefold():
            raise MappingError(
                f"The selected file {PureWindowsPath(path).name} is not named like the workspace entry {expected}",
                hint="WFlash replaces a workspace file with a file of the same name. Check the file in the mapping table.",
            )
        calls_log.debug("setOption %s = %s", url, path)
        ide = self._session()[2]
        try:
            ide.setOption(url, path)
            stored = ide.getOptionStr(url)
        except Exception as exc:
            raise self._fail(f"setting the path of {name}", exc) from exc
        if stored != path:
            raise WinIDEAError(f"winIDEA stored {stored!r} instead of {path!r} for {name}")

    def set_program_path(self, name: str, path: str) -> None:
        self._session()
        row = self._program_rows.get(name)
        if row is None:
            raise WinIDEAError(f"No single enabled download row is named {name!r}")
        self._write_path(f"{DOWNLOAD_FILES}[{row}].Path", name, path)

    def set_symbol_path(self, name: str, path: str) -> None:
        self._session()
        where = self._symbol_files.get(name)
        if where is None:
            raise WinIDEAError(f"No single symbol file is named {name!r}")
        i, j = where
        self._write_path(f"{APPLICATIONS}[{i}].SymbolFiles.File[{j}].Path", name, path)

    def download(self, progress: ProgressCallback, cancel: CancelToken, timeout_s: int) -> None:
        """Program through the session, as Debug > Download does: one erase, then all enabled rows.

        begin_program() blocks and reports nothing, so `progress` is an estimate from elapsed time.
        `cancel` and the timeout cannot apply: stopping mid-erase could leave the ECU empty.
        """
        ic, cmgr, _ide = self._session()
        done = threading.Event()
        started = time.monotonic()

        def report_estimate() -> None:
            warned = False
            while not done.wait(PROGRESS_TICK_S):
                elapsed = time.monotonic() - started
                if elapsed > timeout_s and not warned:
                    warned = True
                    log.warning("Programming has taken over %d s; it cannot be stopped safely, still waiting", timeout_s)
                percent = min(MAX_ESTIMATED_PERCENT, int(elapsed * 100 / EXPECTED_PROGRAM_S))
                try:
                    progress(percent, "Programming external flash (estimated)")
                except Exception:
                    log.warning("Progress callback failed", exc_info=True)

        reporter = threading.Thread(target=report_estimate, name="wflash-program-progress", daemon=True)
        reporter.start()
        calls_log.debug("CSessionCtrl.begin_program")
        try:
            ic.CSessionCtrl(cmgr).begin_program()
        except Exception as exc:
            raise FlashError(
                f"Programming failed: {exc}",
                hint="The external flash may be erased or partly written. Flash again, or use Debug > Download in winIDEA.",
            ) from exc
        finally:
            done.set()
            reporter.join()
        log.info("Programming finished in %.1f s", time.monotonic() - started)

    def reset(self, run: bool) -> None:
        ic, cmgr, _ide = self._session()
        try:
            debug = ic.CDebugFacade(cmgr)
            calls_log.debug("CDebugFacade.reset")
            debug.reset()
            if run:
                calls_log.debug("CDebugFacade.run")
                debug.run()
                return
            # isStopped, not isHalted: after reset winIDEA reports isStopped=1 and isHalted=0.
            deadline = time.monotonic() + HALT_WAIT_S
            while not debug.getCPUStatus().isStopped():
                if time.monotonic() >= deadline:
                    raise WinIDEAError(
                        f"The target did not stop within {HALT_WAIT_S:.0f} s after reset",
                        hint="The flash finished, but the target is not halted. Check its state in winIDEA.",
                    )
                time.sleep(HALT_POLL_S)
        except WinIDEAError:
            raise
        except Exception as exc:
            raise self._fail("resetting the target", exc) from exc

    def verify_flash(self, progress: ProgressCallback) -> None:
        """Compare the start and end of each segment of the enabled files with the flash.

        Each read costs about 4.4 s whatever its size, so a whole-image compare would take over an hour.
        """
        ic, cmgr, ide = self._session()
        umi = ic.CUMIController(cmgr)
        workspace_dir = ide.getPath(ic.CIDEController.WORKSPACE_DIR)
        samples = []
        try:
            for i in range(ide.getDynamicOptionSize(DOWNLOAD_FILES)):
                if self._read(f"{DOWNLOAD_FILES}[{i}].Enabled") != "true":
                    continue
                stored = self._read(f"{DOWNLOAD_FILES}[{i}].Path")
                if not is_srec_file(stored):
                    log.warning("Verify skips %s: not an S-record file", stored)
                    continue
                offset = int(self._read(f"{DOWNLOAD_FILES}[{i}].Offset"), 16)
                segments = parse_srec(Path(workspace_dir) / stored)
                samples += [(address + offset, data, stored) for address, data in sample_ranges(segments)]
        except OSError as exc:
            raise FlashError(f"Cannot read a flashed file for the verify: {exc}") from exc
        except WinIDEAError:
            raise
        except Exception as exc:
            raise self._fail("preparing the verify", exc) from exc
        for done, (address, expected, stored) in enumerate(samples, start=1):
            data = ic.ByteVector(len(expected))  # read() raises unless the vector is already sized
            calls_log.debug("CUMIController.read 0x%06X %d", address, len(expected))
            try:
                umi.read(0, address, len(expected), data)
            except Exception as exc:
                raise WinIDEAError(f"Reading the flash failed at 0x{address:06X}: {exc}; {umi.getLastError()}") from exc
            actual = bytes(b if isinstance(b, int) else ord(b) for b in data)
            if actual != expected:
                offset = next(k for k, (a, b) in enumerate(zip(actual, expected)) if a != b)
                raise FlashError(
                    f"Flash differs from {stored} at 0x{address + offset:06X}: "
                    f"flash 0x{actual[offset]:02X}, file 0x{expected[offset]:02X}",
                    hint="Flash again. If it keeps failing, use Debug > Download in winIDEA and check the log.",
                )
            progress(done * 100 // len(samples), "Verifying flash samples")
