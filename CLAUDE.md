# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

WFlash (v0.1) — a PySide6 desktop app that flashes **NXP SAF85xx** firmware into external QSPI NOR flash (Winbond) through **iSYSTEM winIDEA 9.21.x**, driven by the `isystem.connect` Python API. It fetches the firmware from a self-hosted GitLab (branch/tag → pipeline → job artifact), maps the artifact's `.s3` and per-core `.elf` files onto download/symbol entries that **already exist** in the user's open winIDEA workspace, runs the download, then resets and halts the target.

The approved design spec is `docs/superpowers/specs/2026-10-04-wflash-tool-design.md` and it is the authority for scope and decisions. Read it before planning anything. This file holds the standing engineering rules; where the two ever disagree, the spec wins on *what* is built and this file wins on *how* it is built — except for the one amendment recorded under "GUI" below, which the user asked for after the spec was written.

It is a sibling of a shipped project, **SFlash** (`.../01_STUDY/06_PYSIDE6`), which flashes the same class of ECU over CAN/UDS. The threading, Designer, testing and logging rules here are transferred from that project, where each of them exists because a specific crash or silent failure shipped first. They are facts about PySide6, not about CAN — keep them.

## Current state

Design approved; **no application code written yet**. Do not assume a module exists because this file or the spec names it — check. The first real work is **Phase 0, the Windows spike** (spec §9), because the entire `isystem.connect` surface is still unverified.

## Rule zero: never write a winIDEA API call you have not verified

`isystem.connect` is a SWIG-generated binding shipped **with** winIDEA and versioned alongside it. Class names, method signatures and especially **option path strings** differ between releases. A guessed name fails only at runtime, only on the one Windows machine that has winIDEA and the probe — the most expensive place to find out.

So: every call in `wflash/core/winidea_adapter.py` must trace back to something the spike actually observed. Probe, then write:

```bash
python -c "import isystem.connect as ic; print(ic.getModuleVersion())"
python -c "import isystem.connect as ic; print([n for n in dir(ic) if n.startswith('C')])"
python -c "import isystem.connect as ic; help(ic.CLoaderController)"
```

Record every result in `docs/winidea_api_notes.md` — version, exact signature, what it returns, what it raises, the literal option paths. That file is the authority the adapter cites. Until the spike has run, any real-adapter code carries a `# UNVERIFIED:` comment on each call, and **nothing** is claimed to work on hardware.

Two specific hazards to rule out early, both in the spike and in the environment diagnostics:
- **`isystem.connect`'s version must match the installed winIDEA version** (9.21.x here). A mismatch fails at connect time with a message that rarely names the real cause.
- **Interpreter bitness must match winIDEA's.** In SFlash the single most expensive field failure was a native library that would not load, and the framework's own error message hid the reason (a 32-bit DLL under a 64-bit host). Expect the same shape of failure here and report the *root* cause, keeping the original exception as `__cause__`.

## Commands

The plan's Global Constraints fix these; don't improvise alternatives.

```bash
# Dev environment — the venv lives OUTSIDE OneDrive on purpose, so OneDrive
# does not try to sync thousands of site-packages files.
/Users/tranminhphuc/miniforge3/bin/python3.13 -m venv ~/.venvs/wflash
~/.venvs/wflash/bin/pip install -e ".[dev]"
# Deps: PySide6, requests, pydantic v2, PyYAML, keyring,
#       pytest, pytest-qt, responses, PyInstaller.
# isystem.connect does NOT come from PyPI — on Windows install it from the
# winIDEA 9.21 installation directory so its version matches winIDEA's.

# Run the app (run every command from the repo root)
~/.venvs/wflash/bin/python -m wflash
~/.venvs/wflash/bin/python -m wflash --adapter fake

# Tests
~/.venvs/wflash/bin/pytest -q
~/.venvs/wflash/bin/pytest tests/test_flash_workflow.py -v
~/.venvs/wflash/bin/pytest -k thread -v        # worker lifecycle — never skip
~/.venvs/wflash/bin/pytest -k "not gui" -q     # core only

# Headless end-to-end stress test (see .claude/skills/stress-test)
~/.venvs/wflash/bin/python tools/stress_test.py

# Phase 0 spike — Windows only, needs winIDEA 9.21 + the SAF85xx workspace open
python spike/01_connect.py
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

- **GUI changes go in `wflash/gui/main_window.ui` first, `.py` code second.** If a change can be expressed as a widget/layout/property in the `.ui` XML, make it there and regenerate with `pyside6-uic` — never hand-build the equivalent widget in Python, and never hand-edit `ui_main_window.py`. Fall back to Python-side construction only for what Designer genuinely can't express (logic-driven content, e.g. the mapping table's rows).
- **Name every widget and layout in the `.ui` meaningfully — never Designer's auto-numbered defaults** (`verticalLayout_2`, `label_5`). Use names that say what the thing is or where it lives: `verticalLayout_gitlabBrowser`, `tableWidget_mapping`, `horizontalLayout_flashButtons`. Before renaming an existing one, grep `wflash/gui/*.py` for `self.ui.<name>` — some layouts get widgets added at runtime.
- **Before ending a session that touched the app, run the full test suite and confirm the app still launches** (`~/.venvs/wflash/bin/python -m wflash --adapter fake`). If anything worker- or thread-related changed, run `pytest -k thread` explicitly. A green run is not optional polish: SFlash shipped a real `QThread: Destroyed while thread is still running` crash precisely because that path was only exercised by hand.
- **Before pushing a whole session's changes, stress test first.** Run (1) the full suite, (2) the threading tests explicitly even if untouched, (3) `python tools/stress_test.py` — which does not exist yet; the stress-test skill specifies what it must cover, and building it is part of the first GUI work. It drives the real app headlessly against the fake adapter through many chained actions in one process and fails on Qt threading warnings as well as its own checkpoints. If it all passes, push without asking again. If anything fails, **stop and report — do not push on your own judgment.**
- **Before implementing a newly requested feature, briefly check that it fits** this app's purpose and the spec's explicit non-goals (spec §1: no flash-loader configuration, no launching winIDEA, no local file selection, no winIDEA other than 9.21.x). If it clearly fits, implement it in the same turn. If the fit is questionable — or it is something the spec deliberately excluded — lay out the concern and wait for a decision.
- **Keep `docs/walkthrough.md` up to date as you go** — a new `## Phase X.Y` entry for every notable change, in Vietnamese, following that file's existing format (intro paragraph, `### Thay đổi` with bolded file names, `### Đã kiểm tra` with what was actually verified). Not just at the end, not skipped. Backfilling from git history loses the reasoning, which is the only part worth keeping.

## Architecture

### Layering and the one import rule that matters

Package layout is the plan's "File Structure" section, which is the authority: `wflash/core/` (no Qt at all), `wflash/gui/`, `profiles/`, `spike/`, `tests/`, plus `pyproject.toml`, `wflash.spec` and `scripts/build_windows.bat`. The entry points are `wflash/main.py` and `wflash/__main__.py` (`python -m wflash`).

- **`wflash/core/` must never import from `wflash/gui/`, and must never import Qt.** This is what makes the whole workflow testable headlessly with `FakeWinIDEAAdapter` and no display. The GUI observes the workflow through the callbacks and `CancelToken` that `gui/workers.py` turns into Qt signals — the direction of dependency never reverses.
- **Only `wflash/core/winidea_adapter.py` imports `isystem.connect`**, and it imports it **lazily, inside `connect()`** — never at module scope. That is what lets the app, the tests and the stress test run on macOS where the module does not exist. (SFlash's `vector_can.py` does the same with `python-can`.)
- The GUI never calls GitLab or winIDEA directly; every such call goes through `core/` on a worker thread.

### The adapter boundary is the load-bearing decision — build the fake first

`WinIDEAAdapter` is a `Protocol` (spec §4) with two implementations: `RealWinIDEAAdapter` and `FakeWinIDEAAdapter`. Write the Protocol and the **fake** first, then make the real one satisfy it. If the real one goes first, the "contract" silently becomes whatever winIDEA happened to do, and it can only ever be exercised in the lab.

The fake is not a stub that returns success. Every failure the real probe can produce must be reachable in simulation, because that is the only place the error handling and the rollback get tested: no instance found, a missing `Programs`/`Applications` entry, `set_*_path` refused, download failing at N%, a download that never finishes (timeout), a cancel mid-download, a connection dropped, reset failing. Target state is that `flash_workflow`'s every branch — including both rollback paths — is covered against the fake.

### Approach A: only change paths, never create entries, always be able to roll back

The spec's §3 is a safety decision, not a convenience. The workspace is the user's, already configured so that manual flashing works. Therefore:

1. Read the existing `Programs`/`Applications` entries; **match** by the profile's `winidea_entry`/`winidea_app`.
2. Change **only the file path**. Never touch target device, verify, offset or load mode. Never create a missing entry — that is `MappingError`, surfaced to the user.
3. **Back up every original path before writing**, and roll back on any failure from that point on (set-path or download). A workflow that fails and leaves the workspace pointing at a stale artifact is worse than one that refuses to start.
4. The rollback must also run on the paths that are easy to forget — an exception mid-way through setting the *second* of three paths, a cancel, a timeout. Make it a `try/finally`-shaped guarantee, not a line at the end of the happy path, and prove it with a fake-adapter test per branch.

The debug bundle dumps the download/symbol options **before and after** the edit (spec §7) for exactly this reason: when something goes wrong on a user's machine, the first question is always "what did the tool change?".

### GUI: Designer-first, mixin composition (supersedes spec §4 and the plan's File Structure)

The spec's §4 and the plan's File Structure both list plain hand-written `gui/*.py` modules. The user has since chosen SFlash's UI architecture instead, so this is the decision of record:

- **`wflash/gui/main_window.ui` is the source of truth.** `wflash/gui/ui_main_window.py` is generated by `pyside6-uic` and never hand-edited. A change that can be expressed as a widget, layout or property belongs in the XML.
- **`MainWindow` is composed by multiple inheritance from focused mixins**, all sharing one `self.ui` and free to call each other's methods directly:

```
wflash/gui/main_window.ui        Designer, source of truth
wflash/gui/ui_main_window.py     generated by pyside6-uic, never edited
wflash/gui/main_window.py        MainWindow(GitlabBrowserMixin, MappingTableMixin,
                                            FlashMixin, LogPanelMixin)
wflash/gui/gitlab_browser.py     mixin: ref -> pipeline -> job -> download
wflash/gui/mapping_table.py      mixin: the mapping rows and their validation
wflash/gui/log_panel.py          mixin + QtLogHandler
wflash/gui/flash_mixin.py        mixin: Flash/Cancel, step state, post-flash
wflash/gui/settings_dialog.py    its own .ui
wflash/gui/workers.py            Worker / WorkerContext on QThreadPool
```

Dynamic content stays in Python — mapping rows, log lines, per-core symbol rows. That is the legitimate exception, not a loophole for building static layout in code.

The plan's File Structure has been updated to match. Spec §4 still shows the old list; fix it when that file is next touched.


### Threading model — read before touching `wflash/gui/workers.py`

Artifact download and the flash workflow both run off the GUI thread, as a `Worker` (a `QRunnable` with `autoDelete=False`) on a `QThreadPool`. Progress leaves the worker two different ways, and the distinction is the whole design: `WorkerContext` hands `core/` **plain callbacks** plus a `CancelToken`, while `WorkerSignals(QObject)` is what turns those into Qt signals for the GUI. The plan fixes that choice; this section is the part it does not specify. Every item below is a failure that actually shipped in the sibling project SFlash — the mechanisms are PySide6's, so they apply here in their `QThreadPool` form.

1. **The signal-carrying QObject must outlive the runnable, and must be owned by the main thread.** A `QRunnable` is not a `QObject`, so progress signals come from a helper (`WorkerSignals`). If the only Python reference to that helper is dropped while the worker still runs — the window closed, a panel rebuilt, a local gone out of scope — the next `emit` hits a deleted object and raises `RuntimeError: Signal source has been deleted` on a pool thread, where nothing catches it. Hold an explicit reference for the worker's whole life and clear it only from a slot that runs *after* the worker is known to be done.
2. **`setAutoDelete` and Python ownership.** `QRunnable` defaults to auto-delete: the pool destroys the C++ object as soon as `run()` returns, while Python may still hold the wrapper. The plan already chose `autoDelete=False` (Task 13), which means **Python owns the worker and the main thread disposes of it** — keep a reference until `finished` has been handled, and never touch it from a pool thread. Write that reason next to the flag. Mixing the two is how a use-after-free turns into a random segfault.
3. **Never call `QThreadPool.waitForDone()` on the GUI thread while anything still needs that event loop.** Queued signals from pool threads are delivered only when the GUI loop runs, so blocking that loop to wait for workers which are themselves emitting queued signals is the same deadlock SFlash hit with `thread.wait()` inside `closeEvent()`. Cancel first (the `CancelToken`), then wait with a bounded timeout, pumping events between attempts — and make `closeEvent()` prove it, because that path is where deadlocks live.
4. **Cancelling does not stop a signal already in flight.** A completion signal emitted before the cancel was observed is already queued and will be delivered when the loop next runs. If its slot starts further work — advancing to the next workflow step, loading an artifact, enabling Flash — that work begins *after* the user cancelled. Fix: a guard flag set **before** cancelling and checked at the top of every completion slot, which settles into the cancelled state instead of continuing. The `CancelToken` alone is not enough.
5. **Every exit path out of `run()` must undo what `run()` started** — the winIDEA session, any poller, temp directories, and above all the **backed-up workspace paths**. Early returns are where this gets missed. In SFlash a single early return that skipped cleanup left a background thread calling into an object nothing referenced any more, surfacing minutes later as an intermittent crash in an unrelated test. It failed no assertion, which is exactly why the whole suite is always run.
6. **Worker-side code must not call `connect()`/`disconnect()`/`moveToThread()`, and must never `deleteLater()` the object it reports through.** PySide releases the GIL inside `exec()`/`processEvents()`; when Qt destroys a Python-created QObject that has connections, `~QObject` holds one of Qt's pooled signal/slot mutexes and blocks for the GIL in `disconnectNotify`, while another thread holding the GIL takes the same pooled mutex in `connect()`. That lock-order inversion showed up in SFlash as a random (~1 in 6) deadlock or SIGSEGV. Build and wire every helper QObject on the main thread, in `__init__`.
7. **Cancel and timeout must be honoured inside the blocking call.** `download()` runs for minutes (profile default 600 s), so a token checked only *between* workflow steps does nothing during the one step that takes time. Check it on every progress callback and let it fail through the normal error path, so the rollback still runs and the log and debug bundle are still written. A timeout that leaves the workspace edited and the session attached is a bug, not a timeout.
8. **Never connect a lambda to a signal emitted from a pool thread.** A lambda has no `QObject` thread affinity, so PySide6 cannot tell the call needs queuing and it silently runs on the worker thread. Touching a widget from there is undefined behaviour that usually looks like a cosmetic glitch — until it doesn't.

If this ever moves from `QThreadPool` to a `moveToThread()` QThread, two more rules apply: a slot connected to a worker's completion signal must never drop the last reference to the still-running `QThread` (that is the literal `QThread: Destroyed while thread is still running` crash), and the thread is stopped with a **direct** `thread.quit()` before `thread.wait()` — never via `worker.finished.connect(thread.quit)`, a queued connection whose `quit` can only be delivered by the very loop `wait()` is blocking.

**Headless code is a different problem with a different answer.** With no event loop, a Qt signal emitted from a thread the QObject does not live on is **queued and then never delivered** — a probe of exactly that pattern in SFlash received 0 of 3 emissions, silently, with no error. This is why `core/` reports progress through plain callbacks plus a `CancelToken` rather than Qt signals: a callback is always a direct, in-thread call, and behaves identically under `pytest`, the stress test and the GUI.



### GitLab, secrets, and what must never reach a log

- The Personal Access Token lives in `keyring` (Windows Credential Manager), never in a file in the repo, never in a profile YAML, never in a test fixture, never in a commit.
- The logging filter that replaces the PAT and the `PRIVATE-TOKEN` header with `***` (spec §7) applies to **every** sink: the log panel, the log file, and the debug bundle. Verbose mode logs every `isystem.connect` call with its arguments — that path needs the same filter.
- A test must prove the filter works on a realistic token, because the failure mode is a user cheerfully emailing a debug bundle that contains their credentials.
- Known GitLab failures get specific, actionable messages (spec §8): 401 token wrong/expired, 403 missing scope, 404 artifact expired, SSL failure → internal CA bundle. "Request failed" is not an acceptable message for any of them.

### Mapping: zero or many matches is a user decision, never a guess

`file_matcher` must match **exactly one** file per profile entry. Zero or more than one is not an error to work around by picking the first — it marks that row red and makes the user choose from the artifact's file list, and the Flash button stays disabled until every row is assigned (spec §5). Silently picking a file here means flashing the wrong binary, which is the single worst thing this tool could do.

### Instances and probes are enumerated, never hardcoded

The winIDEA instance list comes from `list_instances()`, wrapped so that any failure returns `[]` — no winIDEA, no running instance, no probe are all normal states to report, not exceptions to propagate. The fake adapter always offers one synthetic instance. Read the user's selection from the combo's `currentData()` (a dict), never by parsing the display text.

### Errors are typed by layer

`GitLabError`, `ArtifactError`, `MappingError`, `WinIDEAError`, `FlashError` (spec §4/§8). The GUI shows a short message plus a hint and keeps the detail in the log. `sys.excepthook` and `threading.excepthook` are installed so nothing crashes silently. Classify at the point that already knows what went wrong — never by matching on message text later.

## Reference docs

- `docs/superpowers/plans/2026-10-04-wflash-tool.md` — **Plan 1** (spike + core + GUI): Global Constraints, File Structure and Tasks 1-6. The authority on layout, dependencies, commands and conventions. `RealWinIDEAAdapter` is Plan 2, written after the spike.
- `docs/superpowers/specs/2026-10-04-wflash-tool-design.md` — the approved design spec; the authority on scope. Two points have drifted: the plan uses `requests` instead of `python-gitlab`, and one `FileEntry(name, path)` instead of `ProgramEntry`/`AppEntry`. The plan states the spec was updated for both; as committed it was not. Fix the spec when it is next touched, and trust the plan meanwhile.
- `docs/walkthrough.md` — phase-by-phase development log (Vietnamese). Read it before assuming something is unimplemented.
- `docs/winidea_api_notes.md` — what the `isystem.connect` probe actually returned, per version. The authority for every real adapter call.
