# winIDEA / isystem.connect — API notes

**This file is the authority for every real `isystem.connect` call in `wflash/core/winidea_adapter.py`.** A call that is not recorded here is a guess and must carry `# UNVERIFIED:` in the code. See `CLAUDE.md`, "Rule zero".

Status: **`RealWinIDEAAdapter` is implemented from these notes (Plan 2) and tested against `tests/fake_isystem.py`. The full flow in WFlash has not run on hardware yet: see Vòng 7 in `docs/windows_test_guide.md`.** **spike round 3 ran on 2026-11-07; see "Round 3 findings" and "Round 3 program run". Path writes and `CUMIController.write` have run. Whether the flash content is correct after the program is NOT verified (spike 09).** Spike round 2 ran on 2026-10-10 (06 + 03; see "Round 2 findings" below). **Spike round 1 ran on 2026-10-06** (spike 01–05, results in the user's `results.7z`). Connect, reading symbol-file paths, debug download, reset and run are observed. **Writing any path, and reading the external-flash (.s3) file list, are NOT verified yet** — see "Open questions". Round 2 is `spike/06_probe_umi.py` plus a corrected `03_set_paths.py` run.

Everything below is pasted or condensed from the probe output; nothing is paraphrased from documentation.

---

## Environment

| Item | Value | How it was obtained |
|---|---|---|
| winIDEA version | `9.21.408.1.260751` | `ide.getWinIDEAVersion().toString()` (01) |
| winIDEA install dir | `C:/Data/_Devtools/Winidea408/` | `ide.getPath(WINIDEA_EXE_DIR)` (01) |
| `isystem.connect` version | **`9.26.11.2.316513`** (`ic.getModuleVersion()` → `9.26.11.2`) | 00_env — **does not match winIDEA 9.21**, see Open questions |
| `isystem.connect` location | `C:\Data\_Devtools\miniforce\envs\pyside6\Lib\site-packages\isystem\connect.py` (conda env `pyside6`) | 00_env |
| Python | 3.12.14 conda-forge, MSC v.1944 **64 bit (AMD64)**, `('64bit', 'WindowsPE')` | 00_env |
| OS | Windows-11-10.0.26200-SP0 | 00_env |
| Workspace | `C:/Data/nguyho11/WinIdea_R_04_01_02/STRX_WinIdea_SUZ_YVF_R_04_01_02/SUZ_7G5_M7.xjrf` | `inst.getWorkspace()` (01) |
| External flash device | Winbond **W25Q64JW**, SPI, x1 (menu *Hardware → Winbond W25Q64JW SPI*) | screenshots 1, 2 |

## Module surface

Full `C*` list is in `00_env.txt`. Relevant to WFlash: `ConnectionMgr`, `CConnectionConfig`, `CIDEController`, `CLoaderController`, `CDebugFacade`, `CExecutionController`, `CDownloadConfiguration`, `CUMIController`, `CStorageDeviceController`, `CStorageDeviceFactory`, `CBasicFlashStorageDevice`, `CMulticoreConnectionMgr`, `CPUStatus`, `CWinIDEAVersion`, `COptionController`, `COptionFilesCfg`, `COptionAppCfg`, `COptionAppsCfg`, `COptionSessionCfg`, `COptionSoCCfg`, `CWorkspaceController`.

Members observed (01):

- `CIDEController`: `getOptionStr`, `getOptionInt`, `getOptionJSON`, `setOption`, `setOption_str`, `setOptionJSON`, `optionExists`, `getDynamicOptionSize`, `getDynamicOptions`, `addDynamicOption`, `removeDynamicOption`, `commitOptions`, `getPath`, `getWinIDEAVersion`, `getDefaultDownloadFile`, `OPT_DEST_IDE`, `OPT_DEST_IOPEN`, `OPT_DEST_DOCUMENT`, `OPT_DEST_PLUGIN`, `WORKSPACE_DIR`, `WORKSPACE_FILE_NAME`, `WINIDEA_EXE_DIR`, … (full list in 01).
- `CLoaderController`: `DLIST_PRIMARY`, `DLIST_TARGET`, `addToDownloadList`, `clearDownloadList`, `download`, `downloadFromList`, `downloadWithoutCode`, `getDownloadList`, `removeFromDownloadList`, `targetDownload`, `verifyDownload`.
- `CDebugFacade`: `download`, `reset`, `run`, `stop`, `getCPUStatus`, `waitUntilStopped`, `waitWhileRunning`, `getLoaderController`, `getExecutionController`, …
- `CExecutionController`: `reset`, `resetAndRun`, `run`, `stop`, `getCPUStatus`, `waitUntilStopped`, `waitWhileRunning`, `TOUT_1s`, `TOUT_10s`, `TOUT_100s`, `TOUT_INF`, `TOUT_NONE`, …

## Connecting / listing instances

```python
cmgr = ic.ConnectionMgr()
vec = ic.VectorWinIDEAInstanceInfo()
cmgr.enumerateWinIDEAInstances("", ic.CConnectionConfig(), vec)
for inst in vec: inst.getInstanceId(), inst.getWorkspace(), inst.getTcpPort()
cmgr.connect()            # no instance id -> most recent winIDEA
cmgr.isAttached()         # -> True
```

Observed: one instance, `getInstanceId() -> ''` (**empty id**), `getWorkspace() -> '.../SUZ_7G5_M7.xjrf'`, `getTcpPort() -> 5315`. Because the id is empty, the `cfg.instanceId(id)` path was never exercised; `cmgr.connect()` with no config was used and worked.

Consequence for the adapter: an instance cannot be identified by id alone. Identify it by **(workspace, TCP port)**; connecting to a specific one of several instances is still unverified (needs a config that selects by port — open question).

## Applications (symbol files) — reading works

Option URL shape that **works** with `ide.getOptionStr(url)`:

```
/IDE/System.Debug.Applications[<i>].Name                       -> 'App_M7'
/IDE/System.Debug.Applications[<i>].SymbolFiles.File[<j>].Path -> '<path as stored, relative to the workspace dir>'
```

Observed values:

| URL | Value |
|---|---|
| `Applications[0].Name` | `'App_M7'` |
| `Applications[0].SymbolFiles.File[0].Path` | `'../../../../Users/testla3/Downloads/artifacts (62)/out/bin/Radar_SUZ05_Gen7.elf'` |
| `Applications[1].SymbolFiles.File[0].Path` | `'BBE_Core_Gen7.elf'` |

From the workspace XML (02) and screenshot 3/4: three Applications **`App_M7`, `App_BBE`, `App_A53`**. `App_M7` has **two** symbol files (`Radar_SUZ05_Gen7.elf`, `Radar_SUZ05_Gen7_BM.elf`, both checked); "Default file for debugging" is `Radar_SUZ05_Gen7_BM.elf`. `App_A53` has two (`RAD_A53_Perception_Core.elf`, `Y:\out\bin\a53-binaries\RAD_A53_Perception_Core.elf`).

URLs that **fail** with `ValueError: E_INVALIDARG ... Cannot resolve path`:
`/IDE/Debug.DownloadFiles.File[0].Path`, `/IDE/Debug.DownloadFiles.File[0].Options.Path`, `/IDE/System.Debug.SoCs[0].Name`, `/IDE/System.Debug.SoCs[0].DLFs_Program.File[0].Path`, `/IDE/System.Debug.SoCs[0].Cores[0].Name`, and every URL formed literally from the XML element path (`/IDE/winIDEA.REG_ROOT...`, `/IDE/REG_ROOT...`, `/IDE/HServer.REG_ROOT...`).

Error shape (always `ValueError`, message contains `E_INVALIDARG`, `error code: -2147024809`, and `__StringOut__: Cannot resolve path: <url>`). The adapter can classify "unknown option" by that `Cannot resolve path` text inside a `ValueError` raised by `getOptionStr`/`setOption`.

## External flash (.s3) file list — where it lives

The .s3 files are **not** in the IDE debug download list. They belong to the external-flash device configured under *Hardware → Winbond W25Q64JW SPI → Configure…* (screenshot 2), stored in the **HServer** part of the workspace:

```
HServer.REG_ROOT.HServerData.Data.UMI1.Devices.Devices.__.0.DownloadFiles.__.0.Path = 'Radar_SUZ05_Gen7.s3'
HServer.REG_ROOT.HServerData.Data.UMI1.Devices.Devices.__.0.DownloadFiles.__.1.Path = '../../../tranph9/debug/CS_R5/APP_NOINSTALL/artifacts (61)/out/FFI/RAD_SUZ05_FFI.s3'
HServer.REG_ROOT.HServerData.HW.BDM.UMIConfig.Devices.Devices.__.0.DownloadFiles.__.0.Path = (same)
HServer.REG_ROOT.HServerData.HW.BDM.UMIConfig.Devices.Devices.__.0.DownloadFiles.__.1.Path = (same)
```

Device dialog (screenshot 2): device `W25Q64JW`, `SPI`, Parallel x1. Options checked: **Mass erase before download, Program at download, Allow mass erase, Use buffer compression, Use hash verification**; not checked: Verify after program, Verify on the fly, Read-only, Allow download only. Download Files list has **at least 4 rows** with a **checkbox (enabled) per row** and an **Offset** column (`Radar_SUZ05_Gen7.s3` unchecked, offset `1AA000`; `../../../tranph9/debug/CS_R5/APP_...` checked; `20260623_142557_2018688_CAL_T...` checked; `../../../tranph9/debug/CS_R5/BM_R...` checked). The XML dump only matched two rows because the spike's file regex looked for `.elf/.s3/.srec/.s19/.mot/.hex` — the other rows are probably `.bin` or another extension.

Rows have **no name**, only path + offset + enabled. The profile cannot match an `.s3` entry by a name, as the original design assumed (`winidea_entry`).

How to read/write this list through `isystem.connect` is **not known yet** (spike 06).

## Setting a file path

**Not verified.** The 03 run passed a file path instead of an option URL (`--url "../../../tranph9/.../Radar_SUZ05_Gen7_BM.elf"`), so every call failed with `Cannot resolve path`. Nothing was changed. Re-run with a real URL (see Open questions).

## download()

```python
ic.CLoaderController(cmgr).download()   # returns normally, no return value printed
```

Observed three runs: **8.3 s, 6.3 s, 6.4 s**. No progress callback; `download()` blocks until done. The `--facade` variant was not run.

Whether this debug download also programmed the Winbond flash is **not proven**: the device has "Program at download" checked, so it is expected to, but 6 s for mass erase + program of several images is short. "Use hash verification" may skip unchanged content. Needs a check (Open questions).

CPU status right after download: `status: 16`, `isMustInit: 1`, `isStopped/isRunning/isReset/isHalted: 0` — the target is in a "must init" state, so WFlash must reset after download.

## reset / halt / run

```python
debug = ic.CDebugFacade(cmgr)
debug.reset()          # -> None
debug.getCPUStatus()   # -> CPUStatus; isStopped(), isRunning(), isReset(), toString()
debug.run()            # -> 0
```

Observed:

- Before (attached, not initialised): `status: 22`, `isAttach: 1`, all others 0.
- After `reset()`: `status: 49`, **`isStopped: 1`**, `isStopReasonStep: 1`, `execAddress: 872985758` (0x3408B59E). `isReset` and `isHalted` stay 0 — **"halted after reset" must be checked with `isStopped()`**, not `isHalted()`/`isReset()`.
- A second `reset()` from stopped: stopped again, `execAddress: 873327368`.
- After `run()`: `status: 18`, `isRunning: 1`.

Multi-core: `cmgr.getCoreIds` / `cmgr.getCores` do not exist (the probe printed nothing). Per-core state is unverified; `CMulticoreConnectionMgr` exists and is the next thing to look at if per-core reset/halt is required.

## Round 2 findings (2026-10-10)

Workspace this time: `C:/Data/tranph9/winIDEA/WinIdea_R_04_01_01/STRX_WinIdea_SUZ_YVF_R_04_01_01/SUZ_7G5_M7.xjrf` (a different copy; its `App_M7` has **one** symbol file). TCP port 5316 for 06, 5315 for 03 (winIDEA was probably restarted in between, see the JSON hazard).

### External-flash file list: the URL that works

```
ide.getOptionStr("/iOPEN/UMIConfig.Devices.Devices[0].DownloadFiles[0].Path")  -> 'Radar_SUZ05_Gen7.s3'
```

`/IOPEN/` (capitals) works too. Every other root fails with `Cannot resolve path`: `/iOPEN/UMI1...`, `/iOPEN/HServerData...`, `/iOPEN/HW.BDM.UMIConfig...`, and all `/HServer/`, `/IDE/...` forms. `/iOPEN/Data.UMI1...` is rewritten by winIDEA to `Cfg.SoC[0].BBS.UMI1...` and then fails. So the XML element `HServerData.HW.BDM.UMIConfig` maps to the option root **`/iOPEN/UMIConfig`**.

Count, offset and enabled fields of each row: not known yet (spike 07). Writing: not tried yet.

### Index out of range is a distinct error

`getOptionStr("/IDE/System.Debug.Applications[0].SymbolFiles.File[1].Path")` when only one file exists:
`ValueError: E_INVALIDARG ... __StringOut__: Array index (1) out of range (1): File[1].Path  [DataDescriptor_Algorithm.cpp, 456]`. `optionExists(<same url>) -> False` (no exception). The adapter can enumerate a list by reading index 0, 1, 2… until this error, or by `optionExists`.

### HAZARD: getOptionJSON on a large tree

`ide.getOptionJSON("/IDE/System.Debug.Applications")` returned a huge string in which every scalar is `"IDArray container not supported: ..."`, and **every call after it failed** with `AttributeError: ICONNECT_E_ROUTING: can not access winIDEA. Check if it is still up and running.` (`error code: -2147221487`), then `ConnectionMgr() should be connected to winIDEA for this operation!`. The user confirmed winIDEA itself did **not** hang or close during that run, so the connection broke while winIDEA stayed up; the cause is unknown. **The adapter must never call `getOptionJSON` on a list/tree.** Read single scalar options only.

`ICONNECT_E_ROUTING` is also the exception shape for "connection lost": `AttributeError` (not `ValueError`), message starts with `ICONNECT_E_ROUTING`.

### UMI / storage API (from docstrings, not yet called)

- `CUMIController(cmgr)` constructs fine. Methods: `getDeviceIndex(deviceName, isThrowOnNotFound=?)`, **`write(deviceIndex, programMode)` — "Writes contents of pre-configured files to device"** (= the *Program* menu item), `verify(deviceIndex, …)` (throws `CUMIException` on mismatch), `erase(deviceIndex, programMode)`, `isDeviceEmpty(DWORD)` / `(DWORD, ADDRESS, ADDRESS)`, `readHash`, `getLastError()`. `programMode` is `IConnectUMI::wProgDevice` or `wProgCache`. `secure/unsecure` removed since 9.21.418.
- `CStorageDeviceFactory`: `DEVICES_OPT_URL`, `getDeviceNames(connectionMgr, deviceNames: std::vector<std::string>)` — "collects all enabled storage device names", `makeDevice(...)`, `terminateDevice(...)` (eMMC only).
- `CStorageDeviceController`: same `write(programMode)`, `verify`, `erase`, without a device index.
- `CLoaderController.download()`: **Deprecated: "Use CSessionCtrl::begin_program instead"**. "Downloads executables to the target. The download files are defined in winIDEA, *Debug / Configure Session / SoCs / Edit / Program Files*. **This method resets the target.**" — so it programs the SoC program files; whether it also triggers the UMI device ("Program at download" is checked) is still open.
- `CLoaderController.getDownloadList(listType, isAbsolutePath)` — needs two arguments (deprecated too).

## Round 3 findings (2026-11-07)

Workspace `.../WinIdea_R_04_01_01/.../SUZ_7G5_M7.xjrf`, `isystem.connect` still 9.26.11.2.316513. Observed with `ide.getOptionStr` unless noted. Root below: `D = /iOPEN/UMIConfig.Devices.Devices[0]`.

### Download file rows

`ide.getDynamicOptionSize(D + ".DownloadFiles") -> 3`, so rows can be counted directly. Index 3 raises `Array index (3) out of range (3)`.

| Row | `.Enabled` | `.Offset` | `.Type` | `.Path` |
|---|---|---|---|---|
| 0 | `'false'` | `'0x1AA000'` | `'Auto'` | `'Radar_SUZ05_Gen7.s3'` |
| 1 | `'true'` | `'0x0'` | `'Auto'` | `'C:/Users/testla3/Downloads/artifacts (16)/out/FFI/RAD_SUZ05_FFI.s3'` |
| 2 | not read | not read | not read | `'20260623_142557_2018688_CAL_T008_v0_0.sre'` |

Field names that do not exist on a row: `Address`, `Enable`, `Use`, `Used`, `Checked`, `Active`, `Download`, `Load`, `Format`, `Options.*`.

### Device entry

| Option | Value |
|---|---|
| `D.Name` | `''` (empty) |
| `D.Device` | `'W25Q64JW'` |
| `D.Enabled` | `'true'` |
| `D.ProgramAtDownload` | `'true'` |
| `D.VerifyOnTheFly` | `'false'` |
| `D.AllowDownloadOnly` | `'false'` |

Not found under these names: `DeviceName`, `Type`, `Interface`, `Parallel`, `MassEraseBeforeDownload`, `AllowMassErase`, `VerifyAfterProgram`, `ReadOnly`, `UseBufferCompression`, `UseHashVerification`.

### Device identity

At 11:24 `CStorageDeviceFactory.getDeviceNames(cmgr, ic.StrVector())` returned `None` and left the vector **empty**. At 11:37 the same call on the same workspace filled it with `['Winbond W25Q64JW SPI']` (see "Round 3 program run"). So the empty `Name` was **not** the cause; the cause of the empty list is unknown. `CStorageDeviceFactory.DEVICES_OPT_URL` is `'/iOPEN/Data.UMI.Devices.Devices'`, a different root from the working `UMIConfig` one. `getDeviceIndex` returns the index or -1 (docstring); not yet called on this workspace with a real name.

### Program API

`ic.IConnectUMI` holds `wProgDevice`, `wProgCache`, `wProgMask` (values not printed yet). The module has no top-level `wProg*` names.

`CUMIController.write` has three overloads (docstring, none called yet):

1. `write(deviceIndex, programMode)`: "Writes contents of pre-configured files to device."
2. `write(deviceIndex, programMode, fileFormat, offset, fileName)`: "Writes contents of file to device." `fileFormat` is a `wFile...` flag such as `IConnectUMI::wFileFormatAuto`. **This could program a file without touching the workspace paths.** Whether it honours the device's erase options is unknown.
3. `write(dwDevice, programMode, address, size, data)`: raw bytes.

`CSessionCtrl` (since 9.21.45, docstring only): `begin_program()` "downloads the executable code to the target SoCs and halts execution at the reset vector"; `begin_reset()` resets and halts without programming; `begin_prepare()`, `end()`, `get_status().SoCs()[i].status_string()` (e.g. `'ATTACHED'`), `program_verify()`. It is the documented replacement for the deprecated `CLoaderController.download()`.

### Spike 08 did not write

The first 08 run stopped at `no device found -> stop` because of the empty device list, **before `umi.write`**, so nothing was programmed. The script now falls back to `--device-index` (default 0) and refuses unless that entry is enabled and its `Device` equals `--expect-device` (default `W25Q64JW`).

## Round 3 program run (2026-11-07)

### Writing paths works

`ide.setOption(url, new)` returned `None`, `getOptionStr` read the new value back, and restoring worked, for both lists (03):

| URL | Old | Read back | After restore |
|---|---|---|---|
| `/iOPEN/UMIConfig.Devices.Devices[0].DownloadFiles[0].Path` | `'Radar_SUZ05_Gen7.s3'` | `'C:\\Data\\tmp\\wflash_test.s3'` | old value |
| `/IDE/System.Debug.Applications[0].SymbolFiles.File[0].Path` | `'../../../debug/cyber_security/artifacts (14)/out/bin/Radar_SUZ05_Gen7.elf'` | `'C:\\Data\\tmp\\wflash_test.elf'` | old value |

The value is stored verbatim (absolute stays absolute). Relative paths resolve against the workspace dir (the Output view shows them absolute). Row 1 was not the row written.

### Device identity

`getDeviceNames` -> `['Winbond W25Q64JW SPI']`. `umi.getDeviceIndex('Winbond W25Q64JW SPI') -> 0`. A wrong name raises `AttributeError: No device with provided name <name> exists.  [CUMIController.cpp, 496]` (`'W25Q64JW'` and `''` both raise). `getDynamicOptionSize("/iOPEN/UMIConfig.Devices.Devices") -> 1`. `IConnectUMI.wProgDevice = 0`.

### umi.write(0, IConnectUMI.wProgDevice)

Returned `None` after **117.4 s**, blocking, with no exception. Rows at the time: row 0 not enabled; row 1 enabled, offset `0x0`, `../../../debug/LED_R5/BENCH_ONLY_UDS27_BYPASS_FFI_STINGRAY_3P5MB_NO_HTSM_d8ba77b5/out/FFI/RAD_SUZ05_FFI.s3`; row 2 enabled, offset `0x0`, `20260623_142557_2018688_CAL_T008_v0_0.sre`.

Output view of that run (`08_winidea_output.txt`, condensed):

```
Running  Emulation Initialization ... Loading <3 ELFs> ... EMULATION STARTED
Running  Erasing       ERASING Winbond W25Q64JW SPI
LOADING  .../RAD_SUZ05_FFI.s3   (20 chunks, Offset 0x0 .. 0x7F7000)
Running  Programming   PROGRAMMING Winbond W25Q64JW SPI (79 sectors)
Running  Erasing       ERASING Winbond W25Q64JW SPI
LOADING  .../20260623_142557_2018688_CAL_T008_v0_0.sre   Offset=0x7F'0000, Size=0x2018
Running  Programming   PROGRAMMING Winbond W25Q64JW SPI (1 sectors)
Running  Reset         EMULATION END - Without cleanup ... EMULATION STARTED
```

- Each enabled row gets its own erase + program pass, in row order.
- The sector counts fit a **64 KB sector** exactly: the 20 chunks touch 79 blocks of 64 KB (148 of 32 KB, 1120 of 4 KB), and the CAL touches 1 of 64 KB (3 of 4 KB).
- The CAL's block `0x7F0000` also holds four `.s3` chunks: `0x7F2FC0`, `0x7F31C0`, `0x7F6000`, `0x7F7000`.
- **INCIDENT, user report 2026-11-07:** after this run the whole chip was erased and the ECU no longer ran. Not yet confirmed by reading the flash back. **`umi.write(index, mode)` must not be used with more than one enabled row.**
- How much the second erase covers was not proven by the log alone. If it is a mass erase, the whole `.s3` is gone. If it erases block `0x7F0000` without preserving it, those four chunks are gone. If winIDEA preserves the rest, nothing is lost. The log cannot tell these apart. `spike/09_flash_compare.py` reads the flash back and compares it with the files.

After `debug.reset()` here, `isStopped -> False`, unlike round 1 (`True`). The status was read immediately, and `toString` was not printed, so the state is unknown. "Reset and halt" needs re-checking.

### umi.read needs a presized vector

`umi.read(0, address, size, ic.ByteVector())` raises `ValueError: Vector size is too small!  [CUMIController.cpp, 136]`, `__size__: 0`. The type `ByteVector` is accepted; both `ByteVector` and `VectorBYTE` exist in the module. Spike 09's S-record parser found 20 segments in the `.s3` at the same addresses as the 20 chunks in the Output view, and the CAL at `0x7F0000`.

### Manual Program differs from umi.write

User report, 2026-11-07: *Hardware → Winbond W25Q64JW SPI → Program* with the same two rows enabled and the same files erased **once** before programming, and restored a working ECU. The Output was not kept. `umi.write(0, wProgDevice)` showed **two** erase phases. So the API call is **not** equivalent to the menu item when more than one row is enabled.

Which API call does what the menu does is unknown. Candidates, none verified: `CLoaderController.download()` / `CSessionCtrl.begin_program()` with `ProgramAtDownload='true'`, or the menu command itself (`ide.getMenuStructure`, `ide.serviceCall`).

`umi.read` with `--full` ran for an unknown time on the 1.4 MB first segment without output and looked stuck. Read speed is not measured yet.

### Device dialog of the R_04_01_01 workspace (user screenshot, 2026-11-07)

Checked: **Mass erase before download**, Allow mass erase, **Program at download**, Use buffer compression, **Use hash verification**. Not checked: Allow download only, Read-only, **Verify after program**, Verify on the fly. Safe mode Auto, Core Auto. Rows: `Radar_SUZ05_Gen7.s3` unticked (offset `1AA000`), `../../../debug/LED_R5/BENCH_...` ticked, `20260623_142557_2018688_...` ticked.

Most likely explanation of the incident, not proven: `umi.write(index, mode)` runs the device's erase option once per enabled row, so the mass erase before the CAL row removed the `.s3` written just before it; the menu item erases once for all rows. "Verify after program" is off, so winIDEA would not have reported the loss. Hash verification may also explain the 6-8 s `download()` in round 1 (content already matching is skipped), also not proven.

### umi.read is not passive (09 --full, 2026-11-07)

On a running ECU, the first segment took a long time with no output, then:

- `0x000000`: `OSError: UMI_ERRORC_OPERATION CUMIController::read() failed! UMI Monitor errCode=0x1  [CUMIController.cpp, 540]`; `getLastError -> '001 - Operation failed! [fpcErrCode=0x01] [extErrCode=0x0000] [(null)]'`.
- Every later segment: `OSError: CUMIController::read failed! Error code unknown to isystem.connect facade: 39  [CUMIController.cpp, 551]`; `getLastError -> '001 - Operation failed! [fpcErrCode=0x39] [extErrCode=0x0000] [Error loading monitor]'`.

Nothing was compared, so this run neither confirms nor rules out the chip erase. "Error loading monitor" indicates `read` needs a monitor loaded into the target, so it can disturb running firmware. What state it needs is unknown; the target was presumably running. **The adapter must not call `umi.read` on a running target without this being resolved.** `CUMIController.flush` ("Programs the device from the intermediate cache") and `write(..., wProgCache)` are a further candidate for a single-erase program; unverified, docstring only.

### Program API docs (spike 10, 2026-11-07)

`IConnectUMI`: `wProgDevice = 0`, `wProgCache = 16384`, `wProgMask = 16384`, `wFileFormatAuto = 0`, `wFileFormatBin = 65536`, `wFileFormatS = 131072`, `wFileFormatHex = 196608`, `wOpWrite = 0`, `wOpFlush = 512`, `wOpErase = 768`, `wOpVerify = 1024`, `wOverrideSafety = 32768`, `wScopeDevice = 4096`.

`ide.invoke(funcUrl, inParams)` calls a named winIDEA service function, for example `'/IDE/Divide'`. An error in the function does not raise: check `ResultB` and `ResultS` in the result. `invoke_T` raises instead. No list of function names is known, so the menu's Program cannot be called yet. `ide.getMenuStructure()` raises `TypeError: missing 1 required positional argument: 'optionUrl'`, and it has no docstring. `CUMIController.flush(deviceIndex)`: "Programs the device from the intermediate cache". `verify` compares the device with the cache. None of these was called. Docstrings name examples (`test_write.py`, `test_flush.py`, `test_begin_program.py`...); spike 11 looks for them on disk.

### umi.read works: baseline after a manual Program (09, 2026-11-07 12:27)

`umi.read(0, address, size, ic.ByteVector(size))` succeeded for all 37 samples (up to 256 bytes at the start and end of each segment) of the two enabled files: **all MATCH**, including the `.s3` chunks in block `0x7F0000` that the CAL shares, and the CAL itself. Sampled only, so this is not proof for the whole image. It shows that after the menu Program both files coexist in flash.

Every read took about **4.3-4.4 s whether it was 11 or 256 bytes**, so the cost is per call, not per byte (probably the monitor load, not proven). `--full` makes about 1120 calls of 4 KB, which would take about 80 minutes; that fits the earlier "stuck" look. Why the earlier `--full` run ended with `Error loading monitor` while this run succeeded is unknown. The effect of `read` on running firmware is still unmeasured.

### Debug -> Download in the GUI: one erase (user log, 2026-11-07)

Same workspace, same two enabled rows. ECU ran normally afterwards (user report). Condensed Output:

```
LOADING App_BBE, App_A53, App_M7 (ELFs) ... EMULATION STARTED
Running  Device 'Program' feature
LOADING  .../RAD_SUZ05_FFI.s3  (20 chunks)
LOADING  .../20260623_142557_2018688_CAL_T008_v0_0.sre  Offset=0x7F'0000, Size=0x2018
Running  Erasing       ERASING Winbond W25Q64JW SPI
Running  Programming   PROGRAMMING Winbond W25Q64JW SPI (79 sectors)
OK
PROGRAMMING 0 bytes
EMULATION END - Executing cleanup
```

All enabled rows are loaded first, then there is **one** erase and one program pass. 79 sectors covers both files because the CAL shares block `0x7F0000` with the `.s3`. The session ends afterwards, which fits `isMustInit: 1` seen after the API `download()` in round 1. The user also confirmed `umi.read` in 09 left the ECU unaffected.

Whether `CLoaderController.download()` and `CSessionCtrl.begin_program()` produce this same sequence is not verified; the round 1 runs did not capture Output. Spikes 04 and 12 test that.

### CLoaderController.download() matches Debug -> Download (04, 2026-11-07 12:43)

`ic.CLoaderController(cmgr).download()` on the same workspace and rows returned normally after **99.0 s**. Its Output has the same sequence as the GUI: `Device 'Program' feature`, both files loaded, **one** `ERASING`, `PROGRAMMING ... (79 sectors)`, `OK`, `PROGRAMMING 0 bytes`. Unlike the GUI log, it has no `EMULATION END` line.

Status right after: `status: 49`, `isStopped: 1`, `isMustInit: 0`, `isStopReasonStep: 1`, `execAddress: 872816248`. So here the target is already stopped after `download()`, without a separate reset. That differs from round 1 (`isMustInit: 1`, 6-8 s, other workspace); the reason is unknown.

09 afterwards: 37 of 37 samples MATCH. The user reports the ECU worked after power cycling. Limit: the files were the same ones already in flash, so MATCH alone does not prove new content is written; the erase and program lines in the Output do show a write ran. A flash of a **different** firmware through the API is not tested yet.

### CSessionCtrl.begin_program() matches too (12, 2026-11-07 12:50)

`ic.CSessionCtrl(cmgr).begin_program()` returned `None` after **98.8 s**, blocking, with no progress callback. Output: the same sequence as the GUI, with one `ERASING` and `PROGRAMMING ... (79 sectors)`, `OK`, `PROGRAMMING 0 bytes`.

`session.get_status().SoCs()[0].status_string() -> 'ATTACHED'` before and after. After: `status: 49`, `isStopped: 1`, `isMustInit: 0`, `isStopReasonStep: 1`, `execAddress: 873315762`, unchanged 2 s later. So the target is stopped after it with no separate reset. Before it, the session was already attached and stopped (`status: 17`, `isStopReasonExplicit: 1`); starting from a running or detached target was not observed.

09 afterwards: 37 of 37 samples MATCH, no errors. The user reports the ECU worked after power cycling. The same limit applies: this was the same firmware already in flash.

**Recommended program call: `begin_program`.** It is the documented replacement for the deprecated `download()`, and the observed result is the same.

### Decisions for Plan 2 (user, 2026-11-07)

1. The `.s3` row is matched by file name (`RAD_SUZ05_FFI.s3`): exactly one enabled row, otherwise no flash. The `App_M7` ELF is matched the same way.
2. Cancel is locked from the moment programming starts.
3. Post-flash sampled compare is an optional checkbox, off by default.
4. A version mismatch of `isystem.connect` is logged as a warning, not blocked.

No checkbox for "Mass erase before download": it follows the workspace configuration, as Approach A requires. Plan: `docs/superpowers/plans/2026-11-07-wflash-real-adapter.md`.

### Intermittent "Error loading monitor" when programming (user report, 2026-11-07)

Happens now and then, with manual flashing too:

```
UMI_ERROR           Code = 15 (Read error)
If the error persist, try to perform CPU reset before flash operation.
UMI ERROR           OW.Pre  Code = 39 / 0. Error loading monitor
Failed              Device 'Program' feature: 'Error loading monitor'
PROGRAMMING         0 bytes
No core which could program flash is stopped
```

Same code 39 as `umi.read` in the failed 09 run. User report: **only a power cycle of the ECU clears it; a reset from winIDEA does not.** Round 9 links it to a core being `NOT ACCESSIBLE` (see "Round 9 and per-core state"). So WFlash shows that advice and does not retry. At the user's request it does reset the CPU once before programming (`debug.reset()`, then waits for `isStopped`); whether that prevents the error is not known, and reset followed by `begin_program` in one session has not run on hardware yet.

Seen in WFlash during the verify: `Reading the flash failed at 0x000000: CUMIController::read failed! Error code unknown to isystem.connect facade: 39  [CUMIController.cpp, 551]; 001 - Operation failed! [fpcErrCode=0x39] [extErrCode=0x0000] [Error loading monitor]`.

**`begin_program()` does not raise on this.** Debug bundle of 2026-11-07, 21 programming runs in 40 minutes:

| `begin_program` returned after | Runs | Verify on | First read | Outcome in that build |
|---|---|---|---|---|
| 4.7 to 6.0 s | 15 | 14 | failed at `0x000000`, 14 of 14 | 14 failed in verify, **1 with Verify off reported `Done`** (14:08:43) |
| 94.8 to 100.8 s | 6 | 3 | worked, 3 of 3 | all `Done` |

WFlash therefore always reads 16 bytes at `0x0` after `begin_program` and treats a failure as a failed program (rollback, power cycle hint). What triggers the failure is unknown: it came in runs of 4 to 5 attempts, each ended by a long run, and some flashes directly after a success worked (14:42, 14:46) while others failed (14:14, 14:26, 14:35).

The round 1 `download()` runs of 6-8 s with `isMustInit: 1` were probably the same failure, not hash skipping; this is not proven. The target status after programming is now logged (`stopped=...`) to see whether it also separates the two cases.

### First runs through WFlash (Vòng 7, user logs, 2026-11-07)

Both with the real GitLab artifacts and the adapter's path changes; Output of each: one `ERASING`, `PROGRAMMING ... (79 sectors)`, `OK`, then `Running Reset`, `EMULATION STARTED`. Both load the files from the WFlash cache, so the paths written by `setOption` are what winIDEA programs.

- Flash 1: `.s3` job 11606126, ELF job 11606119.
- Flash 2, a different firmware with Verify samples: `.s3` job 11593258, ELF job 11593251. Chunk 01 size differs from flash 1 (`0x0B'1382` against `0x0B'2EC2`), then 37 `Running Reading` lines, one per sample, before the reset.

### Reset before programming and the status after it (debug bundle, 2026-11-07 15:06)

`debug.reset()` followed by `begin_program()` in one session works: 98.8 s, then `stopped=True`, read confirmed, `Done`, ECU ran (user report). **The reset does not prevent the monitor failure**: runs with it still returned after 4.9 s, with `stopped=False`, and the confirming read failed. A power cycle cleared it. The user sees the same failure when flashing by hand, so it is not caused by WFlash; whether winIDEA or the external flash causes it is unknown.

### Row ticks (spike 14, 2026-11-08)

Download Files rows: `/iOPEN/UMIConfig.Devices.Devices[0].DownloadFiles[i].Enabled` reads `'true'`/`'false'`; `setOption(url, 'false')` then `getOptionStr` gave `'false'`, and restoring `'true'` read back `'true'` (row 3, the BM `.bin`).

Symbol files: the tick is **`/IDE/System.Debug.Applications[i].SymbolFiles.File[j].Load`**, `'true'`/`'false'`; written and read back the same way (file 1, the BM ELF). `Options.LoadSymbols` and `Options.LoadCode` also exist (read `'false'` with `Load='true'`); WFlash leaves them alone. Not existing: `Enabled`, `Enable`, `Use`, `Used`, `Active`, `Checked`, `Options.Load`.

Workspace observed: rows FFI (1), CAL (2, relative name), BM `FBL_M7_LIP_RfeClock_Image.bin` (3, offset `0x0`), FBL `Radar_SUZ05_Gen7_FBL.bin` (4, first read `0x0`, then `0xF1000` after the user corrected it). `App_M7` symbol files: app ELF, `Radar_SUZ05_Gen7_BM.elf`, `Radar_SUZ05_Gen7_FBL.elf`.

Not yet observed: how winIDEA programs overlapping rows (Vòng 8 part B).

### GitLab: pipelines by commit (spike 15, 2026-11-08)

`GET /projects/:id/pipelines?sha=<full sha>` on gitlab.hella.com returned HTTP 200 and pipeline `1579882`, `ref=Release_DD_05_03_01`, for `8ebd595d…`. The pipeline's own status was `manual` because manual jobs had not run, so WFlash must look at the two jobs, never at the pipeline status. Jobs seen: `build` success with archive, `create_ffi_stingray_3p5mb_no_HTSM` success with archive, `create_ffi_stingray_3p5mb`, `build_STRX_3P5MB`, `build_STINGRAY_3P5MB_UDS27_BYPASS` `manual` without archive, `create_ffi_stingray_uds27_bypass` and `create_ffi_strx_3p5mb_no_HTSM` `skipped`. `find_build_jobs` reports these states by name.

### Matching SDK location

`C:\Data\_Devtools\Winidea408\Python\Lib\site-packages\isystem_connect-9.21.408.1.dist-info`: winIDEA ships its own Python with `isystem.connect` 9.21.408.1. There is no wheel to install. `C:\Data\_Devtools\Winidea408\Python\python.exe` reports Python `3.13.12 (MSC v.1944 64 bit)` and `ic.getModuleVersion() -> 9.21.408.1`. All spike runs so far used 9.26.11.

### Scope decided by the user (2026-11-07)

- Replace only **row 1** of the Winbond Download Files (the `.s3`). Row 2 (CAL `.sre`) stays as it is.
- Replace only the **`App_M7`** symbol file. `App_BBE` and `App_A53` stay as they are.

## Round 8 part B: four overlapping rows (2026-11-09)

Workspace rows: [0] `Radar_SUZ05_Gen7.s3` unticked; [1] FFI `.s3` offset 0x0; [2] CAL `.sre` offset 0x0; [3] BM `FBL_M7_LIP_RfeClock_Image.bin` offset 0x0; [4] FBL `Radar_SUZ05_Gen7_FBL.bin` offset 0xF1000. All of [1]–[4] ticked.

- **Debug → Download by hand** and **`CSessionCtrl.begin_program()`** gave the same Output: the four files load in row order, then **one** `ERASING Winbond W25Q64JW SPI`, then `PROGRAMMING ... (79 sectors)`, `OK`. `begin_program` returned `None` after 99.8 s; the CPU was `isStopped=1` before and after. The user power-cycled the ECU after each run and it ran correctly both times.
- A `.bin` row loads raw at its row offset: `LOADED Offset=0x0000, Size=0x15'6340` (BM) and `Offset=0x0F'1000, Size=0x02'40C0` (FBL).
- Overlaps only warn (`Load WARNING Overlap detected at 0000` and `at 0F'1000`), and **the later row wins**: spike 09 read `0x00` at 0x15617C where the FFI file has `0xFF` and the BM image (0x0..0x156340) covers it. Every other sampled FFI region and the CAL matched. This is the evidence for `srec.visible_segments` (later images overwrite earlier ones) and for `read_image` placing a `.bin` at its row offset.
- The API run's Output ends with an extra `PROGRAMMING 0 bytes` line after `OK`. It did not affect the result. Not explained yet.
- Spike 09 parses every row as S-record, so it fails on the BM `.bin` and reads 0 segments from the FBL `.bin`. That is a limit of the spike only; WFlash's verify uses `read_image`.

## Round 9 and per-core state (spike 16, 2026-11-09)

Round 9 (developer flow through WFlash): three flashes passed on the ECU (FFI+CAL; FFI+CAL+BM+FBL with verify; a firmware from another commit), each with **one** `ERASING`, 79 sectors, `OK`, then `PROGRAMMING 0 bytes`. That last line appears after every API run and has never affected the result. The same session had **34 failed attempts**: `begin_program` returned after 5-9 s, the confirming `umi.read` failed with code 39 (`Error loading monitor`), and the paths were restored. None of them wrote the flash. A `debug.reset()` came before every one of them, so that reset does not clear the state.

User observation: flashing works only when **no core** in the Session Explorer shows `NOT ACCESSIBLE`. Spike 16 read the same state through the API, read only:

```python
session = ic.CSessionCtrl(cmgr)
session.get_status().SoCs()[0].cores()[i].status()         # int, EStatus_Core_*
session.get_status().SoCs()[0].cores()[i].status_string()  # 'STOP', 'RUN', 'IDLE', 'NOT ACCESSIBLE'
session.get_topology().SoCs()[0].cores()[i].name()         # 'M7_0', same order as get_status
```

`SSessionStatus_Core` members: `PC`, `run_duration`, `status`, `status_string`. `SSessionTopology_Core`: `CPU_info`, `core_type`, `name`. Enums: `EStatus_Core_stDetached=0`, `stInaccessible=1`, `stStopped=2`, `stRunning=3`, `stHalted=4`, `stIdle=5`, `stSuspended=6`; `EStatus_SoC_DETACHED=0`, `NOPOWER=1`, `RESET=2`, `ATTACHING=3`, `ATTACHED=4`.

| Core | flashing worked | flashing failed |
|---|---|---|
| M7_0 (Cortex-M7) | STOP | STOP |
| M7_RFE (Cortex-M7) | STOP | RUN |
| A53 (Cortex-A53) | STOP | NOT ACCESSIBLE |
| SPT (SPTv3_4) | IDLE | IDLE |
| BBE32EP (XtensaLX) | RUN | NOT ACCESSIBLE |

In both states `CDebugFacade.getCPUStatus()` said `isStopped: 1`, so the old check could not tell them apart. `/IDE/System.Debug.SoCs[0].Cores` does not resolve (`E_INVALIDARG`).

**Decision (user, 2026-11-09):** set paths → reset → read every core → if one is `NOT ACCESSIBLE`, reset again; otherwise program. RUN, STOP and IDLE are fine. The user found that a reset from winIDEA clears `NOT ACCESSIBLE`. `RealWinIDEAAdapter._prepare_cores` re-reads for up to `CORE_WAIT_S` (2 s, not measured) after each reset, resets at most `MAX_CORE_RESETS` (10) times in all for one press of Flash, the first reset included, then raises `FlashError` and the workflow restores the paths. If the states cannot be read it only warns. Not yet run on hardware.

**Round 10 (debug bundle 2026-11-09 11:23): it works on the ECU.** Two presses of Flash, both with A53 and BBE32EP `NOT ACCESSIBLE` at the start:

| Press | Resets | State after the last reset | Result |
|---|---|---|---|
| 1 (11:18) | 4 (1 + 3 more) | M7_0 STOP, M7_RFE RUN, A53 RUN, SPT IDLE, BBE32EP RUN | `begin_program` 100.8 s, confirmed, Done |
| 2 (11:21) | 2 (1 + 1 more) | same | `begin_program` 99.9 s, confirmed, Done |

Each reset plus read took about 3.2 s (1.3 s reset, then the 2 s grace ran out while the cores stayed inaccessible). So `CDebugFacade.reset()` does clear `NOT ACCESSIBLE`, but not always on the first try; the 34 failures of round 9 had only one reset each. After recovery A53 and BBE32EP were **RUN**, not STOP, and programming worked: only `NOT ACCESSIBLE` matters. `CSessionCtrl.begin_reset()` is not needed. The user confirmed the ECU ran normally after both flashes.

## Round 11: cores accessible, programming still fails (debug bundle 2026-11-09 12:59)

Four presses of Flash on `main` (core check without retries):

| Press | Resets | State before `begin_program` | `begin_program` | Result |
|---|---|---|---|---|
| 1 (12:30:50) | 1 | M7_0 STOP, M7_RFE RUN, A53 RUN, SPT IDLE, BBE32EP RUN | 7.6 s | `Error loading monitor` |
| 2 (12:31:13) | 1 | same | 7.0 s | `Error loading monitor` |
| 3 (12:31:32) | 10 | A53, BBE32EP `NOT ACCESSIBLE` until the 10th reset, then as above | 7.2 s | `Error loading monitor` |
| 4 (12:32:23) | 2 | as above | 101.2 s | Done |

The core states before a failed and before a good run are **identical**, here and in round 10. So the core check catches only one cause; another one does not show in the Session Explorer. Every quick failure so far (34 in round 9, 3 here) returned after 5-9 s with `PROGRAMMING 0 bytes`, and the next press usually worked.

**Decision (user, 2026-11-09):** after such a quick failure WFlash tries again within the same press of Flash: reset, core check, `begin_program`. At most `MAX_PROGRAM_ATTEMPTS` = 3 tries; the resets of all tries share the one budget of `MAX_CORE_RESETS` = 10. Only a failure that took less than `QUICK_FAIL_S` = 30 s **and** whose read-back says `Error loading monitor` is retried; a slower failure or any other error is not, because the flash may already be erased. Not yet run on hardware.

**Change (user, 2026-11-09, after round 11): check the cores first.** `_prepare_cores` reads the core states before any reset and programs at once when none is `NOT ACCESSIBLE`; only otherwise does it reset and read again (with the `CORE_WAIT_S` grace), within the shared budget of 10 resets. Two cases still start with a reset: a retry after a quick failure (in round 11 the cores looked fine before every failed try, so checking alone would just repeat it) and core states that cannot be read (as before the check existed). Not yet run on hardware.

## Round 14: WFlash.exe 1.0, every core NOT OBSERVED (2026-11-10 11:55)

First run of the PyInstaller build (`dist\WFlash\WFlash.exe`, `isystem.connect` 9.26.11 bundled with `collect_all("isystem")`). Instance listed, then **Tools → Check winIDEA cores** (`core_states()`: connect, `get_topology`, `get_status`, disconnect) returned:

```
M7_0 NOT OBSERVED, M7_RFE NOT OBSERVED, A53 NOT OBSERVED, SPT NOT OBSERVED, BBE32EP NOT OBSERVED
```

So the bundled module loads and connects. `NOT OBSERVED` is a `status_string()` never seen before; its `status()` integer was not logged. Guess, **not verified**: `EStatus_Core_stDetached = 0`, i.e. the session was not attached to the target (ECU off, probe not connected, or workspace opened without a debug session). What winIDEA's Session Explorer showed at that moment is not known yet.

Consequence for the flash path: `_prepare_cores` treats only `NOT ACCESSIBLE` as bad, so with every core `NOT OBSERVED` it would program at once without a reset. `begin_program()` from a detached session has never been observed (round 9 started attached). Until it is, the user is asked not to flash in this state but to attach first and check the cores again.

## Round 15 plan: cache + flush, like the Program menu (2026-11-11, not run yet)

User report: *Hardware → Winbond W25Q64JW SPI → Program* by hand fails with `Error loading monitor` less often than Debug → Download / `begin_program()`. Not measured. Hypothesis, not verified: `begin_program` (like Debug → Download) re-initialises the session and touches every SoC core, while the menu only needs one stopped core to load the flash monitor; the failure log already says `No core which could program flash is stopped`.

`umi.write(index, wProgDevice)` is the SDK's "write configured data" (TASKING `test_storage_write.py`) and is the call that erased before each row in round 3, so it stays forbidden. Spike 11 found no example on disk. The online SDK docs (TASKING winIDEA SDK, `test_storage_flush.py` and `IConnectUMI`):

- `wProgCache = 0x4000`: "program the data into the intermediate cache"; `wProgDevice = 0`: "program the data into the device immediately".
- `wOpFlush = 0x200`: "program the device from the intermediate cache". The example writes with `wProgCache`, then calls `storageCtrl.flush()` (a `CStorageDeviceController` from `CStorageDeviceFactory.makeDevice`).
- Nothing in these pages says how flush honours "Mass erase before download".

`spike/17_umi_cache_flush.py` tries `umi.write(index, wProgCache)` (configured rows into the cache), asks the user whether the Output showed any erase or program, then `umi.flush(index)`. It refuses when a core is `NOT ACCESSIBLE` or the default core is not stopped. Success means: one `ERASING`, the whole set programmed, the read at 0x0 works, 09 MATCH, ECU runs. Until then WFlash keeps `begin_program()`.

## Round 15: cache + flush programs with one erase (2026-11-11 15:25)

`spike/17_umi_cache_flush.py`, same workspace, enabled rows: FFI `.s3` (`fde378b4`, offset 0) and the CAL `.sre`. Cores before: M7_0 STOP, M7_RFE STOP, A53 STOP, SPT IDLE, BBE32EP RUN; `isStopped` True.

- `umi.write(0, IConnectUMI.wProgCache)` returned `None` in **0.0-0.1 s**, `getLastError` empty. Output: only `LOADING` / `LOADED` of the 20 `.s3` chunks and the CAL, **no ERASING or PROGRAMMING**. So it loads the configured rows into the cache and does not touch the flash.
- Every chunk, the CAL included, had `Load WARNING  Overlap detected at <its start>`. The chunks do not overlap each other, and the same files had been loaded into the cache at 15:17 (first run, stopped before flush). So the cache **keeps its content between connections**, and a load is laid over it. Whether `flush` empties it is unknown. Risk for any use in WFlash: when the next firmware does not cover a range the previous one did, the old bytes in the cache could be programmed too.
- `umi.flush(0)` returned `None` after **99.6 s**, `getLastError` empty. Output: **one** `ERASING Winbond W25Q64JW SPI`, `PROGRAMMING Winbond W25Q64JW SPI (79 sectors)`, `Running Reading`, `Running Reset`, `EMULATION END - Without cleanup`, then the emulation restarts (`EMULATION STARTED`). Same erase count, sector count and time as the menu Program and `begin_program`. No `OK` line, unlike the GUI log of 2026-11-07.
- `umi.read(0, 0, 16, ByteVector(16))` right after: `d1010060ffffffff00100000ffffffff`.
- Cores after flush: as before. After `debug.reset()`: M7_0 STOP, M7_RFE RUN, **A53 NOT ACCESSIBLE**, SPT IDLE, **BBE32EP NOT ACCESSIBLE**.
- `09_flash_compare.py` 5 minutes later: every read failed with code 39 `Error loading monitor` (the cores were still NOT ACCESSIBLE), so nothing was compared.
- User: the ECU runs.

What this shows: the cache + flush path programs every enabled row with **one** erase, like the menu. What it does not show yet: (1) that new content is written: the files were the ones already in flash; (2) a lower `Error loading monitor` rate: one run, from a good core state; (3) how the stale cache behaves. Spike 17 now has `--no-reset` so that 09 can read right after the flush. WFlash still programs with `begin_program()`.

## Open questions

1. **Version mismatch.** `isystem.connect` 9.26.11 against winIDEA 9.21.408. Connect, read, download, reset and run all worked, but `CLAUDE.md` requires the versions to match. Is there a Python SDK package under `C:/Data/_Devtools/Winidea408/` (9.21.408)? If yes, install it and re-run 01 to confirm nothing changes.
2. ~~External-flash URL~~ found: `/iOPEN/UMIConfig.Devices.Devices[0].DownloadFiles[i].Path`. Fields and program constant are now known (Round 3). Still open: whether `setOption` on that URL works (03); whether `CUMIController.write()` programs the Winbond as the menu does (spike 08).
3. **Writing paths**: re-run 03 with `--url "/IDE/System.Debug.Applications[0].SymbolFiles.File[1].Path"`, and with the external-flash URL once 06 finds it. Confirm the read-back, the restore, and whether the change shows in the dialogs **without saving the workspace**.
4. **Does `CLoaderController.download()` program the Winbond device?** Compare with *Hardware → Winbond W25Q64JW SPI → Program* (time it; check the winIDEA Output/Progress view during the spike download).
5. **Selecting one of several winIDEA instances** when `getInstanceId()` is empty.
6. ~~Per-core state~~ read with `CSessionCtrl.get_status()` (spike 16). `CDebugFacade.reset()` clears `NOT ACCESSIBLE`, sometimes only after a few tries (Round 10: 4 and 2 resets).
