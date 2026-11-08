# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

WFlash (v0.1) — a PySide6 desktop app that flashes **NXP SAF85xx** firmware into external QSPI NOR flash (Winbond) through **iSYSTEM winIDEA 9.21.x**, driven by the `isystem.connect` Python API. It fetches the firmware from a self-hosted GitLab (branch/tag → pipeline → job artifact, one artifact per source in the profile), maps the `.s3` and `.elf` files onto download/symbol entries that **already exist** in the user's open winIDEA workspace, programs the flash, then resets and halts the target.

The approved design spec is `docs/superpowers/specs/2026-10-04-wflash-tool-design.md` and it is the authority for scope and decisions. Read it before planning anything. This file holds the standing engineering rules; where the two ever disagree, the spec wins on *what* is built and this file wins on *how* it is built — except for the amendments recorded in this file (GUI, program call, Cancel, several sources), which the user decided after the spec was written.

It is a sibling of a shipped project, **SFlash** (`.../01_STUDY/06_PYSIDE6`), which flashes the same class of ECU over CAN/UDS. The threading, Designer, testing and logging rules here are transferred from that project, where each of them exists because a specific crash or silent failure shipped first. They are facts about PySide6, not about CAN — keep them.

## Current state

The app is complete and merged to `main`. The full flow passed on the user's Windows machine with a real ECU and real GitLab artifacts (`docs/windows_test_guide.md`, Vòng 7), including flashing a different firmware. Not done yet: `WFlash.exe` has not been built with the real adapter; development and testing so far use `python main.py`.

**macOS can only exercise the fake adapter and `tests/fake_isystem.py`.** Nothing about hardware can be verified here: a change to the real adapter is unverified until the user runs it on Windows, and must be reported that way.

## Rule zero: never write a winIDEA API call you have not verified

`isystem.connect` is a SWIG-generated binding shipped **with** winIDEA and versioned alongside it. Class names, method signatures and especially **option path strings** differ between releases. A guessed name fails only at runtime, only on the one Windows machine that has winIDEA and the probe — the most expensive place to find out.

So: every call in `wflash/core/winidea_adapter.py` must trace back to something the spike actually observed. Probe, then write:

```bash
python -c "import isystem.connect as ic; print(ic.getModuleVersion())"
python -c "import isystem.connect as ic; print([n for n in dir(ic) if n.startswith('C')])"
python -c "import isystem.connect as ic; help(ic.CLoaderController)"
```

Record every result in `docs/winidea_api_notes.md` — version, exact signature, what it returns, what it raises, the literal option paths. That file is the authority the adapter cites. Any real-adapter call not observed there carries a `# UNVERIFIED:` comment, and **nothing** new is claimed to work on hardware until the user has run it.

A new probe goes in `spike/NN_*.py`. It must be read-only unless it says otherwise in its docstring and asks for confirmation before writing to the flash. Testing a spike against a fake module proves only the script's own logic.

### Calls that are known to be dangerous or misleading

Each of these was learned on the real ECU. Read `docs/winidea_api_notes.md` before changing the flash path.

- **Never call `CUMIController.write(index, mode)`, `erase` or `flush`.** With two enabled rows and "Mass erase before download" on, `write` ran an erase before each file. The user reported the chip erased and the ECU dead (recovered by flashing by hand). Its docstring, "writes pre-configured files", did not reveal this: a docstring is not evidence that a call matches a menu item.
- **Program only with `CSessionCtrl.begin_program()`.** Its Output matches Debug → Download: every enabled row is loaded first, then one erase and one program pass.
- **`begin_program()` does not raise when programming fails.** On `Error loading monitor` it returns normally after about 5 s instead of about 100 s, and the failure only appears in winIDEA's Output view. `RealWinIDEAAdapter._confirm_programmed` reads the flash once afterwards for this reason; never remove that read, or WFlash reports `Done` for a failed flash. Only an ECU power cycle clears this failure; a reset from winIDEA does not, and it happens when flashing by hand too.
- **Never call `getOptionJSON` on a list or tree.** It broke the connection (`ICONNECT_E_ROUTING`).
- `umi.read` needs a presized vector (`ic.ByteVector(n)`), costs about 4.4 s per call whatever the size, and loads a monitor into the target, so it is not a passive read. Compare samples, never a whole image.
- After reset, check `isStopped()`, not `isHalted()`, which stays 0.

Two specific hazards in the environment diagnostics:
- **`isystem.connect`'s version may differ from winIDEA's.** The user's working setup is 9.26.11 against winIDEA 9.21.408. Decision: log a warning, do not block. winIDEA's own Python has 9.21.408.1, and no wheel to install.
- **Interpreter bitness must match winIDEA's.** In SFlash the single most expensive field failure was a native library that would not load, and the framework's own error message hid the reason (a 32-bit DLL under a 64-bit host). Expect the same shape of failure here and report the *root* cause, keeping the original exception as `__cause__`.

## Commands

The plan's Global Constraints fix these; don't improvise alternatives.

```bash
# macOS dev environment — the venv lives OUTSIDE OneDrive on purpose, so OneDrive
# does not try to sync thousands of site-packages files.
# On Windows the user works in a conda (Miniforge) env; see docs/windows_test_guide.md.
/Users/tranminhphuc/miniforge3/bin/python3.13 -m venv ~/.venvs/wflash
~/.venvs/wflash/bin/pip install -e ".[dev]"
# Deps: PySide6, requests, pydantic v2, PyYAML, keyring,
#       pytest, pytest-qt, responses, PyInstaller.
# isystem.connect does NOT come from PyPI — on Windows install it from the
# winIDEA 9.21 installation directory so its version matches winIDEA's.

# Run the app (run every command from the repo root)
~/.venvs/wflash/bin/python main.py --adapter fake   # same as: python -m wflash --adapter fake
python main.py                                      # Windows with winIDEA: real adapter is the default

# Tests
~/.venvs/wflash/bin/pytest -q
~/.venvs/wflash/bin/pytest tests/test_flash_workflow.py -v
~/.venvs/wflash/bin/pytest -k thread -v        # worker lifecycle — never skip
~/.venvs/wflash/bin/pytest -k "not gui" -q     # core only

# Headless end-to-end stress test (see .claude/skills/stress-test)
~/.venvs/wflash/bin/python tools/stress_test.py

# Spikes — Windows only, need winIDEA and the workspace open; run from spike/, see spike/README.md
python 01_connect.py
```

`tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen`, so GUI tests need no display. No linter/formatter is configured — don't invent lint commands.

## Conventions fixed by the plan

- **Python >= 3.11.** macOS dev interpreter: `/Users/tranminhphuc/miniforge3/bin/python3.13`. The system `python3` on this machine is an Xcode licence stub and errors out — never use it.
- **GUI text is English; documentation** (README, `spike/README.md`, `docs/walkthrough.md`) **is Vietnamese.**
- **Logging** goes through `get_logger("<module>")` -> `logging.getLogger("wflash.<module>")`. Every handler uses `RedactingFormatter`; a GitLab token is never written unmasked anywhere.
- **Every business error inherits `WFlashError` and carries a `hint`** attribute — that hint is what the GUI shows the user, so write it as advice, not as a restatement of the error.
- **`wflash/core/**` must not import PySide6.** Only the real adapter (Plan 2) and `spike/` may import `isystem.connect`.
- **Commits in this repo end with the trailer** `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (passed as a second `-m`).
- Don't commit a mode change on the pre-existing `README.md` unless the task is about the README.


## Rules

- **GUI changes go in the `.ui` file first (`main_window.ui`, `gitlab_dialog.ui`, `preferences_dialog.ui`, `checkout_dialog.ui`), `.py` code second.** If a change can be expressed as a widget/layout/property in the `.ui` XML, make it there and regenerate with `pyside6-uic` — never hand-build the equivalent widget in Python, and never hand-edit `ui_*.py`. Fall back to Python-side construction only for what Designer genuinely can't express (logic-driven content, e.g. the mapping table's rows and the per-source Load rows).
- **Name every widget and layout in the `.ui` meaningfully — never Designer's auto-numbered defaults** (`verticalLayout_2`, `label_5`). Use names that say what the thing is or where it lives: `verticalLayout_gitlabBrowser`, `tableWidget_mapping`, `horizontalLayout_flashButtons`. Before renaming an existing one, grep `wflash/gui/*.py` for `self.ui.<name>` — some layouts get widgets added at runtime.
- **Before ending a session that touched the app, run the full test suite and confirm the app still launches** (`~/.venvs/wflash/bin/python main.py --adapter fake`). If anything worker- or thread-related changed, run `pytest -k thread` explicitly. A green run is not optional polish: SFlash shipped a real `QThread: Destroyed while thread is still running` crash precisely because that path was only exercised by hand.
- **Before pushing a whole session's changes, stress test first.** Run (1) the full suite, (2) the threading tests explicitly even if untouched, (3) `python tools/stress_test.py`. It drives the real app headlessly against the fake adapter through many chained actions in one process and fails on Qt threading warnings as well as its own checkpoints. If it all passes, push without asking again. If anything fails, **stop and report — do not push on your own judgment.**
- **Before asking the user to run anything that writes to the flash,** say so plainly, say what evidence supports it and what happens if it goes wrong, and give the way to recover (Debug → Download by hand). Never call a step "read only" without checking that it does not touch the target.
- **Before implementing a newly requested feature, briefly check that it fits** this app's purpose and the spec's explicit non-goals (spec §1: no flash-loader configuration, no launching winIDEA, no local file selection, no winIDEA other than 9.21.x). The user decided mass erase stays a workspace setting, with no checkbox in WFlash, and removed Package Registry: firmware comes only from CI artifacts. If it clearly fits, implement it in the same turn. If the fit is questionable — or it is something the spec deliberately excluded — lay out the concern and wait for a decision.
- **Keep `docs/walkthrough.md` up to date as you go** — a new `## Phase X.Y` entry for every notable change, in Vietnamese, following that file's existing format (intro paragraph, `### Thay đổi` with bolded file names, `### Đã kiểm tra` with what was actually verified). Not just at the end, not skipped. Backfilling from git history loses the reasoning, which is the only part worth keeping.

## Architecture

### Layering and the one import rule that matters

Package layout: `wflash/core/` (no Qt at all), `wflash/gui/`, `profiles/`, `spike/`, `tests/`, plus `pyproject.toml`, `wflash.spec` and `scripts/build_windows.bat`. The entry points are `wflash/main.py` and `wflash/__main__.py` (`python -m wflash`).

- **`wflash/core/` must never import from `wflash/gui/`, and must never import Qt.** This is what makes the whole workflow testable headlessly with `FakeWinIDEAAdapter` and no display. The GUI observes the workflow through the callbacks and `CancelToken` that `gui/workers.py` turns into Qt signals — the direction of dependency never reverses.
- **Only `wflash/core/winidea_adapter.py` imports `isystem.connect`**, and it imports it **lazily, inside the adapter's methods** — never at module scope. That is what lets the app, the tests and the stress test run on macOS where the module does not exist. (SFlash's `vector_can.py` does the same with `python-can`.)
- The GUI never calls GitLab or winIDEA directly; every such call goes through `core/` on a worker thread.

### The adapter boundary is the load-bearing decision — build the fake first

`WinIDEAAdapter` is a `Protocol` (spec §4) with two implementations: `RealWinIDEAAdapter` and `FakeWinIDEAAdapter`. A new adapter method goes in the Protocol and the **fake** first, then the real one. `tests/fake_isystem.py` stands in for `isystem.connect` so the real adapter's logic can be tested on macOS; it is built from observed behaviour, and it raises if `umi.write`, `erase`, `flush` or `getOptionJSON` is called. When hardware behaves differently, change it to match the observation first. Its limits are real: spike 09's empty vector passed on a stand-in and failed on the ECU, and no stand-in predicted the silent `begin_program` failure.

The fake is not a stub that returns success. Every failure the real probe can produce must be reachable in simulation, because that is the only place the error handling and the rollback get tested: no instance found, a missing `Programs`/`Applications` entry, `set_*_path` refused, download failing at N%, a download that never finishes (timeout), a cancel mid-download, a connection dropped, reset failing. Target state is that `flash_workflow`'s every branch — including both rollback paths — is covered against the fake.

### Approach A: only change paths, never create entries, always be able to roll back

The spec's §3 is a safety decision, not a convenience. The workspace is the user's, already configured so that manual flashing works. Therefore:

1. Read the existing entries; **match** by the profile's `winidea_entry`/`winidea_app`. Download rows and symbol files have no names of their own, so the adapter names them after their file: `RAD_SUZ05_FFI.s3` for an enabled row of the flash device's Download Files (`/iOPEN/UMIConfig.Devices.Devices[0].DownloadFiles[i]`), `App_M7/Radar_SUZ05_Gen7.elf` for a symbol file. A disabled row or a duplicate name gets a suffix, so it cannot match. The selected file must have the same name as the entry.
2. Change **only the file path**. Never touch target device, verify, offset, row ticks, mass erase or load mode. Never create a missing entry — that is `MappingError`, surfaced to the user. **Exception, for a profile with `builds` only** (developer flow, spec `2026-11-07-wflash-developer-debug-design.md`): `flash_plan.make_plan` also sets the ticks of the BM/FBL download rows and their `App_M7` symbol files (on with Advanced Debug, off without), and points the CAL row at the `.sre` found next to the workspace `.xjrf`. The plan is checked before anything is written. On failure only the **paths** are restored; the ticks stay as WFlash set them (user decision). Offsets, mass erase and every other setting are still never touched.
3. **Back up every original path before writing**, and roll back on any failure from that point on (set-path or download). A workflow that fails and leaves the workspace pointing at a stale artifact is worse than one that refuses to start.
4. The rollback must also run on the paths that are easy to forget — an exception mid-way through setting the *second* of three paths, a cancel, a timeout. Make it a `try/finally`-shaped guarantee, not a line at the end of the happy path, and prove it with a fake-adapter test per branch.

A failed program rolls back, because `download()` raises. A failure in the optional sampled verify does not: the flash has already been written with the new paths. `connect` refuses when winIDEA is attached to another workspace than the selected one, since `cmgr.connect()` picks the most recent winIDEA.

The debug bundle dumps the download/symbol options **before and after** the edit (spec §7) for exactly this reason: when something goes wrong on a user's machine, the first question is always "what did the tool change?".

### GUI: Designer-first, mixin composition (supersedes spec §4 and the plan's File Structure)

The spec's §4 and the plan's File Structure both list plain hand-written `gui/*.py` modules. The user has since chosen SFlash's UI architecture instead, so this is the decision of record:

- **`wflash/gui/main_window.ui` is the source of truth.** `wflash/gui/ui_main_window.py` is generated by `pyside6-uic` and never hand-edited. A change that can be expressed as a widget, layout or property belongs in the XML.
- **`MainWindow` is composed by multiple inheritance from focused mixins**, all sharing one `self.ui` and free to call each other's methods directly:

```
wflash/gui/main_window.ui        Designer, source of truth (also gitlab_dialog.ui, preferences_dialog.ui, checkout_dialog.ui)
wflash/gui/ui_*.py               generated by pyside6-uic, never edited
wflash/gui/main_window.py        MainWindow(SourcePanelMixin, MappingTableMixin, FlashMixin, LogPanelMixin)
wflash/gui/source_panel.py       mixin: developer panel (source repo, build, Advanced Debug, CAL)
wflash/gui/mapping_table.py      mixin: Program Files and Symbol Files tables, the source card, one Load row per source
wflash/gui/checkout_dialog.py    modal Checkout popup: branch or commit of the source repo
wflash/gui/log_panel.py          mixin + QtLogHandler
wflash/gui/flash_mixin.py        mixin: Flash/Cancel, step state, post-flash, Cancel lock
wflash/gui/gitlab_dialog.py      modal Load from GitLab popup: CI artifact only
wflash/gui/preferences_dialog.py cache, profiles, verbose, dark mode
wflash/gui/workers.py            Worker / WorkerRegistry on QThreadPool
wflash/gui/theme.py, style.py    Teal light/dark tokens; resources/style*.qss must use the same colours
```

Dynamic content stays in Python — mapping rows, log lines, per-source Load rows. That is the legitimate exception, not a loophole for building static layout in code.

The redesign spec is `docs/superpowers/specs/2026-10-04-wflash-ui-redesign-design.md`. Spec §4 of the original design still shows the old list.

### Developer flow: source repo and checkout

`wflash/core/source_repo.py` drives the developer's git repo through the `git` command line (`GIT_TERMINAL_PROMPT=0`, no console window on Windows). It refuses a checkout while the repo has local changes, and it **never** stashes, resets, cleans or forces: the working tree is the developer's. Firmware for a profile with `builds` comes from the pipeline of the repo's exact commit (`firmware_fetch.find_build_jobs`), never from another commit; local changes only warn.

### Several sources

A profile may declare `sources`, and then every target names one. Each source gets its own Load button and job filter; a mapping row only sees the files of its source, so a same-named file in another artifact cannot be picked; reloading one source keeps the others; Flash waits for all of them. Two CI artifacts from different commits show a warning but do not block. The commit check cannot catch two different build configurations from one pipeline. A profile without `sources` behaves as one source.


### Threading model — read before touching `wflash/gui/workers.py`

Artifact download and the flash workflow both run off the GUI thread, as a `Worker` (a `QRunnable` with `autoDelete=False`) on a `QThreadPool`. Progress leaves the worker two different ways, and the distinction is the whole design: `WorkerContext` hands `core/` **plain callbacks** plus a `CancelToken`, while `WorkerSignals(QObject)` is what turns those into Qt signals for the GUI. The plan fixes that choice; this section is the part it does not specify. Every item below is a failure that actually shipped in the sibling project SFlash — the mechanisms are PySide6's, so they apply here in their `QThreadPool` form.

1. **The signal-carrying QObject must outlive the runnable, and must be owned by the main thread.** A `QRunnable` is not a `QObject`, so progress signals come from a helper (`WorkerSignals`). If the only Python reference to that helper is dropped while the worker still runs — the window closed, a panel rebuilt, a local gone out of scope — the next `emit` hits a deleted object and raises `RuntimeError: Signal source has been deleted` on a pool thread, where nothing catches it. Hold an explicit reference for the worker's whole life and clear it only from a slot that runs *after* the worker is known to be done.
2. **`setAutoDelete` and Python ownership.** `QRunnable` defaults to auto-delete: the pool destroys the C++ object as soon as `run()` returns, while Python may still hold the wrapper. The plan already chose `autoDelete=False` (Task 13), which means **Python owns the worker and the main thread disposes of it** — keep a reference until `finished` has been handled, and never touch it from a pool thread. Write that reason next to the flag. Mixing the two is how a use-after-free turns into a random segfault.
3. **Never call `QThreadPool.waitForDone()` on the GUI thread while anything still needs that event loop.** Queued signals from pool threads are delivered only when the GUI loop runs, so blocking that loop to wait for workers which are themselves emitting queued signals is the same deadlock SFlash hit with `thread.wait()` inside `closeEvent()`. Cancel first (the `CancelToken`), then wait with a bounded timeout, pumping events between attempts — and make `closeEvent()` prove it, because that path is where deadlocks live.
4. **Cancelling does not stop a signal already in flight.** A completion signal emitted before the cancel was observed is already queued and will be delivered when the loop next runs. If its slot starts further work — advancing to the next workflow step, loading an artifact, enabling Flash — that work begins *after* the user cancelled. Fix: a guard flag set **before** cancelling and checked at the top of every completion slot, which settles into the cancelled state instead of continuing. The `CancelToken` alone is not enough.
5. **Every exit path out of `run()` must undo what `run()` started** — the winIDEA session, any poller, temp directories, and above all the **backed-up workspace paths**. Early returns are where this gets missed. In SFlash a single early return that skipped cleanup left a background thread calling into an object nothing referenced any more, surfacing minutes later as an intermittent crash in an unrelated test. It failed no assertion, which is exactly why the whole suite is always run.
6. **Worker-side code must not call `connect()`/`disconnect()`/`moveToThread()`, and must never `deleteLater()` the object it reports through.** PySide releases the GIL inside `exec()`/`processEvents()`; when Qt destroys a Python-created QObject that has connections, `~QObject` holds one of Qt's pooled signal/slot mutexes and blocks for the GIL in `disconnectNotify`, while another thread holding the GIL takes the same pooled mutex in `connect()`. That lock-order inversion showed up in SFlash as a random (~1 in 6) deadlock or SIGSEGV. Build and wire every helper QObject on the main thread, in `__init__`.
7. **Cancel and timeout must be honoured inside a blocking call wherever that is safe.** A token checked only *between* workflow steps does nothing during a step that takes time. Check it on every progress callback and let it fail through the normal error path, so the rollback still runs. **The exception is the real adapter's programming step** (user decision): `begin_program()` blocks for about 100 s and stopping mid-erase could leave an empty ECU, so `download_cancellable` is False, the GUI locks Cancel from that step on, a timeout only logs a warning, and closing the window asks before abandoning the worker. `WorkerContext.progress` raises `CancelledError` once the token is set; the adapter swallows it there. The fake stays cancellable by default so the rollback branch stays tested (`cancellable=False` or `WFLASH_FAKE_FAIL=no_cancel` matches the real one).
8. **Never connect a lambda to a signal emitted from a pool thread.** A lambda has no `QObject` thread affinity, so PySide6 cannot tell the call needs queuing and it silently runs on the worker thread. Touching a widget from there is undefined behaviour that usually looks like a cosmetic glitch — until it doesn't.

If this ever moves from `QThreadPool` to a `moveToThread()` QThread, two more rules apply: a slot connected to a worker's completion signal must never drop the last reference to the still-running `QThread` (that is the literal `QThread: Destroyed while thread is still running` crash), and the thread is stopped with a **direct** `thread.quit()` before `thread.wait()` — never via `worker.finished.connect(thread.quit)`, a queued connection whose `quit` can only be delivered by the very loop `wait()` is blocking.

**Headless code is a different problem with a different answer.** With no event loop, a Qt signal emitted from a thread the QObject does not live on is **queued and then never delivered** — a probe of exactly that pattern in SFlash received 0 of 3 emissions, silently, with no error. This is why `core/` reports progress through plain callbacks plus a `CancelToken` rather than Qt signals: a callback is always a direct, in-thread call, and behaves identically under `pytest`, the stress test and the GUI.



### GitLab, secrets, and what must never reach a log

- The Personal Access Token lives in `keyring` (Windows Credential Manager), never in a file in the repo, never in a profile YAML, never in a test fixture, never in a commit.
- The logging filter that replaces the PAT and the `PRIVATE-TOKEN` header with `***` (spec §7) applies to **every** sink: the log panel, the log file, and the debug bundle. Verbose mode logs every `isystem.connect` call with its arguments — that path needs the same filter.
- A test must prove the filter works on a realistic token, because the failure mode is a user cheerfully emailing a debug bundle that contains their credentials.
- Known GitLab failures get specific, actionable messages (spec §8): 401 token wrong/expired, 403 missing scope, 404 artifact expired, SSL failure → internal CA bundle. "Request failed" is not an acceptable message for any of them.

### Mapping: zero or many matches is a user decision, never a guess

`file_matcher` must match **exactly one** file per profile entry, among the files of that entry's source. Zero or more than one is not an error to work around by picking the first — it marks that row red and makes the user choose from the artifact's file list, and the Flash button stays disabled until every row is assigned (spec §5). Browse jobs only lists successful jobs, because a failed job can still have artifacts. Silently picking a file here means flashing the wrong binary, which is the single worst thing this tool could do.

### Instances and probes are enumerated, never hardcoded

The winIDEA instance list comes from `list_instances()`, wrapped so that any failure returns `[]` — no winIDEA, no running instance, no probe are all normal states to report, not exceptions to propagate. `getInstanceId()` returned `''` on the real machine, so the real id is the TCP port. The fake adapter always offers one synthetic instance. Read the user's selection from the combo's `currentData()` (a dict), never by parsing the display text.

### Errors are typed by layer

`GitLabError`, `ArtifactError`, `MappingError`, `WinIDEAError`, `FlashError` (spec §4/§8). The GUI shows a short message plus a hint and keeps the detail in the log. The user asked for this explicitly: binding text such as `fpcErrCode=0x39` goes to `log.error` and `__cause__`, never into the message of an exception the popup will show. `sys.excepthook` and `threading.excepthook` are installed so nothing crashes silently. Classify at the point that already knows what went wrong — never by matching on message text later.

## Reference docs

- `docs/winidea_api_notes.md` — what the `isystem.connect` probes actually returned. The authority for every real adapter call; read it first.
- `docs/windows_test_guide.md` — what the user runs on Windows, round by round (Vietnamese).
- `docs/superpowers/specs/2026-10-04-wflash-tool-design.md` — the approved design spec; the authority on scope, with the amendments in this file. It still says `python-gitlab` and `ProgramEntry`/`AppEntry`; the code uses `requests` and one `FileEntry(name, path)`.
- `docs/superpowers/specs/2026-10-04-wflash-ui-redesign-design.md` — the GUI redesign. Its Package Registry parts were removed later at the user's request.
- `docs/superpowers/plans/` — Plan 1 (`2026-10-04-wflash-tool.md`, `-gui.md`), the redesign plan, and Plan 2 (`2026-11-07-wflash-real-adapter.md`). History of how it was built; the code is the authority now.
- `docs/walkthrough.md` — phase-by-phase development log (Vietnamese). Read it before assuming something is unimplemented.
