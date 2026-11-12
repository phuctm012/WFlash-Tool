"""Interface between the flash workflow and winIDEA. Only adapters talk to isystem.connect."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Callable, Protocol

from wflash.core.cancel import CancelToken
from wflash.core.flash_plan import ProgramRow, SymbolRow
from wflash.core.errors import CancelledError, FlashError, MappingError, WinIDEAError
from wflash.core.logging_setup import CALLS_LOGGER, get_logger
from wflash.core.srec import is_image_file, read_image, sample_ranges, visible_segments

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

    def core_states(self) -> list[tuple[str, str]]:
        """(core name, Session Explorer status text) of every core; read only. Needs connect()."""
        ...

    # Resets, begin_program tries and programming seconds of the last download() (flash history).
    program_stats: dict[str, float]

    # Row view of the workspace, for the planned flash (profiles with builds).
    def workspace_dir(self) -> Path: ...

    def read_program_rows(self) -> list[ProgramRow]: ...

    def read_symbol_rows(self) -> list[SymbolRow]: ...

    def set_program_row(self, index: int, path: str | None = None, tick: bool | None = None) -> None: ...

    def set_symbol_row(self, app_index: int, file_index: int, path: str | None = None, tick: bool | None = None) -> None: ...


def create_adapter(kind: str) -> WinIDEAAdapter:
    if kind == "fake":
        from wflash.core.fake_adapter import FakeWinIDEAAdapter

        return FakeWinIDEAAdapter.from_env()
    if kind == "real":
        return RealWinIDEAAdapter()
    raise ValueError(f"Unknown adapter kind: {kind}")


DEVICES = "/iOPEN/UMIConfig.Devices.Devices"
DEVICE = f"{DEVICES}[0]"
DOWNLOAD_FILES = f"{DEVICE}.DownloadFiles"
APPLICATIONS = "/IDE/System.Debug.Applications"
# Observed with spike 14 (2026-11-08): the tick of a symbol file, "true"/"false", writable and read back.
SYMBOL_TICK_FIELD = "Load"
EXPECTED_PROGRAM_S = 100  # observed 98.8 s and 99.0 s; only for the estimated progress
MAX_ESTIMATED_PERCENT = 95
PROGRESS_TICK_S = 1.0
HALT_WAIT_S = 5.0
HALT_POLL_S = 0.2
MONITOR_ERROR_TEXT = "error loading monitor"
PROBE_BYTES = 16
# Shown once WFlash has used up its own retries (resets and programming tries) for one press of Flash.
POWER_CYCLE_HINT = "Turn the ECU power off and on, then flash again."
# Rounds 9-11: "Error loading monitor" makes begin_program return after 5-9 s with "PROGRAMMING 0 bytes",
# nothing erased; a good run takes about 100 s. User decision (2026-11-09): such a quick failure is tried
# again (reset, core check, begin_program) within the same press of Flash. A slower failure may have
# erased the flash and is never retried.
MAX_PROGRAM_ATTEMPTS = 3
QUICK_FAIL_S = 30.0
# Spike 16 (2026-11-09): EStatus_Core_stInaccessible. Flashing failed with "Error loading monitor" whenever
# a core showed NOT ACCESSIBLE in the Session Explorer, and worked when none did (a core in RUN was fine).
CORE_INACCESSIBLE = 1
CORE_STOPPED = 2  # EStatus_Core_stStopped
# Round 16 (2026-11-12): right after a power cycle the cores are always M7_0 STOP, M7_RFE STOP, A53, SPT and
# BBE32EP NOT ACCESSIBLE (not started yet), and Debug > Download by hand always works. WFlash's reset in that
# state started the firmware (M7_RFE, A53, BBE32EP RUN), begin_program failed with "Error loading monitor",
# and further resets never cleared it. So that state is programmed at once, without a reset (user, 2026-11-12).
CORE_WAIT_S = 2.0  # not measured: a short grace after each reset before the states count
# User decision (2026-11-09): a reset from winIDEA cleared NOT ACCESSIBLE, so reset again while a core is in
# that state, at most this many resets in all for one press of Flash (the first reset included).
MAX_CORE_RESETS = 10
CORE_HINT = (
    "Nothing was written to the flash. Turn the ECU power off and on (Tools > Power-cycle ECU), check that "
    "winIDEA's Session Explorer shows M7_0 and M7_RFE STOP and no core RUN, then flash again."
)


def just_powered_on(statuses: list[int], stopped: int = CORE_STOPPED, inaccessible: int = CORE_INACCESSIBLE) -> bool:
    """Every core STOP or NOT ACCESSIBLE, at least one STOP: the state right after power on (round 16).

    Any core in RUN, IDLE or another state means the firmware has started, and the old check applies.
    """
    return bool(statuses) and stopped in statuses and all(s in (stopped, inaccessible) for s in statuses)


def just_powered_on_text(texts: list[str]) -> bool:
    """The same test on status_string() values (Tools > Check winIDEA cores)."""
    upper = [t.strip().upper() for t in texts]
    return bool(upper) and "STOP" in upper and all(t in ("STOP", "NOT ACCESSIBLE") for t in upper)


def inaccessible_cores_error(names: list[str]) -> FlashError:
    return FlashError(
        f"Flash not started: {', '.join(names)} still not accessible after {MAX_CORE_RESETS} resets.",
        hint=CORE_HINT,
    )


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
        self.program_stats: dict[str, float] = {"resets": 0, "tries": 0, "program_s": 0.0}
        self._workspaces: dict[str, str] = {}
        self._program_rows: dict[str, int] = {}
        self._symbol_files: dict[str, tuple[int, int]] = {}

    def _load_module(self):
        try:
            import isystem.connect as ic
        except Exception as exc:  # a wrong-bitness DLL raises ImportError or OSError
            log.error("Cannot load isystem.connect: %s", exc)
            raise WinIDEAError("Cannot load isystem.connect.", hint=BITNESS_HINT) from exc
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
            log.error("Cannot connect to winIDEA: %s", exc)
            raise WinIDEAError("Cannot connect to winIDEA.") from exc
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
        # The binding's text is long and technical: it goes to the log, the popup stays short.
        text = str(exc)
        log.error("winIDEA failed while %s: %s", action, text)
        if "ICONNECT_E_ROUTING" in text:
            return WinIDEAError(f"Connection to winIDEA lost while {action}.")
        return WinIDEAError(f"winIDEA failed while {action}.")

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

        begin_program() does NOT raise when winIDEA fails to load its flash monitor: it returned
        normally after 4.8 s instead of about 100 s, and winIDEA only printed the failure in its
        Output view. The next read failed at once with the same error, so one read confirms it.

        Such a quick failure is tried again, up to MAX_PROGRAM_ATTEMPTS in all: reset, core check,
        begin_program. The resets of every try share one budget of MAX_CORE_RESETS (user decision).
        """
        ic, cmgr, _ide = self._session()
        self.program_stats = {"resets": 0, "tries": 0, "program_s": 0.0}
        resets_left = MAX_CORE_RESETS
        for attempt in range(1, MAX_PROGRAM_ATTEMPTS + 1):
            # The first try checks the cores before any reset; a retry follows a failure whose cores
            # looked fine (round 11), so it resets first.
            resets_left = self._prepare_cores(ic, cmgr, resets_left, reset_first=attempt > 1)
            label = "Programming external flash (estimated)"
            if attempt > 1:
                label = f"Programming external flash, try {attempt} of {MAX_PROGRAM_ATTEMPTS} (estimated)"
            elapsed = self._begin_program(ic, cmgr, progress, timeout_s, label)
            self.program_stats["tries"] = attempt
            self.program_stats["program_s"] = round(self.program_stats["program_s"] + elapsed, 1)
            failure = self._read_back(ic, cmgr)
            if failure is None:
                log.info("Programming finished in %.1f s (try %d of %d)", elapsed, attempt, MAX_PROGRAM_ATTEMPTS)
                return
            detail, exc = failure
            if MONITOR_ERROR_TEXT not in detail.lower():
                raise FlashError(
                    "The flash could not be confirmed.", hint="Check the Output view in winIDEA, then flash again."
                ) from exc
            if elapsed >= QUICK_FAIL_S:
                log.error("Not trying again: programming ran %.0f s before it failed, the flash may be erased", elapsed)
            elif attempt == MAX_PROGRAM_ATTEMPTS:
                log.error("Programming did not start in %d tries", attempt)
            elif resets_left == 0:
                log.error("Not trying again: the %d resets for this flash are used up", MAX_CORE_RESETS)
            else:
                log.warning(
                    "Programming did not start (Error loading monitor after %.1f s); trying again, %d of %d",
                    elapsed, attempt + 1, MAX_PROGRAM_ATTEMPTS,
                )
                continue
            message = "Flash failed: winIDEA could not start programming."
            if attempt > 1:
                message = f"Flash failed: winIDEA could not start programming in {attempt} tries."
            raise FlashError(message, hint=POWER_CYCLE_HINT) from exc

    def _begin_program(self, ic, cmgr, progress: ProgressCallback, timeout_s: int, label: str) -> float:
        """One begin_program call with the estimated progress; returns how long it took."""
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
                    progress(percent, label)
                except CancelledError:
                    pass  # WorkerContext.progress raises once cancelled; programming cannot stop
                except Exception:
                    log.warning("Progress callback failed", exc_info=True)

        reporter = threading.Thread(target=report_estimate, name="wflash-program-progress", daemon=True)
        reporter.start()
        calls_log.debug("CSessionCtrl.begin_program")
        try:
            ic.CSessionCtrl(cmgr).begin_program()
        except Exception as exc:  # never retried: only the silent failure below is known to be harmless
            log.error("begin_program failed: %s", exc)
            if MONITOR_ERROR_TEXT in str(exc).lower():
                raise FlashError("Flash failed: winIDEA could not start programming.", hint=POWER_CYCLE_HINT) from exc
            raise FlashError(
                "Flash failed.",
                hint="The flash may be erased or incomplete. Flash again, or use Debug > Download in winIDEA.",
            ) from exc
        finally:
            done.set()
            reporter.join()
        elapsed = time.monotonic() - started
        log.info("begin_program returned after %.1f s", elapsed)
        return elapsed

    def _read_back(self, ic, cmgr) -> tuple[str, Exception] | None:
        """Read the flash once; None when it worked, else (error text, exception). The text goes to the log."""
        try:
            log.info("Target after programming: stopped=%s", ic.CDebugFacade(cmgr).getCPUStatus().isStopped())
        except Exception as exc:
            log.warning("Cannot read the target status after programming: %s", exc)
        umi = ic.CUMIController(cmgr)
        calls_log.debug("CUMIController.read (confirm programming)")
        try:
            umi.read(0, 0, PROBE_BYTES, ic.ByteVector(PROBE_BYTES))
        except Exception as exc:
            detail = f"{exc}; {umi.getLastError()}"
            log.error("Programming could not be confirmed: %s", detail)
            return detail, exc
        return None

    def _reset_before_programming(self, ic, cmgr) -> None:
        """Asked for by the user; winIDEA also suggests it. begin_program resets too, so a failure only warns."""
        try:
            debug = ic.CDebugFacade(cmgr)
            calls_log.debug("CDebugFacade.reset (before programming)")
            debug.reset()
            deadline = time.monotonic() + HALT_WAIT_S
            while not debug.getCPUStatus().isStopped():
                if time.monotonic() >= deadline:
                    log.warning("The target did not stop after the reset before programming; programming anyway")
                    return
                time.sleep(HALT_POLL_S)
        except Exception as exc:
            log.warning("The reset before programming failed; programming anyway: %s", exc)

    def core_states(self) -> list[tuple[str, str]]:
        """Tools > Check winIDEA cores: the calls of spike 16, read only (no reset, no program)."""
        ic, cmgr, _ide = self._session()
        try:
            return [(name, text) for name, _status, text in self._core_states(ic, cmgr)]
        except Exception as exc:
            raise self._fail("reading the core states", exc) from exc

    def _core_states(self, ic, cmgr) -> list[tuple[str, int, str]]:
        """(name, status, text) per core, as winIDEA's Session Explorer shows them (spike 16)."""
        session = ic.CSessionCtrl(cmgr)
        calls_log.debug("CSessionCtrl.get_topology / get_status")
        names = [core.name() for core in session.get_topology().SoCs()[0].cores()]
        states = []
        for i, core in enumerate(session.get_status().SoCs()[0].cores()):
            name = names[i] if i < len(names) else f"core {i}"
            states.append((name, int(core.status()), core.status_string()))
        return states

    def _prepare_cores(self, ic, cmgr, resets_left: int, reset_first: bool) -> int:
        """Read every core first; program at once when none is NOT ACCESSIBLE, or when the ECU has just
        been powered on (only STOP and NOT ACCESSIBLE, round 16); else reset and read again while one
        is NOT ACCESSIBLE (user decision, 2026-11-09: check first, reset only when needed).

        begin_program fails silently in that state. `reset_first` (a try after a quick failure, whose
        cores looked fine) and unreadable states start with a reset, as before. `resets_left` is
        what is left of the MAX_CORE_RESETS for this press of Flash; returns what is left. When they
        are used up it raises, so download() fails before programming and the workflow restores the
        paths. The caller never passes 0.
        """
        if not reset_first:
            if self._just_powered_on(ic, cmgr):
                return resets_left  # a reset here starts the firmware and breaks programming (round 16)
            bad, summary, readable = self._inaccessible_cores(ic, cmgr, grace=False)
            if readable and not bad:
                return resets_left  # no reset needed
            if bad:
                log.warning("Cores not accessible (%s); resetting", summary)
        bad, summary = [], ""
        while resets_left > 0:
            self._reset_before_programming(ic, cmgr)
            resets_left -= 1
            self.program_stats["resets"] = self.program_stats.get("resets", 0) + 1
            bad, summary, _readable = self._inaccessible_cores(ic, cmgr)
            if not bad:
                return resets_left
            used = MAX_CORE_RESETS - resets_left
            if resets_left > 0:
                log.warning("Cores not accessible (%s) after reset %d of %d; resetting again", summary, used, MAX_CORE_RESETS)
        log.error("Not programming, cores not accessible after %d resets: %s", MAX_CORE_RESETS, summary)
        raise inaccessible_cores_error(bad)

    def _just_powered_on(self, ic, cmgr) -> bool:
        try:
            states = self._core_states(ic, cmgr)
        except Exception:
            return False  # _inaccessible_cores reads again and reports it
        stopped = getattr(ic, "EStatus_Core_stStopped", CORE_STOPPED)
        inaccessible = getattr(ic, "EStatus_Core_stInaccessible", CORE_INACCESSIBLE)
        if not just_powered_on([status for _name, status, _text in states], stopped, inaccessible):
            return False
        summary = ", ".join(f"{name} {text}" for name, _status, text in states)
        log.info("Cores before programming: %s. ECU just powered on: programming without a reset", summary)
        return True

    def _inaccessible_cores(self, ic, cmgr, grace: bool = True) -> tuple[list[str], str, bool]:
        """(NOT ACCESSIBLE core names, summary, readable). After a reset (`grace`) it re-reads for up
        to CORE_WAIT_S; the first check before any reset reads once.

        An unreadable state only warns: unknown is not bad, and programming worked before this check.
        """
        inaccessible = getattr(ic, "EStatus_Core_stInaccessible", CORE_INACCESSIBLE)
        deadline = time.monotonic() + (CORE_WAIT_S if grace else 0.0)
        while True:
            try:
                states = self._core_states(ic, cmgr)
            except Exception as exc:
                log.warning("Cannot read the core states before programming; programming anyway: %s", exc)
                return [], "", False
            summary = ", ".join(f"{name} {text}" for name, _status, text in states)
            bad = [name for name, status, _text in states if status == inaccessible]
            if not bad:
                log.info("Cores before programming: %s", summary)
                return [], summary, True
            if time.monotonic() >= deadline:
                return bad, summary, True
            time.sleep(HALT_POLL_S)

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
        images: list[list[tuple[int, bytes]]] = []
        names: list[str] = []
        try:
            for i in range(ide.getDynamicOptionSize(DOWNLOAD_FILES)):
                if self._read(f"{DOWNLOAD_FILES}[{i}].Enabled") != "true":
                    continue
                stored = self._read(f"{DOWNLOAD_FILES}[{i}].Path")
                if not is_image_file(stored):
                    log.warning("Verify skips %s: unknown file type", stored)
                    continue
                offset = int(self._read(f"{DOWNLOAD_FILES}[{i}].Offset"), 16)
                images.append(read_image(Path(workspace_dir) / stored, offset))
                names.append(stored)
        except OSError as exc:
            log.error("Cannot read a flashed file for the verify: %s", exc)
            raise FlashError("Cannot read a flashed file for the check.") from exc
        except WinIDEAError:
            raise
        except Exception as exc:
            raise self._fail("preparing the verify", exc) from exc
        # Rows are written in order, so a later row covers an earlier one; compare what stays on the flash.
        samples = [
            (address, data, name)
            for name, segments in zip(names, visible_segments(images))
            for address, data in sample_ranges(segments)
        ]
        for done, (address, expected, stored) in enumerate(samples, start=1):
            data = ic.ByteVector(len(expected))  # read() raises unless the vector is already sized
            calls_log.debug("CUMIController.read 0x%06X %d", address, len(expected))
            try:
                umi.read(0, address, len(expected), data)
            except Exception as exc:
                detail = f"{exc}; {umi.getLastError()}"
                log.error("Reading the flash failed at 0x%06X: %s", address, detail)
                hint = "Programming finished, but it could not be checked."
                if MONITOR_ERROR_TEXT in detail.lower():
                    hint += f" {POWER_CYCLE_HINT}"
                raise WinIDEAError("The flash check could not read the flash.", hint=hint) from exc
            actual = bytes(b if isinstance(b, int) else ord(b) for b in data)
            if actual != expected:
                offset = next(k for k, (a, b) in enumerate(zip(actual, expected)) if a != b)
                raise FlashError(
                    f"Flash differs from {stored} at 0x{address + offset:06X}: "
                    f"flash 0x{actual[offset]:02X}, file 0x{expected[offset]:02X}",
                    hint="Flash again. If it keeps failing, use Debug > Download in winIDEA and check the log.",
                )
            try:
                progress(done * 100 // len(samples), "Verifying flash samples")
            except CancelledError:
                pass  # a Cancel pressed just before the lock; the flash is already done, finish the check

    # -- rows, for the planned flash (spike 14: .Enabled and .Load write and read back) --
    def workspace_dir(self) -> Path:
        ic, _cmgr, ide = self._session()
        return Path(ide.getPath(ic.CIDEController.WORKSPACE_DIR))

    def read_program_rows(self) -> list[ProgramRow]:
        try:
            self._check_device()
            ide = self._session()[2]
            rows = []
            for i in range(ide.getDynamicOptionSize(DOWNLOAD_FILES)):
                path = self._read(f"{DOWNLOAD_FILES}[{i}].Path")
                rows.append(ProgramRow(
                    i, PureWindowsPath(path).name, path,
                    self._read(f"{DOWNLOAD_FILES}[{i}].Enabled") == "true",
                    int(self._read(f"{DOWNLOAD_FILES}[{i}].Offset"), 16),
                ))
            return rows
        except WinIDEAError:
            raise
        except Exception as exc:
            raise self._fail("reading the download files", exc) from exc

    def read_symbol_rows(self) -> list[SymbolRow]:
        rows: list[SymbolRow] = []
        try:
            for i in range(1000):
                try:
                    app = self._read(f"{APPLICATIONS}[{i}].Name")
                except ValueError as exc:
                    if _is_out_of_range(exc):
                        return rows
                    raise
                for j, path in enumerate(self._read_symbol_paths(i)):
                    tick = self._read(f"{APPLICATIONS}[{i}].SymbolFiles.File[{j}].{SYMBOL_TICK_FIELD}")
                    rows.append(SymbolRow(i, j, f"{app}/{PureWindowsPath(path).name}", path, tick == "true"))
        except WinIDEAError:
            raise
        except Exception as exc:
            raise self._fail("reading the symbol files", exc) from exc
        return rows

    def _write_option(self, url: str, value: str, label: str) -> None:
        ide = self._session()[2]
        calls_log.debug("setOption %s = %s", url, value)
        try:
            ide.setOption(url, value)
            stored = ide.getOptionStr(url)
        except Exception as exc:
            raise self._fail(f"changing {label}", exc) from exc
        if stored != value:
            log.error("winIDEA stored %r instead of %r for %s", stored, value, url)
            raise WinIDEAError(f"winIDEA did not accept the change to {label}.")

    def set_program_row(self, index: int, path: str | None = None, tick: bool | None = None) -> None:
        row = f"{DOWNLOAD_FILES}[{index}]"
        if path is not None:
            self._write_option(f"{row}.Path", path, f"download row {index}")
        if tick is not None:
            self._write_option(f"{row}.Enabled", "true" if tick else "false", f"download row {index}")

    def set_symbol_row(self, app_index: int, file_index: int, path: str | None = None, tick: bool | None = None) -> None:
        row = f"{APPLICATIONS}[{app_index}].SymbolFiles.File[{file_index}]"
        if path is not None:
            self._write_option(f"{row}.Path", path, f"symbol file {file_index}")
        if tick is not None:
            self._write_option(f"{row}.{SYMBOL_TICK_FIELD}", "true" if tick else "false", f"symbol file {file_index}")
