# Test

Run the test suite for WFlash.

The venv lives **outside** OneDrive (`~/.venvs/wflash`) — always call its binaries explicitly, from the repo root. The system `python3` on this machine is an Xcode licence stub and errors out.

## Steps

1. Run everything:
   ```bash
   ~/.venvs/wflash/bin/pytest -q
   ```

2. If any GUI or worker-related code changed, run the worker-lifecycle tests explicitly — they are timing-dependent and easy to lose in a `-q` run:
   ```bash
   ~/.venvs/wflash/bin/pytest -k thread -v
   ```

3. If the `.ui` changed, regenerate and check the import (see the regenerate-ui skill).

4. Confirm the app still starts headlessly — the suite does not cover start-up:
   ```bash
   ~/.venvs/wflash/bin/python -m wflash --adapter fake
   ```

5. Report what passed, what failed, and any traceback in full.

## Notes

- `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen`, so GUI tests need no display.
- `core/` tests need neither a display nor winIDEA — they run against `FakeWinIDEAAdapter`. If a `core/` test needs Qt, that is a layering bug: `wflash/core/**` must not import PySide6.
- Real-adapter behaviour cannot be tested here. It has a manual checklist on Windows (spec §10); never claim it passes from a macOS run.
