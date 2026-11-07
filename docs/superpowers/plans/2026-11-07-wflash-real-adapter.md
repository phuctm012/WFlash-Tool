# WFlash Real winIDEA Adapter (Plan 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make WFlash flash the SAF85xx's Winbond flash through a real winIDEA session, using only API calls observed on the user's machine.

**Architecture:** `RealWinIDEAAdapter` in `wflash/core/winidea_adapter.py` satisfies the existing `WinIDEAAdapter` Protocol, so `FlashWorkflow`'s path backup and rollback stay as they are. Download rows and symbol files have no names of their own, so the adapter names them after their file: `RAD_SUZ05_FFI.s3` and `App_M7/Radar_SUZ05_Gen7.elf`. Programming is `CSessionCtrl.begin_program()`, which cannot be interrupted, so the GUI locks Cancel from that step on.

**Tech Stack:** Python 3.11+, PySide6, pytest + pytest-qt, `isystem.connect` (imported lazily).

**Spec:** `docs/superpowers/specs/2026-10-04-wflash-tool-design.md`. API authority: `docs/winidea_api_notes.md`.

## Global Constraints

- Every `isystem.connect` call must be recorded in `docs/winidea_api_notes.md`, or carry a `# UNVERIFIED:` comment (CLAUDE.md, Rule zero).
- **Never call `CUMIController.write`, `erase` or `flush`.** `umi.write(index, mode)` with two enabled rows ran two erase passes, and the user reported the chip erased and the ECU dead (2026-11-07).
- **Never call `getOptionJSON`.** On a tree it broke the connection.
- Only change file paths. Never touch device options, mass erase, verify, offsets or row ticks. Mass erase follows the workspace (user decision, 2026-11-07).
- `isystem.connect` is imported lazily, only by `wflash/core/winidea_adapter.py`, never at module scope.
- Only the `.s3` row and the `App_M7` ELF named in the profile change. The CAL row, `App_BBE` and `App_A53` stay.
- `wflash/core/**` must not import PySide6. GUI text is English. `docs/walkthrough.md` and the Windows guide are Vietnamese.
- GUI layout goes in `.ui` first, then `pyside6-uic`; never hand-edit `ui_*.py`. Widgets are named `<kind>_<what>`.
- Every business error inherits `WFlashError` and carries advice in `hint`.
- Test commands: `~/.venvs/wflash/bin/pytest`. Every commit ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` as a second `-m`.
- Add a `## Phase X.Y` entry to `docs/walkthrough.md` in each task, continuing from the last number, with intro, `### Thay đổi`, `### Đã kiểm tra`.
- Do not push until the full suite, `-k thread` and `tools/stress_test.py` all pass.

## Call traceability

| Call | Evidence in `docs/winidea_api_notes.md` |
|---|---|
| `ic.ConnectionMgr()`, `enumerateWinIDEAInstances("", ic.CConnectionConfig(), vec)`, `cmgr.connect()`, `cmgr.isAttached()` | "Connecting / listing instances" |
| `ide.getPath(WORKSPACE_FILE_NAME / WORKSPACE_DIR)`, `ide.getWinIDEAVersion().toString()`, `ic.getModuleVersion()` | "Environment" |
| `ide.getOptionStr`, `ide.setOption` on `/iOPEN/UMIConfig.Devices.Devices[0].DownloadFiles[i].Path` and `/IDE/System.Debug.Applications[i].SymbolFiles.File[j].Path` | "Writing paths works" |
| `getDynamicOptionSize`, row `.Enabled`, `.Offset`, device `.Enabled`, `.ProgramAtDownload` | "Round 3 findings" |
| `CSessionCtrl(cmgr).begin_program()` | "CSessionCtrl.begin_program() matches too" |
| `CDebugFacade.reset()`, `.run()`, `.getCPUStatus().isStopped()` | "reset / halt / run" |
| `CUMIController.read(0, addr, n, ic.ByteVector(n))`, `getLastError()` | "umi.read works" |

Not observed, so marked `# UNVERIFIED:` in code: enumerating `Applications[i]` past the end. The "out of range" error was only observed on `File[1]` and `DownloadFiles[3]`.

`ConnectionMgr.disconnect` was never called in a spike. `disconnect()` only drops the references, which is what happened at the end of every spike process. Acceptance step 5 in Task 7 checks two flashes in one session.

## File Structure

- Create `wflash/core/srec.py`: S-record parsing and sample selection. No winIDEA knowledge.
- Modify `wflash/core/winidea_adapter.py`: Protocol additions, `RealWinIDEAAdapter`, `create_adapter("real")`.
- Modify `wflash/core/fake_adapter.py`: `verify_flash`, `download_cancellable`.
- Modify `wflash/core/flash_workflow.py`: `Step.VERIFY`, `FlashRequest.verify`.
- Modify `wflash/gui/flash_mixin.py`, `wflash/gui/main_window.py`, `wflash/gui/main_window.ui`: Cancel lock, close prompt, verify checkbox.
- Create `tests/fake_isystem.py`: a stand-in `isystem.connect` built from the observed behaviour.
- Create `tests/test_srec.py`, `tests/test_real_adapter.py`.
- Create `profiles/suz05_m7_ffi.yaml`.

---

### Task 1: S-record parsing

**Files:**
- Create: `wflash/core/srec.py`
- Test: `tests/test_srec.py`

**Interfaces:**
- Produces: `parse_srec(path: Path) -> list[tuple[int, bytes]]`, `sample_ranges(segments, sample: int = 256) -> list[tuple[int, bytes]]`, `is_srec_file(name: str) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
from wflash.core.srec import is_srec_file, parse_srec, sample_ranges


def record(address: int, data: bytes) -> str:
    body = bytes([4 + len(data) + 1]) + address.to_bytes(4, "big") + data
    return "S3" + body.hex().upper() + f"{(~sum(body)) & 0xFF:02X}"


def test_parse_srec_merges_contiguous_records_and_skips_headers(tmp_path):
    path = tmp_path / "a.s3"
    path.write_text(
        "S00600004844521B\n"
        + record(0x110, b"\x22" * 16) + "\n"
        + record(0x100, b"\x11" * 16) + "\n"
        + record(0x7F2FC0, b"\x33" * 4) + "\n"
        + "S70500000000FA\n"
    )
    assert parse_srec(path) == [(0x100, b"\x11" * 16 + b"\x22" * 16), (0x7F2FC0, b"\x33" * 4)]


def test_parse_srec_reads_s1_and_s2_addresses(tmp_path):
    path = tmp_path / "a.sre"
    s1 = bytes([2 + 1 + 1]) + (0x1234).to_bytes(2, "big") + b"\xAA"
    s2 = bytes([3 + 1 + 1]) + (0x7F0000).to_bytes(3, "big") + b"\xBB"
    path.write_text(f"S1{s1.hex()}00\nS2{s2.hex()}00\n")
    assert parse_srec(path) == [(0x1234, b"\xAA"), (0x7F0000, b"\xBB")]


def test_sample_ranges_takes_head_and_tail_of_long_segments():
    data = bytes(range(256)) * 3
    assert sample_ranges([(0x1000, data)], sample=256) == [(0x1000, data[:256]), (0x1000 + 512, data[-256:])]


def test_sample_ranges_keeps_short_segments_whole():
    assert sample_ranges([(0x10, b"abc")], sample=256) == [(0x10, b"abc")]


def test_is_srec_file():
    assert is_srec_file("RAD_SUZ05_FFI.s3")
    assert is_srec_file("x_CAL.SRE")
    assert not is_srec_file("image.bin")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `~/.venvs/wflash/bin/pytest tests/test_srec.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'wflash.core.srec'`

- [ ] **Step 3: Write minimal implementation**

```python
"""S-record files: contiguous segments and the samples compared after a flash. No winIDEA here."""
from __future__ import annotations

from pathlib import Path, PurePath

ADDRESS_BYTES = {"1": 2, "2": 3, "3": 4}
SREC_SUFFIXES = {".s3", ".s2", ".s1", ".sre", ".srec", ".s19", ".mot"}


def is_srec_file(name: str) -> bool:
    return PurePath(name).suffix.lower() in SREC_SUFFIXES


def parse_srec(path: Path) -> list[tuple[int, bytes]]:
    """Return (address, data) segments sorted by address, with adjacent records merged."""
    pieces: list[tuple[int, bytes]] = []
    for line in Path(path).read_text(encoding="ascii", errors="replace").splitlines():
        line = line.strip()
        if len(line) < 4 or line[0] != "S" or line[1] not in ADDRESS_BYTES:
            continue
        width = ADDRESS_BYTES[line[1]]
        raw = bytes.fromhex(line[2:])
        pieces.append((int.from_bytes(raw[1:1 + width], "big"), raw[1 + width:-1]))
    segments: list[tuple[int, bytearray]] = []
    for address, data in sorted(pieces, key=lambda p: p[0]):
        if segments and segments[-1][0] + len(segments[-1][1]) == address:
            segments[-1][1].extend(data)
        else:
            segments.append((address, bytearray(data)))
    return [(address, bytes(data)) for address, data in segments]


def sample_ranges(segments: list[tuple[int, bytes]], sample: int = 256) -> list[tuple[int, bytes]]:
    """The start and end of each segment; a short segment is taken whole."""
    ranges: list[tuple[int, bytes]] = []
    for address, data in segments:
        if len(data) <= 2 * sample:
            ranges.append((address, data))
        else:
            ranges.append((address, data[:sample]))
            ranges.append((address + len(data) - sample, data[-sample:]))
    return ranges
```

- [ ] **Step 4: Run test to verify it passes**

Run: `~/.venvs/wflash/bin/pytest tests/test_srec.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Add the walkthrough entry and commit**

```bash
git add wflash/core/srec.py tests/test_srec.py docs/walkthrough.md
git commit -m "feat(core): S-record parsing and flash sample selection" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Real adapter: instances, connect, info

**Files:**
- Create: `tests/fake_isystem.py`
- Modify: `wflash/core/winidea_adapter.py`
- Test: `tests/test_real_adapter.py`

**Interfaces:**
- Produces: `RealWinIDEAAdapter` with `list_instances()`, `connect(instance_id)`, `disconnect()`, `get_info()`, class attribute `download_cancellable = False`. `InstanceInfo.instance_id` is `str(tcp_port)`, because `getInstanceId()` returned `''`.
- Produces: `tests.fake_isystem.World` and `install(monkeypatch, world)`.

- [ ] **Step 1: Write the stand-in module**

`tests/fake_isystem.py`:

```python
"""Stand-in for isystem.connect, built from what the spikes observed (docs/winidea_api_notes.md)."""
from __future__ import annotations

import re
import sys
import types

DEVICE = "/iOPEN/UMIConfig.Devices.Devices[0]"
WORKSPACE = "C:/ws/SUZ_7G5_M7.xjrf"
RMS = "E_INVALIDARG: Invalid parameter. /   [CIDEController.cpp, 744], error code: -2147024809\n"


def default_options() -> dict[str, str]:
    return {
        f"{DEVICE}.Device": "W25Q64JW",
        f"{DEVICE}.Enabled": "true",
        f"{DEVICE}.ProgramAtDownload": "true",
        f"{DEVICE}.DownloadFiles[0].Path": "Radar_SUZ05_Gen7.s3",
        f"{DEVICE}.DownloadFiles[0].Enabled": "false",
        f"{DEVICE}.DownloadFiles[0].Offset": "0x1AA000",
        f"{DEVICE}.DownloadFiles[1].Path": "../debug/out/FFI/RAD_SUZ05_FFI.s3",
        f"{DEVICE}.DownloadFiles[1].Enabled": "true",
        f"{DEVICE}.DownloadFiles[1].Offset": "0x0",
        f"{DEVICE}.DownloadFiles[2].Path": "20260623_CAL_T008.sre",
        f"{DEVICE}.DownloadFiles[2].Enabled": "true",
        f"{DEVICE}.DownloadFiles[2].Offset": "0x0",
        "/IDE/System.Debug.Applications[0].Name": "App_M7",
        "/IDE/System.Debug.Applications[0].SymbolFiles.File[0].Path": "../debug/out/bin/Radar_SUZ05_Gen7.elf",
        "/IDE/System.Debug.Applications[1].Name": "App_BBE",
        "/IDE/System.Debug.Applications[1].SymbolFiles.File[0].Path": "BBE_Core_Gen7.elf",
        "/IDE/System.Debug.Applications[2].Name": "App_A53",
        "/IDE/System.Debug.Applications[2].SymbolFiles.File[0].Path": "RAD_A53_Perception_Core.elf",
        "/IDE/System.Debug.Applications[2].SymbolFiles.File[1].Path": "Y:\\out\\RAD_A53_Perception_Core.elf",
    }


class World:
    """State of the simulated winIDEA. Tests read `calls` and change the fields."""

    def __init__(self) -> None:
        self.options = default_options()
        self.instances = [("", WORKSPACE, 5315)]
        self.workspace = WORKSPACE
        self.workspace_dir = "C:\\ws\\"
        self.winidea_version = "9.21.408.1.260751"
        self.module_version = "9.21.408.1"
        self.attached = True
        self.connect_error: Exception | None = None
        self.routing_lost = False
        self.set_error: Exception | None = None
        self.set_stores: str | None = None  # store this instead of the value given
        self.begin_program_error: Exception | None = None
        self.begin_program_hook = lambda: None
        self.stopped_after_reset = True
        self.running = False
        self.flash: dict[int, int] = {}
        self.read_error: Exception | None = None
        self.calls: list[str] = []


def _size_of(world: World, url: str) -> int:
    pattern = re.compile(re.escape(url) + r"\[(\d+)\]\.")
    return len({m.group(1) for key in world.options if (m := pattern.match(key))})


def build_module(world: World) -> types.ModuleType:
    mod = types.ModuleType("isystem.connect")
    routing = "ICONNECT_E_ROUTING: can not access winIDEA. Check if it is still up and running."

    class CConnectionConfig:
        pass

    class VectorWinIDEAInstanceInfo(list):
        pass

    class ByteVector(list):
        def __init__(self, size: int = 0) -> None:
            super().__init__([0] * size)

    class StrVector(list):
        pass

    class Info:
        def __init__(self, item):
            self.item = item

        def getInstanceId(self):
            return self.item[0]

        def getWorkspace(self):
            return self.item[1]

        def getTcpPort(self):
            return self.item[2]

    class ConnectionMgr:
        def enumerateWinIDEAInstances(self, _name, _cfg, vec):
            vec.extend(Info(item) for item in world.instances)

        def connect(self):
            world.calls.append("connect")
            if world.connect_error:
                raise world.connect_error

        def isAttached(self):
            return world.attached

    class Version:
        def toString(self):
            return world.winidea_version

    class CIDEController:
        WORKSPACE_FILE_NAME = 1
        WORKSPACE_DIR = 2

        def __init__(self, _cmgr):
            pass

        def _check(self):
            if world.routing_lost:
                raise AttributeError(routing)

        def getWinIDEAVersion(self):
            return Version()

        def getPath(self, which):
            return world.workspace if which == 1 else world.workspace_dir

        def getOptionStr(self, url):
            self._check()
            if url in world.options:
                return world.options[url]
            if "[" in url:
                raise ValueError(RMS + f"    __StringOut__: Array index (9) out of range (9): {url}")
            raise ValueError(RMS + f"    __StringOut__: Cannot resolve path: {url}")

        def setOption(self, url, value):
            self._check()
            world.calls.append(f"setOption {url}={value}")
            if world.set_error:
                raise world.set_error
            if url not in world.options:
                raise ValueError(RMS + f"    __StringOut__: Cannot resolve path: {url}")
            world.options[url] = world.set_stores if world.set_stores is not None else value

        def getDynamicOptionSize(self, url):
            self._check()
            return 1 if url.endswith(".Devices.Devices") else _size_of(world, url)

        def getOptionJSON(self, url):
            raise AssertionError("getOptionJSON must never be called")

    class Status:
        def isStopped(self):
            return not world.running

        def isRunning(self):
            return world.running

    class CDebugFacade:
        def __init__(self, _cmgr):
            pass

        def reset(self):
            world.calls.append("reset")
            world.running = not world.stopped_after_reset

        def run(self):
            world.calls.append("run")
            world.running = True
            return 0

        def getCPUStatus(self):
            return Status()

    class CSessionCtrl:
        def __init__(self, _cmgr):
            pass

        def begin_program(self):
            world.calls.append("begin_program")
            world.begin_program_hook()
            if world.begin_program_error:
                raise world.begin_program_error

    class CUMIController:
        def __init__(self, _cmgr):
            pass

        def read(self, index, address, size, data):
            world.calls.append(f"read {index} {address:#x} {size}")
            if world.read_error:
                raise world.read_error
            if len(data) < size:
                raise ValueError("Vector size is too small!  [CUMIController.cpp, 136]")
            for i in range(size):
                data[i] = world.flash.get(address + i, 0xFF)

        def getLastError(self):
            return "001 - Operation failed!"

        def write(self, *_args):
            raise AssertionError("umi.write must never be called")

        def erase(self, *_args):
            raise AssertionError("umi.erase must never be called")

        def flush(self, *_args):
            raise AssertionError("umi.flush must never be called")

    for item in (CConnectionConfig, VectorWinIDEAInstanceInfo, ByteVector, StrVector, ConnectionMgr,
                 CIDEController, CDebugFacade, CSessionCtrl, CUMIController):
        setattr(mod, item.__name__, item)
    mod.getModuleVersion = lambda: world.module_version
    return mod


def install(monkeypatch, world: World) -> types.ModuleType:
    mod = build_module(world)
    package = types.ModuleType("isystem")
    package.connect = mod
    monkeypatch.setitem(sys.modules, "isystem", package)
    monkeypatch.setitem(sys.modules, "isystem.connect", mod)
    return mod
```

- [ ] **Step 2: Write the failing test**

`tests/test_real_adapter.py`:

```python
import logging
import sys

import pytest

from tests.fake_isystem import WORKSPACE, World, install
from wflash.core.errors import WinIDEAError
from wflash.core.winidea_adapter import RealWinIDEAAdapter


@pytest.fixture
def world(monkeypatch):
    world = World()
    install(monkeypatch, world)
    return world


@pytest.fixture
def adapter(world):
    adapter = RealWinIDEAAdapter()
    adapter.list_instances()
    return adapter


@pytest.fixture
def connected(adapter):
    adapter.connect("5315")
    yield adapter
    adapter.disconnect()


def test_list_instances_uses_the_port_as_id_because_winidea_gives_an_empty_id(world):
    [info] = RealWinIDEAAdapter().list_instances()
    assert (info.instance_id, info.workspace, info.tcp_port) == ("5315", WORKSPACE, 5315)
    assert info.label() == "SUZ_7G5_M7.xjrf (5315)"


def test_list_instances_returns_empty_when_the_module_is_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "isystem.connect", None)
    assert RealWinIDEAAdapter().list_instances() == []


def test_connect_reports_the_root_cause_when_the_module_cannot_load(monkeypatch):
    monkeypatch.setitem(sys.modules, "isystem.connect", None)
    with pytest.raises(WinIDEAError) as err:
        RealWinIDEAAdapter().connect("5315")
    assert "isystem.connect" in str(err.value)
    assert "bitness" in err.value.hint
    assert isinstance(err.value.__cause__, ImportError)


def test_connect_refuses_when_winidea_attached_to_another_workspace(adapter, world):
    world.workspace = "C:/other/Other.xjrf"
    with pytest.raises(WinIDEAError) as err:
        adapter.connect("5315")
    assert "Other.xjrf" in str(err.value)
    assert "Close" in err.value.hint
    with pytest.raises(WinIDEAError):
        adapter.get_info()  # the session was dropped


def test_connect_accepts_the_same_workspace_written_with_other_slashes(adapter, world):
    world.workspace = "C:\\WS\\suz_7g5_m7.xjrf"
    adapter.connect("5315")
    assert adapter.get_info()["workspace"] == "C:\\WS\\suz_7g5_m7.xjrf"


def test_connect_fails_when_not_attached(adapter, world):
    world.attached = False
    with pytest.raises(WinIDEAError):
        adapter.connect("5315")


def test_connect_wraps_a_connection_failure(adapter, world):
    world.connect_error = OSError("no winIDEA")
    with pytest.raises(WinIDEAError) as err:
        adapter.connect("5315")
    assert isinstance(err.value.__cause__, OSError)


def test_connect_to_an_unknown_instance_fails(adapter):
    with pytest.raises(WinIDEAError):
        adapter.connect("9999")


def test_get_info_reports_versions(connected):
    info = connected.get_info()
    assert info["winidea_version"] == "9.21.408.1.260751"
    assert info["isystem_connect"] == "9.21.408.1"
    assert info["adapter"] == "real"


def test_version_mismatch_is_a_warning_not_a_block(adapter, world, caplog):
    world.module_version = "9.26.11.2"
    with caplog.at_level(logging.WARNING):
        adapter.connect("5315")
        adapter.get_info()
    assert any("does not match" in r.getMessage() and r.levelno == logging.WARNING for r in caplog.records)


def test_download_is_not_cancellable():
    assert RealWinIDEAAdapter.download_cancellable is False
```

- [ ] **Step 3: Run test to verify it fails**

Run: `~/.venvs/wflash/bin/pytest tests/test_real_adapter.py -v`
Expected: FAIL with `ImportError: cannot import name 'RealWinIDEAAdapter'`

- [ ] **Step 4: Write minimal implementation**

In `wflash/core/winidea_adapter.py`, change the imports and add below `create_adapter`:

```python
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
```

`MappingError`, `FlashError`, `threading`, `time`, `Path` and the `srec` names are used by Tasks 3 to 5.

```python
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
        expected = self._workspaces.get(instance_id)
        if expected is None:
            raise WinIDEAError(
                f"No winIDEA instance {instance_id!r} in the last list",
                hint="Click Refresh next to the winIDEA instance list and select it again.",
            )
        ic = self._load_module()
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
```

Add to the `WinIDEAAdapter` Protocol, above `list_instances`:

```python
    download_cancellable: bool
```

Add after `download` in the Protocol:

```python
    def verify_flash(self, progress: ProgressCallback) -> None:
        """Compare samples of the flash with the enabled files; raises FlashError on a difference."""
        ...
```

- [ ] **Step 5: Run test to verify it passes**

Run: `~/.venvs/wflash/bin/pytest tests/test_real_adapter.py -v`
Expected: PASS (11 tests)

- [ ] **Step 6: Add the walkthrough entry and commit**

```bash
git add wflash/core/winidea_adapter.py tests/fake_isystem.py tests/test_real_adapter.py docs/walkthrough.md
git commit -m "feat(core): real winIDEA adapter connects and refuses the wrong workspace" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Real adapter: read and set paths

**Files:**
- Modify: `wflash/core/winidea_adapter.py`
- Test: `tests/test_real_adapter.py`

**Interfaces:**
- Produces: `read_programs()`, `read_applications()`, `set_program_path(name, path)`, `set_symbol_path(name, path)`.
- Naming contract: enabled row `RAD_SUZ05_FFI.s3`; disabled row `Radar_SUZ05_Gen7.s3 (disabled)`; two enabled rows with one file name `x.s3 #1`, `x.s3 #2`, neither matching the bare name; symbol file `App_M7/Radar_SUZ05_Gen7.elf`. Only rows named by their bare file name can be set.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_real_adapter.py`:

```python
from tests.fake_isystem import DEVICE
from wflash.core.errors import MappingError

ROW1 = f"{DEVICE}.DownloadFiles[1].Path"
ELF = "/IDE/System.Debug.Applications[0].SymbolFiles.File[0].Path"


def test_read_programs_names_rows_after_their_file(connected):
    assert {e.name: e.path for e in connected.read_programs()} == {
        "Radar_SUZ05_Gen7.s3 (disabled)": "Radar_SUZ05_Gen7.s3",
        "RAD_SUZ05_FFI.s3": "../debug/out/FFI/RAD_SUZ05_FFI.s3",
        "20260623_CAL_T008.sre": "20260623_CAL_T008.sre",
    }


def test_read_programs_does_not_guess_between_two_enabled_rows_with_one_name(connected, world):
    world.options[f"{DEVICE}.DownloadFiles[2].Path"] = "other/RAD_SUZ05_FFI.s3"
    names = [e.name for e in connected.read_programs()]
    assert "RAD_SUZ05_FFI.s3" not in names
    assert "RAD_SUZ05_FFI.s3 #1" in names and "RAD_SUZ05_FFI.s3 #2" in names
    with pytest.raises(WinIDEAError):
        connected.set_program_path("RAD_SUZ05_FFI.s3", "C:/new/RAD_SUZ05_FFI.s3")


@pytest.mark.parametrize("option", ["Enabled", "ProgramAtDownload"])
def test_read_programs_refuses_a_device_that_would_not_be_programmed(connected, world, option):
    world.options[f"{DEVICE}.{option}"] = "false"
    with pytest.raises(WinIDEAError) as err:
        connected.read_programs()
    assert "Configure" in err.value.hint


def test_read_applications_lists_every_symbol_file_and_ends_at_out_of_range(connected):
    assert {e.name: e.path for e in connected.read_applications()} == {
        "App_M7/Radar_SUZ05_Gen7.elf": "../debug/out/bin/Radar_SUZ05_Gen7.elf",
        "App_BBE/BBE_Core_Gen7.elf": "BBE_Core_Gen7.elf",
        "App_A53/RAD_A53_Perception_Core.elf #0": "RAD_A53_Perception_Core.elf",
        "App_A53/RAD_A53_Perception_Core.elf #1": "Y:\\out\\RAD_A53_Perception_Core.elf",
    }


def test_set_program_path_writes_only_that_row_and_reads_back(connected, world):
    connected.read_programs()
    before = dict(world.options)
    connected.set_program_path("RAD_SUZ05_FFI.s3", "C:/new/RAD_SUZ05_FFI.s3")
    changed = {k for k in world.options if world.options[k] != before[k]}
    assert changed == {ROW1}
    assert world.options[ROW1] == "C:/new/RAD_SUZ05_FFI.s3"


def test_set_symbol_path_writes_only_that_file(connected, world):
    connected.read_applications()
    connected.set_symbol_path("App_M7/Radar_SUZ05_Gen7.elf", "C:/new/Radar_SUZ05_Gen7.elf")
    assert world.options[ELF] == "C:/new/Radar_SUZ05_Gen7.elf"
    assert world.options["/IDE/System.Debug.Applications[1].SymbolFiles.File[0].Path"] == "BBE_Core_Gen7.elf"


def test_set_path_refuses_a_file_with_another_name(connected, world):
    connected.read_programs()
    with pytest.raises(MappingError) as err:
        connected.set_program_path("RAD_SUZ05_FFI.s3", "C:/new/Other.s3")
    assert "Other.s3" in str(err.value)
    assert world.options[ROW1] == "../debug/out/FFI/RAD_SUZ05_FFI.s3"


def test_set_path_file_name_check_ignores_case_like_windows(connected, world):
    connected.read_programs()
    connected.set_program_path("RAD_SUZ05_FFI.s3", "C:/new/rad_suz05_ffi.S3")
    assert world.options[ROW1] == "C:/new/rad_suz05_ffi.S3"


def test_set_path_fails_when_the_read_back_differs(connected, world):
    connected.read_programs()
    world.set_stores = "something else"
    with pytest.raises(WinIDEAError):
        connected.set_program_path("RAD_SUZ05_FFI.s3", "C:/new/RAD_SUZ05_FFI.s3")


def test_set_path_for_a_disabled_row_fails(connected):
    connected.read_programs()
    with pytest.raises(WinIDEAError):
        connected.set_program_path("Radar_SUZ05_Gen7.s3 (disabled)", "C:/new/Radar_SUZ05_Gen7.s3")


def test_lost_connection_is_reported_as_such(connected, world):
    world.routing_lost = True
    with pytest.raises(WinIDEAError) as err:
        connected.read_programs()
    assert "lost" in str(err.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `~/.venvs/wflash/bin/pytest tests/test_real_adapter.py -v`
Expected: FAIL with `AttributeError: 'RealWinIDEAAdapter' object has no attribute 'read_programs'`

- [ ] **Step 3: Write minimal implementation**

Add to `RealWinIDEAAdapter`:

```python
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
```

Note on `test_read_programs_does_not_guess...`: `#i` uses the row index, so rows 1 and 2 give `#1` and `#2`.

- [ ] **Step 4: Run test to verify it passes**

Run: `~/.venvs/wflash/bin/pytest tests/test_real_adapter.py -v`
Expected: PASS (23 tests, counting both parametrized cases)

- [ ] **Step 5: Add the walkthrough entry and commit**

```bash
git add wflash/core/winidea_adapter.py tests/test_real_adapter.py docs/walkthrough.md
git commit -m "feat(core): real adapter names rows after their file and changes only paths" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Real adapter: program, reset, and the workflow against it

**Files:**
- Modify: `wflash/core/winidea_adapter.py`
- Test: `tests/test_real_adapter.py`

**Interfaces:**
- Produces: `download(progress, cancel, timeout_s)`, `reset(run)`, `EXPECTED_PROGRAM_S = 100`.
- `download` ignores `cancel`. Past `timeout_s` it logs a warning and keeps waiting, because aborting mid-erase is unsafe.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_real_adapter.py`:

```python
from wflash.core import winidea_adapter
from wflash.core.cancel import CancelToken
from wflash.core.debug_bundle import DebugContext
from wflash.core.errors import FlashError
from wflash.core.file_matcher import MappingRow
from wflash.core.flash_workflow import FlashRequest, FlashWorkflow


def test_download_calls_begin_program_once(connected, world):
    connected.download(lambda p, m: None, CancelToken(), 600)
    assert world.calls.count("begin_program") == 1


def test_download_ignores_cancel_because_it_cannot_be_stopped_safely(connected, world):
    token = CancelToken()
    token.cancel()
    connected.download(lambda p, m: None, token, 600)
    assert world.calls.count("begin_program") == 1


def test_download_reports_estimated_progress_below_100(connected, world, monkeypatch):
    monkeypatch.setattr(winidea_adapter, "PROGRESS_TICK_S", 0.01)
    monkeypatch.setattr(winidea_adapter, "EXPECTED_PROGRAM_S", 0.02)
    world.begin_program_hook = lambda: __import__("time").sleep(0.1)
    seen = []
    connected.download(lambda p, m: seen.append((p, m)), CancelToken(), 600)
    assert seen and all(0 <= p <= winidea_adapter.MAX_ESTIMATED_PERCENT for p, _m in seen)
    assert "estimated" in seen[0][1]


def test_download_survives_a_failing_progress_callback(connected, world, monkeypatch):
    monkeypatch.setattr(winidea_adapter, "PROGRESS_TICK_S", 0.01)
    world.begin_program_hook = lambda: __import__("time").sleep(0.05)

    def boom(_p, _m):
        raise RuntimeError("signal source deleted")

    connected.download(boom, CancelToken(), 600)
    assert world.calls.count("begin_program") == 1


def test_download_past_the_timeout_warns_and_keeps_waiting(connected, world, monkeypatch, caplog):
    monkeypatch.setattr(winidea_adapter, "PROGRESS_TICK_S", 0.01)
    world.begin_program_hook = lambda: __import__("time").sleep(0.05)
    with caplog.at_level(logging.WARNING):
        connected.download(lambda p, m: None, CancelToken(), 0)
    assert any("cannot be stopped" in r.getMessage() for r in caplog.records)


def test_download_failure_warns_that_the_flash_may_be_erased(connected, world):
    world.begin_program_error = OSError("probe lost")
    with pytest.raises(FlashError) as err:
        connected.download(lambda p, m: None, CancelToken(), 600)
    assert "erased" in err.value.hint
    assert isinstance(err.value.__cause__, OSError)


def test_reset_halts_and_confirms_with_is_stopped(connected, world):
    connected.reset(run=False)
    assert world.calls[-1] == "reset"


def test_reset_with_run_runs(connected, world):
    connected.reset(run=True)
    assert world.calls[-2:] == ["reset", "run"]


def test_reset_fails_when_the_target_does_not_stop(connected, world, monkeypatch):
    monkeypatch.setattr(winidea_adapter, "HALT_WAIT_S", 0.05)
    monkeypatch.setattr(winidea_adapter, "HALT_POLL_S", 0.01)
    world.stopped_after_reset = False
    with pytest.raises(WinIDEAError) as err:
        connected.reset(run=False)
    assert "flash finished" in err.value.hint


def _rows(tmp_path):
    s3 = tmp_path / "RAD_SUZ05_FFI.s3"
    elf = tmp_path / "Radar_SUZ05_Gen7.elf"
    s3.write_text("S0\n")
    elf.write_text("x")
    return [
        MappingRow(kind="program", target="RAD_SUZ05_FFI.s3", pattern="**/RAD_SUZ05_FFI.s3", selected=s3),
        MappingRow(kind="application", target="App_M7/Radar_SUZ05_Gen7.elf", pattern="**/Radar_SUZ05_Gen7.elf", selected=elf),
    ]


def test_workflow_changes_only_the_two_paths_then_programs_once(adapter, world, tmp_path):
    before = dict(world.options)
    rows = _rows(tmp_path)
    FlashWorkflow(adapter, DebugContext()).run(FlashRequest("5315", rows), CancelToken())
    changed = {k for k in world.options if world.options[k] != before[k]}
    assert changed == {ROW1, ELF}
    assert world.options[ROW1] == str(rows[0].selected.resolve())
    assert world.calls.count("begin_program") == 1
    assert world.calls[-1] == "reset"


def test_workflow_rolls_back_both_paths_when_programming_fails(adapter, world, tmp_path):
    before = dict(world.options)
    world.begin_program_error = OSError("probe lost")
    with pytest.raises(FlashError):
        FlashWorkflow(adapter, DebugContext()).run(FlashRequest("5315", _rows(tmp_path)), CancelToken())
    assert world.options == before


def test_workflow_stops_before_programming_when_the_profile_names_a_missing_row(adapter, world, tmp_path):
    rows = _rows(tmp_path)
    rows[0] = MappingRow(kind="program", target="Nope.s3", pattern="*", selected=rows[0].selected)
    with pytest.raises(MappingError):
        FlashWorkflow(adapter, DebugContext()).run(FlashRequest("5315", rows), CancelToken())
    assert "begin_program" not in world.calls


def test_workflow_stops_before_programming_when_the_file_is_named_differently(adapter, world, tmp_path):
    before = dict(world.options)
    other = tmp_path / "Other.s3"
    other.write_text("S0\n")
    rows = _rows(tmp_path)
    rows[0] = MappingRow(kind="program", target="RAD_SUZ05_FFI.s3", pattern="*", selected=other)
    with pytest.raises(MappingError):
        FlashWorkflow(adapter, DebugContext()).run(FlashRequest("5315", rows), CancelToken())
    assert "begin_program" not in world.calls
    assert world.options == before
```

- [ ] **Step 2: Run test to verify it fails**

Run: `~/.venvs/wflash/bin/pytest tests/test_real_adapter.py -v`
Expected: FAIL with `AttributeError` on `PROGRESS_TICK_S` or `download`

- [ ] **Step 3: Write minimal implementation**

Add module constants next to `DEVICES`:

```python
EXPECTED_PROGRAM_S = 100  # observed 98.8 s and 99.0 s; only for the estimated progress
MAX_ESTIMATED_PERCENT = 95
PROGRESS_TICK_S = 1.0
HALT_WAIT_S = 5.0
HALT_POLL_S = 0.2
```

Add to `RealWinIDEAAdapter`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `~/.venvs/wflash/bin/pytest tests/test_real_adapter.py -v`
Expected: all PASS

- [ ] **Step 5: Run the core suite, add the walkthrough entry, commit**

Run: `~/.venvs/wflash/bin/pytest -k "not gui" -q`
Expected: all pass

```bash
git add wflash/core/winidea_adapter.py tests/test_real_adapter.py docs/walkthrough.md
git commit -m "feat(core): real adapter programs through begin_program and confirms the halt" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Sampled verify after flash (core)

**Files:**
- Modify: `wflash/core/winidea_adapter.py`, `wflash/core/fake_adapter.py`, `wflash/core/flash_workflow.py`
- Test: `tests/test_real_adapter.py`, `tests/test_fake_adapter.py`, `tests/test_flash_workflow.py`

**Interfaces:**
- Produces: `verify_flash(progress)` on both adapters; `Step.VERIFY = "Verifying flash samples"`; `FlashRequest.verify: bool = False`; fake `fail_on` name `verify`.
- Order: DOWNLOAD, then VERIFY, then RESET. A verify failure does **not** roll back: the flash has already happened with the new paths.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_real_adapter.py`:

```python
def _prepare_flash(world, tmp_path, corrupt=False):
    world.workspace_dir = str(tmp_path)
    world.options[f"{DEVICE}.DownloadFiles[1].Path"] = "RAD_SUZ05_FFI.s3"
    world.options[f"{DEVICE}.DownloadFiles[2].Path"] = "CAL.bin"
    (tmp_path / "RAD_SUZ05_FFI.s3").write_text(_s3(0x100, b"\x11" * 16) + "\n")
    world.flash = {0x100 + i: 0x11 for i in range(16)}
    if corrupt:
        world.flash[0x105] = 0xFF


def _s3(address, data):
    body = bytes([4 + len(data) + 1]) + address.to_bytes(4, "big") + data
    return "S3" + body.hex().upper() + f"{(~sum(body)) & 0xFF:02X}"


def test_verify_flash_passes_and_skips_disabled_and_non_srec_rows(connected, world, tmp_path):
    _prepare_flash(world, tmp_path)
    seen = []
    connected.verify_flash(lambda p, m: seen.append(p))
    assert [c for c in world.calls if c.startswith("read")] == ["read 0 0x100 16"]
    assert seen[-1] == 100


def test_verify_flash_reports_the_first_difference(connected, world, tmp_path):
    _prepare_flash(world, tmp_path, corrupt=True)
    with pytest.raises(FlashError) as err:
        connected.verify_flash(lambda p, m: None)
    assert "0x000105" in str(err.value)
    assert "Flash again" in err.value.hint


def test_verify_flash_applies_the_row_offset(connected, world, tmp_path):
    _prepare_flash(world, tmp_path)
    world.options[f"{DEVICE}.DownloadFiles[1].Offset"] = "0x1000"
    world.flash = {0x1100 + i: 0x11 for i in range(16)}
    connected.verify_flash(lambda p, m: None)
    assert "read 0 0x1100 16" in world.calls


def test_verify_flash_read_failure_quotes_the_device_error(connected, world, tmp_path):
    _prepare_flash(world, tmp_path)
    world.read_error = OSError("CUMIController::read failed!")
    with pytest.raises(WinIDEAError) as err:
        connected.verify_flash(lambda p, m: None)
    assert "Operation failed" in str(err.value)


def test_verify_flash_with_a_missing_file_fails(connected, world, tmp_path):
    _prepare_flash(world, tmp_path)
    (tmp_path / "RAD_SUZ05_FFI.s3").unlink()
    with pytest.raises(FlashError):
        connected.verify_flash(lambda p, m: None)
```

Append to `tests/test_fake_adapter.py` (it already imports `FlashError` and has a `connected()` helper):

```python
def test_verify_flash_passes_and_can_fail():
    connected().verify_flash(lambda p, m: None)
    failing = FakeWinIDEAAdapter(fail_on=["verify"])
    failing.connect(INSTANCE_ID)
    with pytest.raises(FlashError):
        failing.verify_flash(lambda p, m: None)
```

Change that file's import to `from wflash.core.fake_adapter import INSTANCE_ID, FakeWinIDEAAdapter`.

Append to `tests/test_flash_workflow.py`, using a local helper because its fixtures vary:

```python
from wflash.core.cancel import CancelToken as _Token
from wflash.core.debug_bundle import DebugContext as _Ctx
from wflash.core.errors import FlashError as _FlashError
from wflash.core.fake_adapter import INSTANCE_ID as _ID, FakeWinIDEAAdapter as _Fake
from wflash.core.file_matcher import MappingRow as _Row
from wflash.core.flash_workflow import FlashRequest as _Req, FlashWorkflow as _Flow, Step as _Step


def _verify_setup(tmp_path, fail_on=()):
    adapter = _Fake(download_seconds=0.01, fail_on=fail_on)
    s3 = tmp_path / "App.s3"
    s3.write_text("S0\n")
    steps = []
    flow = _Flow(adapter, _Ctx(), on_step=steps.append)
    req = lambda verify: _Req(_ID, [_Row(kind="program", target="App", pattern="*", selected=s3)], verify=verify)
    return adapter, flow, req, steps, s3


def test_verify_runs_between_download_and_reset_when_requested(tmp_path):
    _adapter, flow, req, steps, _s3 = _verify_setup(tmp_path)
    flow.run(req(True), _Token())
    assert steps.index(_Step.DOWNLOAD) < steps.index(_Step.VERIFY) < steps.index(_Step.RESET)


def test_verify_is_skipped_by_default(tmp_path):
    _adapter, flow, req, steps, _s3 = _verify_setup(tmp_path)
    flow.run(req(False), _Token())
    assert _Step.VERIFY not in steps


def test_verify_failure_does_not_roll_back_the_paths(tmp_path):
    adapter, flow, req, steps, s3 = _verify_setup(tmp_path, fail_on=["verify"])
    with pytest.raises(_FlashError):
        flow.run(req(True), _Token())
    assert _Step.ROLLBACK not in steps
    assert adapter.programs["App"] == str(s3.resolve())
```

Add `import pytest` to `tests/test_flash_workflow.py` if missing.

- [ ] **Step 2: Run tests to verify they fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_real_adapter.py tests/test_fake_adapter.py tests/test_flash_workflow.py -v`
Expected: FAIL with `AttributeError` on `verify_flash` / `VERIFY`, or `TypeError` on `verify=`

- [ ] **Step 3: Implement in the real adapter**

```python
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
```

- [ ] **Step 4: Implement in the fake adapter**

Add `"verify"` to `_NON_RAISING`:

```python
_NON_RAISING = {"download", "list_instances", "connection_lost", "verify"}
```

Add the class attribute and the method:

```python
    download_cancellable = True

    def verify_flash(self, progress: ProgressCallback) -> None:
        self._require_connected()
        self._call("verify")
        if "verify" in self.fail_on:
            raise FlashError("Fake failure injected in 'verify'")
        progress(100, "Verifying flash samples (fake)")
```

Add `verify` to the module docstring's failure list.

- [ ] **Step 5: Implement in the workflow**

In `Step`, after `DOWNLOAD`:

```python
    VERIFY = "Verifying flash samples"
```

In `FlashRequest`, after `timeout_s`:

```python
    verify: bool = False
```

In `_run_connected`, between the `try/except` and `if req.reset:`:

```python
        if req.verify:
            # Outside the rollback: the flash has happened, the new paths describe what is on it.
            self._step(Step.VERIFY)
            self.adapter.verify_flash(self._on_progress)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `~/.venvs/wflash/bin/pytest -k "not gui" -q`
Expected: all pass

- [ ] **Step 7: Add the walkthrough entry and commit**

```bash
git add wflash/core/winidea_adapter.py wflash/core/fake_adapter.py wflash/core/flash_workflow.py tests/test_real_adapter.py tests/test_fake_adapter.py tests/test_flash_workflow.py docs/walkthrough.md
git commit -m "feat(core): optional sampled flash verify after programming" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: GUI: lock Cancel while programming, close prompt, verify checkbox

**Files:**
- Modify: `wflash/core/fake_adapter.py`, `wflash/gui/flash_mixin.py`, `wflash/gui/main_window.py`, `wflash/gui/main_window.ui`
- Generated: `wflash/gui/ui_main_window.py`
- Test: `tests/test_gui_flash.py`, `tests/test_gui_close_window.py`

**Interfaces:**
- Consumes: `adapter.download_cancellable`, `FlashRequest.verify`, `Step.VERIFY`.
- Produces: `FlashMixin.flash_locked() -> bool`; widget `checkBox_verifyFlash`; fake `FakeWinIDEAAdapter(cancellable=False)` and `WFLASH_FAKE_FAIL=no_cancel`.
- The fake stays cancellable by default, so the existing rollback-on-cancel tests keep covering that branch.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gui_flash.py` (`make_host` already fills the mapping and selects the instance):

```python
def test_gui_thread_cancel_is_locked_while_programming_when_it_cannot_be_stopped(qtbot, tmp_path):
    w = make_host(qtbot, tmp_path, FakeWinIDEAAdapter(download_seconds=0.5, cancellable=False))
    w.start_flash()
    qtbot.waitUntil(w.flash_locked, timeout=3000)
    assert w.ui.pushButton_flash.text() == "Cancel"
    assert not w.ui.pushButton_flash.isEnabled()
    w.cancel_flash()  # ignored while locked
    assert w.current_step() != "Cancelling"
    qtbot.waitUntil(lambda: not w.flash_active(), timeout=5000)
    assert w.current_step() == Step.DONE.value
    assert not w.flash_locked()


def test_gui_thread_cancellable_adapter_is_not_locked(qtbot, tmp_path):
    w = make_host(qtbot, tmp_path, FakeWinIDEAAdapter(download_seconds=0.5))
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DOWNLOAD.value, timeout=3000)
    assert not w.flash_locked()
    assert w.ui.pushButton_flash.isEnabled()
    w.cancel_flash()
    qtbot.waitUntil(lambda: not w.flash_active(), timeout=5000)


def test_gui_thread_verify_checkbox_is_off_by_default_and_reaches_the_workflow(qtbot, tmp_path):
    adapter = FakeWinIDEAAdapter(download_seconds=0.01)
    w = make_host(qtbot, tmp_path, adapter)
    assert not w.ui.checkBox_verifyFlash.isChecked()
    w.ui.checkBox_verifyFlash.setChecked(True)
    w.start_flash()
    qtbot.waitUntil(lambda: not w.flash_active(), timeout=5000)
    assert "verify" in adapter.calls
```

Append to `tests/test_gui_close_window.py`:

```python
def test_gui_thread_close_while_locked_warns_and_stays_open_on_no(make, qtbot):
    w = make.factory(FakeWinIDEAAdapter(download_seconds=1.0, cancellable=False))
    w.start_flash()
    qtbot.waitUntil(w.flash_locked, timeout=3000)
    make.answer = QMessageBox.StandardButton.No
    w.close()
    assert "cannot be interrupted" in make.questions[0]
    assert not w._closing and w.flash_active()
    qtbot.waitUntil(lambda: not w.flash_active(), timeout=5000)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_gui_flash.py tests/test_gui_close_window.py -v`
Expected: FAIL with `TypeError: ... unexpected keyword argument 'cancellable'`

- [ ] **Step 3: Give the fake a non-cancellable mode**

In `FakeWinIDEAAdapter`: remove the class attribute `download_cancellable = True` added in Task 5, and add a constructor parameter:

```python
        fail_on: Iterable[str] = (),
        cancellable: bool = True,
    ) -> None:
```

```python
        self.download_cancellable = cancellable
```

Change `from_env`:

```python
        return cls(download_seconds=seconds, fail_on=fail, cancellable="no_cancel" not in fail)
```

Add `"no_cancel"` to `_NON_RAISING`, and document it in the module docstring: `no_cancel - download ignores cancel, like the real adapter`.

Change the wait in `download`:

```python
            if self.download_cancellable:
                if cancel.wait(self.download_seconds / steps):
                    cancel.raise_if_cancelled()
            else:
                time.sleep(self.download_seconds / steps)
```

- [ ] **Step 4: Add the checkbox in Designer XML**

In `wflash/gui/main_window.ui`, inside `horizontalLayout_afterFlash`, after the `checkBox_run` item:

```xml
             <item>
              <widget class="QCheckBox" name="checkBox_verifyFlash">
               <property name="toolTip">
                <string>Read samples of the flash back and compare them with the files. Adds about 3 minutes.</string>
               </property>
               <property name="text">
                <string>Verify samples</string>
               </property>
              </widget>
             </item>
```

Run: `~/.venvs/wflash/bin/pyside6-uic wflash/gui/main_window.ui -o wflash/gui/ui_main_window.py`

- [ ] **Step 5: Implement the lock**

In `FlashMixin._init_flash`, after `self._flash_cancel_requested = False`:

```python
        self._flash_locked = False
```

Add after `flash_active`:

```python
    def flash_locked(self) -> bool:
        """Programming has started and cannot be stopped safely; Cancel stays disabled."""
        return self._flash_locked
```

In `_update_flash_controls`, change the button line, and add the checkbox to the disable list:

```python
        self.ui.pushButton_flash.setEnabled(
            can_flash or (flashing and not self._flash_cancel_requested and not self._flash_locked)
        )
```

```python
            self.ui.checkBox_verifyFlash,
```

In `start_flash`, add to the `FlashRequest(...)`:

```python
            verify=self.ui.checkBox_verifyFlash.isChecked(),
```

and next to `self._flash_cancel_requested = False`:

```python
        self._flash_locked = False
```

Change the top of `cancel_flash`:

```python
        if not self.flash_active() or self._flash_cancel_requested or self._flash_locked:
            return
```

In `_on_flash_step`, inside the `if text == Step.DOWNLOAD.value` block, after the stats line:

```python
            if not self.adapter.download_cancellable:
                self._flash_locked = True
                log.info("Programming started; Cancel is locked until it finishes")
                self._update_flash_controls()
```

The `if text == ...` condition also needs `self._estimator` today. Split it so the lock does not depend on the estimator:

```python
        if text == Step.DOWNLOAD.value:
            if self._estimator is not None:
                self._estimator.start(self._flash_total_bytes, time.monotonic())
                self.ui.label_flashStats.setText(self._estimator.running_text())
            if not self.adapter.download_cancellable:
                self._flash_locked = True
                log.info("Programming started; Cancel is locked until it finishes")
                self._update_flash_controls()
```

In `_on_flash_finished`, before `if self._closing:`:

```python
        self._flash_locked = False
```

The existing success path already logs "The flash completed before the cancel took effect" when Cancel was pressed just before the lock arrived.

- [ ] **Step 6: Implement the close prompt**

In `MainWindow.closeEvent`, replace the question:

```python
        if self.flash_active() and not self._closing:
            text = (
                "The flash is being programmed and cannot be interrupted. Quitting now could leave "
                "the ECU with erased flash. Quit anyway?"
                if self.flash_locked()
                else "A flash is in progress. Cancel it (the previous workspace paths will be restored) and quit?"
            )
            answer = QMessageBox.question(self, "WFlash", text)
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
```

"Quit anyway" keeps the existing bounded wait and abandon path, so a hung `begin_program` cannot make the window impossible to close.

- [ ] **Step 7: Run tests to verify they pass**

Run: `~/.venvs/wflash/bin/pytest -q && ~/.venvs/wflash/bin/pytest -k thread -q`
Expected: all pass

- [ ] **Step 8: Add a stress-test checkpoint**

Read `section_flash` in `tools/stress_test.py` and add a run with `FakeWinIDEAAdapter(download_seconds=..., cancellable=False)` built the way that section builds its adapter: press Flash, wait for `window.flash_locked()`, `self.check(not window.ui.pushButton_flash.isEnabled(), "flash: Cancel locked while programming")`, then wait for idle and `self.check(window.current_step() == "Done", "flash: locked run completes")`.

Run: `~/.venvs/wflash/bin/python tools/stress_test.py`
Expected: `STRESS_RESULT=PASS`

- [ ] **Step 9: Add the walkthrough entry and commit**

```bash
git add wflash/core/fake_adapter.py wflash/gui/flash_mixin.py wflash/gui/main_window.py wflash/gui/main_window.ui wflash/gui/ui_main_window.py tests/test_gui_flash.py tests/test_gui_close_window.py tools/stress_test.py docs/walkthrough.md
git commit -m "feat(gui): lock Cancel while programming; verify checkbox; close prompt" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Wire it up, real profile, Windows acceptance

**Files:**
- Modify: `wflash/core/winidea_adapter.py`, `README.md`, `docs/winidea_api_notes.md`, `docs/windows_test_guide.md`
- Create: `profiles/suz05_m7_ffi.yaml`
- Test: `tests/test_real_adapter.py`, `tests/test_profile.py`; update any test that expects the old error

**Interfaces:**
- Produces: `create_adapter("real") -> RealWinIDEAAdapter`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_real_adapter.py`:

```python
from wflash.core.winidea_adapter import create_adapter


def test_create_adapter_real_builds_without_importing_isystem(monkeypatch):
    monkeypatch.setitem(sys.modules, "isystem.connect", None)
    assert isinstance(create_adapter("real"), RealWinIDEAAdapter)
```

Append to `tests/test_profile.py`:

```python
def test_suz05_profile_targets_only_the_ffi_row_and_the_m7_elf():
    from pathlib import Path

    profile = load_profile(Path(__file__).parents[1] / "profiles" / "suz05_m7_ffi.yaml")
    assert [p.winidea_entry for p in profile.programs] == ["RAD_SUZ05_FFI.s3"]
    assert [a.winidea_app for a in profile.applications] == ["App_M7/Radar_SUZ05_Gen7.elf"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_real_adapter.py tests/test_profile.py -v`
Expected: FAIL (`WinIDEAError: The real winIDEA adapter is not available`, and a missing profile)

- [ ] **Step 3: Implement**

In `create_adapter`, replace the `kind == "real"` branch:

```python
    if kind == "real":
        return RealWinIDEAAdapter()
```

Create `profiles/suz05_m7_ffi.yaml`:

```yaml
# SUZ05: chỉ thay file .s3 của Winbond và ELF của App_M7.
# File CAL (.sre), App_BBE và App_A53 giữ nguyên như trong workspace.
# winidea_entry là tên file của dòng đang tick trong Hardware > Winbond > Configure > Download Files.
# winidea_app là "<Application>/<tên file symbol>". File trong artifact phải trùng tên với file này.
# Mass erase và các tùy chọn khác theo cấu hình workspace.
name: SUZ05_M7_FFI
gitlab:
  project: group/saf85xx-sw     # đổi thành project thật, hoặc sửa trong Load from GitLab
  job_filter: "*"
programs:
  - winidea_entry: "RAD_SUZ05_FFI.s3"
    pattern: "**/RAD_SUZ05_FFI.s3"
applications:
  - winidea_app: "App_M7/Radar_SUZ05_Gen7.elf"
    pattern: "**/Radar_SUZ05_Gen7.elf"
post_flash:
  reset: true
  run: false
timeouts:
  download_s: 600
```

- [ ] **Step 4: Fix the tests that expected the old error**

In `test_create_adapter` in `tests/test_fake_adapter.py`, delete only the two lines `with pytest.raises(WinIDEAError):` and `create_adapter("real")`; keep the rest of the test. `test_create_adapter_real_builds_without_importing_isystem` covers the real case. In `README.md`, remove the status note and the "Lưu ý" saying the real adapter is missing, and the instruction to add `--adapter fake` to shortcuts.

- [ ] **Step 5: Run everything**

Run: `~/.venvs/wflash/bin/pytest -q && ~/.venvs/wflash/bin/pytest -k thread -q && ~/.venvs/wflash/bin/python tools/stress_test.py && QT_QPA_PLATFORM=offscreen ~/.venvs/wflash/bin/python main.py --adapter fake --smoke`
Expected: all pass, `STRESS_RESULT=PASS`, exit 0

- [ ] **Step 6: Write the acceptance section, update the notes, commit, push**

Append to `docs/windows_test_guide.md`, in Vietnamese:

```markdown
## Vòng 7: thử WFlash thật

⚠️ Bước 3 trở đi **ghi vào flash**. Nếu ECU không chạy, khôi phục bằng Debug → Download bấm tay rồi gửi log.

1. Lấy bản mới. Mở một winIDEA duy nhất với workspace `R_04_01_01`. `python -m pip install -e ".[dev]"`, rồi `python main.py --verbose`.
2. Chọn profile `SUZ05_M7_FFI`, Load from GitLab, tải artifact. Kiểm tra bảng mapping và chọn instance. Thử **cùng firmware đang có trên ECU trước**.
3. Bấm Flash. Kiểm tra: Cancel bị khóa khi bước Downloading bắt đầu; Output của winIDEA có đúng 1 `ERASING`; xong thì target dừng.
4. Tắt bật nguồn ECU, kiểm tra firmware. Kiểm tra trong winIDEA: dòng `.s3` và ELF `App_M7` trỏ tới file trong cache, dòng CAL và ELF khác giữ nguyên.
5. Không đóng app, bấm Flash lần nữa với tick **Verify samples** (thêm khoảng 3 phút). Mong đợi xong không lỗi.
6. Tải artifact **firmware khác**, Flash, tắt bật nguồn, kiểm tra ECU đúng là chạy firmware mới. Đây là bước đầu tiên chứng minh firmware mới thật sự được ghi.
7. Thử lỗi: chọn sai tên file trong bảng mapping (mong đợi báo lỗi, không flash, path giữ nguyên).
8. Export debug bundle, gửi lại cùng Output của winIDEA.
```

In `docs/winidea_api_notes.md`, change the status line to say the adapter is implemented from these notes and awaits Round 7 on hardware.

```bash
git add wflash/core/winidea_adapter.py profiles/suz05_m7_ffi.yaml tests README.md docs/winidea_api_notes.md docs/windows_test_guide.md docs/walkthrough.md
git commit -m "feat: enable the real winIDEA adapter; SUZ05 profile and Windows acceptance steps" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push
```

Nothing is claimed to work on hardware until the user reports Vòng 7.

---

## Known limits

- A hung `begin_program` cannot be stopped. The user is warned at the timeout through the log, and "Quit anyway" abandons the worker.
- Selecting one of several winIDEA instances is not possible: `connect` attaches to the most recent one and refuses if it is not the selected workspace.
- `isystem.connect` 9.21.408.1 ships inside winIDEA's own Python, with no wheel to install, so the app has so far only been run against 9.26.11 from the user's env. It logs a warning about this.
- All mapped files come from one artifact (see the open question in the handoff message).
