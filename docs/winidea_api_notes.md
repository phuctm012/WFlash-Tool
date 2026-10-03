# winIDEA / isystem.connect — API notes

**This file is the authority for every real `isystem.connect` call in `wflash/core/winidea_adapter.py`.** A call that is not recorded here is a guess and must carry `# UNVERIFIED:` in the code. See `CLAUDE.md`, "Rule zero".

Status: **empty — the Phase 0 spike has not run yet.** Nothing in the real adapter is verified.

Fill one section per observation, from an actual run on the Windows machine with winIDEA 9.21.x and the SAF85xx workspace open. Paste what the probe printed; do not paraphrase.

---

## Environment

| Item | Value | How it was obtained |
|---|---|---|
| winIDEA version | | About dialog / `get_info()` |
| `isystem.connect` version | | `ic.getModuleVersion()` |
| Python version / bitness | | `python -c "import sys,platform;print(sys.version, platform.architecture())"` |
| winIDEA bitness | | installation path / task manager |
| Workspace path | | |
| Probe (BlueBox) model + serial | | |

## Module surface

```
# output of: python -c "import isystem.connect as ic; print([n for n in dir(ic) if n.startswith('C')])"
```

## Connecting / listing instances

- Call(s) used:
- Signature(s) (`help(...)` output):
- Returns:
- Raises on no instance / wrong version:

## Reading Programs (download entries) and Applications (symbol entries)

- Call(s) used:
- Exact option path strings observed:
- Shape of what comes back (paste it):
- Real entry names in the SAF85xx workspace (these go into the profile YAML):

## Setting a file path

- Call(s) used, for a `.s3` download entry:
- Call(s) used, for an `.elf` symbol entry:
- Read-back call that confirms the write:
- What happens when the entry does not exist:
- Which other options are visible but must NOT be touched:

## download()

- Call used:
- How progress is reported (callback? polling? what granularity?):
- How completion is detected:
- How failure is reported (exception type / status value):
- Observed duration for a full SAF85xx image:
- Whether a cancel is possible mid-download, and how:

## reset / halt / run

- Call(s) used:
- How to confirm each core's state afterwards:

## Open questions

-
