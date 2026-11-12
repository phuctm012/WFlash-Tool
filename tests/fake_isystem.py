"""Stand-in for isystem.connect, built from what the spikes observed (docs/winidea_api_notes.md)."""
from __future__ import annotations

import re
import sys
import types

DEVICE = "/iOPEN/UMIConfig.Devices.Devices[0]"
DATA_UMI_DEVICE = "/iOPEN/Data.UMI.Devices.Devices[0]"  # workspace DD_05_02_01, bench 1 (spike 19)
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
        self.reset_error: Exception | None = None
        self.running = False
        self.flash: dict[int, int] = {}
        self.read_error: Exception | None = None
        self.umi_last_error = "001 - Operation failed!"
        # Spike 16 (2026-11-09), the state in which flashing worked: (name, status, status_string).
        self.cores: list[tuple[str, int, str]] = [
            ("M7_0", 2, "STOP"), ("M7_RFE", 2, "STOP"), ("A53", 2, "STOP"), ("SPT", 5, "IDLE"), ("BBE32EP", 3, "RUN"),
        ]
        # Each reset takes the next entry as `cores`; the last one stays. None leaves `cores` alone.
        self.cores_after_reset: list[list[tuple[str, int, str]]] | None = None
        self.core_status_error: Exception | None = None
        self.get_status_hook = lambda: None
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
            if url.endswith(".Devices.Devices"):
                if not any(key.startswith(url + "[") for key in world.options):
                    # spike 19: a root the workspace does not have raises E_INVALIDARG
                    raise ValueError(RMS + f"    __StringOut__: Cannot resolve path: {url}")
                return 1
            return _size_of(world, url)

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
            if world.reset_error:
                raise world.reset_error
            world.running = not world.stopped_after_reset
            if world.cores_after_reset:
                world.cores = world.cores_after_reset.pop(0) if len(world.cores_after_reset) > 1 \
                    else world.cores_after_reset[0]

        def run(self):
            world.calls.append("run")
            world.running = True
            return 0

        def getCPUStatus(self):
            return Status()

    class _Core:
        def __init__(self, entry):
            self._entry = entry

        def name(self):
            return self._entry[0]

        def status(self):
            return self._entry[1]

        def status_string(self):
            return self._entry[2]

    class _SoC:
        def cores(self):
            return [_Core(entry) for entry in world.cores]

        def name(self):
            return "MCU"

    class _Session:
        def SoCs(self):
            return [_SoC()]

    class CSessionCtrl:
        def __init__(self, _cmgr):
            pass

        def get_status(self):
            world.calls.append("get_status")
            world.get_status_hook()
            if world.core_status_error:
                raise world.core_status_error
            return _Session()

        def get_topology(self):
            if world.core_status_error:
                raise world.core_status_error
            return _Session()

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
            return world.umi_last_error

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
    for name, value in (("stDetached", 0), ("stInaccessible", 1), ("stStopped", 2), ("stRunning", 3),
                        ("stHalted", 4), ("stIdle", 5), ("stSuspended", 6)):
        setattr(mod, f"EStatus_Core_{name}", value)
    return mod


def install(monkeypatch, world: World) -> types.ModuleType:
    mod = build_module(world)
    package = types.ModuleType("isystem")
    package.connect = mod
    monkeypatch.setitem(sys.modules, "isystem", package)
    monkeypatch.setitem(sys.modules, "isystem.connect", mod)
    return mod


def use_data_umi_root(world) -> None:
    """Lay the device list out like workspace DD_05_02_01 (bench 1, spike 19): /iOPEN/Data.UMI..."""
    world.options = {(DATA_UMI_DEVICE + key[len(DEVICE):] if key.startswith(DEVICE) else key): value
                     for key, value in world.options.items()}
