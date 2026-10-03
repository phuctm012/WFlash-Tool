# Stress Test

Full stress test before pushing a session's changes — catches the crash class that isolated unit tests structurally cannot. This mirrors the mandatory pre-push protocol in `CLAUDE.md`'s "Rules" section, which is the authority if the two ever drift.

**Status: `tools/stress_test.py` does not exist yet.** Until it does, steps 1-2 are still mandatory before a session-wide push, and "If the script does not exist yet" below is what to build.

## Steps

1. Full suite (start it first and let it run while doing the rest):
   ```bash
   ~/.venvs/wflash/bin/pytest -q
   ```

2. Threading tests explicitly, even if nothing there looks touched:
   ```bash
   ~/.venvs/wflash/bin/pytest -k thread -v
   ```

3. Headless end-to-end stress test — real actions chained back to back in one process, against the real app with the fake adapter:
   ```bash
   ~/.venvs/wflash/bin/python tools/stress_test.py
   ~/.venvs/wflash/bin/python tools/stress_test.py --list
   ~/.venvs/wflash/bin/python tools/stress_test.py --section flash --section races
   ```
   It prints `STRESS_RESULT=PASS` or `STRESS_RESULT=FAIL` plus a checkpoint count.

4. All green → report and push. Anything failed → **stop and report what broke; do not push.** Wait for the user to choose between debugging now and pushing with a note in `docs/walkthrough.md`.

## Reading the result

The script must fail on two independent things, and both matter:

- **A failed checkpoint** — an assertion about app state: a flash never settled, a thread reference was left behind, the workspace paths were not rolled back, `close()` took too long (a deadlock).
- **A Qt threading warning** — install a Qt message handler so `QThread: Destroyed while thread is still running` and `Signal source has been deleted` fail the run instead of scrolling past in stderr. These raise **no Python exception** and are the main symptom of the crash class this protocol exists to catch. Arm `faulthandler` too, so a hard segfault still prints a traceback.

## If the script does not exist yet, build it to cover

- **flash** — a full fetch→map→flash to completion against the fake adapter; a second run cancelled mid-download; the window resized and the log panel filtered while a flash is live.
- **rollback** — every failure branch: missing entry (`MappingError`), `set_*_path` refused, download failing at N%, download timing out, connection dropped mid-transfer. After each, assert the workspace paths are back to their originals.
- **gitlab** — the browser with the network patched out: repeated fetches, connection errors, 401/403/404, refs and job lists, the dialog closed mid-fetch at several delays (no deadlock, no artifact loaded after a cancel), double-click refused.
- **races** — cancels timed into every phase of start-up (0/5/20/60/150/400 ms), double Flash, double Cancel, the window closed mid-download, and closed during the GitLab fetch before any flash worker exists.
- **secrets** — a realistic PAT pushed through every sink (panel, file, bundle) and asserted absent from all of them.

## Traps, each of which has already cost a debugging session in the sibling project

1. **Never `app.quit()` to end a wait loop.** It closes every window, and `closeEvent()` cancels a running flash — so every later step runs against a closed window and a cancelled flash. Use a local `QEventLoop` and quit *that*.
2. **The theme comes from `main.py`, not the window.** Apply the stylesheet with `app.setStyleSheet(...)` if the visual state matters.
3. **Never connect a lambda to a cross-thread signal.** A lambda has no `QObject` thread affinity, so PySide6 cannot tell the call needs queuing and it silently runs on the wrong thread. To close a modal dialog, pump the event loop.
4. **Never `deleteLater()` a worker, and never call `connect()`/`moveToThread()` from worker-thread code.** Both are one half of a GIL ↔ Qt-mutex lock-order inversion that shows up as a random (~1 in 6) deadlock or SIGSEGV. See CLAUDE.md "Threading model", item 5.
5. **Do not judge thread leaks with `threading.active_count()`.** Qt worker threads leave `_DummyThread` placeholders that linger until GC and always report `is_alive() == True`, so the count plateaus even when nothing leaked. Check what matters instead: no surviving poller thread, no real non-Qt worker threads, and — for a suspected leak — the OS thread count (`ps -M <pid>`), which should stay flat across many runs.

## If it crashes or hangs and faulthandler isn't enough

A thread dying with `<no Python frame>`, or a hang at 0% CPU, needs a **native** stack. `lldb` needs the Xcode licence; macOS's `sample` does not, but only works on a live process:

1. Wrap the run so SIGSEGV/SIGBUS **park** the faulting thread instead of killing the process — a `ctypes.CFUNCTYPE` handler installed via `libc.signal()` that loops on `libc.pause()`, with `faulthandler.enable` stubbed out so it doesn't replace yours.
2. Loop the suspect section in the background; on a caught signal, or ~150 s with no new output, run `sample <pid> 2 -file out.txt`, then kill it.
3. In the sample, look for one thread in `take_gil` under `~QObject`/`disconnectNotify` and another in `QBasicMutex::lockInternal` under `QObject::connect`/`moveToThread` — that pair is the inversion.
