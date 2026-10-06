# winIDEA / isystem.connect — API notes

**This file is the authority for every real `isystem.connect` call in `wflash/core/winidea_adapter.py`.** A call that is not recorded here is a guess and must carry `# UNVERIFIED:` in the code. See `CLAUDE.md`, "Rule zero".

Status: **spike round 1 ran on 2026-10-06** (spike 01–05, results in the user's `results.7z`). Connect, reading symbol-file paths, debug download, reset and run are observed. **Writing any path, and reading the external-flash (.s3) file list, are NOT verified yet** — see "Open questions". Round 2 is `spike/06_probe_umi.py` plus a corrected `03_set_paths.py` run.

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

## Open questions

1. **Version mismatch.** `isystem.connect` 9.26.11 against winIDEA 9.21.408. Connect, read, download, reset and run all worked, but `CLAUDE.md` requires the versions to match. Is there a Python SDK package under `C:/Data/_Devtools/Winidea408/` (9.21.408)? If yes, install it and re-run 01 to confirm nothing changes.
2. **External-flash file list API** (spike 06): option prefix for HServer options (`/iOPEN/`? `OPT_DEST_IOPEN`?), exact URL for `DownloadFiles[i].Path`, the field names for offset and enabled, and whether `CUMIController` / storage-device classes expose the list or a "program device" call.
3. **Writing paths**: re-run 03 with `--url "/IDE/System.Debug.Applications[0].SymbolFiles.File[1].Path"`, and with the external-flash URL once 06 finds it. Confirm the read-back, the restore, and whether the change shows in the dialogs **without saving the workspace**.
4. **Does `CLoaderController.download()` program the Winbond device?** Compare with *Hardware → Winbond W25Q64JW SPI → Program* (time it; check the winIDEA Output/Progress view during the spike download).
5. **Selecting one of several winIDEA instances** when `getInstanceId()` is empty.
6. Per-core reset/halt state (`CMulticoreConnectionMgr`).
