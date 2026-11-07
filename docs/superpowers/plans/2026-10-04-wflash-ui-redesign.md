# WFlash UI Redesign (single window, Load from GitLab popup, Teal theme) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the WFlash GUI into the SFlash layout with its own Teal colours: one main window (big Flash button that turns into a red Cancel, progress bar with percent/ETA/speed, a fixed-width *Setting* panel, the mapping table, one *Information* log tab, a status bar with version and author), GitLab browsing and downloading moved into a modal **Load from GitLab** popup with a *CI Artifact* tab and a new *Package Registry* tab, the old Settings dialog replaced by **Preferences** (cache, profiles, verbose, dark mode), and a Teal Light/Dark theme driven by `.qss` files plus one Python token table.

**Architecture:** Core first, without Qt: `ProgressEstimator` (ETA/speed from percent), `FirmwareSource` (what the source card and the debug bundle show), the new `AppSettings` fields, `ArtifactCache.store_file/has` (and a cache that only ever touches digit-named folders, so `<cache>/packages` survives artifact pruning), the Package Registry calls on `GitLabClient` (plus `verify=False`), and `firmware_fetch` (find/browse jobs, fetch an artifact or a package through the cache). Then the GUI: `WorkerRegistry` learns to wait for / abandon one key prefix, the theme (`theme.py` tokens, `style.py` loader, two `.qss`), the `PreferencesDialog`, the `GitlabDialog` (Designer `.ui` + Python, using the main window's `WorkerRegistry`, generation guard, bounded close), and finally the new `main_window.ui` with `MainWindow(MappingTableMixin, FlashMixin, LogPanelMixin)` — `GitlabBrowserMixin` and `SettingsDialog` are deleted in the same task that stops using them. The stress test and packaging follow.

**Tech Stack:** Python ≥3.11 (dev: 3.13), PySide6 6.11 (`pyside6-uic` 6.11.2 in `~/.venvs/wflash`), pytest 9 + pytest-qt 4.5, requests, responses, keyring, PyInstaller 6.

**Spec (scope authority):** `docs/superpowers/specs/2026-10-04-wflash-ui-redesign-design.md` (feature scope of the original spec `docs/superpowers/specs/2026-10-04-wflash-tool-design.md` is unchanged except the Package Registry addition).
**How authority:** `CLAUDE.md` (Designer-first + mixins sharing `self.ui`, meaningful widget names, threading rules 1–8, secrets, core never imports Qt, walkthrough entries). Where this plan and CLAUDE.md disagree on *how*, CLAUDE.md wins — stop and ask the controller.

**Decisions confirmed by the user beyond the spec text (do not re-open):**
- One Flash button that becomes a red "Cancel" while flashing; `pushButton_cancelFlash` is removed.
- The CI project field defaults to the profile's project; an edited value is remembered per profile in `AppSettings.ci_project_overrides` (key = profile file name, e.g. `saf.yaml`).
- "Download Selected Artifact" downloads the selected table row's job; with no row selected it downloads the newest *successful* job matching ref + job name (several candidates without a job name is an error, never a guess).
- Unticking "Verify TLS certificate" is allowed and logs one WARNING per session.
- Theme: Teal Light by default; Dark is toggled manually in Preferences, persisted, and applied immediately.

## Global Constraints

Carried over from Plan 1 / Plan 1b:

- Python `>=3.11`. macOS dev interpreter `/Users/tranminhphuc/miniforge3/bin/python3.13`; never the system `python3` (Xcode licence stub).
- Venv **outside** OneDrive: `~/.venvs/wflash`. Every command in this plan is run **from the repo root** with the venv's binaries (`~/.venvs/wflash/bin/pytest`, `~/.venvs/wflash/bin/python`, `~/.venvs/wflash/bin/pyside6-uic`).
- winIDEA target 9.21.x. **`isystem.connect` stays out of this plan entirely** — no file here imports it.
- `wflash/core/**` must not import PySide6 and must not import `wflash.gui`. The core files this plan adds or changes (`progress.py`, `firmware_source.py`, `firmware_fetch.py`, `settings.py`, `artifact_cache.py`, `gitlab_client.py`, `errors.py`, `debug_bundle.py`) import neither.
- GUI text in English; documentation (README, `docs/walkthrough.md`) in Vietnamese.
- Logging through `get_logger("<module>")`; every handler uses `RedactingFormatter`; a GitLab token never reaches any sink unmasked — including the GitLab dialog's own log box (`redact()` before display) and `settings.json` (the token only ever goes to the keyring).
- Every business error inherits `WFlashError` and carries `hint`; the GUI shows message + hint, details stay in the log.
- GUI tests run with `QT_QPA_PLATFORM=offscreen` (already set in `tests/conftest.py`).
- No test may touch the real system keyring: GUI tests that open the GitLab dialog use `tests.gui_stubs.patch_keyring(monkeypatch)`; the stress test replaces `gitlab_dialog.get_token/set_token` with an in-memory dict.
- Don't commit a mode change on `README.md`; edit its content in place (Task 14 is the README task).
- **Commit trailer (R11):** commit messages end with the `Co-Authored-By:` trailer *your own environment* specifies (it names the model that wrote the code). The commit commands below pass it as a second `-m "$TRAILER"`; set it once per shell, e.g. `TRAILER='Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'` — use your environment's line, not necessarily this one.
- **Walkthrough (R5):** every task's commit includes a new `## Phase 1.N` entry appended to `docs/walkthrough.md` in Vietnamese, in that file's format (intro paragraph saying *why*, `### Thay đổi` with bolded file names, `### Đã kiểm tra` with the commands actually run and their actual output). The last existing entry is Phase 1.26, so numbering continues at **1.27**: Task 1 → Phase 1.27 … Task 14 → Phase 1.40. Each task gives the intro and `Thay đổi`; fill `Đã kiểm tra` with the real result lines you saw (RED and GREEN) — never the "Expected" lines of this plan.

GUI rules (CLAUDE.md "Rules" + "GUI: Designer-first"):

- Static layout lives in `wflash/gui/main_window.ui`, `wflash/gui/gitlab_dialog.ui`, `wflash/gui/preferences_dialog.ui`; regenerate after every edit and never hand-edit `ui_*.py`:
  `~/.venvs/wflash/bin/pyside6-uic wflash/gui/main_window.ui -o wflash/gui/ui_main_window.py`
  `~/.venvs/wflash/bin/pyside6-uic wflash/gui/gitlab_dialog.ui -o wflash/gui/ui_gitlab_dialog.py`
  `~/.venvs/wflash/bin/pyside6-uic wflash/gui/preferences_dialog.ui -o wflash/gui/ui_preferences_dialog.py`
  Python builds only dynamic content (mapping rows, job/version rows and their buttons, log lines) and what Designer cannot express (the platform fixed-pitch font, runtime placeholders, the window title with the version, the two status-bar labels).
- Every widget/layout/spacer name is `<kind>_<what>` — enforced by `tests/test_gui_ui_files.py`. Before renaming one, grep `wflash/gui/*.py` for `self.ui.<name>`.
- Mixins have no `__init__`; each has an `_init_<part>()` called from `MainWindow.__init__` and documents its host contract in its module docstring.
- The instance combo stores a **dict** and is read with `currentData()`; `list_instances()` failures become `[]`.
- Colours: static widgets are styled by objectName / dynamic property in the `.qss` files; colours that code paints at runtime (log lines, red mapping rows, the `#` column) come from `wflash.gui.theme.current_theme()`. No other per-widget `setStyleSheet` in code.
- Flash is enabled only when a profile is loaded, every mapping row has a file, an instance is selected, no flash runs and no `gitlab-` worker runs. While a flash runs the same button is the (red) Cancel; everything that must not change is disabled, including *Load from GitLab…* and *Preferences…*.

Threading rules (CLAUDE.md "Threading model" 1–8) and where this plan implements each:

| Rule | Implementation |
|---|---|
| 1 signals QObject owned by main thread, outlives runnable | unchanged `Worker`/`WorkerRegistry`; the `GitlabDialog` is created once in `MainWindow.__init__` and kept for the window's life, so no receiver of a running worker is ever deleted |
| 2 `autoDelete=False` with the reason next to it | unchanged (`Worker.__init__`) |
| 3 no blocking `waitForDone()` on the GUI thread | dialog close: `WorkerRegistry.wait_idle(DIALOG_CLOSE_TIMEOUT_S, prefix="gitlab-")` (new `prefix`), then `abandon_running(prefix="gitlab-")`; window close: unchanged `wait_idle(CLOSE_TIMEOUT_S)` |
| 4 guard flag set before cancelling, checked in completion slots | `GitlabDialog._generation` is bumped before every cancel (Stop, dialog close, `abort_for_close()` from the window); every dialog slot drops results whose key started under an older generation; the window keeps `_closing` and `_flash_cancel_requested` |
| 5 every exit path undoes what `run()` started | `FlashWorkflow` (core) owns rollback + disconnect; `firmware_fetch` downloads into `TemporaryDirectory` and the cache writes `*.tmp` then renames |
| 6 no connect/moveToThread/deleteLater from worker code | all connects in `WorkerRegistry.start()` (GUI thread); row buttons are wired on the GUI thread when the table is filled |
| 7 cancel/timeout honoured inside the blocking call | `gitlab_dialog.byte_progress(ctx)` reports bytes through `WorkerContext.progress`, which raises after a cancel; the token is also passed into `download_artifacts/download_package` |
| 8 never a lambda on a pool-thread signal | every slot given to `WorkerRegistry.start()` is a bound method of `MainWindow` or `GitlabDialog`; `functools.partial` is used only on GUI-thread widget signals (row buttons, mapping combos) |

Test conventions:

- Every GUI test module is named `tests/test_gui_*.py` **and** sets `pytestmark = pytest.mark.gui`, so `pytest -k "not gui"` runs exactly the core suite.
- Every worker-lifecycle test has `thread` in its name, so `pytest -k thread` selects it. Run `pytest -k thread` after every task that touches workers, the dialog, the flash path or closing (Tasks 7, 11, 12, 13).
- Shared doubles live in `tests/gui_stubs.py` (not collected): `FakeGitLabSession` sits *under* the real `GitLabClient` and now also serves the Package Registry endpoints; `patch_keyring()` keeps tests off the real keyring; `SOURCE` is a ready-made `FirmwareSource`.
- **Between Task 12 and Task 13 `tools/stress_test.py` does not run** (it still drives the deleted GitLab browser). Do not push between those two tasks; Task 13 restores it.
- The smoke run (`main.py --smoke`) reads and writes the real user settings file, exactly as before; to keep yours untouched, run it with a throw-away `HOME` (macOS/Linux) as shown in Task 14.

## File Structure

```
wflash/__init__.py                     modify: APP_AUTHOR (Task 12)
wflash/core/progress.py                create: ProgressEstimator, format_mmss, IDLE_TEXT, CALCULATING_TEXT (Task 1)
wflash/core/firmware_source.py         create: FirmwareSource, files_note, short_timestamp (Task 2)
wflash/core/debug_bundle.py            modify: DebugContext.source, bundle writes source.json (Task 2)
wflash/core/settings.py                modify: new AppSettings fields, dict type check, PACKAGES_SUBDIR,
                                               resolved_package_cache_dir() (Task 3)
wflash/core/artifact_cache.py          modify: store_file(), has(), digit-only folders (Task 4)
wflash/core/gitlab_client.py           modify: verify flag, PackageVersion, list_package_versions,
                                               download_package, shared _stream(), hints (Task 5)
wflash/core/errors.py                  modify: GitLabError default hint names the popup (Task 5)
wflash/core/firmware_fetch.py          create: JobRow, browse_jobs, find_latest_job, fetch_ci_artifact,
                                               latest_package, fetch_package (Task 6)
wflash/gui/workers.py                  modify: wait_idle(prefix=), abandon_running(prefix=) (Task 7)
wflash/gui/theme.py                    create: THEMES tokens, current_theme() (Task 8)
wflash/gui/style.py                    create: load_stylesheet, apply_theme, repolish (Task 8)
wflash/resources/style.qss             create: Teal Light (Task 8)
wflash/resources/style_dark.qss        create: Teal Dark (Task 8)
wflash/gui/log_panel.py                modify: level colours from the theme, refresh_log_theme() (Task 8)
wflash/main.py                         modify: apply the saved theme before the window (Task 8)
pyproject.toml                         modify: package-data for wflash/resources/*.qss (Task 8)
wflash/gui/preferences_dialog.ui       create (Task 9)
wflash/gui/ui_preferences_dialog.py    generated (Task 9)
wflash/gui/preferences_dialog.py       create: PreferencesDialog (Task 9)
wflash/gui/gitlab_dialog.ui            create (Task 10)
wflash/gui/ui_gitlab_dialog.py         generated (Task 10)
wflash/gui/gitlab_dialog.py            create: GitlabDialog, default_client_factory, byte_progress (Task 11)
wflash/gui/main_window.ui              rewrite (Task 12)
wflash/gui/ui_main_window.py           regenerated (Task 12)
wflash/gui/main_window.py              rewrite: 3 mixins, popup, preferences, theme, status bar (Task 12)
wflash/gui/mapping_table.py            rewrite: on_firmware_ready, "#" column, source card, hint (Task 12)
wflash/gui/flash_mixin.py              rewrite: one Flash/Cancel button, ETA/speed, step label (Task 12)
wflash/gui/gitlab_browser.py           DELETE (Task 12)
wflash/gui/settings_dialog.py          DELETE (Task 12)
wflash/gui/settings_dialog.ui          DELETE (Task 12)
wflash/gui/ui_settings_dialog.py       DELETE (Task 12)
tools/stress_test.py                   modify: GitLab via the dialog, packages, theme section (Task 13)
wflash.spec                            modify: bundle wflash/resources (Task 14)
README.md                              modify, Vietnamese (Task 14)
tests/test_progress.py                 create (Task 1)      tests/test_firmware_source.py   create (Task 2)
tests/test_debug_bundle.py             modify (Task 2)      tests/test_settings.py          modify (Task 3)
tests/test_artifact_cache.py           modify (Task 4)      tests/test_gitlab_client.py     modify (Task 5)
tests/test_firmware_fetch.py           create (Task 6)      tests/test_gui_workers.py       modify (Task 7)
tests/test_gui_theme.py                create (Task 8)      tests/test_gui_root_main.py     modify (Task 8)
tests/test_gui_preferences_dialog.py   create (Task 9)      tests/test_gui_ui_files.py      modify (Tasks 9, 10, 12)
tests/gui_stubs.py                     modify (Tasks 11, 12) tests/test_gui_gitlab_dialog.py create (Task 11)
tests/test_gui_flash.py                rewrite (Task 12)    tests/test_gui_mapping_table.py rewrite (Task 12)
tests/test_gui_main_window.py          rewrite (Task 12)    tests/test_gui_close_window.py  rewrite (Task 12)
tests/test_gui_gitlab_browser.py       DELETE (Task 12)     tests/test_gui_settings_dialog.py DELETE (Task 12)
tests/test_packaging.py                create (Task 14)
docs/walkthrough.md                    append Phase 1.27 … 1.40
```

Unchanged and still green throughout: `tests/test_gui_log_panel.py`, `tests/test_gui_main.py`, `tests/test_gui_stubs.py`, `tests/test_gui_workers.py` (only extended), every core test not listed above.

Shared host state after Task 12 (what `MainWindow` provides and `tests/gui_stubs.HostWindow` imitates):

| Attribute / method | Type | Used by |
|---|---|---|
| `ui` | `Ui_MainWindow` | all mixins |
| `settings` | `AppSettings` (replaced by Preferences; the dialog always reads `host.settings`) | main, GitlabDialog |
| `adapter` | `WinIDEAAdapter` | flash |
| `ctx` | `DebugContext` (`source` = loaded `FirmwareSource.to_dict()`) | mapping, flash, log, GitlabDialog |
| `profile` | `Profile \| None` | mapping, flash, GitlabDialog |
| `log_file` | `Path \| None` | log |
| `_workers` | `WorkerRegistry` | flash, GitlabDialog |
| `_closing` | `bool` | mapping, flash |
| `_client_factory` | `Callable[[AppSettings], GitLabClient]` | GitlabDialog |
| `show_error(exc)` | modal `QMessageBox.critical` | flash, main, GitlabDialog |
| `_save_settings()` | writes `settings.json` | main, GitlabDialog |
| `gitlab_busy()` | `_workers.has_running("gitlab-")` | flash |
| `statusBar()` | `QStatusBar` (`statusBar_main`) | log, flash |
| cross-mixin | `on_firmware_ready`, `clear_mapping`, `mapping_rows`, `mapping_complete`, `refresh_mapping_theme` (mapping); `flash_active`, `current_step`, `_update_flash_controls` (flash); `refresh_log_theme`, `_detach_log_panel` (log) | |

---

### Task 1: `ProgressEstimator` — ETA and speed from a percentage

**Files:**
- Create: `wflash/core/progress.py`
- Test: `tests/test_progress.py`

**Interfaces:**
- Consumes: nothing (pure Python; time is passed in).
- Produces (`wflash.core.progress`):
  - `IDLE_TEXT = "ETA: -- | Speed: --"`, `CALCULATING_TEXT = "ETA: calculating… | Speed: --"`
  - `format_mmss(seconds: float) -> str`
  - `ProgressEstimator(started_at: float)` with `start(total_bytes: int, now: float)`, `update(percent: int | None, now: float)`, property `transferring -> bool`, attributes `percent`, `eta_s`, `speed_kbps`, `total_bytes`, and `elapsed(now)`, `running_text()`, `done_text(now)`, `failed_text(now)`, `cancelled_text(now)` — the exact strings of spec §2.1.

- [ ] **Step 1: Write the failing test `tests/test_progress.py`**

```python
import pytest

from wflash.core.progress import CALCULATING_TEXT, IDLE_TEXT, ProgressEstimator, format_mmss


def test_format_mmss():
    assert format_mmss(0) == "00:00"
    assert format_mmss(75.4) == "01:15"
    assert format_mmss(3725) == "62:05"
    assert format_mmss(-3) == "00:00"


def test_idle_and_calculating_texts():
    assert IDLE_TEXT == "ETA: -- | Speed: --"
    est = ProgressEstimator(started_at=100.0)
    assert est.running_text() == CALCULATING_TEXT
    est.start(total_bytes=1024 * 1000, now=110.0)
    assert est.transferring
    est.update(0, now=111.0)
    assert est.running_text() == "ETA: calculating… | Speed: --"


def test_eta_and_speed_from_percent():
    est = ProgressEstimator(started_at=0.0)
    est.start(total_bytes=1024 * 1000, now=10.0)  # 1000 KiB
    est.update(25, now=20.0)  # 10 s for 25 %
    assert est.eta_s == pytest.approx(30.0)
    assert est.speed_kbps == pytest.approx(25.0)  # 250 KiB / 10 s
    assert est.running_text() == "25% | ETA: 00:30 | Speed: 25.0 KB/s"


def test_none_percent_keeps_previous_values():
    est = ProgressEstimator(started_at=0.0)
    est.start(total_bytes=2048, now=0.0)
    est.update(50, now=4.0)
    before = est.running_text()
    est.update(None, now=9.0)
    assert est.running_text() == before
    assert est.percent == 50


def test_update_before_start_is_ignored():
    est = ProgressEstimator(started_at=0.0)
    est.update(40, now=5.0)
    assert est.percent is None and est.running_text() == CALCULATING_TEXT


def test_zero_bytes_gives_eta_without_speed():
    est = ProgressEstimator(started_at=0.0)
    est.start(total_bytes=0, now=0.0)
    est.update(50, now=2.0)
    assert est.running_text() == "50% | ETA: 00:02 | Speed: --"


def test_final_texts_use_time_since_flash_start():
    est = ProgressEstimator(started_at=100.0)
    est.start(total_bytes=1024 * 100, now=105.0)
    est.update(100, now=115.0)  # 100 KiB in 10 s
    assert est.done_text(now=172.0) == "100% | Time: 01:12 | Speed: 10.0 KB/s"
    assert est.failed_text(now=130.0) == "Failed | Time: 00:30 | Speed: --"
    assert est.cancelled_text(now=103.0) == "Cancelled | Time: 00:03"


def test_restart_clears_previous_estimate():
    est = ProgressEstimator(started_at=0.0)
    est.start(total_bytes=1024, now=0.0)
    est.update(50, now=1.0)
    est.start(total_bytes=1024, now=2.0)
    assert est.percent is None and est.eta_s is None and est.speed_kbps is None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `~/.venvs/wflash/bin/pytest tests/test_progress.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'wflash.core.progress'`.

- [ ] **Step 3: Implement `wflash/core/progress.py`**

```python
"""ETA / speed estimate for the flash header (pure Python, no Qt).

winIDEA only reports a percentage, so the speed shown is an *estimate*: the byte total is
the on-disk size of the mapped program files (`.s3` is S-record text, roughly twice the
size of the binary that actually reaches the flash). It is still useful to see that the
download moves and roughly how long it will take — the same trade-off SFlash makes.

Time is always passed in (`now`, e.g. `time.monotonic()`), so the arithmetic is tested
with fake clocks.
"""
from __future__ import annotations

IDLE_TEXT = "ETA: -- | Speed: --"
CALCULATING_TEXT = "ETA: calculating… | Speed: --"


def format_mmss(seconds: float) -> str:
    """`75.4` -> `"01:15"`; minutes are not capped at 59 (`3725` -> `"62:05"`)."""
    total = max(0, int(round(seconds)))
    return f"{total // 60:02d}:{total % 60:02d}"


class ProgressEstimator:
    """One flash: `started_at` is when Flash was pressed, `start()` when DOWNLOAD began."""

    def __init__(self, started_at: float) -> None:
        self.started_at = started_at
        self.total_bytes = 0
        self.transfer_started_at: float | None = None
        self.percent: int | None = None
        self.eta_s: float | None = None
        self.speed_kbps: float | None = None

    @property
    def transferring(self) -> bool:
        return self.transfer_started_at is not None

    def start(self, total_bytes: int, now: float) -> None:
        self.total_bytes = max(0, int(total_bytes))
        self.transfer_started_at = now
        self.percent = None
        self.eta_s = None
        self.speed_kbps = None

    def update(self, percent: int | None, now: float) -> None:
        """`None` means "busy, amount unknown": the previous ETA/speed stay as they were."""
        if percent is None or self.transfer_started_at is None:
            return
        p = max(0, min(100, int(percent)))
        self.percent = p
        elapsed = now - self.transfer_started_at
        if p <= 0 or elapsed <= 0:
            return
        self.eta_s = elapsed * (100 - p) / p
        if self.total_bytes > 0:
            self.speed_kbps = self.total_bytes * p / 100 / 1024 / elapsed

    def elapsed(self, now: float) -> float:
        return max(0.0, now - self.started_at)

    def running_text(self) -> str:
        if not self.percent or self.eta_s is None:
            return CALCULATING_TEXT
        speed = f"{self.speed_kbps:.1f} KB/s" if self.speed_kbps is not None else "--"
        return f"{self.percent}% | ETA: {format_mmss(self.eta_s)} | Speed: {speed}"

    def done_text(self, now: float) -> str:
        speed = f"{self.speed_kbps:.1f} KB/s" if self.speed_kbps is not None else "--"
        return f"100% | Time: {format_mmss(self.elapsed(now))} | Speed: {speed}"

    def failed_text(self, now: float) -> str:
        return f"Failed | Time: {format_mmss(self.elapsed(now))} | Speed: --"

    def cancelled_text(self, now: float) -> str:
        return f"Cancelled | Time: {format_mmss(self.elapsed(now))}"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_progress.py -v` → Expected: `8 passed`.
Run: `~/.venvs/wflash/bin/pytest -q` → Expected: `228 passed`.

- [ ] **Step 5: Walkthrough entry** — append to `docs/walkthrough.md`:

```markdown
## Phase 1.27: Ước lượng ETA và tốc độ (ProgressEstimator)

Phần đầu cửa sổ mới hiện `phần trăm | ETA | Speed` giống SFlash, nhưng winIDEA chỉ báo phần trăm. `ProgressEstimator` (core, không Qt) tính ETA từ thời gian đã trôi và phần trăm, còn tốc độ là **ước lượng** từ kích thước file `.s3` trên đĩa. Thời gian luôn được truyền vào (`now`) nên test dùng đồng hồ giả, không phụ thuộc máy.

### Thay đổi

- **`wflash/core/progress.py`** (mới): `ProgressEstimator`, `format_mmss`, `IDLE_TEXT`, `CALCULATING_TEXT`; đủ các chuỗi của spec §2.1 (đang chạy, xong, lỗi, hủy).
- **`tests/test_progress.py`** (mới): 8 test.

### Đã kiểm tra

- RED / GREEN `tests/test_progress.py`, `pytest -q`: <kết quả thật>
```

- [ ] **Step 6: Commit**

```bash
git add wflash/core/progress.py tests/test_progress.py docs/walkthrough.md
git commit -m "feat(core): add ProgressEstimator for flash ETA and speed" -m "$TRAILER"
```

---

### Task 2: `FirmwareSource` and the debug bundle's `source.json`

**Files:**
- Create: `wflash/core/firmware_source.py`
- Modify: `wflash/core/debug_bundle.py`
- Test: `tests/test_firmware_source.py` (new), `tests/test_debug_bundle.py` (one assertion updated, two tests appended)

**Interfaces:**
- Consumes (current): `wflash.core.debug_bundle.DebugContext(profile_path=None, mapping=[], adapter_info={}, snapshots={}, errors=[])` (dataclass), `create_debug_bundle(ctx: DebugContext, dest_dir: Path, log_file: Path | None) -> Path`; `wflash.core.logging_setup.redact(text) -> str`.
- Produces:
  - `wflash.core.firmware_source.FirmwareSource(kind: Literal["ci", "package"], project: str, title: str, detail: str, cache_note: str)` (frozen dataclass) with `to_dict() -> dict[str, str]`.
  - `files_note(from_cache: bool, count: int) -> str` (`"Cached · 3 files"`, `"Downloaded · 1 file"`), `short_timestamp(iso: str) -> str` (`"2026-10-04 09:20"`).
  - `DebugContext.source: dict[str, str]` (default `{}`); the bundle gains `source.json` (redacted).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_firmware_source.py`:

```python
from wflash.core.firmware_source import FirmwareSource, files_note, short_timestamp


def test_to_dict_has_every_field():
    source = FirmwareSource("package", "group/pkgs", "Package · fw 1.4.0", "group/pkgs · 2026-10-04 09:20", "Downloaded · 1 file")
    assert source.to_dict() == {
        "kind": "package",
        "project": "group/pkgs",
        "title": "Package · fw 1.4.0",
        "detail": "group/pkgs · 2026-10-04 09:20",
        "cache_note": "Downloaded · 1 file",
    }


def test_files_note_singular_and_plural():
    assert files_note(True, 3) == "Cached · 3 files"
    assert files_note(False, 1) == "Downloaded · 1 file"
    assert files_note(False, 0) == "Downloaded · 0 files"


def test_short_timestamp():
    assert short_timestamp("2026-10-04T09:20:11.123Z") == "2026-10-04 09:20"
    assert short_timestamp("yesterday") == "yesterday"
    assert short_timestamp(None) == ""
```

In `tests/test_debug_bundle.py`, `test_bundle_contents_and_redaction` now expects `source.json` too. Replace

```python
        assert names == {
            "log.txt", "environment.json", "profile.yaml", "mapping.json", "workspace_snapshots.json", "errors.txt",
        }
```

with

```python
        assert names == {
            "log.txt", "environment.json", "profile.yaml", "mapping.json", "source.json",
            "workspace_snapshots.json", "errors.txt",
        }
```

and append to the end of `tests/test_debug_bundle.py`:

```python
def test_bundle_records_the_firmware_source_redacted(tmp_path):
    from wflash.core.firmware_source import FirmwareSource

    register_secret("glpat-SECRET-2")
    source = FirmwareSource("ci", "group/p", "CI artifact · job #7 build_app", "x glpat-SECRET-2", "Cached · 3 files")
    ctx = DebugContext(source=source.to_dict())
    path = create_debug_bundle(ctx, tmp_path, None)
    clear_secrets()
    with zipfile.ZipFile(path) as zf:
        data = json.loads(zf.read("source.json"))
    assert data["kind"] == "ci" and data["title"] == "CI artifact · job #7 build_app"
    assert data["detail"] == "x ***"


def test_bundle_source_is_empty_object_when_nothing_loaded(tmp_path):
    path = create_debug_bundle(DebugContext(), tmp_path, None)
    with zipfile.ZipFile(path) as zf:
        assert json.loads(zf.read("source.json")) == {}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_firmware_source.py tests/test_debug_bundle.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'wflash.core.firmware_source'`.

- [ ] **Step 3: Implement**

Create `wflash/core/firmware_source.py`:

```python
"""Where the loaded firmware came from: shown on the source card and written to the debug bundle."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

SourceKind = Literal["ci", "package"]


@dataclass(frozen=True)
class FirmwareSource:
    kind: SourceKind
    project: str  # GitLab project path (or id) the firmware was downloaded from
    title: str  # "CI artifact · job #7 build_app" / "Package · saf85xx-firmware 1.4.0"
    detail: str  # "group/saf85xx-sw · main · pipeline #100" / "group/pkgs · 2026-10-04 09:20"
    cache_note: str  # "Cached · 3 files" / "Downloaded · 3 files"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def files_note(from_cache: bool, count: int) -> str:
    """`files_note(True, 3)` -> "Cached · 3 files"; `files_note(False, 1)` -> "Downloaded · 1 file"."""
    origin = "Cached" if from_cache else "Downloaded"
    return f"{origin} · {count} file{'' if count == 1 else 's'}"


def short_timestamp(iso: str) -> str:
    """'2026-10-04T09:20:11.123Z' -> '2026-10-04 09:20'; anything unexpected is returned unchanged."""
    text = str(iso or "")
    if len(text) >= 16 and text[10] == "T":
        return text[:10] + " " + text[11:16]
    return text
```

In `wflash/core/debug_bundle.py` add the field as the last field of `DebugContext`:

```python
    errors: list[str] = field(default_factory=list)
    source: dict[str, str] = field(default_factory=dict)  # FirmwareSource.to_dict() of the loaded firmware
```

and in `create_debug_bundle`, right after the `mapping.json` line:

```python
        zf.writestr("mapping.json", redact(json.dumps(ctx.mapping, indent=2)))
        zf.writestr("source.json", redact(json.dumps(ctx.source, indent=2)))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_firmware_source.py tests/test_debug_bundle.py -v` → Expected: `11 passed`.
Run: `~/.venvs/wflash/bin/pytest -q` → Expected: `233 passed`.

- [ ] **Step 5: Walkthrough entry**

```markdown
## Phase 1.28: FirmwareSource — firmware đang dùng đến từ đâu

Thẻ nguồn firmware trong vùng Setting và debug bundle cần cùng một mô tả: CI artifact hay package, project nào, job/version nào, lấy từ cache hay vừa tải. `FirmwareSource` (core) chứa đúng các chuỗi đó; `DebugContext.source` giữ bản dict và bundle có thêm `source.json` (đã che token như mọi file khác), vì câu hỏi đầu tiên khi debug luôn là "đã flash bản nào".

### Thay đổi

- **`wflash/core/firmware_source.py`** (mới): `FirmwareSource`, `files_note`, `short_timestamp`.
- **`wflash/core/debug_bundle.py`**: field `DebugContext.source`, file `source.json` trong bundle.
- **`tests/test_firmware_source.py`** (mới, 3 test), **`tests/test_debug_bundle.py`** (thêm `source.json` vào danh sách file, thêm 2 test).

### Đã kiểm tra

- RED / GREEN, `pytest -q`: <kết quả thật>
```

- [ ] **Step 6: Commit**

```bash
git add wflash/core/firmware_source.py wflash/core/debug_bundle.py tests/test_firmware_source.py tests/test_debug_bundle.py docs/walkthrough.md
git commit -m "feat(core): describe the loaded firmware source and add it to the debug bundle" -m "$TRAILER"
```

---

### Task 3: New `AppSettings` fields (TLS, dark mode, CI/package fields) with dict type checking

**Files:**
- Modify: `wflash/core/settings.py`
- Test: `tests/test_settings.py` (tests appended)

**Interfaces:**
- Consumes (current): `AppSettings` dataclass (`gitlab_url, ca_bundle, cache_dir, max_cached_jobs, profiles_dir, last_profile, verbose`), `AppSettings.load(path=None)` (exact-type check per field, warning + default otherwise), `save(path=None)`, `resolved_cache_dir()`, `resolved_profiles_dir()`; `default_cache_dir()`.
- Produces:
  - Fields `verify_tls: bool = True`, `dark_mode: bool = False`, `ci_project_overrides: dict[str, str] = {}` (profile file name → project), `ci_job_name: str = ""`, `package_project: str = ""`, `package_name: str = ""`.
  - `load()` accepts a dict only if every key and value is a `str`; otherwise warning `Ignoring setting 'ci_project_overrides': expected dict[str, str], got …` and the default.
  - `PACKAGES_SUBDIR = "packages"` and `AppSettings.resolved_package_cache_dir() -> Path` (`resolved_cache_dir() / "packages"`).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_settings.py`:

```python
def test_new_fields_default_values():
    s = AppSettings()
    assert s.verify_tls is True and s.dark_mode is False
    assert s.ci_project_overrides == {}
    assert (s.ci_job_name, s.package_project, s.package_name) == ("", "", "")


def test_new_fields_round_trip(tmp_path):
    path = tmp_path / "s.json"
    AppSettings(
        verify_tls=False,
        dark_mode=True,
        ci_project_overrides={"saf.yaml": "group/other"},
        ci_job_name="build_app",
        package_project="group/pkgs",
        package_name="saf85xx-firmware",
    ).save(path)
    loaded = AppSettings.load(path)
    assert loaded.verify_tls is False and loaded.dark_mode is True
    assert loaded.ci_project_overrides == {"saf.yaml": "group/other"}
    assert loaded.ci_job_name == "build_app"
    assert (loaded.package_project, loaded.package_name) == ("group/pkgs", "saf85xx-firmware")


def test_overrides_default_is_not_shared_between_instances():
    a, b = AppSettings(), AppSettings()
    a.ci_project_overrides["x.yaml"] = "g/p"
    assert b.ci_project_overrides == {}


@pytest.mark.parametrize(
    "bad",
    [["saf.yaml", "group/x"], "group/x", {"saf.yaml": 5}, {"saf.yaml": None}],
)
def test_wrong_typed_overrides_fall_back_to_default(tmp_path, caplog, bad):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"ci_project_overrides": bad, "dark_mode": True}), encoding="utf-8")
    with caplog.at_level("WARNING", logger="wflash.settings"):
        loaded = AppSettings.load(path)
    assert loaded.ci_project_overrides == {}
    assert loaded.dark_mode is True
    assert "ci_project_overrides" in caplog.text and "dict[str, str]" in caplog.text


def test_wrong_typed_bool_flags_fall_back(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"verify_tls": "no", "dark_mode": 1}), encoding="utf-8")
    loaded = AppSettings.load(path)
    assert loaded.verify_tls is True and loaded.dark_mode is False


def test_package_cache_sits_inside_the_cache_dir(tmp_path):
    assert AppSettings(cache_dir=str(tmp_path)).resolved_package_cache_dir() == tmp_path / "packages"
    assert AppSettings().resolved_package_cache_dir() == st.default_cache_dir() / st.PACKAGES_SUBDIR
```

- [ ] **Step 2: Run them to verify they fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_settings.py -v`
Expected: `9 failed, 10 passed` — `AttributeError: 'AppSettings' object has no attribute 'verify_tls'` / `'ci_project_overrides'` / `'resolved_package_cache_dir'`.

- [ ] **Step 3: Implement** — replace `wflash/core/settings.py` with:

```python
"""User settings stored as JSON in the user config dir; GitLab token stored in the OS keyring."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import keyring
import keyring.errors

from wflash.core.errors import GitLabError
from wflash.core.logging_setup import get_logger

KEYRING_SERVICE = "WFlash-GitLab"
PACKAGES_SUBDIR = "packages"  # Package Registry downloads are cached in <cache_dir>/packages
log = get_logger("settings")


def config_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "WFlash"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "WFlash"
    return Path.home() / ".config" / "wflash"


def default_cache_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "WFlash" / "cache"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "WFlash"
    return Path.home() / ".cache" / "wflash"


def bundled_profiles_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "profiles"
    return Path(__file__).resolve().parents[2] / "profiles"


def settings_path() -> Path:
    return config_dir() / "settings.json"


def _same_type(value: object, default: object) -> bool:
    # bool is a subclass of int, so require the exact type; a dict must map str -> str.
    if type(value) is not type(default):
        return False
    if isinstance(default, dict):
        return all(isinstance(k, str) and isinstance(v, str) for k, v in value.items())
    return True


def _type_name(default: object) -> str:
    return "dict[str, str]" if isinstance(default, dict) else type(default).__name__


@dataclass
class AppSettings:
    gitlab_url: str = ""
    ca_bundle: str = ""
    cache_dir: str = ""
    max_cached_jobs: int = 10
    profiles_dir: str = ""
    last_profile: str = ""
    verbose: bool = False
    verify_tls: bool = True
    dark_mode: bool = False
    # Profile file name (e.g. "saf.yaml") -> CI project typed in Load from GitLab.
    ci_project_overrides: dict[str, str] = field(default_factory=dict)
    ci_job_name: str = ""
    package_project: str = ""
    package_name: str = ""

    def resolved_cache_dir(self) -> Path:
        return Path(self.cache_dir) if self.cache_dir else default_cache_dir()

    def resolved_package_cache_dir(self) -> Path:
        return self.resolved_cache_dir() / PACKAGES_SUBDIR

    def resolved_profiles_dir(self) -> Path:
        return Path(self.profiles_dir) if self.profiles_dir else bundled_profiles_dir()

    @classmethod
    def load(cls, path: Path | None = None) -> "AppSettings":
        path = path or settings_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError) as exc:
            log.warning("Ignoring unreadable settings file %s: %s", path, exc)
            return cls()
        if not isinstance(data, dict):
            log.warning("Ignoring settings file %s: not a JSON object", path)
            return cls()
        defaults = cls()
        values = {}
        for f in fields(cls):
            if f.name not in data:
                continue
            value, default = data[f.name], getattr(defaults, f.name)
            if _same_type(value, default):
                values[f.name] = value
            else:
                log.warning("Ignoring setting %r: expected %s, got %r", f.name, _type_name(default), value)
        return cls(**values)

    def save(self, path: Path | None = None) -> None:
        path = path or settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


def get_token(gitlab_url: str) -> str | None:
    if not gitlab_url:
        return None
    try:
        return keyring.get_password(KEYRING_SERVICE, gitlab_url)
    except keyring.errors.KeyringError as exc:
        log.warning("Cannot read GitLab token from keyring: %s", exc)
        return None


def set_token(gitlab_url: str, token: str) -> None:
    try:
        keyring.set_password(KEYRING_SERVICE, gitlab_url, token)
    except keyring.errors.KeyringError as exc:
        raise GitLabError(
            "Cannot store the GitLab token",
            hint="The system keyring is unavailable or locked. Unlock it (Windows Credential Manager) and try again.",
        ) from exc
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_settings.py -v` → Expected: `19 passed`.
Run: `~/.venvs/wflash/bin/pytest -q` → Expected: `242 passed`.

- [ ] **Step 5: Walkthrough entry**

```markdown
## Phase 1.29: AppSettings cho popup GitLab, TLS và theme

Popup Load from GitLab và Preferences cần nhớ thêm: có kiểm tra chứng chỉ TLS không, dark mode, project CI người dùng sửa (nhớ theo từng profile), tên job, project và tên package. Cơ chế kiểm kiểu khi load được giữ và mở rộng cho `dict`: chỉ nhận dict str→str, sai thì về mặc định kèm warning — một file settings hỏng không được làm app chết. Cache package nằm trong `<cache_dir>/packages`.

### Thay đổi

- **`wflash/core/settings.py`**: 6 field mới, `_same_type` kiểm cả dict, `PACKAGES_SUBDIR`, `resolved_package_cache_dir()`.
- **`tests/test_settings.py`**: thêm 9 test (mặc định, round-trip, dict không dùng chung, dict sai kiểu, bool sai kiểu, thư mục cache package).

### Đã kiểm tra

- RED / GREEN, `pytest -q`: <kết quả thật>
```

- [ ] **Step 6: Commit**

```bash
git add wflash/core/settings.py tests/test_settings.py docs/walkthrough.md
git commit -m "feat(core): settings for TLS verification, dark mode and Load from GitLab fields" -m "$TRAILER"
```

---

### Task 4: `ArtifactCache.store_file()` / `has()` and a cache that only touches its own folders

**Files:**
- Modify: `wflash/core/artifact_cache.py`
- Test: `tests/test_artifact_cache.py` (tests appended)

**Interfaces:**
- Consumes (current): `ArtifactCache(root: Path, max_jobs: int = 10)` with `job_dir(project_id, job_id)`, `get(project_id, job_id) -> Path | None` (touches the marker), `store_zip(project_id, job_id, zip_path) -> Path`, `entries()`, `prune()`, `clear()`; `ArtifactError(message, hint)`.
- Produces:
  - `store_file(project_id: int, job_id: int, file_path: Path) -> Path` — copies one file into `<root>/<project>/<key>/files/`, same atomic `.tmp` + rename + marker + prune as `store_zip`; a copy failure is `ArtifactError("Failed to cache file …", hint about disk space)`.
  - `has(project_id: int, job_id: int) -> bool` — like `get` without touching the marker (for the "Cached" labels).
  - `entries()`, `prune()` and `clear()` only look at digit-named project and job folders, so the artifact cache at `<cache_dir>` never deletes the package cache at `<cache_dir>/packages` (the old `prune()` deleted every non-marked `*/*` folder — it would have wiped `packages/<project>`).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_artifact_cache.py`:

```python
def test_store_file_caches_a_single_file(tmp_path):
    cache = ArtifactCache(tmp_path / "cache")
    src = tmp_path / "dl" / "App.s3"
    src.parent.mkdir()
    src.write_bytes(b"S0 data")
    files = cache.store_file(43, 501, src)
    assert files == tmp_path / "cache" / "43" / "501" / "files"
    assert (files / "App.s3").read_bytes() == b"S0 data"
    assert cache.get(43, 501) == files
    assert src.exists()  # the download itself is left to its temporary folder


def test_store_file_missing_source_raises_and_leaves_no_entry(tmp_path):
    cache = ArtifactCache(tmp_path / "cache")
    with pytest.raises(ArtifactError, match="Failed to cache file") as info:
        cache.store_file(43, 501, tmp_path / "missing.bin")
    assert "disk space" in info.value.hint
    assert cache.get(43, 501) is None
    assert not list((tmp_path / "cache").glob("**/*.tmp"))


def test_has_does_not_touch_the_marker(tmp_path):
    cache = ArtifactCache(tmp_path / "cache")
    assert not cache.has(1, 10)
    cache.store_zip(1, 10, make_zip(tmp_path / "a.zip", {"f.s3": "x"}))
    marker = cache.job_dir(1, 10) / ".complete"
    os.utime(marker, (1000, 1000))
    assert cache.has(1, 10)
    assert marker.stat().st_mtime == 1000


def test_artifact_prune_never_touches_the_packages_cache(tmp_path):
    root = tmp_path / "cache"
    packages = ArtifactCache(root / "packages")
    src = tmp_path / "fw.bin"
    src.write_bytes(b"fw")
    pkg_files = packages.store_file(43, 501, src)
    (root / "packages" / "43" / "502").mkdir()  # an incomplete package entry belongs to the package cache
    artifacts = ArtifactCache(root, max_jobs=1)
    artifacts.store_zip(1, 10, make_zip(tmp_path / "a.zip", {"f.s3": "x"}))
    artifacts.store_zip(1, 11, make_zip(tmp_path / "b.zip", {"f.s3": "y"}))
    assert (pkg_files / "fw.bin").read_bytes() == b"fw"
    assert (root / "packages" / "43" / "502").is_dir()
    assert artifacts.entries() == [root / "1" / "11"]
    artifacts.clear()
    assert (pkg_files / "fw.bin").exists()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_artifact_cache.py -v`
Expected: `4 failed, 11 passed` — `AttributeError: 'ArtifactCache' object has no attribute 'store_file'` and `… no attribute 'has'`.

- [ ] **Step 3: Implement** — replace `wflash/core/artifact_cache.py` with:

```python
"""On-disk cache of downloaded firmware: <root>/<project_id>/<job_id>/files.

The same layout caches Package Registry downloads under its own root
(`<cache_dir>/packages`, key = package id). Only digit-named directories belong to a
cache, so the artifact cache never touches the `packages` folder next to its entries.
"""
from __future__ import annotations

import datetime
import os
import shutil
import zipfile
from pathlib import Path
from typing import Callable

from wflash.core.errors import ArtifactError
from wflash.core.logging_setup import get_logger

MARKER = ".complete"
log = get_logger("cache")


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    dest_resolved = dest.resolve()
    for info in zf.infolist():
        target = (dest / info.filename).resolve()
        if not target.is_relative_to(dest_resolved):
            raise ArtifactError(
                f"Unsafe path in artifact zip: {info.filename}",
                hint="The artifact contains unsafe file paths; do not use it — check the CI job output."
            )
    zf.extractall(dest)


def _is_cache_dir(path: Path) -> bool:
    return path.name.isdigit() and path.is_dir() and not path.is_symlink()


class ArtifactCache:
    def __init__(self, root: Path, max_jobs: int = 10) -> None:
        self.root = root
        self.max_jobs = max_jobs

    def job_dir(self, project_id: int, job_id: int) -> Path:
        return self.root / str(project_id) / str(job_id)

    def has(self, project_id: int, job_id: int) -> bool:
        """Like get() but without marking the entry as recently used (for "Cached" labels)."""
        return (self.job_dir(project_id, job_id) / MARKER).is_file()

    def get(self, project_id: int, job_id: int) -> Path | None:
        job = self.job_dir(project_id, job_id)
        marker = job / MARKER
        if not marker.is_file():
            return None
        os.utime(marker)
        return job / "files"

    def store_zip(self, project_id: int, job_id: int, zip_path: Path) -> Path:
        def fill(files_dir: Path) -> None:
            try:
                with zipfile.ZipFile(zip_path) as zf:
                    _safe_extract(zf, files_dir)
            except zipfile.BadZipFile as exc:
                raise ArtifactError(
                    f"Artifact is not a valid zip file: {exc}",
                    hint="Download the artifact again; it may be corrupt."
                ) from exc
            except OSError as exc:
                raise ArtifactError(
                    f"Failed to extract artifact: {exc}",
                    hint="Check free disk space and path length, then retry."
                ) from exc

        return self._store(project_id, job_id, fill)

    def store_file(self, project_id: int, job_id: int, file_path: Path) -> Path:
        """Cache one downloaded file as-is (a package file that is not a zip)."""

        def fill(files_dir: Path) -> None:
            try:
                shutil.copy2(file_path, files_dir / file_path.name)
            except OSError as exc:
                raise ArtifactError(
                    f"Failed to cache file {file_path.name}: {exc}",
                    hint="Check free disk space and path length, then retry."
                ) from exc

        return self._store(project_id, job_id, fill)

    def _store(self, project_id: int, job_id: int, fill: Callable[[Path], None]) -> Path:
        final = self.job_dir(project_id, job_id)
        tmp = final.with_name(final.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        files_dir = tmp / "files"
        try:
            files_dir.mkdir(parents=True)
            fill(files_dir)
            (tmp / MARKER).write_text(datetime.datetime.now().isoformat(), encoding="utf-8")
            shutil.rmtree(final, ignore_errors=True)
            try:
                tmp.rename(final)
            except OSError as exc:
                raise ArtifactError(
                    f"Failed to cache artifact (file may be locked): {exc}",
                    hint="Close programs that may hold files in the cache folder (winIDEA, Explorer), "
                         "then retry or clear the cache."
                ) from exc
        except ArtifactError:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        except Exception as exc:
            shutil.rmtree(tmp, ignore_errors=True)
            raise ArtifactError(f"Unexpected error while caching artifact: {exc}") from exc
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        log.info("Cached artifact for project %s job %s at %s", project_id, job_id, final)
        self.prune()
        return final / "files"

    def _project_dirs(self) -> list[Path]:
        if not self.root.is_dir():
            return []
        return [p for p in self.root.iterdir() if _is_cache_dir(p)]

    def entries(self) -> list[Path]:
        return [
            m.parent
            for project in self._project_dirs()
            for m in project.glob(f"*/{MARKER}")
            if m.parent.name.isdigit()
        ]

    def prune(self) -> None:
        jobs = sorted(self.entries(), key=lambda d: (d / MARKER).stat().st_mtime, reverse=True)
        for old in jobs[self.max_jobs:]:
            log.info("Pruning cached artifact %s", old)
            shutil.rmtree(old, ignore_errors=True)
        for project in self._project_dirs():
            for tmp_dir in project.glob("*.tmp"):
                log.info("Cleaning leftover temporary directory %s", tmp_dir)
                shutil.rmtree(tmp_dir, ignore_errors=True)
            for job_dir in project.iterdir():
                if job_dir.is_dir() and job_dir.name.isdigit() and not (job_dir / MARKER).exists():
                    log.info("Cleaning incomplete job directory %s", job_dir)
                    shutil.rmtree(job_dir, ignore_errors=True)

    def clear(self) -> None:
        """Delete only cache-layout entries (<root>/<digits>/<digits>[.tmp]); never root or anything else."""
        log.info("Clearing artifact cache %s", self.root)
        failures: list[OSError] = []
        for project in self._project_dirs():
            for entry in project.iterdir():
                name = entry.name.removesuffix(".tmp")
                if not (name.isdigit() and entry.is_dir() and not entry.is_symlink()):
                    continue
                try:
                    shutil.rmtree(entry)
                except OSError as exc:
                    log.warning("Cannot remove cache entry %s: %s", entry, exc)
                    failures.append(exc)
            try:
                project.rmdir()  # only succeeds when it is now empty
            except OSError:
                pass
        if failures:
            raise ArtifactError(
                f"Could not clear {len(failures)} cached artifact(s)",
                hint="Close programs that may hold files in the cache folder (winIDEA, Explorer), then try again.",
            ) from failures[0]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_artifact_cache.py -v` → Expected: `15 passed` (the 11 existing ones unchanged).
Run: `~/.venvs/wflash/bin/pytest -q` → Expected: `246 passed`.

- [ ] **Step 5: Walkthrough entry**

```markdown
## Phase 1.30: Cache cho file package (store_file) và cache chỉ đụng thư mục của nó

Package Registry có thể trả về một file không phải zip; `store_file` đặt nguyên file vào cache với cùng cơ chế `.tmp` → rename → marker như artifact. Cache package nằm ở `<cache_dir>/packages`, nên `prune()` cũ (xóa mọi thư mục `*/*` không có marker) sẽ xóa luôn cache package mỗi lần lưu một artifact. Giờ `entries/prune/clear` chỉ nhìn thư mục tên toàn chữ số. `has()` cho nhãn "Cached" mà không làm thay đổi thứ tự LRU.

### Thay đổi

- **`wflash/core/artifact_cache.py`**: `store_file`, `has`, `_store` dùng chung, `_project_dirs` chỉ thư mục số.
- **`tests/test_artifact_cache.py`**: thêm 4 test (file đơn, lỗi copy, `has` không chạm marker, prune không đụng `packages/`).

### Đã kiểm tra

- RED / GREEN, `pytest -q`: <kết quả thật>
```

- [ ] **Step 6: Commit**

```bash
git add wflash/core/artifact_cache.py tests/test_artifact_cache.py docs/walkthrough.md
git commit -m "feat(core): cache single package files and keep the cache inside its own folders" -m "$TRAILER"
```

---

### Task 5: `GitLabClient` — Package Registry and `verify=False`

**Files:**
- Modify: `wflash/core/gitlab_client.py`, `wflash/core/errors.py`
- Test: `tests/test_gitlab_client.py` (import line changed, tests appended)

**Interfaces:**
- Consumes (current): `GitLabClient(base_url, token, ca_bundle=None, session=None, timeout=30.0)` with `_get(path, params=None, stream=False)` (HTTP/SSL/connection classification), `_get_all(path, params=None)` (`X-Next-Page`), `get_project_id`, `list_refs`, `list_pipelines(project_id, ref, limit=20)`, `list_jobs(project_id, pipeline_id, name_glob="*")`, `download_artifacts(project_id, job_id, dest, progress_cb=None, cancel=None) -> Path`; `DownloadProgress = Callable[[int, int], None]`; `CancelToken.raise_if_cancelled()`.
- Produces:
  - `GitLabClient(..., verify: bool = True)` — `self.verify` is `False` when `verify=False` (CA bundle ignored, urllib3's per-request warning muted), else `ca_bundle or True`.
  - `PackageVersion(id: int, name: str, version: str, created_at: str)` (frozen dataclass).
  - `list_package_versions(project_id: int, package_name: str, limit: int = 20) -> list[PackageVersion]` — `GET /projects/:id/packages?package_type=generic&package_name=<name>&order_by=created_at&sort=desc&per_page=100&page=N`, exact-name filter, stops paging once `limit` is reached; none → `GitLabError("No versions of package '<name>' found", hint="Check the package project and name in Load from GitLab…")`.
  - `download_package(project_id: int, package: PackageVersion, dest: Path, progress_cb=None, cancel=None) -> Path` — first file of `/packages/:package_id/package_files`, streamed from `/packages/generic/<name>/<version>/<file>` (each part URL-quoted) into `dest/<safe file name>`; no files → `GitLabError("Version '<v>' of package '<name>' has no files", hint=…)`; disk error → `ArtifactError("Cannot write package to …")`; interrupted stream → `GitLabError("Package download interrupted: …")`.
  - Hints that said "Settings" now point to "Load from GitLab…" (the URL/token/CA fields moved there); `GitLabError.default_hint` likewise.

- [ ] **Step 1: Write the failing tests**

In `tests/test_gitlab_client.py` change the import line

```python
from wflash.core.gitlab_client import GitLabClient, Job, Pipeline, Ref
```

to

```python
from wflash.core.gitlab_client import GitLabClient, Job, PackageVersion, Pipeline, Ref
```

and append:

```python
# -- TLS verification ------------------------------------------------------------------


def test_verify_defaults_to_true_or_ca_bundle():
    assert GitLabClient(BASE, TOKEN).verify is True
    assert GitLabClient(BASE, TOKEN, ca_bundle="/ca.pem").verify == "/ca.pem"
    clear_secrets()


@responses.activate
def test_verify_false_is_passed_to_requests():
    client = GitLabClient(BASE, TOKEN, ca_bundle="/ca.pem", verify=False)
    assert client.verify is False
    responses.get(f"{API}/projects/42/repository/branches", json=[])
    responses.get(f"{API}/projects/42/repository/tags", json=[])
    assert client.list_refs(42) == []
    assert all(call.request.req_kwargs["verify"] is False for call in responses.calls)
    clear_secrets()


# -- Package Registry ------------------------------------------------------------------

PKG_LIST = f"{API}/projects/43/packages"


def pkg(id_, name, version, created="2026-10-04T09:20:00Z"):
    return {"id": id_, "name": name, "version": version, "package_type": "generic", "created_at": created}


@responses.activate
def test_list_package_versions_keeps_exact_name_newest_first(client):
    responses.get(
        PKG_LIST,
        match=[matchers.query_param_matcher({
            "package_type": "generic", "package_name": "fw", "order_by": "created_at", "sort": "desc",
            "per_page": "100", "page": "1",
        })],
        json=[pkg(502, "fw", "1.4.0"), pkg(503, "fw-debug", "9.9.9"), pkg(501, "fw", "1.3.0", "2026-10-01T08:00:00Z")],
    )
    assert client.list_package_versions(43, "fw") == [
        PackageVersion(502, "fw", "1.4.0", "2026-10-04T09:20:00Z"),
        PackageVersion(501, "fw", "1.3.0", "2026-10-01T08:00:00Z"),
    ]


@responses.activate
def test_list_package_versions_follows_pages_until_limit(client):
    def page(p, nxt):
        return dict(
            match=[matchers.query_param_matcher({
                "package_type": "generic", "package_name": "fw", "order_by": "created_at", "sort": "desc",
                "per_page": "100", "page": p,
            })],
            headers={"X-Next-Page": nxt},
        )

    responses.get(PKG_LIST, json=[pkg(3, "fw-x", "0")], **page("1", "2"))
    responses.get(PKG_LIST, json=[pkg(2, "fw", "2.0"), pkg(1, "fw", "1.0")], **page("2", "3"))
    versions = client.list_package_versions(43, "fw", limit=1)
    assert [v.version for v in versions] == ["2.0"]
    assert len(responses.calls) == 2  # page 3 is never requested once the limit is reached


@responses.activate
def test_no_package_versions_is_a_gitlab_error_with_hint(client):
    responses.get(PKG_LIST, json=[pkg(9, "fw-debug", "1.0")])
    with pytest.raises(GitLabError, match="No versions of package 'fw' found") as info:
        client.list_package_versions(43, "fw")
    assert "package project and name" in info.value.hint


@responses.activate
def test_download_package_fetches_the_first_file(client, tmp_path):
    version = PackageVersion(502, "fw", "1.4.0", "")
    responses.get(
        f"{API}/projects/43/packages/502/package_files",
        json=[{"id": 1, "file_name": "fw-1.4.0.zip"}, {"id": 2, "file_name": "notes.txt"}],
    )
    body = b"PK" + b"z" * 3000
    responses.get(f"{API}/projects/43/packages/generic/fw/1.4.0/fw-1.4.0.zip", body=body,
                  auto_calculate_content_length=True)
    seen = []
    path = client.download_package(43, version, tmp_path, progress_cb=lambda d, t: seen.append((d, t)))
    assert path == tmp_path / "fw-1.4.0.zip"
    assert path.read_bytes() == body
    assert seen[-1] == (len(body), len(body))
    assert responses.calls[1].request.headers["PRIVATE-TOKEN"] == TOKEN


@responses.activate
def test_download_package_quotes_name_version_and_file(client, tmp_path):
    version = PackageVersion(7, "fw pkg", "1.0+b1", "")
    responses.get(f"{API}/projects/43/packages/7/package_files", json=[{"file_name": "a b.s3"}])
    responses.get(f"{API}/projects/43/packages/generic/fw%20pkg/1.0%2Bb1/a%20b.s3", body=b"S0")
    assert client.download_package(43, version, tmp_path).read_bytes() == b"S0"


@responses.activate
def test_download_package_never_writes_outside_dest(client, tmp_path):
    version = PackageVersion(7, "fw", "1.0", "")
    responses.get(f"{API}/projects/43/packages/7/package_files", json=[{"file_name": "../../evil.bin"}])
    responses.get(f"{API}/projects/43/packages/generic/fw/1.0/..%2F..%2Fevil.bin", body=b"x")
    path = client.download_package(43, version, tmp_path / "dl")
    assert path == tmp_path / "dl" / "evil.bin"


@responses.activate
def test_download_package_without_files_is_a_gitlab_error(client, tmp_path):
    version = PackageVersion(7, "fw", "1.0", "")
    responses.get(f"{API}/projects/43/packages/7/package_files", json=[])
    with pytest.raises(GitLabError, match="Version '1.0' of package 'fw' has no files") as info:
        client.download_package(43, version, tmp_path)
    assert "another version" in info.value.hint


@responses.activate
def test_download_package_cancel_removes_partial_file(client, tmp_path):
    version = PackageVersion(7, "fw", "1.0", "")
    responses.get(f"{API}/projects/43/packages/7/package_files", json=[{"file_name": "fw.zip"}])
    responses.get(f"{API}/projects/43/packages/generic/fw/1.0/fw.zip", body=b"x" * 10)
    token = CancelToken()
    token.cancel()
    with pytest.raises(CancelledError):
        client.download_package(43, version, tmp_path, cancel=token)
    assert list(tmp_path.iterdir()) == []


@responses.activate
def test_download_package_disk_error_is_an_artifact_error(client, tmp_path, monkeypatch):
    version = PackageVersion(7, "fw", "1.0", "")
    responses.get(f"{API}/projects/43/packages/7/package_files", json=[{"file_name": "fw.zip"}])
    responses.get(f"{API}/projects/43/packages/generic/fw/1.0/fw.zip", body=b"x" * 10)

    def boom(self, *a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(type(tmp_path), "open", boom)
    with pytest.raises(ArtifactError, match="Cannot write package") as info:
        client.download_package(43, version, tmp_path)
    assert "disk space" in info.value.hint
    assert list(tmp_path.iterdir()) == []


@responses.activate
def test_download_package_interrupted_is_a_gitlab_error(client, tmp_path):
    version = PackageVersion(7, "fw", "1.0", "")
    responses.get(f"{API}/projects/43/packages/7/package_files", json=[{"file_name": "fw.zip"}])
    responses.get(
        f"{API}/projects/43/packages/generic/fw/1.0/fw.zip",
        body=requests.exceptions.ConnectionError("reset by peer"),
    )
    with pytest.raises(GitLabError, match="Cannot reach GitLab"):
        client.download_package(43, version, tmp_path)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_gitlab_client.py -v`
Expected: collection error `ImportError: cannot import name 'PackageVersion' from 'wflash.core.gitlab_client'`.

- [ ] **Step 3: Implement**

Replace `wflash/core/gitlab_client.py` with:

```python
"""Minimal GitLab REST v4 client: refs → pipelines → jobs → artifacts, and generic packages."""
from __future__ import annotations

import fnmatch
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Literal
from urllib.parse import quote

import requests
import urllib3

from wflash.core.cancel import CancelToken
from wflash.core.errors import ArtifactError, GitLabError
from wflash.core.logging_setup import get_logger, register_secret

log = get_logger("gitlab")
CHUNK = 1024 * 1024
DownloadProgress = Callable[[int, int], None]  # (bytes_done, bytes_total or 0 if unknown)

_HINTS = {
    401: "Token is invalid or expired. Create a Personal Access Token with scope read_api and enter it in Load from GitLab…",
    403: "Your token has no access to this project. Ask for project access or check the token scope.",
    404: "Not found. Check the project path (profile or Load from GitLab…); the artifact may also have expired.",
}


_BAD_RESPONSE_HINT = (
    "GitLab returned something that is not its API (a proxy or login page?). "
    "Check the GitLab URL in Load from GitLab… and that you can open it in a browser."
)


@contextmanager
def _parsing(path: str) -> Iterator[None]:
    try:
        yield
    except (ValueError, KeyError, TypeError) as exc:
        raise GitLabError(f"Unexpected response from GitLab for {path}", hint=_BAD_RESPONSE_HINT) from exc


@dataclass(frozen=True)
class Ref:
    name: str
    kind: Literal["branch", "tag"]


@dataclass(frozen=True)
class Pipeline:
    id: int
    ref: str
    status: str
    sha: str
    created_at: str


@dataclass(frozen=True)
class Job:
    id: int
    name: str
    stage: str
    status: str
    finished_at: str


@dataclass(frozen=True)
class PackageVersion:
    id: int  # package id (one id per version of a generic package)
    name: str
    version: str
    created_at: str


def _safe_file_name(name: str) -> str:
    """A server-supplied file name must never escape the download folder."""
    base = Path(str(name).replace("\\", "/")).name
    return base if base not in ("", ".", "..") else "package.bin"


def _has_archive(job: dict) -> bool:
    if any(a.get("file_type") == "archive" for a in job.get("artifacts") or []):
        return True
    return bool(job.get("artifacts_file"))


class GitLabClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        ca_bundle: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 30.0,
        verify: bool = True,
    ) -> None:
        self.base = base_url.rstrip("/") + "/api/v4"
        self.session = session or requests.Session()
        self.session.headers["PRIVATE-TOKEN"] = token
        # verify=False is the user's explicit choice ("Verify TLS certificate" unticked); the
        # GUI logs a WARNING for it once per session, so urllib3's per-request warning is muted.
        self.verify: bool | str = (ca_bundle or True) if verify else False
        if not verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.timeout = timeout
        register_secret(token)

    def _get(self, path: str, params: dict | None = None, stream: bool = False) -> requests.Response:
        url = self.base + path
        log.debug("GET %s params=%s", url, params)
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout, verify=self.verify, stream=stream)
        except requests.exceptions.SSLError as exc:
            raise GitLabError(
                f"SSL error connecting to GitLab: {exc}",
                hint="If GitLab uses an internal certificate, set the CA bundle file in Load from GitLab…",
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise GitLabError(f"Cannot reach GitLab: {exc}") from exc
        if resp.status_code >= 400:
            raise GitLabError(
                f"GitLab returned HTTP {resp.status_code} for {path}: {resp.text[:200]}",
                hint=_HINTS.get(resp.status_code, ""),
            )
        return resp

    def _get_all(self, path: str, params: dict | None = None) -> list:
        """Fetch every page of a list endpoint by following the X-Next-Page header."""
        items: list = []
        page = "1"
        while page:
            resp = self._get(path, {**(params or {}), "per_page": 100, "page": page})
            with _parsing(path):
                data = resp.json()
                if not isinstance(data, list):
                    raise TypeError("expected a JSON list")
            items.extend(data)
            page = resp.headers.get("X-Next-Page", "")
        return items

    def get_project_id(self, project: str) -> int:
        if project.isdigit():
            return int(project)
        path = f"/projects/{quote(project, safe='')}"
        resp = self._get(path)
        with _parsing(path):
            return int(resp.json()["id"])

    def list_refs(self, project_id: int) -> list[Ref]:
        base = f"/projects/{project_id}/repository"
        branches = self._get_all(f"{base}/branches")
        tags = self._get_all(f"{base}/tags")
        with _parsing(base):
            return [Ref(b["name"], "branch") for b in branches] + [Ref(t["name"], "tag") for t in tags]

    def list_pipelines(self, project_id: int, ref: str, limit: int = 20) -> list[Pipeline]:
        """Latest pipelines of `ref`, newest first. `limit` is clamped to 1..100 (one GitLab page)."""
        path = f"/projects/{project_id}/pipelines"
        params = {"ref": ref, "per_page": max(1, min(limit, 100)), "order_by": "id", "sort": "desc"}
        resp = self._get(path, params)
        with _parsing(path):
            return [
                Pipeline(p["id"], p.get("ref", ""), p.get("status", ""), p.get("sha", ""), p.get("created_at") or "")
                for p in resp.json()
            ]

    def list_jobs(self, project_id: int, pipeline_id: int, name_glob: str = "*") -> list[Job]:
        path = f"/projects/{project_id}/pipelines/{pipeline_id}/jobs"
        data = self._get_all(path)
        with _parsing(path):
            jobs = [
                Job(j["id"], j["name"], j.get("stage", ""), j.get("status", ""), j.get("finished_at") or "")
                for j in data
                if _has_archive(j) and fnmatch.fnmatchcase(j["name"], name_glob)
            ]
        return sorted(jobs, key=lambda j: j.name)

    def download_artifacts(
        self,
        project_id: int,
        job_id: int,
        dest: Path,
        progress_cb: DownloadProgress | None = None,
        cancel: CancelToken | None = None,
    ) -> Path:
        path = f"/projects/{project_id}/jobs/{job_id}/artifacts"
        log.info("Downloading artifacts of job #%s", job_id)
        return self._stream(path, dest / f"artifacts_{job_id}.zip", "Artifact", progress_cb, cancel)

    def list_package_versions(self, project_id: int, package_name: str, limit: int = 20) -> list[PackageVersion]:
        """Versions of one generic package, newest first. Raises GitLabError when there is none."""
        path = f"/projects/{project_id}/packages"
        params = {
            "package_type": "generic",
            "package_name": package_name,
            "order_by": "created_at",
            "sort": "desc",
            "per_page": 100,
        }
        versions: list[PackageVersion] = []
        page = "1"
        while page and len(versions) < limit:
            resp = self._get(path, {**params, "page": page})
            with _parsing(path):
                data = resp.json()
                if not isinstance(data, list):
                    raise TypeError("expected a JSON list")
                # GitLab matches package_name as a prefix/substring: keep the exact name only.
                versions += [
                    PackageVersion(int(p["id"]), p["name"], p["version"], p.get("created_at") or "")
                    for p in data
                    if p.get("name") == package_name
                ]
            page = resp.headers.get("X-Next-Page", "")
        if not versions:
            raise GitLabError(
                f"No versions of package '{package_name}' found",
                hint="Check the package project and name in Load from GitLab…",
            )
        return versions[:limit]

    def download_package(
        self,
        project_id: int,
        package: PackageVersion,
        dest: Path,
        progress_cb: DownloadProgress | None = None,
        cancel: CancelToken | None = None,
    ) -> Path:
        """Download the first file attached to `package` into `dest`; return its path."""
        files_path = f"/projects/{project_id}/packages/{package.id}/package_files"
        files = self._get_all(files_path)
        with _parsing(files_path):
            names = [f["file_name"] for f in files]
        if not names:
            raise GitLabError(
                f"Version '{package.version}' of package '{package.name}' has no files",
                hint="Pick another version, or check the package in GitLab (Deploy > Package Registry).",
            )
        file_name = names[0]
        path = (
            f"/projects/{project_id}/packages/generic/{quote(package.name, safe='')}/"
            f"{quote(package.version, safe='')}/{quote(file_name, safe='')}"
        )
        log.info("Downloading package %s %s (%s)", package.name, package.version, file_name)
        return self._stream(path, dest / _safe_file_name(file_name), "Package", progress_cb, cancel)

    def _stream(
        self,
        path: str,
        final: Path,
        what: str,
        progress_cb: DownloadProgress | None,
        cancel: CancelToken | None,
    ) -> Path:
        resp = self._get(path, stream=True)
        part = final.with_name(final.name + ".part")
        try:
            total = int(resp.headers.get("Content-Length") or 0)
        except ValueError:
            total = 0  # malformed header: size unknown
        done = 0
        log.debug("%s download: %s bytes", what, total or "unknown")
        try:
            with resp:
                final.parent.mkdir(parents=True, exist_ok=True)
                with part.open("wb") as fh:
                    for chunk in resp.iter_content(CHUNK):
                        if cancel is not None:
                            cancel.raise_if_cancelled()
                        fh.write(chunk)
                        done += len(chunk)
                        if progress_cb is not None:
                            progress_cb(done, total)
                part.replace(final)
        except BaseException as exc:
            try:
                part.unlink(missing_ok=True)
            except OSError:
                pass
            if isinstance(exc, requests.exceptions.RequestException):
                raise GitLabError(f"{what} download interrupted: {exc}") from exc
            if isinstance(exc, OSError):
                raise ArtifactError(
                    f"Cannot write {what.lower()} to {final.parent}: {exc}",
                    hint=f"Cannot write the downloaded {what.lower()}. Check free disk space and folder permissions, then retry.",
                ) from exc
            raise
        log.info("Downloaded %.1f MB to %s", done / 1e6, final)
        return final
```

In `wflash/core/errors.py` change the `GitLabError` default hint:

```python
class GitLabError(WFlashError):
    default_hint = "Check the GitLab URL, token and network connection in Load from GitLab…"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_gitlab_client.py -v` → Expected: `31 passed` (19 existing, 12 new).
Run: `~/.venvs/wflash/bin/pytest -q` → Expected: `258 passed`. (No existing test asserts on the word "Settings" in these hints; the GitLab browser test that checks `default_client_factory`'s own hint is untouched here and deleted in Task 12.)

- [ ] **Step 5: Walkthrough entry**

```markdown
## Phase 1.31: GitLabClient — Package Registry và tùy chọn tắt kiểm tra TLS

Tab Package Registry làm giống SFlash: package generic, mỗi version có file đính kèm, tải file đầu tiên. Client vẫn dùng `requests` với phân loại lỗi và phân trang `X-Next-Page` sẵn có; API lọc tên package theo tiền tố nên client chỉ giữ đúng tên. Phần stream xuống đĩa (`.part`, hủy, lỗi ổ đĩa) được dùng chung cho artifact và package. Tên file server trả về được làm sạch để không ghi ra ngoài thư mục tải. `verify=False` là lựa chọn rõ ràng của người dùng (popup ghi WARNING), nên cảnh báo urllib3 mỗi request được tắt. Các hint nhắc "Settings" giờ trỏ tới "Load from GitLab…".

### Thay đổi

- **`wflash/core/gitlab_client.py`**: `verify`, `PackageVersion`, `list_package_versions`, `download_package`, `_stream`, `_safe_file_name`, hint mới.
- **`wflash/core/errors.py`**: hint mặc định của `GitLabError`.
- **`tests/test_gitlab_client.py`**: thêm 12 test (TLS, lọc đúng tên, phân trang tới limit, không có version, file đầu tiên, quote URL, không ghi ra ngoài, không có file, hủy, lỗi ổ đĩa, mất kết nối).

### Đã kiểm tra

- RED / GREEN, `pytest -q`: <kết quả thật>
```

- [ ] **Step 6: Commit**

```bash
git add wflash/core/gitlab_client.py wflash/core/errors.py tests/test_gitlab_client.py docs/walkthrough.md
git commit -m "feat(core): GitLab package registry download and optional TLS verification" -m "$TRAILER"
```

---

### Task 6: `firmware_fetch` — find, browse and fetch CI artifacts and packages through the cache

**Files:**
- Create: `wflash/core/firmware_fetch.py`
- Test: `tests/test_firmware_fetch.py`

**Interfaces:**
- Consumes: `GitLabClient.list_pipelines(project_id, ref, limit)` (newest first), `list_jobs(project_id, pipeline_id, name_glob)` (jobs with an archive), `download_artifacts(project_id, job_id, dest, progress_cb, cancel) -> Path`, `list_package_versions(project_id, name, limit)`, `download_package(project_id, package, dest, progress_cb, cancel) -> Path` (Task 5); `ArtifactCache.get/store_zip/store_file` (Task 4); `FirmwareSource`, `files_note`, `short_timestamp` (Task 2).
- Produces (`wflash.core.firmware_fetch`):
  - `JobRow(pipeline_id: int, job_id: int, job_name: str, ref: str, status: str, when: str)` (frozen dataclass).
  - `browse_jobs(client, project_id, ref, job_filter="*", job_name="", pipelines=BROWSE_PIPELINES (10), cancel=None) -> list[JobRow]`.
  - `find_latest_job(client, project_id, ref, job_filter="*", job_name="", pipelines=LATEST_PIPELINES (5), cancel=None) -> JobRow` — newest pipeline that has a successful match wins; several matches in that pipeline → `GitLabError(… successful jobs …, hint="Enter the job name to download, or use Browse jobs… and pick a row.")`; none → `GitLabError("No successful job '<name>' with artifacts on '<ref>' in the newest N pipelines", hint=…)`.
  - `fetch_ci_artifact(client, project, project_id, job: JobRow, cache, progress=None, cancel=None) -> tuple[Path, FirmwareSource]`.
  - `latest_package(client, project_id, package_name) -> PackageVersion`.
  - `fetch_package(client, project, project_id, package, cache, progress=None, cancel=None) -> tuple[Path, FirmwareSource]` — zip → `store_zip`, anything else → `store_file`.
  - `count_files(root: Path) -> int`.

- [ ] **Step 1: Write the failing test `tests/test_firmware_fetch.py`** (a duck-typed `StubClient`; core tests need neither network nor Qt)

```python
"""Core firmware lookups against a duck-typed client (no network, no Qt)."""
import io
import zipfile
from pathlib import Path

import pytest

from wflash.core.artifact_cache import ArtifactCache
from wflash.core.cancel import CancelToken
from wflash.core.errors import CancelledError, GitLabError
from wflash.core.firmware_fetch import (
    JobRow,
    browse_jobs,
    fetch_ci_artifact,
    fetch_package,
    find_latest_job,
    latest_package,
)
from wflash.core.gitlab_client import Job, PackageVersion, Pipeline

FILES = {"out/App.s3": b"S0", "out/x_cm7_0.elf": b"E0", "out/x_cm7_1.elf": b"E1"}


def zip_bytes(files=FILES) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


class StubClient:
    """Answers the GitLabClient calls firmware_fetch makes; records them."""

    def __init__(self, pipelines=None, jobs=None, package_file=("fw.zip", zip_bytes())):
        self.pipelines = pipelines if pipelines is not None else [
            Pipeline(101, "main", "success", "b" * 8, "2026-10-04T09:00:00Z"),
            Pipeline(100, "main", "success", "a" * 8, "2026-10-03T09:00:00Z"),
        ]
        self.jobs = jobs if jobs is not None else {
            101: [Job(9, "build_app", "build", "failed", "2026-10-04T09:05:00Z")],
            100: [Job(7, "build_app", "build", "success", "2026-10-03T09:05:00Z"),
                  Job(8, "build_boot", "build", "success", "")],
        }
        self.package_file = package_file
        self.calls = []

    def list_pipelines(self, project_id, ref, limit=20):
        self.calls.append(("pipelines", ref, limit))
        return self.pipelines[:limit]

    def list_jobs(self, project_id, pipeline_id, name_glob="*"):
        self.calls.append(("jobs", pipeline_id, name_glob))
        return [j for j in self.jobs.get(pipeline_id, []) if name_glob == "*" or j.name.startswith(name_glob.rstrip("*"))]

    def download_artifacts(self, project_id, job_id, dest, progress_cb=None, cancel=None):
        self.calls.append(("artifacts", job_id))
        data = zip_bytes()
        if progress_cb:
            progress_cb(len(data), len(data))
        if cancel is not None:
            cancel.raise_if_cancelled()
        path = dest / f"artifacts_{job_id}.zip"
        path.write_bytes(data)
        return path

    def list_package_versions(self, project_id, package_name, limit=20):
        self.calls.append(("versions", package_name, limit))
        return [PackageVersion(502, package_name, "1.4.0", "2026-10-04T09:20:00Z")][:limit]

    def download_package(self, project_id, package, dest, progress_cb=None, cancel=None):
        self.calls.append(("package", package.id))
        name, data = self.package_file
        path = dest / name
        path.write_bytes(data)
        return path


def test_browse_jobs_lists_every_pipeline_newest_first():
    client = StubClient()
    rows = browse_jobs(client, 42, "main", "build_*")
    assert [(r.pipeline_id, r.job_id, r.job_name, r.status) for r in rows] == [
        (101, 9, "build_app", "failed"),
        (100, 7, "build_app", "success"),
        (100, 8, "build_boot", "success"),
    ]
    assert rows[0].when == "2026-10-04 09:05"
    assert rows[2].when == "2026-10-03 09:00"  # no finished_at: pipeline creation time
    assert client.calls[0] == ("pipelines", "main", 10)


def test_browse_jobs_filters_by_job_name():
    rows = browse_jobs(StubClient(), 42, "main", "*", job_name="build_boot")
    assert [r.job_id for r in rows] == [8]


def test_browse_jobs_honours_cancel_between_pipelines():
    token = CancelToken()
    token.cancel()
    with pytest.raises(CancelledError):
        browse_jobs(StubClient(), 42, "main", cancel=token)


def test_latest_job_skips_failed_pipeline_and_matches_name():
    row = find_latest_job(StubClient(), 42, "main", "*", job_name="build_app")
    assert (row.pipeline_id, row.job_id, row.job_name, row.ref) == (100, 7, "build_app", "main")


def test_latest_job_with_several_candidates_and_no_name_is_an_error():
    with pytest.raises(GitLabError, match="2 successful jobs") as info:
        find_latest_job(StubClient(), 42, "main", "*")
    assert "job name" in info.value.hint


def test_latest_job_none_found_is_an_error():
    with pytest.raises(GitLabError, match="No successful job 'flash_x' with artifacts on 'main'") as info:
        find_latest_job(StubClient(), 42, "main", "*", job_name="flash_x", pipelines=5)
    assert "Browse jobs" in info.value.hint


def test_fetch_ci_artifact_downloads_then_uses_cache(tmp_path):
    client = StubClient()
    cache = ArtifactCache(tmp_path / "cache")
    job = JobRow(100, 7, "build_app", "main", "success", "2026-10-03 09:05")
    seen = []
    path, source = fetch_ci_artifact(client, "group/sw", 42, job, cache, progress=lambda d, t: seen.append(d))
    assert (path / "out" / "App.s3").read_bytes() == b"S0"
    assert seen
    assert source.kind == "ci" and source.project == "group/sw"
    assert source.title == "CI artifact · job #7 build_app"
    assert source.detail == "group/sw · main · pipeline #100"
    assert source.cache_note == "Downloaded · 3 files"
    path2, source2 = fetch_ci_artifact(client, "group/sw", 42, job, cache)
    assert path2 == path and source2.cache_note == "Cached · 3 files"
    assert [c for c in client.calls if c[0] == "artifacts"] == [("artifacts", 7)]


def test_fetch_ci_artifact_cancel_leaves_no_cache_entry(tmp_path):
    token = CancelToken()
    token.cancel()
    cache = ArtifactCache(tmp_path / "cache")
    with pytest.raises(CancelledError):
        fetch_ci_artifact(StubClient(), "g/p", 42, JobRow(1, 7, "b", "main", "success", ""), cache, cancel=token)
    assert cache.entries() == []


def test_latest_package_asks_for_one_version():
    client = StubClient()
    assert latest_package(client, 43, "fw").version == "1.4.0"
    assert client.calls == [("versions", "fw", 1)]


def test_fetch_package_zip_is_extracted(tmp_path):
    client = StubClient()
    cache = ArtifactCache(tmp_path / "cache" / "packages")
    version = PackageVersion(502, "fw", "1.4.0", "2026-10-04T09:20:00Z")
    path, source = fetch_package(client, "group/pkgs", 43, version, cache)
    assert (path / "out" / "x_cm7_1.elf").read_bytes() == b"E1"
    assert source.kind == "package"
    assert source.title == "Package · fw 1.4.0"
    assert source.detail == "group/pkgs · 2026-10-04 09:20"
    assert source.cache_note == "Downloaded · 3 files"
    _, again = fetch_package(client, "group/pkgs", 43, version, cache)
    assert again.cache_note == "Cached · 3 files"
    assert [c for c in client.calls if c[0] == "package"] == [("package", 502)]


def test_fetch_package_non_zip_is_cached_as_is(tmp_path):
    client = StubClient(package_file=("App.s3", b"S0 raw"))
    cache = ArtifactCache(tmp_path / "packages")
    path, source = fetch_package(client, "g/p", 43, PackageVersion(9, "fw", "2.0", ""), cache)
    assert (path / "App.s3").read_bytes() == b"S0 raw"
    assert source.cache_note == "Downloaded · 1 file"
    assert isinstance(path, Path)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `~/.venvs/wflash/bin/pytest tests/test_firmware_fetch.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'wflash.core.firmware_fetch'`.

- [ ] **Step 3: Implement `wflash/core/firmware_fetch.py`**

```python
"""Find and download firmware for Load from GitLab: CI job artifacts and generic packages.

Plain blocking calls (no Qt): the GUI runs them on a worker thread and passes the
worker's CancelToken and a byte-progress callback. Everything that is downloaded goes
through an ArtifactCache, and the result says where it came from (FirmwareSource).
"""
from __future__ import annotations

import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from wflash.core.artifact_cache import ArtifactCache
from wflash.core.cancel import CancelToken
from wflash.core.errors import GitLabError
from wflash.core.firmware_source import FirmwareSource, files_note, short_timestamp
from wflash.core.gitlab_client import DownloadProgress, GitLabClient, PackageVersion
from wflash.core.logging_setup import get_logger

log = get_logger("gitlab.fetch")
BROWSE_PIPELINES = 10  # "Browse jobs…" looks at the newest 10 pipelines of the ref
LATEST_PIPELINES = 5  # "Download Selected Artifact" without a row searches the newest 5


@dataclass(frozen=True)
class JobRow:
    pipeline_id: int
    job_id: int
    job_name: str
    ref: str
    status: str
    when: str  # "2026-10-04 09:20" (job finished, else pipeline created)


def _check(cancel: CancelToken | None) -> None:
    if cancel is not None:
        cancel.raise_if_cancelled()


def count_files(root: Path) -> int:
    return sum(1 for p in root.rglob("*") if p.is_file())


def browse_jobs(
    client: GitLabClient,
    project_id: int,
    ref: str,
    job_filter: str = "*",
    job_name: str = "",
    pipelines: int = BROWSE_PIPELINES,
    cancel: CancelToken | None = None,
) -> list[JobRow]:
    """Jobs with an artifact archive in the newest pipelines of `ref`, newest pipeline first."""
    rows: list[JobRow] = []
    for pipeline in client.list_pipelines(project_id, ref, limit=pipelines):
        _check(cancel)
        for job in client.list_jobs(project_id, pipeline.id, job_filter):
            if job_name and job.name != job_name:
                continue
            when = short_timestamp(job.finished_at or pipeline.created_at)
            rows.append(JobRow(pipeline.id, job.id, job.name, pipeline.ref or ref, job.status, when))
    return rows


def find_latest_job(
    client: GitLabClient,
    project_id: int,
    ref: str,
    job_filter: str = "*",
    job_name: str = "",
    pipelines: int = LATEST_PIPELINES,
    cancel: CancelToken | None = None,
) -> JobRow:
    """The newest *successful* job of `ref` matching the filter and (if given) the job name.

    Several matching jobs in the newest pipeline that has any is an error, never a guess:
    flashing the wrong binary is the worst thing this tool can do.
    """
    for pipeline in client.list_pipelines(project_id, ref, limit=pipelines):
        _check(cancel)
        jobs = [
            job
            for job in client.list_jobs(project_id, pipeline.id, job_filter)
            if job.status == "success" and (not job_name or job.name == job_name)
        ]
        if len(jobs) > 1:
            names = ", ".join(sorted(job.name for job in jobs))
            raise GitLabError(
                f"Pipeline #{pipeline.id} has {len(jobs)} successful jobs with artifacts: {names}",
                hint="Enter the job name to download, or use Browse jobs… and pick a row.",
            )
        if jobs:
            job = jobs[0]
            when = short_timestamp(job.finished_at or pipeline.created_at)
            return JobRow(pipeline.id, job.id, job.name, pipeline.ref or ref, job.status, when)
    wanted = f"'{job_name}' " if job_name else ""
    raise GitLabError(
        f"No successful job {wanted}with artifacts on '{ref}' in the newest {pipelines} pipelines",
        hint="Check the branch/tag and the job name, or use Browse jobs… to pick a job.",
    )


def fetch_ci_artifact(
    client: GitLabClient,
    project: str,
    project_id: int,
    job: JobRow,
    cache: ArtifactCache,
    progress: DownloadProgress | None = None,
    cancel: CancelToken | None = None,
) -> tuple[Path, FirmwareSource]:
    """Extracted artifact of `job` (from the cache when it is there) and its source description."""
    path = cache.get(project_id, job.job_id)
    from_cache = path is not None
    if path is None:
        with tempfile.TemporaryDirectory(prefix="wflash_dl_") as tmp:
            zip_path = client.download_artifacts(project_id, job.job_id, Path(tmp), progress, cancel)
            _check(cancel)
            path = cache.store_zip(project_id, job.job_id, zip_path)
    else:
        log.info("Using cached artifact of job #%s: %s", job.job_id, path)
    source = FirmwareSource(
        kind="ci",
        project=project,
        title=f"CI artifact · job #{job.job_id} {job.job_name}",
        detail=f"{project} · {job.ref} · pipeline #{job.pipeline_id}",
        cache_note=files_note(from_cache, count_files(path)),
    )
    return path, source


def latest_package(client: GitLabClient, project_id: int, package_name: str) -> PackageVersion:
    return client.list_package_versions(project_id, package_name, limit=1)[0]


def fetch_package(
    client: GitLabClient,
    project: str,
    project_id: int,
    package: PackageVersion,
    cache: ArtifactCache,
    progress: DownloadProgress | None = None,
    cancel: CancelToken | None = None,
) -> tuple[Path, FirmwareSource]:
    """First file of a package version: a zip is extracted, anything else is cached as-is."""
    path = cache.get(project_id, package.id)
    from_cache = path is not None
    if path is None:
        with tempfile.TemporaryDirectory(prefix="wflash_pkg_") as tmp:
            file_path = client.download_package(project_id, package, Path(tmp), progress, cancel)
            _check(cancel)
            if zipfile.is_zipfile(file_path):
                path = cache.store_zip(project_id, package.id, file_path)
            else:
                path = cache.store_file(project_id, package.id, file_path)
    else:
        log.info("Using cached package %s %s: %s", package.name, package.version, path)
    source = FirmwareSource(
        kind="package",
        project=project,
        title=f"Package · {package.name} {package.version}",
        detail=f"{project} · {short_timestamp(package.created_at)}",
        cache_note=files_note(from_cache, count_files(path)),
    )
    return path, source
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_firmware_fetch.py -v` → Expected: `11 passed`.
Run: `~/.venvs/wflash/bin/pytest -q` → Expected: `269 passed`; `~/.venvs/wflash/bin/pytest -k "not gui" -q` must import no PySide6 module from `wflash/core` (the new module imports only core).

- [ ] **Step 5: Walkthrough entry**

```markdown
## Phase 1.32: firmware_fetch — logic tìm/tải firmware nằm ở core

Popup GitLab chỉ nên lo giao diện; phần "job mới nhất thành công khớp ref + job name", "liệt kê job của các pipeline gần nhất", "tải qua cache rồi mô tả nguồn" là logic thuần, đặt ở core để test không cần Qt hay mạng. Nhiều job khớp mà không có tên job là lỗi có hint, không bao giờ tự chọn (CLAUDE.md: chọn sai file là điều tệ nhất tool có thể làm). Package zip được giải nén, file khác được giữ nguyên.

### Thay đổi

- **`wflash/core/firmware_fetch.py`** (mới): `JobRow`, `browse_jobs`, `find_latest_job`, `fetch_ci_artifact`, `latest_package`, `fetch_package`, `count_files`.
- **`tests/test_firmware_fetch.py`** (mới): 11 test với client giả.

### Đã kiểm tra

- RED / GREEN, `pytest -q`, `pytest -k "not gui" -q`: <kết quả thật>
```

- [ ] **Step 6: Commit**

```bash
git add wflash/core/firmware_fetch.py tests/test_firmware_fetch.py docs/walkthrough.md
git commit -m "feat(core): find and fetch CI artifacts and packages through the cache" -m "$TRAILER"
```

---

### Task 7: `WorkerRegistry` — wait for / abandon one key prefix

**Files:**
- Modify: `wflash/gui/workers.py`
- Test: `tests/test_gui_workers.py` (two `thread` tests appended)

**Interfaces:**
- Consumes (current): `WorkerRegistry.wait_idle(timeout_s: float) -> bool` (pumps events, bounded), `abandon_running() -> list[str]` (parks running and retired workers in `workers._ABANDONED`), `has_running(prefix="")`, `is_running(key)`, `running_keys()`.
- Produces: `wait_idle(timeout_s: float, prefix: str = "") -> bool` and `abandon_running(prefix: str = "") -> list[str]` — with a prefix only keys starting with it are waited for / parked; without one the behaviour is exactly the current one. The GitLab dialog uses `prefix="gitlab-"` so closing it never waits for, or abandons, the window's instance or flash workers.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_gui_workers.py` (they use the module's existing `env` fixture and `start()` helper):

```python
def test_thread_wait_idle_with_prefix_ignores_other_workers(env):
    registry, rx = env
    gate = threading.Event()
    other = start(registry, rx, lambda ctx: gate.wait(5), "winidea-instances")
    mine = start(registry, rx, lambda ctx: "done", "gitlab-refs")
    assert registry.wait_idle(5.0, prefix="gitlab-") is True
    assert mine in rx.finished
    assert registry.is_running(other)
    assert registry.wait_idle(0.2) is False  # without a prefix the stuck one still counts
    gate.set()
    assert registry.wait_idle(5.0) is True


def test_thread_abandon_with_prefix_parks_only_matching_workers(env):
    registry, rx = env
    gate = threading.Event()
    other = start(registry, rx, lambda ctx: gate.wait(5), "flash")
    mine = start(registry, rx, lambda ctx: gate.wait(5), "gitlab-download")
    before = len(workers._ABANDONED)
    assert registry.abandon_running(prefix="gitlab-") == [mine]
    assert [w.key for w in workers._ABANDONED[before:]] == [mine]
    assert registry.running_keys() == [other]
    gate.set()
    assert registry.wait_idle(5.0) is True
    assert workers._ABANDONED[-1].done.wait(5)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_gui_workers.py -v`
Expected: `2 failed, 13 passed` — `TypeError: WorkerRegistry.wait_idle() got an unexpected keyword argument 'prefix'` and the same for `abandon_running()`.

- [ ] **Step 3: Implement** — in `wflash/gui/workers.py` replace the two methods `wait_idle` and `abandon_running` of `WorkerRegistry` with:

```python
    def wait_idle(self, timeout_s: float, prefix: str = "") -> bool:
        """Pump events until every finished signal was handled, or the deadline passes.

        With `prefix`, only workers whose key starts with it are waited for (a dialog waits
        for its own "gitlab-" workers without depending on unrelated ones).

        Rule 3: never block the GUI loop on the pool — the workers' queued signals can only
        be delivered while this loop runs.
        """
        deadline = time.monotonic() + timeout_s
        while self.has_running(prefix):
            if time.monotonic() >= deadline:
                return False
            QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
            pending = next((w for k, w in self._running.items() if k.startswith(prefix)), None)
            if pending is not None:
                pending.done.wait(0.01)
        return True

    def abandon_running(self, prefix: str = "") -> list[str]:
        """Park still-running workers (keys starting with `prefix`) for the rest of the process."""
        keys = [key for key in self._running if key.startswith(prefix)]
        for key in keys:
            worker = self._running.pop(key)
            log.warning("Worker %s did not stop in time; abandoning it", key)
            _ABANDONED.append(worker)
        _ABANDONED.extend(w for w in self._retired if w.key.startswith(prefix))
        self._retired = [w for w in self._retired if not w.key.startswith(prefix)]
        return keys
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_gui_workers.py -v` → Expected: `15 passed`.
Run: `~/.venvs/wflash/bin/pytest -k thread -v` → Expected: `31 passed`.
Run: `~/.venvs/wflash/bin/pytest -q` → Expected: `271 passed`.

- [ ] **Step 5: Walkthrough entry**

```markdown
## Phase 1.33: WorkerRegistry chờ/bỏ theo tiền tố key

Popup GitLab dùng chung `WorkerRegistry` của cửa sổ chính. Khi đóng popup, nó phải chờ (có giới hạn, vẫn bơm event — quy tắc 3) đúng các worker `gitlab-` của nó, không chờ worker liệt kê instance winIDEA, và khi hết giờ chỉ được "bỏ" (park trong `_ABANDONED`, quy tắc 1) worker của nó. Không truyền tiền tố thì hành vi y như cũ, nên `closeEvent` của cửa sổ chính không đổi.

### Thay đổi

- **`wflash/gui/workers.py`**: tham số `prefix` cho `wait_idle` và `abandon_running`.
- **`tests/test_gui_workers.py`**: thêm `test_thread_wait_idle_with_prefix_ignores_other_workers`, `test_thread_abandon_with_prefix_parks_only_matching_workers`.

### Đã kiểm tra

- RED / GREEN, `pytest -k thread -v`, `pytest -q`: <kết quả thật>
```

- [ ] **Step 6: Commit**

```bash
git add wflash/gui/workers.py tests/test_gui_workers.py docs/walkthrough.md
git commit -m "feat(gui): let WorkerRegistry wait for and abandon one key prefix" -m "$TRAILER"
```

---

### Task 8: Teal theme — tokens, stylesheets, loader, themed log colours, theme at start-up

**Files:**
- Create: `wflash/gui/theme.py`, `wflash/gui/style.py`, `wflash/resources/style.qss`, `wflash/resources/style_dark.qss`
- Modify: `wflash/gui/log_panel.py`, `wflash/main.py`, `pyproject.toml`
- Test: `tests/test_gui_theme.py` (new), `tests/test_gui_root_main.py` (one test appended)

**Interfaces:**
- Consumes (current): `LogPanelMixin._write_log_line(level, text)` (colours from the module dict `LEVEL_COLORS`), `_refilter_log()`; `wflash.main.main(argv)` (creates the `QApplication`, then `MainWindow`); `AppSettings.dark_mode` (Task 3); `tests.gui_stubs.HostWindow`.
- Produces:
  - `wflash.gui.theme`: `THEMES: dict[str, dict[str, str]]` (`"light"`, `"dark"`, identical keys: the spec §6 table plus `disabled` and `cancel_hover`), `current_theme() -> dict[str, str]`, `current_theme_name() -> str`, `set_theme_name(name)` (`ValueError` for an unknown name).
  - `wflash.gui.style`: `RESOURCES_DIR` (`wflash/resources`, `__file__`-relative), `stylesheet_path(dark) -> Path`, `load_stylesheet(dark: bool) -> str` (never raises; missing file → `""` + WARNING "… using the default Qt style"), `apply_theme(app, dark)` (sets the token table **and** `app.setStyleSheet`), `repolish(widget)` (after a dynamic property changed).
  - `wflash.gui.log_panel`: `LEVEL_TOKENS`, `level_color(level) -> str | None` (theme-dependent; `None` for INFO), `LogPanelMixin.refresh_log_theme()`. `LEVEL_COLORS` is removed (nothing else imports it).
  - `main()` applies the saved theme before the window exists and logs `Theme: dark|light`.
  - QSS hooks used later: `#pushButton_flash[state="flashing"]`, `#progressBar_flash[state="done"|"failed"|"cancelled"]::chunk`, `#label_downloadStatus[state="error"]`, `#pushButton_loadFromGitlab`, `#pushButton_downloadSelected`, `#pushButton_fetchLatest`, `#frame_settingPanel`, `#label_settingHeader`, `#frame_sourceCard`, `#label_rollbackWarning`, `#groupBox_connection`, `#label_error`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_gui_theme.py`:

```python
"""Teal theme: tokens, stylesheet files, loader, and theme-driven log colours."""
import logging

import pytest
from PySide6.QtWidgets import QApplication

from tests.gui_stubs import HostWindow
from wflash.gui import style
from wflash.gui.log_panel import LogPanelMixin, level_color
from wflash.gui.style import apply_theme, load_stylesheet, stylesheet_path
from wflash.gui.theme import THEMES, current_theme, current_theme_name, set_theme_name

pytestmark = pytest.mark.gui


@pytest.fixture
def light_after(qapp):
    yield qapp
    apply_theme(qapp, False)
    qapp.setStyleSheet("")


def contrast(fg: str, bg: str) -> float:
    def luminance(color: str) -> float:
        channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    hi, lo = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_gui_both_themes_define_the_same_tokens():
    assert set(THEMES) == {"light", "dark"}
    assert set(THEMES["light"]) == set(THEMES["dark"])


@pytest.mark.parametrize("name", ["light", "dark"])
def test_gui_white_text_on_primary_and_cancel_is_readable(name):
    assert contrast("#ffffff", THEMES[name]["primary"]) >= 4.5
    assert contrast("#ffffff", THEMES[name]["cancel"]) >= 4.5


@pytest.mark.parametrize("dark, name", [(False, "light"), (True, "dark")])
def test_gui_stylesheet_files_use_their_own_tokens(dark, name):
    text = load_stylesheet(dark)
    assert text, f"{stylesheet_path(dark)} is missing or empty"
    tokens = THEMES[name]
    for token in ("ground", "surface", "primary", "cancel", "accent", "head", "soft", "banner_bg"):
        assert tokens[token] in text, f"{token} {tokens[token]} not used in {name} stylesheet"
    other = THEMES["dark" if name == "light" else "light"]
    assert other["primary"] not in text and other["ground"] not in text
    for selector in (
        "#pushButton_flash",
        '#pushButton_flash[state="flashing"]',
        "#pushButton_loadFromGitlab",
        '#progressBar_flash[state="done"]',
        "#label_rollbackWarning",
        "#frame_sourceCard",
        "#label_settingHeader",
    ):
        assert selector in text


def test_gui_missing_stylesheet_returns_empty_and_warns(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(style, "RESOURCES_DIR", tmp_path)
    with caplog.at_level(logging.WARNING, logger="wflash.ui.style"):
        assert load_stylesheet(False) == ""
    assert "default Qt style" in caplog.text


def test_gui_apply_theme_switches_tokens_and_app_stylesheet(light_after):
    app = light_after
    apply_theme(app, True)
    assert current_theme_name() == "dark"
    assert current_theme()["primary"] == THEMES["dark"]["primary"]
    assert THEMES["dark"]["primary"] in app.styleSheet()
    apply_theme(app, False)
    assert current_theme_name() == "light"
    assert THEMES["light"]["primary"] in app.styleSheet()


def test_gui_unknown_theme_name_is_refused():
    with pytest.raises(ValueError):
        set_theme_name("purple")


class LogHost(LogPanelMixin, HostWindow):
    def __init__(self, tmp):
        super().__init__(tmp)
        self._init_log_panel()

    def flash_active(self):
        return False


def first_line_color(w) -> str:
    block = w.ui.plainTextEdit_log.document().firstBlock()
    return block.begin().fragment().charFormat().foreground().color().name()


def test_gui_log_colours_follow_the_theme(qtbot, tmp_path, light_after):
    w = LogHost(tmp_path)
    qtbot.addWidget(w)
    assert level_color(logging.INFO) is None
    logging.getLogger("wflash.test_theme").warning("careful")
    qtbot.waitUntil(lambda: "careful" in w.log_visible_text(), timeout=1000)
    assert first_line_color(w) == THEMES["light"]["log_warn"]
    apply_theme(QApplication.instance(), True)
    w.refresh_log_theme()
    assert first_line_color(w) == THEMES["dark"]["log_warn"]
    assert level_color(logging.ERROR) == THEMES["dark"]["log_error"]
```

Append to `tests/test_gui_root_main.py` (it already imports `os`, `subprocess`, `sys` and defines `REPO`):

```python
def test_gui_root_main_smoke_in_dark_mode(tmp_path):
    """The saved dark_mode setting is applied at start-up without breaking the launch."""
    import json

    home = tmp_path / "home"
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "HOME": str(home),
        "USERPROFILE": str(home),
        "APPDATA": str(home / "AppData" / "Roaming"),
        "LOCALAPPDATA": str(home / "AppData" / "Local"),
    }
    # The locations config_dir() and default_log_dir() compute, under the fake home.
    if sys.platform == "win32":
        config, logs = home / "AppData" / "Roaming" / "WFlash", home / "AppData" / "Local" / "WFlash" / "logs"
    elif sys.platform == "darwin":
        config, logs = home / "Library" / "Application Support" / "WFlash", home / "Library" / "Logs" / "WFlash"
    else:
        config, logs = home / ".config" / "wflash", home / ".local" / "state" / "wflash" / "logs"
    config.mkdir(parents=True)
    (config / "settings.json").write_text(json.dumps({"dark_mode": True}), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(REPO / "main.py"), "--adapter", "fake", "--smoke"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    log_text = "".join(p.read_text(encoding="utf-8") for p in logs.glob("wflash_*.log"))
    assert "Theme: dark" in log_text
```

- [ ] **Step 2: Run them to verify they fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_gui_theme.py tests/test_gui_root_main.py -v`
Expected: collection error `ImportError: cannot import name 'style' from 'wflash.gui'`. (Run alone, `test_gui_root_main_smoke_in_dark_mode` fails on `assert "Theme: dark" in log_text`.)

- [ ] **Step 3: Implement**

Create `wflash/gui/theme.py`:

```python
"""Teal theme tokens shared by the stylesheets and by code that colours dynamic content.

The .qss files (wflash/resources) style every static widget by objectName and dynamic
property. Colours that code applies at runtime — log lines, red mapping rows, the "#"
column — come from `current_theme()`, so both use the same values. `style.apply_theme()`
switches the current theme together with the application stylesheet.
"""
from __future__ import annotations

THEMES: dict[str, dict[str, str]] = {
    "light": {
        "ground": "#f2f6f6",
        "surface": "#ffffff",
        "panel": "#e3eceb",
        "border": "#d7dde5",
        "line": "#e9edf2",
        "text": "#1a1a1a",
        "muted": "#5a6472",
        "disabled": "#9aa4b2",
        "primary": "#0f6b63",
        "primary_hover": "#1f9488",
        "accent": "#1f9488",
        "head": "#0f6b63",
        "soft": "#e7f3f1",
        "cancel": "#b23b3b",
        "cancel_hover": "#d1574f",
        "done": "#3f8f5f",
        "log_debug": "#8a8a8a",
        "log_warn": "#c77700",
        "log_error": "#d32f2f",
        "missing_bg": "#ffcdd2",
        "missing_border": "#d1574f",
        "banner_bg": "#fdecea",
        "banner_border": "#e6a5a0",
        "banner_text": "#8f1d17",
    },
    "dark": {
        "ground": "#1b2023",
        "surface": "#232a2d",
        "panel": "#262e31",
        "border": "#3a464a",
        "line": "#2e383b",
        "text": "#e4eceb",
        "muted": "#9aaaa8",
        "disabled": "#6b7a7c",
        "primary": "#138277",
        "primary_hover": "#1a988b",
        "accent": "#2bb3a3",
        "head": "#6fd3c6",
        "soft": "#22383a",
        "cancel": "#c24b45",
        "cancel_hover": "#d65c55",
        "done": "#3a8a5c",
        "log_debug": "#7d8b8a",
        "log_warn": "#e0a03b",
        "log_error": "#ef7b74",
        "missing_bg": "#4a2a2c",
        "missing_border": "#c96058",
        "banner_bg": "#3a2324",
        "banner_border": "#7a3a37",
        "banner_text": "#f3b1ac",
    },
}

_current = "light"


def current_theme_name() -> str:
    return _current


def current_theme() -> dict[str, str]:
    return THEMES[_current]


def set_theme_name(name: str) -> None:
    global _current
    if name not in THEMES:
        raise ValueError(f"Unknown theme {name!r}")
    _current = name
```

Create `wflash/gui/style.py`:

```python
"""Load and apply the Teal stylesheets (wflash/resources/style.qss, style_dark.qss).

`load_stylesheet()` never raises: a missing or unreadable file logs a WARNING and returns
"", so the app runs with Qt's default look instead of crashing (spec §8). The resources
folder sits inside the package, so the same path works from source and from the
PyInstaller build (wflash.spec copies wflash/resources to the same relative place).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget

from wflash.core.logging_setup import get_logger
from wflash.gui.theme import set_theme_name

log = get_logger("ui.style")

RESOURCES_DIR = Path(__file__).resolve().parents[1] / "resources"


def stylesheet_path(dark: bool) -> Path:
    return RESOURCES_DIR / ("style_dark.qss" if dark else "style.qss")


def load_stylesheet(dark: bool) -> str:
    path = stylesheet_path(dark)
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        log.warning("Theme file %s cannot be read (%s); using the default Qt style", path, exc)
        return ""


def apply_theme(app: QApplication, dark: bool) -> None:
    """Switch the token table and the application stylesheet together."""
    set_theme_name("dark" if dark else "light")
    app.setStyleSheet(load_stylesheet(dark))


def repolish(widget: QWidget) -> None:
    """Re-evaluate the stylesheet after a dynamic property changed (e.g. state="flashing")."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
```

Create `wflash/resources/style.qss` (Teal Light):

```css
/* WFlash "Teal Light" theme. Colours are the tokens of wflash/gui/theme.py THEMES["light"];
   keep both in sync. Widgets are addressed by objectName and dynamic property, never by
   per-widget stylesheets in code. */

QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    color: #1a1a1a;
}

QMainWindow, QDialog {
    background-color: #f2f6f6;
}

QPushButton {
    background-color: #ffffff;
    border: 1px solid #d7dde5;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover {
    background-color: #e7f3f1;
    border-color: #1f9488;
}
QPushButton:pressed {
    background-color: #e3eceb;
}
QPushButton:disabled {
    color: #9aa4b2;
    background-color: #ffffff;
    border-color: #e9edf2;
}

/* Primary actions: the big Flash button and the main button of each dialog tab. */
QPushButton#pushButton_flash,
QPushButton#pushButton_downloadSelected,
QPushButton#pushButton_fetchLatest {
    background-color: #0f6b63;
    color: #ffffff;
    font-weight: 600;
    border: none;
}
QPushButton#pushButton_flash {
    font-size: 15px;
    border-radius: 8px;
    padding: 0px;
}
QPushButton#pushButton_flash:hover,
QPushButton#pushButton_downloadSelected:hover,
QPushButton#pushButton_fetchLatest:hover {
    background-color: #1f9488;
}
QPushButton#pushButton_flash:disabled,
QPushButton#pushButton_downloadSelected:disabled,
QPushButton#pushButton_fetchLatest:disabled {
    background-color: #e3eceb;
    color: #9aa4b2;
}
/* While a flash runs the same button is "Cancel" (FlashMixin sets state="flashing"). */
QPushButton#pushButton_flash[state="flashing"] {
    background-color: #b23b3b;
    color: #ffffff;
}
QPushButton#pushButton_flash[state="flashing"]:hover {
    background-color: #d1574f;
}

QPushButton#pushButton_loadFromGitlab {
    border: 1px solid #1f9488;
    color: #0f6b63;
    font-weight: 600;
}
QPushButton#pushButton_loadFromGitlab:disabled {
    border-color: #e9edf2;
    color: #9aa4b2;
}

QTabWidget::pane {
    border: 1px solid #d7dde5;
    border-radius: 6px;
    top: -1px;
    background: #ffffff;
}
QTabBar::tab {
    background: #e3eceb;
    padding: 8px 20px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    color: #5a6472;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #0f6b63;
    font-weight: 600;
    border: 1px solid #d7dde5;
    border-bottom: none;
}

QProgressBar {
    border: none;
    border-radius: 6px;
    background-color: #e9edf2;
    text-align: center;
}
QProgressBar::chunk {
    border-radius: 6px;
    background-color: #1f9488;
}
QProgressBar#progressBar_flash[state="done"]::chunk {
    background-color: #3f8f5f;
}
QProgressBar#progressBar_flash[state="failed"]::chunk,
QProgressBar#progressBar_flash[state="cancelled"]::chunk {
    background-color: #b23b3b;
}

QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f2f6f6;
    gridline-color: #e9edf2;
    border: 1px solid #d7dde5;
    border-radius: 6px;
    selection-background-color: #e7f3f1;
    selection-color: #1a1a1a;
}
QTableWidget::item {
    padding: 3px;
}
QHeaderView {
    background-color: #e7f3f1;
}
QTableCornerButton::section {
    background-color: #e7f3f1;
    border: none;
}
QHeaderView::section {
    background-color: #e7f3f1;
    color: #0f6b63;
    padding: 5px;
    border: none;
    border-bottom: 2px solid #1f9488;
    font-weight: 600;
}

QLineEdit, QComboBox, QSpinBox {
    border: 1px solid #d7dde5;
    border-radius: 5px;
    padding: 4px 8px;
    background: #ffffff;
    color: #1a1a1a;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #1f9488;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    color: #9aa4b2;
}
/* The popup list of every combo box: it does not inherit the box colours. */
QComboBox QAbstractItemView {
    background: #ffffff;
    color: #1a1a1a;
    border: 1px solid #d7dde5;
    selection-background-color: #0f6b63;
    selection-color: #ffffff;
}

QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #d7dde5;
    border-radius: 6px;
}

QGroupBox {
    border: 1px solid #d7dde5;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #0f6b63;
    font-weight: 600;
}
QGroupBox#groupBox_connection {
    background-color: #e3eceb;
}

QCheckBox {
    spacing: 6px;
}

/* Main window: Setting panel, source card, hints, rollback banner. */
QFrame#frame_settingPanel {
    background-color: #ffffff;
    border: 1px solid #d7dde5;
    border-radius: 6px;
}
QLabel#label_settingHeader {
    background-color: #e7f3f1;
    color: #0f6b63;
    font-weight: 600;
    padding: 6px 8px;
    border: none;
    border-bottom: 2px solid #1f9488;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QFrame#frame_sourceCard {
    background-color: #e7f3f1;
    border: 1px solid #d7dde5;
    border-left: 3px solid #1f9488;
    border-radius: 6px;
}
QLabel#label_sourceTitle {
    font-weight: 600;
    color: #0f6b63;
}
QLabel#label_sourceDetail, QLabel#label_sourceCache,
QLabel#label_mappingHint, QLabel#label_connectionHint, QLabel#label_ciProjectSource,
QLabel#label_flashStats {
    color: #5a6472;
}
QLabel#label_step {
    font-weight: 600;
}
QLabel#label_rollbackWarning {
    background-color: #fdecea;
    border: 1px solid #e6a5a0;
    border-radius: 6px;
    color: #8f1d17;
    font-weight: 600;
    padding: 6px 8px;
}
QLabel#label_error,
QLabel#label_downloadStatus[state="error"] {
    color: #d32f2f;
}

QStatusBar {
    background: #ffffff;
    border-top: 1px solid #d7dde5;
    color: #5a6472;
}
QStatusBar QLabel {
    color: #5a6472;
    padding: 0 8px;
}
```

Create `wflash/resources/style_dark.qss` (Teal Dark — the same rules with the dark tokens):

```css
/* WFlash "Teal Dark" theme. Colours are the tokens of wflash/gui/theme.py THEMES["dark"];
   keep both in sync. Widgets are addressed by objectName and dynamic property, never by
   per-widget stylesheets in code. */

QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    color: #e4eceb;
}

QMainWindow, QDialog {
    background-color: #1b2023;
}

QPushButton {
    background-color: #232a2d;
    border: 1px solid #3a464a;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover {
    background-color: #22383a;
    border-color: #2bb3a3;
}
QPushButton:pressed {
    background-color: #262e31;
}
QPushButton:disabled {
    color: #6b7a7c;
    background-color: #232a2d;
    border-color: #2e383b;
}

/* Primary actions: the big Flash button and the main button of each dialog tab. */
QPushButton#pushButton_flash,
QPushButton#pushButton_downloadSelected,
QPushButton#pushButton_fetchLatest {
    background-color: #138277;
    color: #ffffff;
    font-weight: 600;
    border: none;
}
QPushButton#pushButton_flash {
    font-size: 15px;
    border-radius: 8px;
    padding: 0px;
}
QPushButton#pushButton_flash:hover,
QPushButton#pushButton_downloadSelected:hover,
QPushButton#pushButton_fetchLatest:hover {
    background-color: #1a988b;
}
QPushButton#pushButton_flash:disabled,
QPushButton#pushButton_downloadSelected:disabled,
QPushButton#pushButton_fetchLatest:disabled {
    background-color: #262e31;
    color: #6b7a7c;
}
/* While a flash runs the same button is "Cancel" (FlashMixin sets state="flashing"). */
QPushButton#pushButton_flash[state="flashing"] {
    background-color: #c24b45;
    color: #ffffff;
}
QPushButton#pushButton_flash[state="flashing"]:hover {
    background-color: #d65c55;
}

QPushButton#pushButton_loadFromGitlab {
    border: 1px solid #2bb3a3;
    color: #6fd3c6;
    font-weight: 600;
}
QPushButton#pushButton_loadFromGitlab:disabled {
    border-color: #2e383b;
    color: #6b7a7c;
}

QTabWidget::pane {
    border: 1px solid #3a464a;
    border-radius: 6px;
    top: -1px;
    background: #232a2d;
}
QTabBar::tab {
    background: #262e31;
    padding: 8px 20px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    color: #9aaaa8;
}
QTabBar::tab:selected {
    background: #232a2d;
    color: #6fd3c6;
    font-weight: 600;
    border: 1px solid #3a464a;
    border-bottom: none;
}

QProgressBar {
    border: none;
    border-radius: 6px;
    background-color: #2e383b;
    text-align: center;
}
QProgressBar::chunk {
    border-radius: 6px;
    background-color: #2bb3a3;
}
QProgressBar#progressBar_flash[state="done"]::chunk {
    background-color: #3a8a5c;
}
QProgressBar#progressBar_flash[state="failed"]::chunk,
QProgressBar#progressBar_flash[state="cancelled"]::chunk {
    background-color: #c24b45;
}

QTableWidget {
    background-color: #232a2d;
    alternate-background-color: #1b2023;
    gridline-color: #2e383b;
    border: 1px solid #3a464a;
    border-radius: 6px;
    selection-background-color: #22383a;
    selection-color: #e4eceb;
}
QTableWidget::item {
    padding: 3px;
}
QHeaderView {
    background-color: #22383a;
}
QTableCornerButton::section {
    background-color: #22383a;
    border: none;
}
QHeaderView::section {
    background-color: #22383a;
    color: #6fd3c6;
    padding: 5px;
    border: none;
    border-bottom: 2px solid #2bb3a3;
    font-weight: 600;
}

QLineEdit, QComboBox, QSpinBox {
    border: 1px solid #3a464a;
    border-radius: 5px;
    padding: 4px 8px;
    background: #232a2d;
    color: #e4eceb;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #2bb3a3;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    color: #6b7a7c;
}
/* The popup list of every combo box: it does not inherit the box colours. */
QComboBox QAbstractItemView {
    background: #232a2d;
    color: #e4eceb;
    border: 1px solid #3a464a;
    selection-background-color: #138277;
    selection-color: #ffffff;
}

QTextEdit, QPlainTextEdit {
    background-color: #232a2d;
    color: #e4eceb;
    border: 1px solid #3a464a;
    border-radius: 6px;
}

QGroupBox {
    border: 1px solid #3a464a;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #6fd3c6;
    font-weight: 600;
}
QGroupBox#groupBox_connection {
    background-color: #262e31;
}

QCheckBox {
    spacing: 6px;
}

/* Main window: Setting panel, source card, hints, rollback banner. */
QFrame#frame_settingPanel {
    background-color: #232a2d;
    border: 1px solid #3a464a;
    border-radius: 6px;
}
QLabel#label_settingHeader {
    background-color: #22383a;
    color: #6fd3c6;
    font-weight: 600;
    padding: 6px 8px;
    border: none;
    border-bottom: 2px solid #2bb3a3;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QFrame#frame_sourceCard {
    background-color: #22383a;
    border: 1px solid #3a464a;
    border-left: 3px solid #2bb3a3;
    border-radius: 6px;
}
QLabel#label_sourceTitle {
    font-weight: 600;
    color: #6fd3c6;
}
QLabel#label_sourceDetail, QLabel#label_sourceCache,
QLabel#label_mappingHint, QLabel#label_connectionHint, QLabel#label_ciProjectSource,
QLabel#label_flashStats {
    color: #9aaaa8;
}
QLabel#label_step {
    font-weight: 600;
}
QLabel#label_rollbackWarning {
    background-color: #3a2324;
    border: 1px solid #7a3a37;
    border-radius: 6px;
    color: #f3b1ac;
    font-weight: 600;
    padding: 6px 8px;
}
QLabel#label_error,
QLabel#label_downloadStatus[state="error"] {
    color: #ef7b74;
}

QStatusBar {
    background: #232a2d;
    border-top: 1px solid #3a464a;
    color: #9aaaa8;
}
QStatusBar QLabel {
    color: #9aaaa8;
    padding: 0 8px;
}
```

In `wflash/gui/log_panel.py`:

1. Add the import below the `logging_setup` import:

```python
from wflash.gui.theme import current_theme
```

2. Replace the `LEVEL_COLORS = {…}` dict with:

```python
# Theme token per level; INFO uses the widget's normal text colour.
LEVEL_TOKENS = {
    logging.DEBUG: "log_debug",
    logging.WARNING: "log_warn",
    logging.ERROR: "log_error",
    logging.CRITICAL: "log_error",
}


def level_color(level: int) -> str | None:
    token = LEVEL_TOKENS.get(level)
    return current_theme()[token] if token else None
```

3. In `_write_log_line`, replace `color = LEVEL_COLORS.get(level)` with `color = level_color(level)`.

4. Add this method right above `_refilter_log`:

```python
    def refresh_log_theme(self) -> None:
        """Repaint every visible line with the current theme's level colours."""
        self._refilter_log()
```

In `wflash/main.py`, right after `app.setApplicationName("WFlash")`, insert:

```python
    from wflash.gui.style import apply_theme

    # Before the window exists, so the first paint already uses the saved theme.
    apply_theme(app, settings.dark_mode)
    log.info("Theme: %s", "dark" if settings.dark_mode else "light")
```

(The import stays local, like the existing `MainWindow` import, so `wflash.main` can be imported for its argument parsing without loading the GUI modules.)

In `pyproject.toml`, add after the `[tool.setuptools.packages.find]` table:

```toml
[tool.setuptools.package-data]
wflash = ["resources/*.qss"]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_gui_theme.py tests/test_gui_root_main.py -v` → Expected: `12 passed`.
Run: `~/.venvs/wflash/bin/pytest -q` → Expected: `281 passed` (`tests/test_gui_log_panel.py` unchanged and green).

- [ ] **Step 5: Walkthrough entry**

```markdown
## Phase 1.34: Theme Teal sáng/tối

WFlash dùng bố cục quen thuộc của SFlash nhưng phải khác màu để không nhầm hai tool: Teal. Màu tĩnh nằm trong hai file `.qss` (chọn widget theo objectName và dynamic property như `state="flashing"`); màu do code tô lúc chạy (dòng log, dòng mapping đỏ, cột `#`) lấy từ cùng bảng token `theme.py`. Thiếu file theme thì app chạy với style mặc định của Qt và ghi WARNING, không crash. `main.py` áp theme đã lưu trước khi tạo cửa sổ để lần vẽ đầu đã đúng màu. Chữ trắng trên màu primary và cancel đạt ≥ 4.5:1 ở cả hai chế độ (có test).

### Thay đổi

- **`wflash/gui/theme.py`**, **`wflash/gui/style.py`**, **`wflash/resources/style.qss`**, **`wflash/resources/style_dark.qss`** (mới).
- **`wflash/gui/log_panel.py`**: màu log theo theme, `refresh_log_theme()`.
- **`wflash/main.py`**: áp theme lúc khởi động, log `Theme: …`.
- **`pyproject.toml`**: package-data cho `.qss`.
- **`tests/test_gui_theme.py`** (mới, 9 test), **`tests/test_gui_root_main.py`** (smoke ở dark mode với HOME tạm).

### Đã kiểm tra

- RED / GREEN, `pytest -q`: <kết quả thật>
```

- [ ] **Step 6: Commit**

```bash
git add wflash/gui/theme.py wflash/gui/style.py wflash/resources/style.qss wflash/resources/style_dark.qss wflash/gui/log_panel.py wflash/main.py pyproject.toml tests/test_gui_theme.py tests/test_gui_root_main.py docs/walkthrough.md
git commit -m "feat(gui): Teal light/dark theme with shared colour tokens" -m "$TRAILER"
```

---

### Task 9: Preferences dialog (cache, profiles, verbose, dark mode)

**Files:**
- Create: `wflash/gui/preferences_dialog.ui`, `wflash/gui/ui_preferences_dialog.py` (generated), `wflash/gui/preferences_dialog.py`
- Modify: `tests/test_gui_ui_files.py`
- Test: `tests/test_gui_preferences_dialog.py`

`SettingsDialog` stays in place (still used by the old main window) until Task 12 deletes it.

**Interfaces:**
- Consumes: `AppSettings` (Task 3 fields), `PACKAGES_SUBDIR`, `default_cache_dir()`, `bundled_profiles_dir()`; `ArtifactCache(root).clear()` (raises `ArtifactError` with a hint).
- Produces: `PreferencesDialog(settings: AppSettings, parent: QWidget | None = None)` (`QDialog`) with `.ui` (`Ui_PreferencesDialog`), `cache_cleared: bool`, `ok_button()`, `result_settings() -> AppSettings` (a `dataclasses.replace` copy: `cache_dir`, `max_cached_jobs`, `profiles_dir`, `verbose`, `dark_mode`; every other field carried over). OK refuses a profiles folder that does not exist (`label_error`). *Clear cache* asks first, then clears `<cache>` **and** `<cache>/packages`; `cache_cleared` becomes `True` even after a partial failure (the loaded firmware may be gone).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_gui_preferences_dialog.py`:

```python
import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from wflash.core.artifact_cache import ArtifactCache
from wflash.core.errors import ArtifactError
from wflash.core.settings import AppSettings
from wflash.gui.preferences_dialog import PreferencesDialog

pytestmark = pytest.mark.gui


def make(qtbot, **kwargs):
    settings = AppSettings(last_profile="keep.yaml", gitlab_url="https://gl", package_name="fw", **kwargs)
    dialog = PreferencesDialog(settings)
    qtbot.addWidget(dialog)
    return dialog


def test_gui_fields_loaded(qtbot):
    dialog = make(qtbot, max_cached_jobs=7, verbose=True, dark_mode=True, cache_dir="/c")
    assert dialog.ui.lineEdit_cacheDir.text() == "/c"
    assert dialog.ui.spinBox_maxCachedJobs.value() == 7
    assert dialog.ui.checkBox_verbose.isChecked()
    assert dialog.ui.checkBox_darkMode.isChecked()


def test_gui_preferences_has_no_gitlab_fields(qtbot):
    dialog = make(qtbot)
    names = set(vars(dialog.ui))
    assert not {"lineEdit_gitlabUrl", "lineEdit_token", "lineEdit_caBundle"} & names


def test_gui_accept_returns_new_settings_and_keeps_the_rest(qtbot, tmp_path):
    dialog = make(qtbot)
    dialog.ui.lineEdit_cacheDir.setText(f" {tmp_path / 'cache'} ")
    dialog.ui.lineEdit_profilesDir.setText(str(tmp_path))
    dialog.ui.spinBox_maxCachedJobs.setValue(5)
    dialog.ui.checkBox_verbose.setChecked(True)
    dialog.ui.checkBox_darkMode.setChecked(True)
    dialog.ok_button().click()
    assert dialog.result() == QDialog.DialogCode.Accepted
    result = dialog.result_settings()
    assert result.cache_dir == str(tmp_path / "cache")
    assert result.profiles_dir == str(tmp_path)
    assert result.max_cached_jobs == 5
    assert result.verbose is True and result.dark_mode is True
    # Fields edited elsewhere are carried over untouched.
    assert (result.last_profile, result.gitlab_url, result.package_name) == ("keep.yaml", "https://gl", "fw")


def test_gui_missing_profiles_folder_blocks_accept(qtbot, tmp_path):
    dialog = make(qtbot)
    dialog.ui.lineEdit_profilesDir.setText(str(tmp_path / "missing"))
    dialog.ok_button().click()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "Profiles folder not found" in dialog.ui.label_error.text()


def test_gui_clear_cache_clears_artifacts_and_packages_after_confirmation(qtbot, tmp_path, monkeypatch):
    root = tmp_path / "cache"
    for base in (root, root / "packages"):
        (base / "42" / "7" / "files").mkdir(parents=True)
        (base / "42" / "7" / ".complete").write_text("x")
    dialog = make(qtbot, cache_dir=str(root))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    dialog.ui.pushButton_clearCache.click()
    assert ArtifactCache(root).entries() and not dialog.cache_cleared
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    dialog.ui.pushButton_clearCache.click()
    assert ArtifactCache(root).entries() == []
    assert ArtifactCache(root / "packages").entries() == []
    assert root.exists()  # the root itself is never deleted
    assert dialog.cache_cleared


def test_gui_clear_cache_failure_is_shown(qtbot, tmp_path, monkeypatch):
    dialog = make(qtbot, cache_dir=str(tmp_path / "cache"))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)

    def boom(self):
        raise ArtifactError("Could not clear 2 cached artifact(s)", hint="Close programs holding files.")

    monkeypatch.setattr(ArtifactCache, "clear", boom)
    dialog.ui.pushButton_clearCache.click()
    assert "Could not clear 2" in dialog.ui.label_error.text()
    assert "Close programs" in dialog.ui.label_error.text()
    assert dialog.cache_cleared  # a partial clear may still have removed the loaded files
```

Replace `tests/test_gui_ui_files.py` with (adds the new `.ui` to the name/sync checks):

```python
"""Designer files: meaningful names, generated modules in sync, every self.ui.<name> exists."""
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

pytestmark = pytest.mark.gui

GUI = Path(__file__).resolve().parents[1] / "wflash" / "gui"
UI_FILES = {
    "main_window.ui": "ui_main_window.py",
    "settings_dialog.ui": "ui_settings_dialog.py",
    "preferences_dialog.ui": "ui_preferences_dialog.py",
}
TOP_LEVEL = {"MainWindow", "SettingsDialog", "PreferencesDialog"}
# <kind>_<what>, e.g. verticalLayout_gitlabBrowser, tableWidget_mapping.
MEANINGFUL = re.compile(r"^[a-z][A-Za-z]*_[a-z][A-Za-z0-9]*$")


def ui_names(ui_file: Path) -> list[str]:
    root = ET.parse(ui_file).getroot()
    return [el.get("name") for el in root.iter() if el.tag in ("widget", "layout", "spacer")]


def without_uic_version(text: str) -> str:
    # The header names the uic version; a PySide6 upgrade alone must not fail the build.
    return "\n".join(line for line in text.splitlines() if "User Interface Compiler version" not in line)


def uic_executable() -> str | None:
    folder = Path(sys.executable).parent
    for candidate in (folder / "pyside6-uic", folder / "pyside6-uic.exe"):
        if candidate.is_file():
            return str(candidate)
    return shutil.which("pyside6-uic")


@pytest.mark.parametrize("ui_name", sorted(UI_FILES))
def test_gui_every_widget_and_layout_has_a_meaningful_name(ui_name):
    names = ui_names(GUI / ui_name)
    assert names, f"no widgets parsed from {ui_name}"
    bad = [n for n in names if n not in TOP_LEVEL and not (n and MEANINGFUL.match(n))]
    assert bad == [], f"Designer default or unclear names in {ui_name}: {bad}"
    assert len(names) == len(set(names)), "duplicate object names"


@pytest.mark.parametrize("ui_name", sorted(UI_FILES))
def test_gui_generated_module_matches_ui_file(ui_name, tmp_path):
    uic = uic_executable()
    if uic is None:
        pytest.skip("pyside6-uic not found next to the interpreter")
    out = tmp_path / UI_FILES[ui_name]
    subprocess.run([uic, str(GUI / ui_name), "-o", str(out)], check=True)
    committed = (GUI / UI_FILES[ui_name]).read_text(encoding="utf-8")
    assert without_uic_version(committed) == without_uic_version(out.read_text(encoding="utf-8")), (
        f"{UI_FILES[ui_name]} is out of date or hand-edited; run "
        f"pyside6-uic wflash/gui/{ui_name} -o wflash/gui/{UI_FILES[ui_name]}"
    )


def test_gui_every_self_ui_reference_exists_in_a_ui_file():
    known = set()
    for ui_name in UI_FILES:
        known.update(ui_names(GUI / ui_name))
    referenced = set()
    for py in GUI.glob("*.py"):
        if py.name.startswith("ui_"):
            continue
        referenced.update(re.findall(r"self\.ui\.([A-Za-z_][A-Za-z0-9_]*)", py.read_text(encoding="utf-8")))
    referenced -= {"setupUi", "retranslateUi"}  # methods of the generated Ui_ class
    assert sorted(referenced - known) == []


def test_gui_generated_modules_import(qapp):
    from PySide6.QtWidgets import QDialog, QMainWindow

    from wflash.gui.ui_main_window import Ui_MainWindow
    from wflash.gui.ui_preferences_dialog import Ui_PreferencesDialog
    from wflash.gui.ui_settings_dialog import Ui_SettingsDialog

    window = QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(window)
    assert ui.tableWidget_mapping.columnCount() == 4
    assert ui.comboBox_logLevel.currentText() == "INFO"
    assert ui.label_rollbackWarning.isHidden()
    dialog = QDialog()
    Ui_SettingsDialog().setupUi(dialog)
    preferences = QDialog()
    Ui_PreferencesDialog().setupUi(preferences)
    window.deleteLater()
    dialog.deleteLater()
    preferences.deleteLater()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_gui_preferences_dialog.py tests/test_gui_ui_files.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'wflash.gui.preferences_dialog'`.

- [ ] **Step 3: Create `wflash/gui/preferences_dialog.ui`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>PreferencesDialog</class>
 <widget class="QDialog" name="PreferencesDialog">
  <property name="geometry">
   <rect>
    <x>0</x>
    <y>0</y>
    <width>600</width>
    <height>260</height>
   </rect>
  </property>
  <property name="minimumSize">
   <size>
    <width>560</width>
    <height>0</height>
   </size>
  </property>
  <property name="windowTitle">
   <string>Preferences</string>
  </property>
  <layout class="QVBoxLayout" name="verticalLayout_preferences">
   <item>
    <layout class="QFormLayout" name="formLayout_preferences">
     <item row="0" column="0">
      <widget class="QLabel" name="label_cacheDir">
       <property name="text">
        <string>Cache folder:</string>
       </property>
       <property name="buddy">
        <cstring>lineEdit_cacheDir</cstring>
       </property>
      </widget>
     </item>
     <item row="0" column="1">
      <layout class="QHBoxLayout" name="horizontalLayout_cacheDir">
       <item>
        <widget class="QLineEdit" name="lineEdit_cacheDir"/>
       </item>
       <item>
        <widget class="QPushButton" name="pushButton_browseCacheDir">
         <property name="text">
          <string>Browse…</string>
         </property>
        </widget>
       </item>
       <item>
        <widget class="QPushButton" name="pushButton_clearCache">
         <property name="text">
          <string>Clear cache</string>
         </property>
        </widget>
       </item>
      </layout>
     </item>
     <item row="1" column="0">
      <widget class="QLabel" name="label_maxCachedJobs">
       <property name="text">
        <string>Cached downloads to keep:</string>
       </property>
       <property name="buddy">
        <cstring>spinBox_maxCachedJobs</cstring>
       </property>
      </widget>
     </item>
     <item row="1" column="1">
      <widget class="QSpinBox" name="spinBox_maxCachedJobs">
       <property name="minimum">
        <number>1</number>
       </property>
       <property name="maximum">
        <number>100</number>
       </property>
       <property name="value">
        <number>10</number>
       </property>
      </widget>
     </item>
     <item row="2" column="0">
      <widget class="QLabel" name="label_profilesDir">
       <property name="text">
        <string>Profiles folder:</string>
       </property>
       <property name="buddy">
        <cstring>lineEdit_profilesDir</cstring>
       </property>
      </widget>
     </item>
     <item row="2" column="1">
      <layout class="QHBoxLayout" name="horizontalLayout_profilesDir">
       <item>
        <widget class="QLineEdit" name="lineEdit_profilesDir"/>
       </item>
       <item>
        <widget class="QPushButton" name="pushButton_browseProfilesDir">
         <property name="text">
          <string>Browse…</string>
         </property>
        </widget>
       </item>
      </layout>
     </item>
     <item row="3" column="1">
      <widget class="QCheckBox" name="checkBox_verbose">
       <property name="text">
        <string>Verbose winIDEA call logging</string>
       </property>
      </widget>
     </item>
     <item row="4" column="1">
      <widget class="QCheckBox" name="checkBox_darkMode">
       <property name="text">
        <string>Dark mode</string>
       </property>
      </widget>
     </item>
    </layout>
   </item>
   <item>
    <widget class="QLabel" name="label_error">
     <property name="text">
      <string/>
     </property>
     <property name="wordWrap">
      <bool>true</bool>
     </property>
    </widget>
   </item>
   <item>
    <spacer name="verticalSpacer_preferences">
     <property name="orientation">
      <enum>Qt::Orientation::Vertical</enum>
     </property>
     <property name="sizeHint" stdset="0">
      <size>
       <width>20</width>
       <height>0</height>
      </size>
     </property>
    </spacer>
   </item>
   <item>
    <widget class="QDialogButtonBox" name="buttonBox_preferences">
     <property name="standardButtons">
      <set>QDialogButtonBox::StandardButton::Cancel|QDialogButtonBox::StandardButton::Ok</set>
     </property>
    </widget>
   </item>
  </layout>
 </widget>
 <resources/>
 <connections/>
</ui>
```

- [ ] **Step 4: Generate the Python module (regenerate-ui skill)**

Run: `~/.venvs/wflash/bin/pyside6-uic wflash/gui/preferences_dialog.ui -o wflash/gui/ui_preferences_dialog.py`

- [ ] **Step 5: Implement `wflash/gui/preferences_dialog.py`**

```python
"""Preferences dialog (layout in preferences_dialog.ui): cache, profiles, verbose, dark mode.

GitLab URL, token and TLS options live in the Load from GitLab popup. The dialog only
edits a copy: `result_settings()` returns a new AppSettings and the main window decides
what to apply (theme, verbose logging) and saves it.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFileDialog, QMessageBox, QWidget

from wflash.core.artifact_cache import ArtifactCache
from wflash.core.errors import ArtifactError
from wflash.core.logging_setup import get_logger
from wflash.core.settings import PACKAGES_SUBDIR, AppSettings, bundled_profiles_dir, default_cache_dir
from wflash.gui.ui_preferences_dialog import Ui_PreferencesDialog

log = get_logger("ui.preferences")


class PreferencesDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ui = Ui_PreferencesDialog()
        self.ui.setupUi(self)
        self._settings = settings
        self.cache_cleared = False

        self.ui.lineEdit_cacheDir.setText(settings.cache_dir)
        # Placeholders show the platform defaults, which only exist at runtime.
        self.ui.lineEdit_cacheDir.setPlaceholderText(str(default_cache_dir()))
        self.ui.spinBox_maxCachedJobs.setValue(settings.max_cached_jobs)
        self.ui.lineEdit_profilesDir.setText(settings.profiles_dir)
        self.ui.lineEdit_profilesDir.setPlaceholderText(str(bundled_profiles_dir()))
        self.ui.checkBox_verbose.setChecked(settings.verbose)
        self.ui.checkBox_darkMode.setChecked(settings.dark_mode)

        self.ui.buttonBox_preferences.accepted.connect(self._on_accept)
        self.ui.buttonBox_preferences.rejected.connect(self.reject)
        self.ui.pushButton_browseCacheDir.clicked.connect(self._browse_cache_dir)
        self.ui.pushButton_browseProfilesDir.clicked.connect(self._browse_profiles_dir)
        self.ui.pushButton_clearCache.clicked.connect(self._clear_cache)

    def ok_button(self):
        return self.ui.buttonBox_preferences.button(QDialogButtonBox.StandardButton.Ok)

    def _browse_cache_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select cache folder", self.ui.lineEdit_cacheDir.text())
        if path:
            self.ui.lineEdit_cacheDir.setText(path)

    def _browse_profiles_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select profiles folder", self.ui.lineEdit_profilesDir.text())
        if path:
            self.ui.lineEdit_profilesDir.setText(path)

    def _cache_root(self) -> Path:
        text = self.ui.lineEdit_cacheDir.text().strip()
        return Path(text) if text else default_cache_dir()

    def _clear_cache(self) -> None:
        root = self._cache_root()
        answer = QMessageBox.question(
            self, "Clear cache", f"Delete every cached artifact and package in\n{root}?"
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        errors: list[ArtifactError] = []
        for cache_root in (root, root / PACKAGES_SUBDIR):
            try:
                ArtifactCache(cache_root).clear()
            except ArtifactError as exc:
                log.error("Cannot clear the cache %s: %s", cache_root, exc)
                errors.append(exc)
        # Whatever was removed is gone: the loaded firmware may point into it.
        self.cache_cleared = True
        if errors:
            self.ui.label_error.setText(f"{errors[0]}\n{errors[0].hint}")
            return
        self.ui.label_error.setText("")
        log.info("Cache cleared: %s", root)

    def _on_accept(self) -> None:
        profiles = self.ui.lineEdit_profilesDir.text().strip()
        if profiles and not Path(profiles).is_dir():
            self.ui.label_error.setText(f"Profiles folder not found: {profiles}")
            return
        self.ui.label_error.clear()
        self.accept()

    def result_settings(self) -> AppSettings:
        return replace(
            self._settings,
            cache_dir=self.ui.lineEdit_cacheDir.text().strip(),
            max_cached_jobs=self.ui.spinBox_maxCachedJobs.value(),
            profiles_dir=self.ui.lineEdit_profilesDir.text().strip(),
            verbose=self.ui.checkBox_verbose.isChecked(),
            dark_mode=self.ui.checkBox_darkMode.isChecked(),
        )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_gui_preferences_dialog.py tests/test_gui_ui_files.py -v` → Expected: `14 passed`.
Run: `~/.venvs/wflash/bin/pytest -q` → Expected: `289 passed`.

- [ ] **Step 7: Walkthrough entry**

```markdown
## Phase 1.35: Hộp thoại Preferences

Settings cũ bị tách làm hai: phần kết nối GitLab (URL, token, TLS, CA) chuyển sang popup Load from GitLab, phần còn lại thành Preferences: thư mục cache + số bản giữ lại + Clear cache (giờ xóa cả cache package), thư mục profile, verbose và Dark mode. Layout trong `preferences_dialog.ui`; Python chỉ nạp giá trị, kiểm tra thư mục profile có tồn tại và trả về bản sao `AppSettings`. `SettingsDialog` cũ còn đến Task 12.

### Thay đổi

- **`wflash/gui/preferences_dialog.ui`** (mới) + **`ui_preferences_dialog.py`** (sinh bằng `pyside6-uic`).
- **`wflash/gui/preferences_dialog.py`** (mới): `PreferencesDialog`.
- **`tests/test_gui_preferences_dialog.py`** (mới, 6 test), **`tests/test_gui_ui_files.py`** (thêm file `.ui` mới).

### Đã kiểm tra

- RED / GREEN, `pytest -q`: <kết quả thật>
```

- [ ] **Step 8: Commit**

```bash
git add wflash/gui/preferences_dialog.ui wflash/gui/ui_preferences_dialog.py wflash/gui/preferences_dialog.py tests/test_gui_preferences_dialog.py tests/test_gui_ui_files.py docs/walkthrough.md
git commit -m "feat(gui): add Preferences dialog with cache, profiles, verbose and dark mode" -m "$TRAILER"
```

---

### Task 10: Designer file for the Load from GitLab popup

**Files:**
- Create: `wflash/gui/gitlab_dialog.ui`, `wflash/gui/ui_gitlab_dialog.py` (generated)
- Modify: `tests/test_gui_ui_files.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Ui_GitlabDialog` with (spec §3): `groupBox_connection` (`lineEdit_gitlabUrl`, `lineEdit_token` (password), `checkBox_verifyTls` (checked), `lineEdit_caBundle`, `pushButton_browseCa`, `label_connectionHint`), `tabWidget_source` with `tab_ciArtifact` (`lineEdit_ciProject`, `label_ciProjectSource`, `comboBox_ref` (editable), `pushButton_loadRefs`, `comboBox_jobName` (editable), `pushButton_downloadSelected`, `pushButton_browseJobs`, `tableWidget_jobs` — 6 columns `Pipeline | Job | Ref | Status | When | Download`) and `tab_packageRegistry` (`lineEdit_pkgProject`, `lineEdit_packageName`, `pushButton_fetchLatest`, `pushButton_browseVersions`, `tableWidget_versions` — 3 columns `Version | Uploaded | Download`), `progressBar_download`, `label_downloadStatus`, `pushButton_stopDownload` (disabled), `label_gitlabLog`, `plainTextEdit_gitlabLog`, `pushButton_cancel`.

- [ ] **Step 1: Write the failing test** — replace `tests/test_gui_ui_files.py` with:

```python
"""Designer files: meaningful names, generated modules in sync, every self.ui.<name> exists."""
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

pytestmark = pytest.mark.gui

GUI = Path(__file__).resolve().parents[1] / "wflash" / "gui"
UI_FILES = {
    "main_window.ui": "ui_main_window.py",
    "settings_dialog.ui": "ui_settings_dialog.py",
    "preferences_dialog.ui": "ui_preferences_dialog.py",
    "gitlab_dialog.ui": "ui_gitlab_dialog.py",
}
TOP_LEVEL = {"MainWindow", "SettingsDialog", "PreferencesDialog", "GitlabDialog"}
# <kind>_<what>, e.g. verticalLayout_gitlabBrowser, tableWidget_mapping.
MEANINGFUL = re.compile(r"^[a-z][A-Za-z]*_[a-z][A-Za-z0-9]*$")


def ui_names(ui_file: Path) -> list[str]:
    root = ET.parse(ui_file).getroot()
    return [el.get("name") for el in root.iter() if el.tag in ("widget", "layout", "spacer")]


def without_uic_version(text: str) -> str:
    # The header names the uic version; a PySide6 upgrade alone must not fail the build.
    return "\n".join(line for line in text.splitlines() if "User Interface Compiler version" not in line)


def uic_executable() -> str | None:
    folder = Path(sys.executable).parent
    for candidate in (folder / "pyside6-uic", folder / "pyside6-uic.exe"):
        if candidate.is_file():
            return str(candidate)
    return shutil.which("pyside6-uic")


@pytest.mark.parametrize("ui_name", sorted(UI_FILES))
def test_gui_every_widget_and_layout_has_a_meaningful_name(ui_name):
    names = ui_names(GUI / ui_name)
    assert names, f"no widgets parsed from {ui_name}"
    bad = [n for n in names if n not in TOP_LEVEL and not (n and MEANINGFUL.match(n))]
    assert bad == [], f"Designer default or unclear names in {ui_name}: {bad}"
    assert len(names) == len(set(names)), "duplicate object names"


@pytest.mark.parametrize("ui_name", sorted(UI_FILES))
def test_gui_generated_module_matches_ui_file(ui_name, tmp_path):
    uic = uic_executable()
    if uic is None:
        pytest.skip("pyside6-uic not found next to the interpreter")
    out = tmp_path / UI_FILES[ui_name]
    subprocess.run([uic, str(GUI / ui_name), "-o", str(out)], check=True)
    committed = (GUI / UI_FILES[ui_name]).read_text(encoding="utf-8")
    assert without_uic_version(committed) == without_uic_version(out.read_text(encoding="utf-8")), (
        f"{UI_FILES[ui_name]} is out of date or hand-edited; run "
        f"pyside6-uic wflash/gui/{ui_name} -o wflash/gui/{UI_FILES[ui_name]}"
    )


def test_gui_every_self_ui_reference_exists_in_a_ui_file():
    known = set()
    for ui_name in UI_FILES:
        known.update(ui_names(GUI / ui_name))
    referenced = set()
    for py in GUI.glob("*.py"):
        if py.name.startswith("ui_"):
            continue
        referenced.update(re.findall(r"self\.ui\.([A-Za-z_][A-Za-z0-9_]*)", py.read_text(encoding="utf-8")))
    referenced -= {"setupUi", "retranslateUi"}  # methods of the generated Ui_ class
    assert sorted(referenced - known) == []


def test_gui_generated_modules_import(qapp):
    from PySide6.QtWidgets import QDialog, QMainWindow

    from wflash.gui.ui_gitlab_dialog import Ui_GitlabDialog
    from wflash.gui.ui_main_window import Ui_MainWindow
    from wflash.gui.ui_preferences_dialog import Ui_PreferencesDialog
    from wflash.gui.ui_settings_dialog import Ui_SettingsDialog

    window = QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(window)
    assert ui.tableWidget_mapping.columnCount() == 4
    assert ui.comboBox_logLevel.currentText() == "INFO"
    assert ui.label_rollbackWarning.isHidden()
    dialog = QDialog()
    Ui_SettingsDialog().setupUi(dialog)
    preferences = QDialog()
    Ui_PreferencesDialog().setupUi(preferences)
    gitlab = QDialog()
    gitlab_ui = Ui_GitlabDialog()
    gitlab_ui.setupUi(gitlab)
    assert gitlab_ui.tableWidget_jobs.columnCount() == 6
    assert gitlab_ui.tableWidget_versions.columnCount() == 3
    assert gitlab_ui.tabWidget_source.count() == 2
    assert gitlab_ui.checkBox_verifyTls.isChecked()
    window.deleteLater()
    dialog.deleteLater()
    preferences.deleteLater()
    gitlab.deleteLater()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `~/.venvs/wflash/bin/pytest tests/test_gui_ui_files.py -v`
Expected: `4 failed, 6 passed` — `FileNotFoundError: … wflash/gui/gitlab_dialog.ui` and `ModuleNotFoundError: No module named 'wflash.gui.ui_gitlab_dialog'`.

- [ ] **Step 3: Create `wflash/gui/gitlab_dialog.ui`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>GitlabDialog</class>
 <widget class="QDialog" name="GitlabDialog">
  <property name="geometry">
   <rect>
    <x>0</x>
    <y>0</y>
    <width>880</width>
    <height>720</height>
   </rect>
  </property>
  <property name="minimumSize">
   <size>
    <width>760</width>
    <height>600</height>
   </size>
  </property>
  <property name="windowTitle">
   <string>Load from GitLab</string>
  </property>
  <layout class="QVBoxLayout" name="verticalLayout_gitlabDialog">
   <item>
    <widget class="QGroupBox" name="groupBox_connection">
     <property name="title">
      <string>GitLab Connection</string>
     </property>
     <layout class="QGridLayout" name="gridLayout_connection">
      <item row="0" column="0">
       <widget class="QLabel" name="label_gitlabUrl">
        <property name="text">
         <string>Instance URL:</string>
        </property>
        <property name="buddy">
         <cstring>lineEdit_gitlabUrl</cstring>
        </property>
       </widget>
      </item>
      <item row="0" column="1">
       <widget class="QLineEdit" name="lineEdit_gitlabUrl">
        <property name="placeholderText">
         <string>https://gitlab.company.com</string>
        </property>
       </widget>
      </item>
      <item row="1" column="0">
       <widget class="QLabel" name="label_token">
        <property name="text">
         <string>Access token:</string>
        </property>
        <property name="buddy">
         <cstring>lineEdit_token</cstring>
        </property>
       </widget>
      </item>
      <item row="1" column="1">
       <widget class="QLineEdit" name="lineEdit_token">
        <property name="echoMode">
         <enum>QLineEdit::EchoMode::Password</enum>
        </property>
        <property name="placeholderText">
         <string>Personal Access Token (scope read_api)</string>
        </property>
       </widget>
      </item>
      <item row="2" column="1">
       <widget class="QCheckBox" name="checkBox_verifyTls">
        <property name="text">
         <string>Verify TLS certificate (recommended)</string>
        </property>
        <property name="checked">
         <bool>true</bool>
        </property>
       </widget>
      </item>
      <item row="3" column="0">
       <widget class="QLabel" name="label_caBundle">
        <property name="text">
         <string>CA bundle:</string>
        </property>
        <property name="buddy">
         <cstring>lineEdit_caBundle</cstring>
        </property>
       </widget>
      </item>
      <item row="3" column="1">
       <layout class="QHBoxLayout" name="horizontalLayout_caBundle">
        <item>
         <widget class="QLineEdit" name="lineEdit_caBundle">
          <property name="placeholderText">
           <string>Optional: .pem file for an internal certificate</string>
          </property>
         </widget>
        </item>
        <item>
         <widget class="QPushButton" name="pushButton_browseCa">
          <property name="text">
           <string>Browse…</string>
          </property>
         </widget>
        </item>
       </layout>
      </item>
      <item row="4" column="0" colspan="2">
       <widget class="QLabel" name="label_connectionHint">
        <property name="text">
         <string>Required token scope: read_api (branches/tags, pipelines, jobs, artifacts, packages). The token is stored in the system keyring (Windows Credential Manager), never in a file.</string>
        </property>
        <property name="wordWrap">
         <bool>true</bool>
        </property>
       </widget>
      </item>
     </layout>
    </widget>
   </item>
   <item>
    <widget class="QTabWidget" name="tabWidget_source">
     <property name="currentIndex">
      <number>0</number>
     </property>
     <widget class="QWidget" name="tab_ciArtifact">
      <attribute name="title">
       <string>CI Artifact</string>
      </attribute>
      <layout class="QVBoxLayout" name="verticalLayout_ciArtifact">
       <item>
        <layout class="QGridLayout" name="gridLayout_ciArtifact">
         <item row="0" column="0">
          <widget class="QLabel" name="label_ciProject">
           <property name="text">
            <string>Project:</string>
           </property>
           <property name="buddy">
            <cstring>lineEdit_ciProject</cstring>
           </property>
          </widget>
         </item>
         <item row="0" column="1">
          <layout class="QHBoxLayout" name="horizontalLayout_ciProject">
           <item>
            <widget class="QLineEdit" name="lineEdit_ciProject">
             <property name="placeholderText">
              <string>group/project (empty = the profile's project)</string>
             </property>
            </widget>
           </item>
           <item>
            <widget class="QLabel" name="label_ciProjectSource">
             <property name="text">
              <string>from profile</string>
             </property>
            </widget>
           </item>
          </layout>
         </item>
         <item row="1" column="0">
          <widget class="QLabel" name="label_ref">
           <property name="text">
            <string>Branch/tag:</string>
           </property>
           <property name="buddy">
            <cstring>comboBox_ref</cstring>
           </property>
          </widget>
         </item>
         <item row="1" column="1">
          <layout class="QHBoxLayout" name="horizontalLayout_ref">
           <item>
            <widget class="QComboBox" name="comboBox_ref">
             <property name="sizePolicy">
              <sizepolicy hsizetype="Expanding" vsizetype="Fixed">
               <horstretch>1</horstretch>
               <verstretch>0</verstretch>
              </sizepolicy>
             </property>
             <property name="editable">
              <bool>true</bool>
             </property>
             <property name="insertPolicy">
              <enum>QComboBox::InsertPolicy::NoInsert</enum>
             </property>
            </widget>
           </item>
           <item>
            <widget class="QPushButton" name="pushButton_loadRefs">
             <property name="text">
              <string>Load branches/tags</string>
             </property>
            </widget>
           </item>
          </layout>
         </item>
         <item row="2" column="0">
          <widget class="QLabel" name="label_jobName">
           <property name="text">
            <string>Job name:</string>
           </property>
           <property name="buddy">
            <cstring>comboBox_jobName</cstring>
           </property>
          </widget>
         </item>
         <item row="2" column="1">
          <widget class="QComboBox" name="comboBox_jobName">
           <property name="editable">
            <bool>true</bool>
           </property>
           <property name="insertPolicy">
            <enum>QComboBox::InsertPolicy::NoInsert</enum>
           </property>
          </widget>
         </item>
        </layout>
       </item>
       <item>
        <layout class="QHBoxLayout" name="horizontalLayout_ciActions">
         <item>
          <widget class="QPushButton" name="pushButton_downloadSelected">
           <property name="text">
            <string>Download Selected Artifact</string>
           </property>
          </widget>
         </item>
         <item>
          <widget class="QPushButton" name="pushButton_browseJobs">
           <property name="text">
            <string>Browse jobs…</string>
           </property>
          </widget>
         </item>
         <item>
          <spacer name="horizontalSpacer_ciActions">
           <property name="orientation">
            <enum>Qt::Orientation::Horizontal</enum>
           </property>
           <property name="sizeHint" stdset="0">
            <size>
             <width>40</width>
             <height>20</height>
            </size>
           </property>
          </spacer>
         </item>
        </layout>
       </item>
       <item>
        <widget class="QTableWidget" name="tableWidget_jobs">
         <property name="minimumSize">
          <size>
           <width>0</width>
           <height>128</height>
          </size>
         </property>
         <property name="editTriggers">
          <set>QAbstractItemView::EditTrigger::NoEditTriggers</set>
         </property>
         <property name="selectionMode">
          <enum>QAbstractItemView::SelectionMode::SingleSelection</enum>
         </property>
         <property name="selectionBehavior">
          <enum>QAbstractItemView::SelectionBehavior::SelectRows</enum>
         </property>
         <attribute name="verticalHeaderVisible">
          <bool>false</bool>
         </attribute>
         <column>
          <property name="text">
           <string>Pipeline</string>
          </property>
         </column>
         <column>
          <property name="text">
           <string>Job</string>
          </property>
         </column>
         <column>
          <property name="text">
           <string>Ref</string>
          </property>
         </column>
         <column>
          <property name="text">
           <string>Status</string>
          </property>
         </column>
         <column>
          <property name="text">
           <string>When</string>
          </property>
         </column>
         <column>
          <property name="text">
           <string>Download</string>
          </property>
         </column>
        </widget>
       </item>
      </layout>
     </widget>
     <widget class="QWidget" name="tab_packageRegistry">
      <attribute name="title">
       <string>Package Registry</string>
      </attribute>
      <layout class="QVBoxLayout" name="verticalLayout_packageRegistry">
       <item>
        <layout class="QGridLayout" name="gridLayout_package">
         <item row="0" column="0">
          <widget class="QLabel" name="label_pkgProject">
           <property name="text">
            <string>Project:</string>
           </property>
           <property name="buddy">
            <cstring>lineEdit_pkgProject</cstring>
           </property>
          </widget>
         </item>
         <item row="0" column="1">
          <widget class="QLineEdit" name="lineEdit_pkgProject">
           <property name="placeholderText">
            <string>group/project holding the generic package</string>
           </property>
          </widget>
         </item>
         <item row="1" column="0">
          <widget class="QLabel" name="label_packageName">
           <property name="text">
            <string>Package name:</string>
           </property>
           <property name="buddy">
            <cstring>lineEdit_packageName</cstring>
           </property>
          </widget>
         </item>
         <item row="1" column="1">
          <widget class="QLineEdit" name="lineEdit_packageName">
           <property name="placeholderText">
            <string>e.g. saf85xx-firmware</string>
           </property>
          </widget>
         </item>
        </layout>
       </item>
       <item>
        <layout class="QHBoxLayout" name="horizontalLayout_packageActions">
         <item>
          <widget class="QPushButton" name="pushButton_fetchLatest">
           <property name="text">
            <string>Fetch Latest Version</string>
           </property>
          </widget>
         </item>
         <item>
          <widget class="QPushButton" name="pushButton_browseVersions">
           <property name="text">
            <string>Browse versions…</string>
           </property>
          </widget>
         </item>
         <item>
          <spacer name="horizontalSpacer_packageActions">
           <property name="orientation">
            <enum>Qt::Orientation::Horizontal</enum>
           </property>
           <property name="sizeHint" stdset="0">
            <size>
             <width>40</width>
             <height>20</height>
            </size>
           </property>
          </spacer>
         </item>
        </layout>
       </item>
       <item>
        <widget class="QTableWidget" name="tableWidget_versions">
         <property name="minimumSize">
          <size>
           <width>0</width>
           <height>128</height>
          </size>
         </property>
         <property name="editTriggers">
          <set>QAbstractItemView::EditTrigger::NoEditTriggers</set>
         </property>
         <property name="selectionMode">
          <enum>QAbstractItemView::SelectionMode::SingleSelection</enum>
         </property>
         <property name="selectionBehavior">
          <enum>QAbstractItemView::SelectionBehavior::SelectRows</enum>
         </property>
         <attribute name="verticalHeaderVisible">
          <bool>false</bool>
         </attribute>
         <column>
          <property name="text">
           <string>Version</string>
          </property>
         </column>
         <column>
          <property name="text">
           <string>Uploaded</string>
          </property>
         </column>
         <column>
          <property name="text">
           <string>Download</string>
          </property>
         </column>
        </widget>
       </item>
      </layout>
     </widget>
    </widget>
   </item>
   <item>
    <layout class="QHBoxLayout" name="horizontalLayout_download">
     <item>
      <widget class="QProgressBar" name="progressBar_download">
       <property name="sizePolicy">
        <sizepolicy hsizetype="Expanding" vsizetype="Fixed">
         <horstretch>1</horstretch>
         <verstretch>0</verstretch>
        </sizepolicy>
       </property>
       <property name="maximumSize">
        <size>
         <width>16777215</width>
         <height>20</height>
        </size>
       </property>
       <property name="value">
        <number>0</number>
       </property>
       <property name="textVisible">
        <bool>false</bool>
       </property>
      </widget>
     </item>
     <item>
      <widget class="QLabel" name="label_downloadStatus">
       <property name="minimumSize">
        <size>
         <width>220</width>
         <height>0</height>
        </size>
       </property>
       <property name="text">
        <string>Ready</string>
       </property>
      </widget>
     </item>
     <item>
      <widget class="QPushButton" name="pushButton_stopDownload">
       <property name="enabled">
        <bool>false</bool>
       </property>
       <property name="text">
        <string>Stop</string>
       </property>
      </widget>
     </item>
    </layout>
   </item>
   <item>
    <widget class="QLabel" name="label_gitlabLog">
     <property name="text">
      <string>GitLab log</string>
     </property>
     <property name="buddy">
      <cstring>plainTextEdit_gitlabLog</cstring>
     </property>
    </widget>
   </item>
   <item>
    <widget class="QPlainTextEdit" name="plainTextEdit_gitlabLog">
     <property name="maximumSize">
      <size>
       <width>16777215</width>
       <height>120</height>
      </size>
     </property>
     <property name="lineWrapMode">
      <enum>QPlainTextEdit::LineWrapMode::NoWrap</enum>
     </property>
     <property name="readOnly">
      <bool>true</bool>
     </property>
     <property name="maximumBlockCount">
      <number>2000</number>
     </property>
    </widget>
   </item>
   <item>
    <layout class="QHBoxLayout" name="horizontalLayout_dialogButtons">
     <item>
      <spacer name="horizontalSpacer_dialogButtons">
       <property name="orientation">
        <enum>Qt::Orientation::Horizontal</enum>
       </property>
       <property name="sizeHint" stdset="0">
        <size>
         <width>40</width>
         <height>20</height>
        </size>
       </property>
      </spacer>
     </item>
     <item>
      <widget class="QPushButton" name="pushButton_cancel">
       <property name="text">
        <string>Cancel</string>
       </property>
       <property name="autoDefault">
        <bool>false</bool>
       </property>
      </widget>
     </item>
    </layout>
   </item>
  </layout>
 </widget>
 <tabstops>
  <tabstop>lineEdit_gitlabUrl</tabstop>
  <tabstop>lineEdit_token</tabstop>
  <tabstop>checkBox_verifyTls</tabstop>
  <tabstop>lineEdit_caBundle</tabstop>
  <tabstop>pushButton_browseCa</tabstop>
  <tabstop>tabWidget_source</tabstop>
  <tabstop>lineEdit_ciProject</tabstop>
  <tabstop>comboBox_ref</tabstop>
  <tabstop>pushButton_loadRefs</tabstop>
  <tabstop>comboBox_jobName</tabstop>
  <tabstop>pushButton_downloadSelected</tabstop>
  <tabstop>pushButton_browseJobs</tabstop>
  <tabstop>tableWidget_jobs</tabstop>
  <tabstop>lineEdit_pkgProject</tabstop>
  <tabstop>lineEdit_packageName</tabstop>
  <tabstop>pushButton_fetchLatest</tabstop>
  <tabstop>pushButton_browseVersions</tabstop>
  <tabstop>tableWidget_versions</tabstop>
  <tabstop>pushButton_stopDownload</tabstop>
  <tabstop>pushButton_cancel</tabstop>
 </tabstops>
 <resources/>
 <connections/>
</ui>
```

- [ ] **Step 4: Generate the Python module (regenerate-ui skill)**

Run: `~/.venvs/wflash/bin/pyside6-uic wflash/gui/gitlab_dialog.ui -o wflash/gui/ui_gitlab_dialog.py`

- [ ] **Step 5: Run the tests to verify they pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_gui_ui_files.py -v` → Expected: `10 passed`.
Run: `~/.venvs/wflash/bin/pytest -q` → Expected: `291 passed`.

- [ ] **Step 6: Walkthrough entry**

```markdown
## Phase 1.36: File Designer cho popup Load from GitLab

Popup GitLab theo CLAUDE.md là Designer trước: khung GitLab Connection (URL, token, Verify TLS, CA bundle, ghi chú scope `read_api`), hai tab CI Artifact và Package Registry, thanh tải + trạng thái + Stop, ô GitLab log và nút Cancel. Mọi widget/layout có tên `<loại>_<ý nghĩa>`; chỉ các dòng của hai bảng (và nút Download từng dòng) sẽ dựng bằng Python ở task sau.

### Thay đổi

- **`wflash/gui/gitlab_dialog.ui`** (mới) + **`ui_gitlab_dialog.py`** (sinh bằng `pyside6-uic`).
- **`tests/test_gui_ui_files.py`**: kiểm tên, đồng bộ file sinh, số cột hai bảng, hai tab, Verify TLS bật sẵn.

### Đã kiểm tra

- RED / GREEN, `pytest -q`: <kết quả thật>
```

- [ ] **Step 7: Commit**

```bash
git add wflash/gui/gitlab_dialog.ui wflash/gui/ui_gitlab_dialog.py tests/test_gui_ui_files.py docs/walkthrough.md
git commit -m "feat(gui): Designer layout for the Load from GitLab popup" -m "$TRAILER"
```

---

### Task 11: `GitlabDialog` — CI artifact and Package Registry downloads in the popup

**Files:**
- Create: `wflash/gui/gitlab_dialog.py`
- Modify: `tests/gui_stubs.py` (package endpoints, `patch_keyring`, `SOURCE`, host `_save_settings`/`on_firmware_ready`)
- Test: `tests/test_gui_gitlab_dialog.py`

The old `GitlabBrowserMixin` keeps working untouched until Task 12 (both use `gitlab-` worker keys; they never run in the same test).

**Interfaces:**
- Consumes: `WorkerRegistry.start(name, fn, *, on_succeeded, on_failed, on_finished=None, on_progress=None, on_step=None) -> str`, `cancel(key)`, `is_running(key)`, `wait_idle(timeout_s, prefix)`, `abandon_running(prefix)` (Task 7); `WorkerContext(cancel, progress, step)` — `progress(percent, message)` raises `CancelledError` after a cancel; `GitLabClient(base_url, token, ca_bundle=None, session=None, timeout=30.0, verify=True)`, `get_project_id`, `list_refs`, `list_package_versions` (Task 5); `firmware_fetch.browse_jobs/find_latest_job/fetch_ci_artifact/latest_package/fetch_package` (Task 6); `ArtifactCache.has` (Task 4); `AppSettings` fields + `resolved_cache_dir()`, `resolved_package_cache_dir()` (Task 3); `settings.get_token(url) -> str | None`, `set_token(url, token)` (raises `GitLabError`); `logging_setup.redact`, `register_secret`; `style.repolish` (Task 8).
- Produces (`wflash.gui.gitlab_dialog`):
  - `ClientFactory = Callable[[AppSettings], GitLabClient]`; `default_client_factory(settings)` (moved here from `gitlab_browser.py`; now passes `verify=settings.verify_tls`; hint names "Load from GitLab…").
  - `WORKER_PREFIX = "gitlab-"`, `DIALOG_CLOSE_TIMEOUT_S = 10.0`, `JOB_DOWNLOAD_COLUMN = 5`, `VERSION_DOWNLOAD_COLUMN = 2`, `VERSIONS_TO_LIST = 20`, module flag `_tls_warning_logged`, `warn_tls_disabled_once(url)`, `byte_progress(ctx) -> Callable[[int, int], None]` (`"Downloading 12.4 / 19.3 MB"`).
  - `GitlabDialog(host)` (`QDialog`, parent = host) with signal `firmwareReady = Signal(object, object)` (`Path`, `FirmwareSource`); public `prepare()`, `busy()`, `ci_project()`, `load_refs()`, `browse_jobs()`, `download_selected()`, `fetch_latest()`, `browse_versions()`, `stop()`, `abort_for_close()`, `job_button(i)`, `version_button(i)`; `done()` stops its workers (bounded), saves the fields and closes.
  - Host contract: `settings`, `profile`, `ctx`, `_workers`, `_client_factory`, `_save_settings()`, `show_error()`, `_update_flash_controls()`.
- Produces (`tests.gui_stubs`): constants `PKG_PROJECT`, `PKG_PROJECT_ID = 43`, `PKG_NAME`, `PKG_ZIP_ID = 502` (1.4.0, zip), `PKG_RAW_ID = 501` (1.3.0, plain `App.s3`); `SOURCE: FirmwareSource`; `patch_keyring(monkeypatch, store=None) -> dict`; `FakeGitLabSession.package_versions` / `.package_files` and the endpoints `/projects/group/saf85xx-packages`, `/projects/43/packages`, `/projects/43/packages/<id>/package_files`, `/projects/43/packages/generic/<name>/<version>/<file>`; `HostWindow.settings.gitlab_url = GITLAB_URL`, `HostWindow._save_settings()` (counts into `settings_saved`), `HostWindow.on_firmware_ready()` (records into `firmware_loaded`).

Behaviour the tests pin down: a missing URL, a missing CA file, a missing ref or package field is reported in `label_downloadStatus` (property `state="error"`) without starting a worker; a new token is written to the keyring (once) and never into `AppSettings`; with Verify TLS unticked the CA field is disabled, `settings.verify_tls` is saved and exactly one WARNING "TLS certificate verification is OFF …" is logged per session; every button is locked while one request runs (one worker at a time) and Stop is the only active control; Stop keeps the dialog open and shows "Cancelled"; closing mid-download cancels and returns within the bound; a result already queued before Stop/close is dropped (generation guard); a request that ignores the cancel is abandoned after `DIALOG_CLOSE_TIMEOUT_S`.

- [ ] **Step 1: Extend the shared test doubles** — replace `tests/gui_stubs.py` with:

```python
"""Test doubles shared by the GUI tests and tools/stress_test.py.

`FakeGitLabSession` replaces `requests.Session` *under* the real `GitLabClient`, so the
client's own pagination, error classification (401/403/404, connection errors) and
streaming download run unchanged — only the network is fake.
"""
from __future__ import annotations

import io
import json
import threading
import time
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QMainWindow
from requests.structures import CaseInsensitiveDict

from wflash.core.debug_bundle import DebugContext
from wflash.core.firmware_source import FirmwareSource
from wflash.core.gitlab_client import GitLabClient
from wflash.core.settings import AppSettings
from wflash.gui import gitlab_dialog
from wflash.gui.ui_main_window import Ui_MainWindow
from wflash.gui.workers import WorkerRegistry

REPO = Path(__file__).resolve().parents[1]
EXAMPLE_PROFILE = REPO / "profiles" / "saf85xx_example.yaml"
GITLAB_URL = "https://gitlab.example.com"
# Realistic PAT shape (glpat- + 20 chars) so the redaction is tested on the real thing.
# Built by concatenation so push-protection secret scanners do not flag a fake token.
TOKEN = "glpat-" + "Zx9Qw3Er5Ty7Ui1Op2As"
PROJECT = "group/saf85xx-sw"
PROJECT_ID = 42
PIPELINE_ID = 100
JOB_ID = 7
PKG_PROJECT = "group/saf85xx-packages"
PKG_PROJECT_ID = 43
PKG_NAME = "saf85xx-firmware"
PKG_ZIP_ID = 502  # version 1.4.0: one zip with the usual artifact files
PKG_RAW_ID = 501  # version 1.3.0: one plain .s3 file (not a zip)
OLD_APP = r"C:\fake\old\App.s3"
OLD_CM7_0 = r"C:\fake\old\cm7_0.elf"
OLD_CM7_1 = r"C:\fake\old\cm7_1.elf"
ARTIFACT_FILES = {"out/App.s3": b"S0", "out/x_cm7_0.elf": b"E0", "out/x_cm7_1.elf": b"E1"}


# What a CI download of JOB_ID reports; tests that load a local tree use it as the source.
SOURCE = FirmwareSource(
    kind="ci",
    project=PROJECT,
    title=f"CI artifact \u00b7 job #{JOB_ID} build_app",
    detail=f"{PROJECT} \u00b7 main \u00b7 pipeline #{PIPELINE_ID}",
    cache_note="Downloaded \u00b7 3 files",
)


def patch_keyring(monkeypatch, store: dict | None = None) -> dict:
    """Keep the GitLab dialog away from the real system keyring; returns the fake store."""
    store = {} if store is None else store
    monkeypatch.setattr(gitlab_dialog, "get_token", lambda url: store.get(url))
    monkeypatch.setattr(gitlab_dialog, "set_token", lambda url, token: store.__setitem__(url, token))
    return store


def artifact_zip_bytes(files: dict[str, bytes] = ARTIFACT_FILES, padding: int = 64 * 1024) -> bytes:
    """Zip of the artifact. `padding` bytes of stored data make the stream span many chunks."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
        if padding:
            zf.writestr("out/padding.bin", b"\0" * padding)
    return buf.getvalue()


def make_artifact_tree(root: Path, files: dict[str, bytes] = ARTIFACT_FILES) -> Path:
    for rel, data in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return root


def write_profiles(folder: Path, download_s: int | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    text = EXAMPLE_PROFILE.read_text(encoding="utf-8")
    if download_s is not None:
        text = text.replace("download_s: 600", f"download_s: {download_s}")
    (folder / "saf.yaml").write_text(text, encoding="utf-8")
    return folder


class _SlowRaw(io.BytesIO):
    """Response body that hands out small chunks with a delay, like a slow network."""

    def __init__(self, data: bytes, chunk: int, delay_s: float) -> None:
        super().__init__(data)
        self._chunk = chunk
        self._delay_s = delay_s

    def read(self, size: int | None = -1) -> bytes:
        if self._delay_s:
            time.sleep(self._delay_s)
        limit = self._chunk if size is None or size < 0 else min(size, self._chunk)
        return super().read(limit)


class FakeGitLabSession:
    """Answers the GitLab REST v4 calls GitLabClient makes. Thread-safe."""

    def __init__(
        self,
        delay_s: float = 0.0,
        fail_status: int | None = None,
        connection_error: bool = False,
        chunk_delay_s: float = 0.0,
    ) -> None:
        self.headers = CaseInsensitiveDict()
        self.delay_s = delay_s
        self.fail_status = fail_status
        self.connection_error = connection_error
        self.chunk_delay_s = chunk_delay_s
        self.zip_bytes = artifact_zip_bytes()
        self.package_versions = [
            {"id": PKG_ZIP_ID, "name": PKG_NAME, "version": "1.4.0", "created_at": "2026-10-04T09:20:00Z"},
            {"id": 503, "name": PKG_NAME + "-debug", "version": "9.9.9", "created_at": "2026-10-03T08:00:00Z"},
            {"id": PKG_RAW_ID, "name": PKG_NAME, "version": "1.3.0", "created_at": "2026-10-01T07:00:00Z"},
        ]
        self.package_files = {PKG_ZIP_ID: f"{PKG_NAME}-1.4.0.zip", PKG_RAW_ID: "App.s3"}
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def count(self, suffix: str) -> int:
        with self._lock:
            return sum(1 for path in self.calls if path.endswith(suffix))

    def get(self, url, params=None, timeout=None, verify=None, stream=False):
        path = unquote(urlparse(url).path).removeprefix("/api/v4")
        with self._lock:
            self.calls.append(path)
        if self.delay_s:
            time.sleep(self.delay_s)  # like a real request: not interruptible by cancel
        if self.connection_error:
            raise requests.exceptions.ConnectionError(f"Failed to establish a new connection to {url}")
        if self.fail_status is not None:
            return self._response(self.fail_status, {"message": f"{self.fail_status} error"})
        if path == f"/projects/{PROJECT}":
            return self._response(200, {"id": PROJECT_ID})
        if path == f"/projects/{PROJECT_ID}/repository/branches":
            return self._response(200, [{"name": "main"}])
        if path == f"/projects/{PROJECT_ID}/repository/tags":
            return self._response(200, [{"name": "v1.0"}])
        if path == f"/projects/{PROJECT_ID}/pipelines":
            ref = (params or {}).get("ref", "main")
            return self._response(
                200,
                [{"id": PIPELINE_ID, "ref": ref, "status": "success", "sha": "abcdef1234567",
                  "created_at": "2026-10-01T10:00:00Z"}],
            )
        if path == f"/projects/{PROJECT_ID}/pipelines/{PIPELINE_ID}/jobs":
            return self._response(
                200,
                [{"id": JOB_ID, "name": "build_app", "stage": "build", "status": "success",
                  "finished_at": "2026-10-01T10:05:00Z", "artifacts": [{"file_type": "archive"}]},
                 {"id": 8, "name": "lint", "stage": "test", "status": "success", "artifacts": []}],
            )
        if path == f"/projects/{PROJECT_ID}/jobs/{JOB_ID}/artifacts":
            return self._stream(url, self.zip_bytes)
        if path == f"/projects/{PKG_PROJECT}":
            return self._response(200, {"id": PKG_PROJECT_ID})
        if path == f"/projects/{PKG_PROJECT_ID}/packages":
            name = (params or {}).get("package_name", "")
            return self._response(200, [p for p in self.package_versions if p["name"].startswith(name)])
        for package_id, file_name in self.package_files.items():
            if path == f"/projects/{PKG_PROJECT_ID}/packages/{package_id}/package_files":
                return self._response(200, [{"id": 1, "file_name": file_name}])
            version = next((p["version"] for p in self.package_versions if p["id"] == package_id), None)
            if path == f"/projects/{PKG_PROJECT_ID}/packages/generic/{PKG_NAME}/{version}/{file_name}":
                return self._stream(url, self.zip_bytes if file_name.endswith(".zip") else b"S0 raw")
        return self._response(404, {"message": "404 Not Found"})

    def _stream(self, url: str, data: bytes) -> requests.Response:
        resp = requests.Response()
        resp.status_code = 200
        resp.url = url
        resp.headers = CaseInsensitiveDict({"Content-Length": str(len(data))})
        resp.raw = _SlowRaw(data, 4096, self.chunk_delay_s)
        return resp

    @staticmethod
    def _response(status: int, payload) -> requests.Response:
        resp = requests.Response()
        resp.status_code = status
        resp._content = json.dumps(payload).encode()
        resp.headers = CaseInsensitiveDict({"Content-Type": "application/json"})
        return resp


class SessionClientFactory:
    """`client_factory` for MainWindow: a real GitLabClient over a FakeGitLabSession."""

    def __init__(self, session: FakeGitLabSession) -> None:
        self.session = session

    def __call__(self, settings: AppSettings) -> GitLabClient:
        return GitLabClient(GITLAB_URL, TOKEN, session=self.session)


class HostWindow(QMainWindow):
    """Minimal stand-in for MainWindow's shared state, to test one mixin at a time.

    Provides exactly the host contract the mixins and GitlabDialog document: ui, settings,
    adapter, ctx, profile, log_file, _workers, _closing, _client_factory, show_error(),
    _save_settings(), plus no-op versions of the cross-mixin hooks a part under test may call.
    """

    def __init__(self, tmp: Path, adapter=None, client_factory=None) -> None:
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.settings = AppSettings(
            gitlab_url=GITLAB_URL, cache_dir=str(tmp / "cache"), profiles_dir=str(tmp / "profiles")
        )
        self.adapter = adapter
        self.ctx = DebugContext()
        self.profile = None
        self.log_file = None
        self._closing = False
        self._client_factory = client_factory
        self._pool = QThreadPool(self)
        self._workers = WorkerRegistry(self._pool, self)
        self.errors_shown: list[BaseException] = []
        self.artifacts_loaded: list[tuple[Path, str]] = []
        self.firmware_loaded: list[tuple[Path, FirmwareSource]] = []
        self.flash_control_updates = 0
        self.settings_saved = 0

    def show_error(self, exc: BaseException) -> None:
        self.errors_shown.append(exc)

    def _save_settings(self) -> None:
        self.settings_saved += 1

    # Cross-mixin hooks; the real mixin wins over these when it is in the MRO first.
    def _update_flash_controls(self) -> None:
        self.flash_control_updates += 1

    def on_artifact_ready(self, path: Path, label: str) -> None:
        self.artifacts_loaded.append((path, label))

    def on_firmware_ready(self, path: Path, source: FirmwareSource) -> None:
        self.firmware_loaded.append((path, source))

    def flash_active(self) -> bool:
        return False

    def gitlab_busy(self) -> bool:
        return False

    def closeEvent(self, event) -> None:
        self._closing = True
        self._workers.cancel_all()
        if not self._workers.wait_idle(10.0):
            self._workers.abandon_running()
        if hasattr(self, "log_handler"):
            self._detach_log_panel()
        super().closeEvent(event)
```

- [ ] **Step 2: Write the failing test `tests/test_gui_gitlab_dialog.py`**

```python
"""Load from GitLab popup: CI artifact tab, Package Registry tab, Stop/close, settings, TLS."""
import dataclasses
import json
import logging
import threading
import time

import pytest
from PySide6.QtCore import Qt

from tests.gui_stubs import (
    EXAMPLE_PROFILE,
    GITLAB_URL,
    JOB_ID,
    PKG_NAME,
    PKG_PROJECT,
    PKG_PROJECT_ID,
    PKG_RAW_ID,
    PKG_ZIP_ID,
    PROJECT,
    PROJECT_ID,
    TOKEN,
    FakeGitLabSession,
    HostWindow,
    SessionClientFactory,
    patch_keyring,
)
from wflash.core.artifact_cache import ArtifactCache
from wflash.core.errors import GitLabError
from wflash.core.profile import load_profile
from wflash.core.settings import AppSettings
from wflash.gui import gitlab_dialog
from wflash.gui.gitlab_dialog import GitlabDialog, default_client_factory

pytestmark = pytest.mark.gui


class DialogHost(HostWindow):
    def __init__(self, tmp, session):
        super().__init__(tmp, client_factory=SessionClientFactory(session))
        self.profile = load_profile(EXAMPLE_PROFILE)
        self.settings.last_profile = "saf.yaml"
        self.dialog = GitlabDialog(self)
        self.dialog.firmwareReady.connect(self.on_firmware_ready)  # bound method, GUI thread


@pytest.fixture
def keyring_store(monkeypatch):
    return patch_keyring(monkeypatch)


@pytest.fixture
def session():
    return FakeGitLabSession()


@pytest.fixture
def host(qtbot, tmp_path, session, keyring_store):
    window = DialogHost(tmp_path, session)
    qtbot.addWidget(window)
    window.dialog.prepare()
    window.dialog.open()
    return window


def idle(d, qtbot, timeout=5000):
    qtbot.waitUntil(lambda: not d.busy(), timeout=timeout)


def load_and_browse(d, qtbot):
    d.load_refs()
    idle(d, qtbot)
    d.browse_jobs()
    idle(d, qtbot)


def test_gui_prepare_fills_fields_from_settings_profile_and_keyring(qtbot, tmp_path, session, monkeypatch):
    patch_keyring(monkeypatch, {GITLAB_URL: TOKEN})
    w = DialogHost(tmp_path, session)
    qtbot.addWidget(w)
    w.settings = dataclasses.replace(
        w.settings, verify_tls=False, ca_bundle="/ca.pem", package_project=PKG_PROJECT, package_name=PKG_NAME,
        ci_job_name="build_app",
    )
    d = w.dialog
    d.prepare()
    assert d.ui.lineEdit_gitlabUrl.text() == GITLAB_URL
    assert d.ui.lineEdit_token.text() == TOKEN
    assert not d.ui.checkBox_verifyTls.isChecked() and not d.ui.lineEdit_caBundle.isEnabled()
    assert d.ui.lineEdit_ciProject.text() == PROJECT
    assert d.ui.label_ciProjectSource.isVisibleTo(d)
    assert d.ui.comboBox_jobName.currentText() == "build_app"
    assert (d.ui.lineEdit_pkgProject.text(), d.ui.lineEdit_packageName.text()) == (PKG_PROJECT, PKG_NAME)
    assert d.ui.label_downloadStatus.text() == "Ready"
    assert not d.ui.pushButton_stopDownload.isEnabled()


def test_gui_ci_refs_jobs_and_row_download(host, qtbot, tmp_path):
    d = host.dialog
    d.load_refs()
    idle(d, qtbot)
    assert [d.ui.comboBox_ref.itemText(i) for i in range(d.ui.comboBox_ref.count())] == ["main", "v1.0"]
    assert d.ui.comboBox_ref.currentText() == "main"
    d.browse_jobs()
    idle(d, qtbot)
    table = d.ui.tableWidget_jobs
    assert table.rowCount() == 1  # "lint" has no archive, and does not match build_*
    assert [table.item(0, c).text() for c in range(5)] == ["#100", "build_app", "main", "success", "2026-10-01 10:05"]
    assert d.job_button(0).text() == "Download"
    assert d.ui.comboBox_jobName.itemText(0) == "build_app"
    qtbot.mouseClick(d.job_button(0), Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: len(host.firmware_loaded) == 1, timeout=5000)
    path, source = host.firmware_loaded[0]
    assert (path / "out" / "App.s3").read_bytes() == b"S0"
    assert source.kind == "ci" and source.title == f"CI artifact · job #{JOB_ID} build_app"
    assert source.detail == f"{PROJECT} · main · pipeline #100"
    assert source.cache_note.startswith("Downloaded")
    assert not d.isVisible()
    assert ArtifactCache(tmp_path / "cache").has(PROJECT_ID, JOB_ID)
    assert host.settings_saved > 0
    # Reopened: the row now says Cached, and downloading it again needs no network.
    d.prepare()
    d.open()
    assert d.job_button(0).text() == "Cached"


def test_gui_download_selected_without_a_row_takes_the_newest_successful_job(host, qtbot):
    d = host.dialog
    d.ui.comboBox_ref.setEditText("main")
    d.ui.comboBox_jobName.setEditText("build_app")
    qtbot.mouseClick(d.ui.pushButton_downloadSelected, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: len(host.firmware_loaded) == 1, timeout=5000)
    assert host.firmware_loaded[0][1].title.endswith(f"job #{JOB_ID} build_app")
    assert host.settings.ci_job_name == "build_app"


def test_gui_download_selected_uses_the_selected_row(host, session, qtbot):
    d = host.dialog
    load_and_browse(d, qtbot)
    d.ui.tableWidget_jobs.selectRow(0)
    d.download_selected()
    qtbot.waitUntil(lambda: len(host.firmware_loaded) == 1, timeout=5000)
    assert session.count("/pipelines") == 1  # the selected row needs no new pipeline lookup


def test_gui_double_click_on_a_job_row_downloads_it(host, qtbot):
    d = host.dialog
    load_and_browse(d, qtbot)
    d.ui.tableWidget_jobs.cellDoubleClicked.emit(0, 1)
    qtbot.waitUntil(lambda: len(host.firmware_loaded) == 1, timeout=5000)


def test_gui_missing_ref_is_reported_in_the_dialog(host):
    d = host.dialog
    d.ui.comboBox_ref.setEditText("")
    d.browse_jobs()
    assert not d.busy()
    assert "branch or tag" in d.ui.label_downloadStatus.text()
    assert d.ui.label_downloadStatus.property("state") == "error"


def test_gui_ci_project_edit_is_remembered_per_profile(host, qtbot):
    d = host.dialog
    d.ui.lineEdit_ciProject.setText("group/other")
    d.ui.lineEdit_ciProject.editingFinished.emit()
    assert host.settings.ci_project_overrides == {"saf.yaml": "group/other"}
    assert not d.ui.label_ciProjectSource.isVisibleTo(d)
    assert d.ci_project() == "group/other"
    d.reject()
    d.prepare()
    assert d.ui.lineEdit_ciProject.text() == "group/other"
    # Another profile starts from its own project.
    host.settings.last_profile = "other.yaml"
    d.prepare()
    assert d.ui.lineEdit_ciProject.text() == PROJECT
    host.settings.last_profile = "saf.yaml"
    d.prepare()
    d.ui.lineEdit_ciProject.setText("")
    d.ui.lineEdit_ciProject.editingFinished.emit()
    assert host.settings.ci_project_overrides == {}
    assert d.ci_project() == PROJECT and d.ui.label_ciProjectSource.isVisibleTo(d)


def test_gui_package_fetch_latest_extracts_the_zip(host, qtbot, tmp_path):
    d = host.dialog
    d.ui.tabWidget_source.setCurrentWidget(d.ui.tab_packageRegistry)
    d.ui.lineEdit_pkgProject.setText(PKG_PROJECT)
    d.ui.lineEdit_packageName.setText(PKG_NAME)
    qtbot.mouseClick(d.ui.pushButton_fetchLatest, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: len(host.firmware_loaded) == 1, timeout=5000)
    path, source = host.firmware_loaded[0]
    assert (path / "out" / "x_cm7_0.elf").read_bytes() == b"E0"
    assert source.kind == "package" and source.title == f"Package · {PKG_NAME} 1.4.0"
    assert source.detail == f"{PKG_PROJECT} · 2026-10-04 09:20"
    assert ArtifactCache(tmp_path / "cache" / "packages").has(PKG_PROJECT_ID, PKG_ZIP_ID)
    assert (host.settings.package_project, host.settings.package_name) == (PKG_PROJECT, PKG_NAME)


def test_gui_package_browse_versions_and_download_a_plain_file(host, qtbot):
    d = host.dialog
    d.ui.lineEdit_pkgProject.setText(PKG_PROJECT)
    d.ui.lineEdit_packageName.setText(PKG_NAME)
    d.browse_versions()
    idle(d, qtbot)
    table = d.ui.tableWidget_versions
    assert [table.item(i, 0).text() for i in range(table.rowCount())] == ["1.4.0", "1.3.0"]  # -debug dropped
    assert table.item(1, 1).text() == "2026-10-01 07:00"
    assert d.version_button(1).text() == "Download"
    qtbot.mouseClick(d.version_button(1), Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: len(host.firmware_loaded) == 1, timeout=5000)
    path, source = host.firmware_loaded[0]
    assert (path / "App.s3").read_bytes() == b"S0 raw"
    assert source.cache_note == "Downloaded · 1 file"
    assert path.parent.name == str(PKG_RAW_ID)


def test_gui_package_without_versions_shows_the_error(host, session, qtbot):
    session.package_versions = []
    d = host.dialog
    d.ui.lineEdit_pkgProject.setText(PKG_PROJECT)
    d.ui.lineEdit_packageName.setText(PKG_NAME)
    d.fetch_latest()
    qtbot.waitUntil(lambda: len(host.errors_shown) == 1, timeout=5000)
    exc = host.errors_shown[0]
    assert isinstance(exc, GitLabError) and f"No versions of package '{PKG_NAME}'" in str(exc)
    assert d.isVisible()
    assert d.ui.label_downloadStatus.property("state") == "error"
    assert "No versions" in d.ui.plainTextEdit_gitlabLog.toPlainText()
    assert len(host.ctx.errors) == 1


def test_gui_package_fields_required(host):
    d = host.dialog
    d.ui.lineEdit_pkgProject.setText("")
    d.fetch_latest()
    assert not d.busy() and "package project" in d.ui.label_downloadStatus.text()


def test_gui_url_required_before_any_request(host, session):
    d = host.dialog
    d.ui.lineEdit_gitlabUrl.setText("gitlab.example.com")
    d.load_refs()
    assert not d.busy() and session.calls == []
    assert "GitLab URL" in d.ui.label_downloadStatus.text()


def test_gui_missing_ca_bundle_refused(host, tmp_path):
    d = host.dialog
    d.ui.lineEdit_caBundle.setText(str(tmp_path / "missing.pem"))
    d.load_refs()
    assert not d.busy() and "CA bundle file not found" in d.ui.label_downloadStatus.text()


def test_gui_token_goes_to_the_keyring_never_to_settings(host, keyring_store, qtbot):
    d = host.dialog
    d.ui.lineEdit_token.setText(f" {TOKEN} ")
    d.load_refs()
    idle(d, qtbot)
    assert keyring_store == {GITLAB_URL: TOKEN}
    assert TOKEN not in json.dumps(dataclasses.asdict(host.settings))
    assert "Token stored" in d.ui.plainTextEdit_gitlabLog.toPlainText()
    d.load_refs()  # unchanged token: not written again
    idle(d, qtbot)
    assert d.ui.plainTextEdit_gitlabLog.toPlainText().count("Token stored") == 1


def test_gui_dialog_log_is_redacted(host):
    d = host.dialog
    d._note(logging.INFO, f"header PRIVATE-TOKEN: {TOKEN}")
    text = d.ui.plainTextEdit_gitlabLog.toPlainText()
    assert TOKEN not in text and "***" in text


def test_gui_verify_tls_off_is_saved_and_warned_once_per_session(host, qtbot, monkeypatch, caplog):
    monkeypatch.setattr(gitlab_dialog, "_tls_warning_logged", False)
    d = host.dialog
    d.ui.checkBox_verifyTls.setChecked(False)
    assert not d.ui.lineEdit_caBundle.isEnabled()
    with caplog.at_level(logging.WARNING, logger="wflash.gitlab"):
        for _ in range(2):
            d.load_refs()
            idle(d, qtbot)
    warnings = [r for r in caplog.records if "TLS certificate verification is OFF" in r.getMessage()]
    assert len(warnings) == 1 and warnings[0].levelno == logging.WARNING
    assert host.settings.verify_tls is False


def test_gui_default_client_factory_requires_url_and_token_and_passes_verify(monkeypatch):
    monkeypatch.setattr(gitlab_dialog, "get_token", lambda url: None)
    with pytest.raises(GitLabError, match="not configured") as info:
        default_client_factory(AppSettings(gitlab_url="https://gl"))
    assert "Load from GitLab" in info.value.hint
    monkeypatch.setattr(gitlab_dialog, "get_token", lambda url: TOKEN)
    client = default_client_factory(AppSettings(gitlab_url="https://gl/", ca_bundle=""))
    assert client.base == "https://gl/api/v4" and client.verify is True
    insecure = default_client_factory(AppSettings(gitlab_url="https://gl", ca_bundle="/ca.pem", verify_tls=False))
    assert insecure.verify is False


@pytest.mark.parametrize("status, hint_word", [(401, "expired"), (403, "access"), (404, "expired")])
def test_gui_http_errors_show_specific_hints(qtbot, tmp_path, keyring_store, status, hint_word):
    w = DialogHost(tmp_path, FakeGitLabSession(fail_status=status))
    qtbot.addWidget(w)
    w.dialog.prepare()
    w.dialog.load_refs()
    qtbot.waitUntil(lambda: len(w.errors_shown) == 1, timeout=3000)
    exc = w.errors_shown[0]
    assert isinstance(exc, GitLabError) and f"HTTP {status}" in str(exc)
    assert hint_word in exc.hint


def test_gui_thread_buttons_locked_while_a_request_runs(host, session, qtbot):
    session.delay_s = 0.3
    d = host.dialog
    d.load_refs()
    assert d.busy()
    assert not d.ui.pushButton_loadRefs.isEnabled() and not d.ui.groupBox_connection.isEnabled()
    assert d.ui.pushButton_stopDownload.isEnabled()
    d.load_refs()  # refused while busy
    assert len([k for k in host._workers.running_keys() if k.startswith("gitlab-")]) == 1
    idle(d, qtbot)
    assert d.ui.pushButton_loadRefs.isEnabled() and not d.ui.pushButton_stopDownload.isEnabled()


def test_gui_thread_stop_download_keeps_the_dialog_open(host, session, qtbot, tmp_path):
    session.chunk_delay_s = 0.02  # 64 KiB in 4 KiB chunks: ~0.4 s
    d = host.dialog
    load_and_browse(d, qtbot)
    d.job_button(0).click()
    assert d.job_button(0).text() == "Downloading…"
    qtbot.waitUntil(lambda: d.ui.progressBar_download.value() > 0, timeout=3000)
    assert "MB" in d.ui.label_downloadStatus.text()
    qtbot.mouseClick(d.ui.pushButton_stopDownload, Qt.MouseButton.LeftButton)
    idle(d, qtbot)
    assert d.isVisible()
    assert d.ui.label_downloadStatus.text() == "Cancelled"
    assert host.firmware_loaded == [] and host.errors_shown == []
    assert not ArtifactCache(tmp_path / "cache").has(PROJECT_ID, JOB_ID)
    assert d.job_button(0).text() == "Download"


def test_gui_thread_completion_queued_before_stop_is_dropped(host, qtbot):
    d = host.dialog
    load_and_browse(d, qtbot)
    d.job_button(0).click()
    key = next(k for k in host._workers.running_keys() if k.startswith("gitlab-download"))
    assert host._workers.worker(key).done.wait(5)  # finished, signals still queued
    d.stop()
    idle(d, qtbot)
    assert host.firmware_loaded == []
    assert d.isVisible() and d.ui.label_downloadStatus.text() == "Cancelled"


def test_gui_thread_closing_the_dialog_mid_download_cancels_it(host, session, qtbot):
    session.chunk_delay_s = 0.02
    d = host.dialog
    load_and_browse(d, qtbot)
    d.job_button(0).click()
    qtbot.waitUntil(lambda: d.ui.progressBar_download.value() > 0, timeout=3000)
    t0 = time.monotonic()
    d.reject()
    assert time.monotonic() - t0 < 3.0
    assert not d.isVisible() and not d.busy()
    assert not [k for k in host._workers.running_keys() if k.startswith("gitlab-")]
    qtbot.wait(100)
    assert host.firmware_loaded == [] and host.errors_shown == []


def test_gui_thread_close_wait_is_bounded_when_a_request_hangs(host, session, qtbot, monkeypatch):
    from wflash.gui import workers

    release = threading.Event()
    original_get = session.get

    def hanging_get(url, **kwargs):
        release.wait(5)  # like a stuck socket: ignores the cancel token
        return original_get(url, **kwargs)

    session.get = hanging_get
    monkeypatch.setattr(gitlab_dialog, "DIALOG_CLOSE_TIMEOUT_S", 0.3)
    d = host.dialog
    d.load_refs()
    key = next(k for k in host._workers.running_keys() if k.startswith("gitlab-"))
    worker = host._workers.worker(key)
    t0 = time.monotonic()
    d.reject()
    assert time.monotonic() - t0 < 2.0
    assert not d.busy() and not host._workers.is_running(key)
    assert worker in workers._ABANDONED
    release.set()
    assert worker.done.wait(5)
    qtbot.wait(100)
    assert d.ui.comboBox_ref.count() == 0  # the late result was dropped
```

- [ ] **Step 3: Run it to verify it fails**

Run: `~/.venvs/wflash/bin/pytest tests/test_gui_gitlab_dialog.py -v`
Expected: collection error `ImportError: cannot import name 'gitlab_dialog' from 'wflash.gui'` (raised by `tests/gui_stubs.py`, so every GUI test that imports the stubs errors the same way until Step 4).

- [ ] **Step 4: Implement `wflash/gui/gitlab_dialog.py`**

```python
"""Load from GitLab popup (layout in gitlab_dialog.ui): CI artifact and Package Registry tabs.

The dialog finds and downloads firmware, then emits `firmwareReady(path, source)` and
closes; the main window builds the mapping from it. Every GitLab call runs on the main
window's WorkerRegistry under a "gitlab-" key, so closing the main window also waits for
the dialog's work (CLAUDE.md threading model):

- Rule 4: `_generation` is bumped *before* anything is cancelled (Stop, close, main
  window shutdown); every completion slot drops results of an older generation.
- Rule 8: every slot handed to the registry is a bound method of this QDialog.
- Rule 3: closing waits for the dialog's own workers with a bound, pumping events
  (`WorkerRegistry.wait_idle(prefix="gitlab-")`), and parks stragglers instead of hanging.
- Rule 7: downloads report bytes through `WorkerContext.progress`, which raises once the
  token is cancelled, so Stop takes effect inside the transfer.

The main window keeps one instance for its whole life (never deleted while a worker might
still report to it) and calls `prepare()` before each `open()`.

Host contract (MainWindow, or tests.gui_stubs.HostWindow): `settings`, `profile`, `ctx`,
`_workers`, `_client_factory`, `_save_settings()`, `show_error()`, `_update_flash_controls()`.
"""
from __future__ import annotations

import dataclasses
import datetime
import logging
from functools import partial
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QDialog, QFileDialog, QHeaderView, QPushButton, QTableWidgetItem

from wflash.core.artifact_cache import ArtifactCache
from wflash.core.errors import CancelledError, GitLabError
from wflash.core.firmware_fetch import (
    JobRow,
    browse_jobs,
    fetch_ci_artifact,
    fetch_package,
    find_latest_job,
    latest_package,
)
from wflash.core.firmware_source import short_timestamp
from wflash.core.gitlab_client import GitLabClient, PackageVersion
from wflash.core.logging_setup import get_logger, redact, register_secret
from wflash.core.settings import AppSettings, get_token, set_token
from wflash.gui.style import repolish
from wflash.gui.ui_gitlab_dialog import Ui_GitlabDialog
from wflash.gui.workers import WorkerContext

# Same logger as the core client: the dialog's own lines reach the log file and the
# debug bundle, redacted like everything else.
log = get_logger("gitlab")

ClientFactory = Callable[[AppSettings], GitLabClient]
WORKER_PREFIX = "gitlab-"
DIALOG_CLOSE_TIMEOUT_S = 10.0
JOB_DOWNLOAD_COLUMN = 5
VERSION_DOWNLOAD_COLUMN = 2
VERSIONS_TO_LIST = 20

_tls_warning_logged = False  # "Verify TLS" off is logged once per session


def default_client_factory(settings: AppSettings) -> GitLabClient:
    """Called on a worker thread: builds a client from the settings and the keyring token."""
    token = get_token(settings.gitlab_url)
    if not settings.gitlab_url or not token:
        raise GitLabError(
            "GitLab URL or token is not configured",
            hint="Open Load from GitLab… and enter the GitLab URL and a Personal Access Token (scope read_api).",
        )
    return GitLabClient(
        settings.gitlab_url, token, ca_bundle=settings.ca_bundle or None, verify=settings.verify_tls
    )


def warn_tls_disabled_once(url: str) -> None:
    global _tls_warning_logged
    if _tls_warning_logged:
        return
    _tls_warning_logged = True
    log.warning(
        "TLS certificate verification is OFF for %s. Use this only on a trusted network; "
        "if GitLab uses an internal certificate, set its CA bundle instead.",
        url,
    )


def byte_progress(ctx: WorkerContext) -> Callable[[int, int], None]:
    """Turn the client's (bytes_done, bytes_total) into worker progress (raises after a cancel)."""

    def on_bytes(done: int, total: int) -> None:
        if total:
            ctx.progress(int(done * 100 / total), f"Downloading {done / 1e6:.1f} / {total / 1e6:.1f} MB")
        else:
            ctx.progress(None, f"Downloading {done / 1e6:.1f} MB")

    return on_bytes


class GitlabDialog(QDialog):
    firmwareReady = Signal(object, object)  # Path of the extracted files, FirmwareSource

    def __init__(self, host) -> None:
        super().__init__(host)
        self.ui = Ui_GitlabDialog()
        self.ui.setupUi(self)
        self._host = host
        self._generation = 0  # bumped before every cancel (threading rule 4)
        self._keys: dict[str, int] = {}  # running worker key -> generation at start
        self._stopped: set[str] = set()  # keys cancelled by Stop/close: show "Cancelled"
        self._profile_key: str | None = None
        self._token_saved_for: tuple[str, str] = ("", "")  # (url, token) known to be in the keyring
        self._job_rows: list[JobRow] = []
        self._jobs_project: tuple[str, int] | None = None  # project the job table was listed from
        self._versions: list[PackageVersion] = []
        self._versions_project: tuple[str, int] | None = None
        self._downloading_button: QPushButton | None = None

        self.ui.plainTextEdit_gitlabLog.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        for table, stretch in ((self.ui.tableWidget_jobs, 1), (self.ui.tableWidget_versions, 0)):
            header = table.horizontalHeader()
            for column in range(table.columnCount()):
                mode = QHeaderView.ResizeMode.Stretch if column == stretch else QHeaderView.ResizeMode.ResizeToContents
                header.setSectionResizeMode(column, mode)
        self._reset_progress()

        self.ui.pushButton_loadRefs.clicked.connect(self.load_refs)
        self.ui.pushButton_browseJobs.clicked.connect(self.browse_jobs)
        self.ui.pushButton_downloadSelected.clicked.connect(self.download_selected)
        self.ui.tableWidget_jobs.cellDoubleClicked.connect(self._on_job_double_clicked)
        self.ui.pushButton_fetchLatest.clicked.connect(self.fetch_latest)
        self.ui.pushButton_browseVersions.clicked.connect(self.browse_versions)
        self.ui.tableWidget_versions.cellDoubleClicked.connect(self._on_version_double_clicked)
        self.ui.pushButton_stopDownload.clicked.connect(self.stop)
        self.ui.pushButton_cancel.clicked.connect(self.reject)
        self.ui.pushButton_browseCa.clicked.connect(self._browse_ca)
        self.ui.checkBox_verifyTls.toggled.connect(self._on_verify_toggled)
        self.ui.lineEdit_ciProject.textChanged.connect(self._update_ci_project_label)
        self.ui.lineEdit_ciProject.editingFinished.connect(self._store_ci_project)
        self._update_controls()

    # -- opening and closing ----------------------------------------------------------
    def prepare(self) -> None:
        """Load the current settings and profile into the fields; called before each open()."""
        settings = self._host.settings
        self.ui.lineEdit_gitlabUrl.setText(settings.gitlab_url)
        token = (get_token(settings.gitlab_url) or "") if settings.gitlab_url else ""
        self._token_saved_for = (settings.gitlab_url, token)
        self.ui.lineEdit_token.setText(token)
        self.ui.checkBox_verifyTls.setChecked(settings.verify_tls)
        self.ui.lineEdit_caBundle.setText(settings.ca_bundle)
        self._on_verify_toggled(settings.verify_tls)
        self.ui.lineEdit_pkgProject.setText(settings.package_project)
        self.ui.lineEdit_packageName.setText(settings.package_name)
        key = self._profile_key_now()
        if key != self._profile_key:
            # Another profile: its project and jobs are different, start the CI tab afresh.
            self._profile_key = key
            profile = self._host.profile
            override = settings.ci_project_overrides.get(key, "")
            self.ui.lineEdit_ciProject.setText(override or (profile.gitlab.project if profile else ""))
            self.ui.comboBox_ref.clear()
            self.ui.comboBox_jobName.clear()
            self.ui.comboBox_jobName.setEditText(settings.ci_job_name)
            self._fill_jobs([], None)
        self._update_ci_project_label()
        self._reset_progress()
        self._set_status("Ready")
        self._update_controls()

    def done(self, result: int) -> None:
        # Accept (firmware ready), Cancel, Esc and the window's X all end here.
        self._stop_workers(wait=True)
        self._store_fields()
        super().done(result)

    def abort_for_close(self) -> None:
        """The main window is closing: drop every pending result (it cancels and waits itself)."""
        self._generation += 1
        self._stopped.update(self._keys)

    # -- state --------------------------------------------------------------------------
    def busy(self) -> bool:
        return bool(self._keys)

    def _stale(self, key: str) -> bool:
        return self._keys.get(key) != self._generation

    def _profile_key_now(self) -> str:
        profile = self._host.profile
        return self._host.settings.last_profile or (profile.name if profile else "")

    def ci_project(self) -> str:
        profile = self._host.profile
        return self.ui.lineEdit_ciProject.text().strip() or (profile.gitlab.project if profile else "")

    def _current_ref(self) -> str:
        return self.ui.comboBox_ref.currentText().strip()

    def _job_name(self) -> str:
        return self.ui.comboBox_jobName.currentText().strip()

    def _update_controls(self, *_args) -> None:
        busy = self.busy()
        for widget in (
            self.ui.groupBox_connection,
            self.ui.lineEdit_ciProject,
            self.ui.comboBox_ref,
            self.ui.pushButton_loadRefs,
            self.ui.comboBox_jobName,
            self.ui.pushButton_downloadSelected,
            self.ui.pushButton_browseJobs,
            self.ui.tableWidget_jobs,
            self.ui.lineEdit_pkgProject,
            self.ui.lineEdit_packageName,
            self.ui.pushButton_fetchLatest,
            self.ui.pushButton_browseVersions,
            self.ui.tableWidget_versions,
        ):
            widget.setEnabled(not busy)
        self.ui.pushButton_stopDownload.setEnabled(busy)

    def _update_ci_project_label(self, *_args) -> None:
        profile = self._host.profile
        text = self.ui.lineEdit_ciProject.text().strip()
        self.ui.label_ciProjectSource.setVisible(
            profile is not None and (not text or text == profile.gitlab.project)
        )

    def _on_verify_toggled(self, checked: bool) -> None:
        # The CA bundle only matters while certificates are verified.
        self.ui.lineEdit_caBundle.setEnabled(checked)
        self.ui.pushButton_browseCa.setEnabled(checked)

    # -- status, log --------------------------------------------------------------------
    def _note(self, level: int, text: str) -> None:
        log.log(level, "%s", text)
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.ui.plainTextEdit_gitlabLog.appendPlainText(f"{stamp} {logging.getLevelName(level)}: {redact(text)}")

    def _set_status(self, text: str, error: bool = False) -> None:
        label = self.ui.label_downloadStatus
        label.setText(redact(text))
        label.setProperty("state", "error" if error else "")
        repolish(label)

    def _reset_progress(self) -> None:
        bar = self.ui.progressBar_download
        bar.setRange(0, 100)
        bar.setValue(0)

    def _busy_progress(self, text: str) -> None:
        self.ui.progressBar_download.setRange(0, 0)
        self._set_status(text)

    def _fail_input(self, text: str) -> None:
        """A field is missing or wrong: say so in the dialog, no modal box."""
        self._set_status(text, error=True)
        self._note(logging.WARNING, text)

    # -- settings -----------------------------------------------------------------------
    def _store_ci_project(self) -> None:
        profile = self._host.profile
        key = self._profile_key or self._profile_key_now()
        if profile is None or not key:
            return
        text = self.ui.lineEdit_ciProject.text().strip()
        overrides = self._host.settings.ci_project_overrides
        if not text or text == profile.gitlab.project:
            overrides.pop(key, None)
        else:
            overrides[key] = text

    def _store_fields(self) -> None:
        """Copy the fields to the settings and save them (never the token)."""
        settings = self._host.settings
        url = self.ui.lineEdit_gitlabUrl.text().strip().rstrip("/")
        if not url or url.startswith(("http://", "https://")):
            settings.gitlab_url = url
        settings.ca_bundle = self.ui.lineEdit_caBundle.text().strip()
        settings.verify_tls = self.ui.checkBox_verifyTls.isChecked()
        settings.ci_job_name = self._job_name()
        settings.package_project = self.ui.lineEdit_pkgProject.text().strip()
        settings.package_name = self.ui.lineEdit_packageName.text().strip()
        self._store_ci_project()
        self._host._save_settings()

    def _commit_connection(self) -> bool:
        """Validate and save the connection before an operation; store a new token in the keyring."""
        url = self.ui.lineEdit_gitlabUrl.text().strip().rstrip("/")
        if not url.startswith(("http://", "https://")):
            self._fail_input("Enter the GitLab URL (https://…) first.")
            return False
        ca = self.ui.lineEdit_caBundle.text().strip()
        if self.ui.checkBox_verifyTls.isChecked() and ca and not Path(ca).is_file():
            self._fail_input(f"CA bundle file not found: {ca}")
            return False
        self._store_fields()
        token = self.ui.lineEdit_token.text().strip()
        if token:
            register_secret(token)
            if (url, token) != self._token_saved_for:
                try:
                    set_token(url, token)
                except GitLabError as exc:
                    self._report_error(exc)
                    return False
                self._token_saved_for = (url, token)
                self._note(logging.INFO, "Token stored in the system keyring")
        if not self._host.settings.verify_tls:
            warn_tls_disabled_once(url)
        return True

    def _browse_ca(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CA bundle", self.ui.lineEdit_caBundle.text(), "Certificates (*.pem *.crt *.cer);;All files (*)"
        )
        if path:
            self.ui.lineEdit_caBundle.setText(path)

    # -- workers --------------------------------------------------------------------------
    def _snapshot(self) -> AppSettings:
        # Workers get their own copy; the GUI thread may keep editing the settings.
        return dataclasses.replace(self._host.settings)

    def _start(self, name: str, fn: Callable[[WorkerContext], object], on_succeeded, progress: bool = False) -> None:
        key = self._host._workers.start(
            f"{WORKER_PREFIX}{name}",
            fn,
            on_succeeded=on_succeeded,
            on_failed=self._on_failed,
            on_finished=self._on_finished,
            on_progress=self._on_progress if progress else None,
        )
        self._keys[key] = self._generation
        self._update_controls()
        self._host._update_flash_controls()

    def stop(self, *_args) -> None:
        if not self.busy():
            return
        self._note(logging.WARNING, "Stop requested")
        self._set_status("Stopping…")
        self._stop_workers(wait=False)

    def _stop_workers(self, wait: bool) -> None:
        if not self._keys:
            return
        self._generation += 1  # rule 4: results already queued are now stale
        for key in list(self._keys):
            self._stopped.add(key)
            self._host._workers.cancel(key)
        if not wait:
            return
        if not self._host._workers.wait_idle(DIALOG_CLOSE_TIMEOUT_S, prefix=WORKER_PREFIX):
            keys = self._host._workers.abandon_running(prefix=WORKER_PREFIX)
            log.warning("GitLab work did not stop within %.0f s; abandoned: %s", DIALOG_CLOSE_TIMEOUT_S, keys)
            for key in keys:
                self._keys.pop(key, None)
                self._stopped.discard(key)
            self._update_controls()

    def _on_progress(self, percent, message: str) -> None:
        if all(self._stale(key) for key in self._keys):
            return
        bar = self.ui.progressBar_download
        if percent is None:
            bar.setRange(0, 0)
        else:
            bar.setRange(0, 100)
            bar.setValue(percent)
        self._set_status(message)

    def _on_failed(self, key: str, exc: BaseException) -> None:
        if self._stale(key):
            log.debug("Dropping the result of stopped GitLab work %s: %s", key, exc)
            return
        self._reset_progress()
        if isinstance(exc, CancelledError):
            self._set_status("Cancelled")
            return
        self._report_error(exc)

    def _report_error(self, exc: BaseException) -> None:
        hint = getattr(exc, "hint", "")
        self._set_status(f"Failed: {exc}", error=True)
        self._note(logging.ERROR, f"{exc}" + (f" (hint: {hint})" if hint else ""))
        self._host.ctx.add_error(exc)  # no flash can run while this modal dialog is open
        self._host.show_error(exc)

    def _on_finished(self, key: str) -> None:
        self._keys.pop(key, None)
        stopped = key in self._stopped
        self._stopped.discard(key)
        if not self.busy():
            if self._downloading_button is not None:
                self._refresh_download_buttons()
                self._downloading_button = None
            if self.ui.progressBar_download.maximum() == 0:
                self._reset_progress()
            if stopped:
                self._reset_progress()
                self._set_status("Cancelled")
        self._update_controls()
        self._host._update_flash_controls()

    # -- CI artifact tab ---------------------------------------------------------------
    def load_refs(self, *_args) -> None:
        if self.busy() or not self._commit_connection():
            return
        project = self.ci_project()
        factory, settings = self._host._client_factory, self._snapshot()

        def job(ctx: WorkerContext):
            client = factory(settings)
            project_id = client.get_project_id(project)
            return client.list_refs(project_id)

        self._note(logging.INFO, f"Loading branches and tags of {project}")
        self._busy_progress("Loading branches/tags…")
        self._start("refs", job, self._on_refs_loaded)

    def _on_refs_loaded(self, key: str, refs) -> None:
        if self._stale(key):
            return
        combo = self.ui.comboBox_ref
        current = combo.currentText().strip()
        combo.blockSignals(True)
        combo.clear()
        for ref in refs:
            combo.addItem(ref.name)
            if ref.kind == "tag":
                combo.setItemData(combo.count() - 1, "tag", Qt.ItemDataRole.ToolTipRole)
        names = [ref.name for ref in refs]
        if current:
            combo.setEditText(current)
        elif names:
            combo.setCurrentIndex(names.index("main") if "main" in names else 0)
        combo.blockSignals(False)
        self._note(logging.INFO, f"Loaded {len(refs)} branches/tags")
        self._set_status("Ready")

    def browse_jobs(self, *_args) -> None:
        if self.busy() or not self._commit_connection():
            return
        ref = self._current_ref()
        if not ref:
            self._fail_input("Choose a branch or tag first (Load branches/tags).")
            return
        project, job_filter = self.ci_project(), self._host.profile.gitlab.job_filter
        factory, settings = self._host._client_factory, self._snapshot()

        def job(ctx: WorkerContext):
            client = factory(settings)
            project_id = client.get_project_id(project)
            return project, project_id, ref, browse_jobs(client, project_id, ref, job_filter, cancel=ctx.cancel)

        self._note(logging.INFO, f"Listing jobs '{job_filter}' with artifacts on {ref}")
        self._busy_progress("Loading jobs…")
        self._start("jobs", job, self._on_jobs_loaded)

    def _on_jobs_loaded(self, key: str, result) -> None:
        if self._stale(key):
            return
        project, project_id, ref, rows = result
        self._fill_jobs(rows, (project, project_id))
        names = sorted({row.job_name for row in rows})
        combo = self.ui.comboBox_jobName
        typed = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(names)
        combo.setEditText(typed)
        combo.blockSignals(False)
        if rows:
            self._note(logging.INFO, f"Found {len(rows)} job(s) with artifacts on {ref}")
        else:
            self._note(logging.WARNING, f"No job with artifacts on {ref} matches the profile filter")
        self._set_status("Ready")

    def _fill_jobs(self, rows: list[JobRow], project: tuple[str, int] | None) -> None:
        self._job_rows = rows
        self._jobs_project = project
        table = self.ui.tableWidget_jobs
        table.clearSelection()
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            cells = (f"#{row.pipeline_id}", row.job_name, row.ref, row.status, row.when)
            for column, text in enumerate(cells):
                table.setItem(index, column, QTableWidgetItem(text))
            button = QPushButton()
            # GUI-thread signal from a GUI-thread widget: a partial is fine here; the lambda
            # ban (threading rule 8) is about signals emitted from pool threads.
            button.clicked.connect(partial(self._download_job_row, index))
            table.setCellWidget(index, JOB_DOWNLOAD_COLUMN, button)
        self._refresh_download_buttons()

    def _refresh_download_buttons(self) -> None:
        settings = self._host.settings
        if self._jobs_project is not None:
            cache = ArtifactCache(settings.resolved_cache_dir())
            _, project_id = self._jobs_project
            for index, row in enumerate(self._job_rows):
                button = self.ui.tableWidget_jobs.cellWidget(index, JOB_DOWNLOAD_COLUMN)
                button.setText("Cached" if cache.has(project_id, row.job_id) else "Download")
        if self._versions_project is not None:
            cache = ArtifactCache(settings.resolved_package_cache_dir())
            _, project_id = self._versions_project
            for index, version in enumerate(self._versions):
                button = self.ui.tableWidget_versions.cellWidget(index, VERSION_DOWNLOAD_COLUMN)
                button.setText("Cached" if cache.has(project_id, version.id) else "Download")

    def job_button(self, index: int) -> QPushButton:
        return self.ui.tableWidget_jobs.cellWidget(index, JOB_DOWNLOAD_COLUMN)

    def version_button(self, index: int) -> QPushButton:
        return self.ui.tableWidget_versions.cellWidget(index, VERSION_DOWNLOAD_COLUMN)

    def _on_job_double_clicked(self, row: int, _column: int) -> None:
        self._download_job_row(row)

    def _download_job_row(self, index: int, *_args) -> None:
        if self.busy() or not 0 <= index < len(self._job_rows) or not self._commit_connection():
            return
        self._start_job_download(self._job_rows[index], self.job_button(index))

    def download_selected(self, *_args) -> None:
        """The selected row's job; with no row selected, the newest successful job of ref + job name."""
        if self.busy() or not self._commit_connection():
            return
        selected = self.ui.tableWidget_jobs.selectionModel().selectedRows()
        if selected:
            index = selected[0].row()
            self._start_job_download(self._job_rows[index], self.job_button(index))
            return
        ref = self._current_ref()
        if not ref:
            self._fail_input("Choose a branch or tag first (Load branches/tags).")
            return
        project, job_filter, job_name = self.ci_project(), self._host.profile.gitlab.job_filter, self._job_name()
        factory, settings = self._host._client_factory, self._snapshot()
        cache_root, max_jobs = settings.resolved_cache_dir(), settings.max_cached_jobs

        def job(ctx: WorkerContext):
            client = factory(settings)
            project_id = client.get_project_id(project)
            row = find_latest_job(client, project_id, ref, job_filter, job_name, cancel=ctx.cancel)
            ctx.progress(None, f"Job #{row.job_id} {row.job_name} (pipeline #{row.pipeline_id})")
            cache = ArtifactCache(cache_root, max_jobs)
            return fetch_ci_artifact(client, project, project_id, row, cache, byte_progress(ctx), ctx.cancel)

        wanted = f"'{job_name}'" if job_name else f"matching '{job_filter}'"
        self._note(logging.INFO, f"Looking for the newest successful job {wanted} on {ref}")
        self._busy_progress("Looking for the newest job…")
        self._start("download", job, self._on_download_succeeded, progress=True)

    def _start_job_download(self, row: JobRow, button: QPushButton | None) -> None:
        project, project_id = self._jobs_project
        factory, settings = self._host._client_factory, self._snapshot()
        cache_root, max_jobs = settings.resolved_cache_dir(), settings.max_cached_jobs

        def job(ctx: WorkerContext):
            client = factory(settings)
            cache = ArtifactCache(cache_root, max_jobs)
            return fetch_ci_artifact(client, project, project_id, row, cache, byte_progress(ctx), ctx.cancel)

        self._mark_downloading(button)
        self._note(logging.INFO, f"Downloading the artifact of job #{row.job_id} {row.job_name}")
        self._busy_progress("Starting download…")
        self._start("download", job, self._on_download_succeeded, progress=True)

    def _mark_downloading(self, button: QPushButton | None) -> None:
        self._downloading_button = button
        if button is not None:
            button.setText("Downloading…")

    def _on_download_succeeded(self, key: str, result) -> None:
        if self._stale(key):
            log.info("Download finished after Stop/close; not loading it")
            return
        path, source = result
        self.ui.progressBar_download.setRange(0, 100)
        self.ui.progressBar_download.setValue(100)
        self._set_status(f"Ready: {source.title}")
        self._note(logging.INFO, f"Firmware ready: {source.title} ({source.cache_note}) at {path}")
        self.firmwareReady.emit(path, source)
        self.accept()

    # -- Package Registry tab ------------------------------------------------------------
    def _package_fields(self) -> tuple[str, str] | None:
        project = self.ui.lineEdit_pkgProject.text().strip()
        name = self.ui.lineEdit_packageName.text().strip()
        if not project or not name:
            self._fail_input("Enter the package project and the package name first.")
            return None
        return project, name

    def fetch_latest(self, *_args) -> None:
        if self.busy() or not self._commit_connection():
            return
        fields = self._package_fields()
        if fields is None:
            return
        project, name = fields
        factory, settings = self._host._client_factory, self._snapshot()
        cache_root, max_jobs = settings.resolved_package_cache_dir(), settings.max_cached_jobs

        def job(ctx: WorkerContext):
            client = factory(settings)
            project_id = client.get_project_id(project)
            version = latest_package(client, project_id, name)
            ctx.progress(None, f"Latest version: {version.version}")
            cache = ArtifactCache(cache_root, max_jobs)
            return fetch_package(client, project, project_id, version, cache, byte_progress(ctx), ctx.cancel)

        self._note(logging.INFO, f"Fetching the latest version of package {name} from {project}")
        self._busy_progress("Looking for the latest version…")
        self._start("download", job, self._on_download_succeeded, progress=True)

    def browse_versions(self, *_args) -> None:
        if self.busy() or not self._commit_connection():
            return
        fields = self._package_fields()
        if fields is None:
            return
        project, name = fields
        factory, settings = self._host._client_factory, self._snapshot()

        def job(ctx: WorkerContext):
            client = factory(settings)
            project_id = client.get_project_id(project)
            return project, project_id, client.list_package_versions(project_id, name, limit=VERSIONS_TO_LIST)

        self._note(logging.INFO, f"Listing versions of package {name}")
        self._busy_progress("Loading versions…")
        self._start("versions", job, self._on_versions_loaded)

    def _on_versions_loaded(self, key: str, result) -> None:
        if self._stale(key):
            return
        project, project_id, versions = result
        self._versions = versions
        self._versions_project = (project, project_id)
        table = self.ui.tableWidget_versions
        table.clearSelection()
        table.setRowCount(len(versions))
        for index, version in enumerate(versions):
            table.setItem(index, 0, QTableWidgetItem(version.version))
            table.setItem(index, 1, QTableWidgetItem(short_timestamp(version.created_at)))
            button = QPushButton()
            button.clicked.connect(partial(self._download_version_row, index))  # GUI-thread signal
            table.setCellWidget(index, VERSION_DOWNLOAD_COLUMN, button)
        self._refresh_download_buttons()
        self._note(logging.INFO, f"Found {len(versions)} version(s)")
        self._set_status("Ready")

    def _on_version_double_clicked(self, row: int, _column: int) -> None:
        self._download_version_row(row)

    def _download_version_row(self, index: int, *_args) -> None:
        if self.busy() or not 0 <= index < len(self._versions) or not self._commit_connection():
            return
        version = self._versions[index]
        project, project_id = self._versions_project
        factory, settings = self._host._client_factory, self._snapshot()
        cache_root, max_jobs = settings.resolved_package_cache_dir(), settings.max_cached_jobs

        def job(ctx: WorkerContext):
            client = factory(settings)
            cache = ArtifactCache(cache_root, max_jobs)
            return fetch_package(client, project, project_id, version, cache, byte_progress(ctx), ctx.cancel)

        self._mark_downloading(self.version_button(index))
        self._note(logging.INFO, f"Downloading package {version.name} {version.version}")
        self._busy_progress("Starting download…")
        self._start("download", job, self._on_download_succeeded, progress=True)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_gui_gitlab_dialog.py -v` → Expected: `25 passed`.
Run: `~/.venvs/wflash/bin/pytest -k thread -v` → Expected: `36 passed` (5 new `test_gui_thread_*`).
Run: `~/.venvs/wflash/bin/pytest -q` → Expected: `316 passed`.

- [ ] **Step 6: Walkthrough entry**

```markdown
## Phase 1.37: Popup Load from GitLab (CI Artifact + Package Registry)

Logic duyệt/tải GitLab rời khỏi cửa sổ chính sang một dialog modal giống SFlash. Dialog dùng `WorkerRegistry` của cửa sổ chính (key `gitlab-`), giữ đủ 8 quy tắc threading: slot luôn là bound method, `_generation` tăng *trước* mọi lần hủy (Stop, đóng dialog, đóng cửa sổ) nên kết quả đã xếp hàng bị bỏ, đóng dialog chờ có giới hạn và bơm event (chỉ worker `gitlab-`), quá giờ thì "bỏ" worker thay vì treo. Tải qua `firmware_fetch` (core) nên cache và mô tả nguồn giống nhau cho CI và package. Token chỉ vào keyring; log riêng của dialog đi qua `redact()` và logger `wflash.gitlab`. Tắt Verify TLS được phép nhưng ghi WARNING một lần mỗi phiên. Tải xong dialog phát `firmwareReady(path, source)` rồi tự đóng.

### Thay đổi

- **`wflash/gui/gitlab_dialog.py`** (mới): `GitlabDialog`, `default_client_factory` (chuyển từ `gitlab_browser.py`, thêm `verify`), `byte_progress`, `warn_tls_disabled_once`.
- **`tests/gui_stubs.py`**: endpoint Package Registry giả, `patch_keyring`, `SOURCE`, `HostWindow._save_settings/on_firmware_ready`.
- **`tests/test_gui_gitlab_dialog.py`** (mới): 25 test, trong đó 5 test `thread`.

### Đã kiểm tra

- RED / GREEN, `pytest -k thread -v`, `pytest -q`: <kết quả thật>
```

- [ ] **Step 7: Commit**

```bash
git add wflash/gui/gitlab_dialog.py tests/gui_stubs.py tests/test_gui_gitlab_dialog.py docs/walkthrough.md
git commit -m "feat(gui): Load from GitLab popup with CI artifact and package registry tabs" -m "$TRAILER"
```

---

### Task 12: The new main window — one window, Flash/Cancel button, Setting panel, Information tab; remove the GitLab browser and Settings dialog

This is the task that switches the app over, so every test that used a removed widget or name is replaced here, in the same commit.

**Files:**
- Rewrite: `wflash/gui/main_window.ui` (then regenerate `wflash/gui/ui_main_window.py`), `wflash/gui/main_window.py`, `wflash/gui/mapping_table.py`, `wflash/gui/flash_mixin.py`
- Modify: `wflash/__init__.py`, `tests/gui_stubs.py`
- Delete: `wflash/gui/gitlab_browser.py`, `wflash/gui/settings_dialog.py`, `wflash/gui/settings_dialog.ui`, `wflash/gui/ui_settings_dialog.py`, `tests/test_gui_gitlab_browser.py` (its cases now live in `tests/test_gui_gitlab_dialog.py`: browse/download, cache, double-click, cancel, queued completion, HTTP hints, connection error, `default_client_factory`), `tests/test_gui_settings_dialog.py` (replaced by `tests/test_gui_preferences_dialog.py`)
- Rewrite tests: `tests/test_gui_ui_files.py`, `tests/test_gui_mapping_table.py`, `tests/test_gui_flash.py`, `tests/test_gui_main_window.py`, `tests/test_gui_close_window.py`

Tests that break and how each is replaced:

| Old test / name | Why it breaks | Replacement |
|---|---|---|
| `test_gui_ui_files.py` (`settings_dialog.ui`, 4 mapping columns) | file deleted, `#` column added | new `UI_FILES`/`TOP_LEVEL`, 5 columns, tab/flash-header checks, `test_gui_old_widgets_are_gone` |
| `test_gui_mapping_table.py` (`on_artifact_ready`, `label_artifact`, `MISSING_STYLE`, column 1 = target) | renamed hook, card replaces label, theme style, `#` column | `on_firmware_ready(path, SOURCE)`, source card + hint asserts, `missing_style()`, target in column 2, theme repaint test |
| `test_gui_flash.py` (`pushButton_cancelFlash`, `label_step.text() == "Done"`, `on_artifact_ready`) | button removed, label now `Step: …` | Cancel through `pushButton_flash` (`text() == "Cancel"`, `state="flashing"`), `current_step()`, `_set_step()`, stats/ETA asserts |
| `test_gui_main_window.py` (`GitlabBrowserMixin`, `label_project`, `refresh_gitlab`, `pushButton_settings`, `groupBox_gitlab`, `SettingsDialog`, `get_token`/`set_token` patches) | all removed | three-mixin composition, full chain through the dialog, package chain, Preferences/dark-mode tests with a fake `PreferencesDialog`, status bar/title, keyring stays in the dialog tests |
| `test_gui_close_window.py` (`refresh_gitlab`, `comboBox_ref` on the window, `get_token` patch, `label_step`) | moved into the dialog | close during the dialog's fetch and during the dialog's download; `patch_keyring`; `current_step()` |
| `tests/gui_stubs.py` (`artifacts_loaded`, `on_artifact_ready`) | hook renamed | removed |

**Interfaces:**
- Consumes: everything from Tasks 1–11, plus (current) `LogPanelMixin` (`_init_log_panel`, `_detach_log_panel`, `export_bundle`, `log_visible_text`, `refresh_log_theme` from Task 8), `WorkerRegistry`, `DebugContext`, `list_profiles`, `load_profile`, `set_verbose`, `redact`, `FlashWorkflow(adapter, ctx, on_step, on_progress).run(request, cancel)`, `FlashRequest(instance_id, mapping, reset, run, timeout_s)`, `Step`, `build_mapping(profile, root)`, `candidates_for_kind(root, kind)`, `MappingRow` (`kind`, `target`, `pattern`, `candidates`, `selected`, `ok`).
- Produces:
  - `wflash.APP_AUTHOR = "tranph9 (TRAN Phuc)"`.
  - `main_window.ui`: `pushButton_flash` (90×70, dynamic property `state`), `progressBar_flash` (20 px, no text), `label_flashStats`, `label_step` (`Step: Idle`), `label_rollbackWarning`, `frame_settingPanel` (360 px) with `label_settingHeader`, `comboBox_profile`, `pushButton_reloadProfiles`, `pushButton_loadFromGitlab`, `frame_sourceCard` (`label_sourceTitle`, `label_sourceDetail`, `label_sourceCache`), `comboBox_instance`, `pushButton_refreshInstances`, `checkBox_reset` ("Reset target"), `checkBox_run`, `pushButton_preferences`; `tableWidget_mapping` (`# | Type | winIDEA target | Pattern | File`), `label_mappingHint`; `tabWidget_output` with one `tab_information` (log bar + `plainTextEdit_log`); `statusBar_main`.
  - `MappingTableMixin`: `on_firmware_ready(path: Path, source: FirmwareSource)` (replaces `on_artifact_ready(path, label)`; ignored while `_closing` or without a profile; sets `ctx.source`), `clear_mapping()` (also clears the card and `ctx.source`), `refresh_mapping_theme()`, `missing_style() -> str`, constants `NUMBER_COLUMN … FILE_COLUMN = 0 … 4`, `NO_FIRMWARE_TITLE`, `HINT_NO_FIRMWARE`, `HINT_INCOMPLETE`, `HINT_COMPLETE`; red combos also carry the property `missing=True`.
  - `FlashMixin`: one button (`_on_flash_button_clicked` → `start_flash` / `cancel_flash`), `current_step() -> str`, `_set_step(text)`, `STEP_PREFIX = "Step: "`, `program_bytes(rows) -> int`; stats via `ProgressEstimator`; bar property `state` = `""|"done"|"failed"|"cancelled"`. After one Cancel the button is disabled until the rollback finished.
  - `MainWindow(settings, adapter, client_factory=default_client_factory, log_file=None, settings_path=None, pool=None)` = `MappingTableMixin, FlashMixin, LogPanelMixin, QMainWindow`; `gitlab_busy()`, `open_gitlab_dialog()` (refused while flashing/closing/without profile; `prepare()` + window-modal `open()`), `open_preferences()` (replaces `open_settings()`), `apply_dark_mode(dark)`, `label_version`, `label_author`, window title `WFlash v<version>`; `closeEvent` calls `_gitlab_dialog.abort_for_close()` before cancelling and closes a visible dialog after the wait.

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_gui_ui_files.py` with:

```python
"""Designer files: meaningful names, generated modules in sync, every self.ui.<name> exists."""
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

pytestmark = pytest.mark.gui

GUI = Path(__file__).resolve().parents[1] / "wflash" / "gui"
UI_FILES = {
    "main_window.ui": "ui_main_window.py",
    "preferences_dialog.ui": "ui_preferences_dialog.py",
    "gitlab_dialog.ui": "ui_gitlab_dialog.py",
}
TOP_LEVEL = {"MainWindow", "PreferencesDialog", "GitlabDialog"}
# <kind>_<what>, e.g. verticalLayout_gitlabBrowser, tableWidget_mapping.
MEANINGFUL = re.compile(r"^[a-z][A-Za-z]*_[a-z][A-Za-z0-9]*$")


def ui_names(ui_file: Path) -> list[str]:
    root = ET.parse(ui_file).getroot()
    return [el.get("name") for el in root.iter() if el.tag in ("widget", "layout", "spacer")]


def without_uic_version(text: str) -> str:
    # The header names the uic version; a PySide6 upgrade alone must not fail the build.
    return "\n".join(line for line in text.splitlines() if "User Interface Compiler version" not in line)


def uic_executable() -> str | None:
    folder = Path(sys.executable).parent
    for candidate in (folder / "pyside6-uic", folder / "pyside6-uic.exe"):
        if candidate.is_file():
            return str(candidate)
    return shutil.which("pyside6-uic")


@pytest.mark.parametrize("ui_name", sorted(UI_FILES))
def test_gui_every_widget_and_layout_has_a_meaningful_name(ui_name):
    names = ui_names(GUI / ui_name)
    assert names, f"no widgets parsed from {ui_name}"
    bad = [n for n in names if n not in TOP_LEVEL and not (n and MEANINGFUL.match(n))]
    assert bad == [], f"Designer default or unclear names in {ui_name}: {bad}"
    assert len(names) == len(set(names)), "duplicate object names"


@pytest.mark.parametrize("ui_name", sorted(UI_FILES))
def test_gui_generated_module_matches_ui_file(ui_name, tmp_path):
    uic = uic_executable()
    if uic is None:
        pytest.skip("pyside6-uic not found next to the interpreter")
    out = tmp_path / UI_FILES[ui_name]
    subprocess.run([uic, str(GUI / ui_name), "-o", str(out)], check=True)
    committed = (GUI / UI_FILES[ui_name]).read_text(encoding="utf-8")
    assert without_uic_version(committed) == without_uic_version(out.read_text(encoding="utf-8")), (
        f"{UI_FILES[ui_name]} is out of date or hand-edited; run "
        f"pyside6-uic wflash/gui/{ui_name} -o wflash/gui/{UI_FILES[ui_name]}"
    )


def test_gui_every_self_ui_reference_exists_in_a_ui_file():
    known = set()
    for ui_name in UI_FILES:
        known.update(ui_names(GUI / ui_name))
    referenced = set()
    for py in GUI.glob("*.py"):
        if py.name.startswith("ui_"):
            continue
        referenced.update(re.findall(r"self\.ui\.([A-Za-z_][A-Za-z0-9_]*)", py.read_text(encoding="utf-8")))
    referenced -= {"setupUi", "retranslateUi"}  # methods of the generated Ui_ class
    assert sorted(referenced - known) == []


def test_gui_generated_modules_import(qapp):
    from PySide6.QtWidgets import QDialog, QMainWindow

    from wflash.gui.ui_gitlab_dialog import Ui_GitlabDialog
    from wflash.gui.ui_main_window import Ui_MainWindow
    from wflash.gui.ui_preferences_dialog import Ui_PreferencesDialog

    window = QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(window)
    assert ui.tableWidget_mapping.columnCount() == 5
    assert ui.tableWidget_mapping.horizontalHeaderItem(0).text() == "#"
    assert ui.tabWidget_output.count() == 1 and ui.tabWidget_output.tabText(0) == "Information"
    assert ui.comboBox_logLevel.currentText() == "INFO"
    assert ui.label_rollbackWarning.isHidden()
    assert ui.label_step.text() == "Step: Idle"
    assert ui.pushButton_flash.minimumSize().width() == 90 and ui.pushButton_flash.maximumSize().height() == 70
    assert not ui.progressBar_flash.isTextVisible()
    assert ui.frame_settingPanel.maximumWidth() == 360
    preferences = QDialog()
    Ui_PreferencesDialog().setupUi(preferences)
    gitlab = QDialog()
    gitlab_ui = Ui_GitlabDialog()
    gitlab_ui.setupUi(gitlab)
    assert gitlab_ui.tableWidget_jobs.columnCount() == 6
    assert gitlab_ui.tableWidget_versions.columnCount() == 3
    assert gitlab_ui.tabWidget_source.count() == 2
    assert gitlab_ui.checkBox_verifyTls.isChecked()
    window.deleteLater()
    preferences.deleteLater()
    gitlab.deleteLater()


def test_gui_old_widgets_are_gone():
    names = set(ui_names(GUI / "main_window.ui"))
    gone = {
        "groupBox_gitlab", "comboBox_ref", "listWidget_pipelines", "listWidget_jobs",
        "pushButton_downloadArtifact", "progressBar_artifact", "pushButton_settings",
        "pushButton_cancelFlash", "splitter_mainVertical", "splitter_upperHorizontal",
    }
    assert names & gone == set()
    assert not (GUI / "settings_dialog.ui").exists() and not (GUI / "gitlab_browser.py").exists()
```

Replace `tests/test_gui_mapping_table.py` with:

```python
import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent

from tests.gui_stubs import EXAMPLE_PROFILE, SOURCE, HostWindow, make_artifact_tree
from wflash.core.profile import load_profile
from wflash.gui.mapping_table import (
    HINT_COMPLETE,
    HINT_INCOMPLETE,
    HINT_NO_FIRMWARE,
    NO_FIRMWARE_TITLE,
    MappingTableMixin,
    missing_style,
)
from wflash.gui.theme import THEMES, set_theme_name

pytestmark = pytest.mark.gui


class MappingHost(MappingTableMixin, HostWindow):
    def __init__(self, tmp):
        super().__init__(tmp)
        self.profile = load_profile(EXAMPLE_PROFILE)
        self._init_mapping_table()


@pytest.fixture
def host(qtbot, tmp_path):
    window = MappingHost(tmp_path)
    qtbot.addWidget(window)
    yield window
    set_theme_name("light")


def test_gui_starts_with_the_empty_source_card_and_hint(host):
    assert host.ui.label_sourceTitle.text() == NO_FIRMWARE_TITLE
    assert host.ui.label_sourceDetail.text() == "" and host.ui.label_sourceCache.text() == ""
    assert host.ui.label_mappingHint.text() == HINT_NO_FIRMWARE


def test_gui_unique_matches_are_selected_and_the_card_filled(host, tmp_path):
    root = make_artifact_tree(tmp_path / "art")
    host.on_firmware_ready(root, SOURCE)
    table = host.ui.tableWidget_mapping
    assert table.rowCount() == 3
    assert host.mapping_complete()
    assert [table.item(0, c).text() for c in range(4)] == ["1", "Program", "App", "**/*App*.s3"]
    assert [table.item(2, c).text() for c in range(3)] == ["3", "Symbols", "CM7_1"]
    assert host.mapping_combo(0).currentText() == "out/App.s3"
    assert host.mapping_combo(0).styleSheet() == ""
    assert host.ui.label_sourceTitle.text() == SOURCE.title
    assert host.ui.label_sourceDetail.text() == SOURCE.detail
    assert host.ui.label_sourceCache.text() == SOURCE.cache_note
    assert host.ui.frame_sourceCard.toolTip() == str(root)
    assert host.ui.label_mappingHint.text() == HINT_COMPLETE
    assert host.ctx.source == SOURCE.to_dict()
    assert host.flash_control_updates >= 1


def test_gui_ambiguous_and_missing_rows_need_a_manual_choice(host, tmp_path):
    root = make_artifact_tree(
        tmp_path / "art", {"a/App.s3": b"1", "b/App.s3": b"2", "x_cm7_0.elf": b"3", "other.elf": b"4"}
    )
    host.on_firmware_ready(root, SOURCE)
    assert not host.mapping_complete()
    assert host.ui.label_mappingHint.text() == HINT_INCOMPLETE
    program, cm7_1 = host.mapping_combo(0), host.mapping_combo(2)
    assert program.count() == 3  # "-- select file --" + the two candidates
    assert program.styleSheet() == missing_style() and program.property("missing") is True
    assert cm7_1.count() == 3  # "-- select file --" + every .elf in the artifact
    updates = host.flash_control_updates
    program.setCurrentIndex(program.findText("b/App.s3"))
    assert host.flash_control_updates == updates + 1
    assert not host.mapping_complete()
    cm7_1.setCurrentIndex(cm7_1.findText("other.elf"))
    assert host.mapping_complete()
    assert host.ui.label_mappingHint.text() == HINT_COMPLETE
    assert host.mapping_rows()[0].selected == root / "b" / "App.s3"
    assert host.mapping_rows()[2].selected == root / "other.elf"
    assert program.styleSheet() == "" and program.property("missing") is False
    program.setCurrentIndex(0)
    assert not host.mapping_complete()
    assert program.styleSheet() == missing_style()


def test_gui_red_rows_follow_the_theme(host, tmp_path):
    host.on_firmware_ready(make_artifact_tree(tmp_path / "art", {"x_cm7_0.elf": b"3"}), SOURCE)
    program = host.mapping_combo(0)
    assert THEMES["light"]["missing_bg"] in program.styleSheet()
    set_theme_name("dark")
    host.refresh_mapping_theme()
    assert THEMES["dark"]["missing_bg"] in program.styleSheet()
    number = host.ui.tableWidget_mapping.item(0, 0)
    assert number.background().color().name() == THEMES["dark"]["soft"]


def test_gui_clear_mapping(host, tmp_path):
    host.on_firmware_ready(make_artifact_tree(tmp_path / "art"), SOURCE)
    host.clear_mapping()
    assert host.ui.tableWidget_mapping.rowCount() == 0
    assert not host.mapping_complete()
    assert host.artifact_root is None and host.firmware_source is None
    assert host.ui.label_sourceTitle.text() == NO_FIRMWARE_TITLE
    assert host.ui.label_mappingHint.text() == HINT_NO_FIRMWARE
    assert host.ctx.source == {}


def test_gui_no_profile_or_closing_ignores_firmware(host, tmp_path):
    host.profile = None
    host.on_firmware_ready(make_artifact_tree(tmp_path / "art"), SOURCE)
    assert host.ui.tableWidget_mapping.rowCount() == 0
    host.profile = load_profile(EXAMPLE_PROFILE)
    host._closing = True
    host.on_firmware_ready(make_artifact_tree(tmp_path / "art2"), SOURCE)
    assert host.ui.tableWidget_mapping.rowCount() == 0
    assert host.ui.label_sourceTitle.text() == NO_FIRMWARE_TITLE


def test_gui_wheel_over_a_row_combo_does_not_change_the_choice(host, tmp_path, qtbot):
    root = make_artifact_tree(tmp_path / "art", {"a/App.s3": b"1", "b/App.s3": b"2", "x_cm7_0.elf": b"3"})
    host.on_firmware_ready(root, SOURCE)
    combo = host.mapping_combo(0)
    before = combo.currentIndex()
    event = QWheelEvent(
        QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, -120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False,
    )
    assert host.eventFilter(combo, event) is True
    assert combo.currentIndex() == before
    assert host.eventFilter(combo, QEvent(QEvent.Type.Enter)) is False
```

Replace `tests/test_gui_flash.py` with:

```python
import logging
import threading

import pytest
from PySide6.QtCore import Qt

from tests.gui_stubs import EXAMPLE_PROFILE, OLD_APP, OLD_CM7_0, SOURCE, HostWindow, make_artifact_tree
from wflash.core.errors import FlashError, MappingError, WinIDEAError
from wflash.core.fake_adapter import FakeWinIDEAAdapter
from wflash.core.flash_workflow import Step
from wflash.core.profile import load_profile
from wflash.core.progress import IDLE_TEXT
from wflash.gui.flash_mixin import FlashMixin, program_bytes, safe_list_instances
from wflash.gui.mapping_table import MappingTableMixin

pytestmark = pytest.mark.gui


class FlashHost(FlashMixin, MappingTableMixin, HostWindow):
    def __init__(self, tmp, adapter):
        super().__init__(tmp, adapter=adapter)
        self._init_mapping_table()
        self._init_flash()
        self.profile = load_profile(EXAMPLE_PROFILE)
        self.refresh_instances()


class RestoreFails(FakeWinIDEAAdapter):
    """Download fails, and writing the old App path back fails too: rollback_failed."""

    def set_program_path(self, name, path):
        if path == OLD_APP:
            raise WinIDEAError("restore App failed")
        super().set_program_path(name, path)


def make_host(qtbot, tmp_path, adapter):
    w = FlashHost(tmp_path, adapter)
    qtbot.addWidget(w)
    qtbot.waitUntil(lambda: w.ui.comboBox_instance.count() == 1, timeout=3000)
    w.on_firmware_ready(make_artifact_tree(tmp_path / "art"), SOURCE)
    return w


def wait_idle(w, qtbot):
    qtbot.waitUntil(lambda: not w.flash_active() and w.ui.pushButton_flash.isEnabled(), timeout=10000)


def test_gui_instance_combo_holds_a_dict(qtbot, tmp_path):
    w = make_host(qtbot, tmp_path, FakeWinIDEAAdapter(download_seconds=0.1))
    data = w.ui.comboBox_instance.currentData()
    assert data == {"instance_id": "fake-1", "workspace": r"C:\fake\SAF85xx\SAF85xx.xjrf", "tcp_port": 5313}
    assert w.selected_instance()["instance_id"] == "fake-1"


def test_gui_no_instance_keeps_flash_disabled(qtbot, tmp_path):
    w = FlashHost(tmp_path, FakeWinIDEAAdapter(fail_on={"list_instances"}))
    qtbot.addWidget(w)
    qtbot.waitUntil(lambda: not w._workers.running_keys(), timeout=3000)
    w.on_firmware_ready(make_artifact_tree(tmp_path / "art"), SOURCE)
    assert w.ui.comboBox_instance.count() == 0
    assert not w.ui.pushButton_flash.isEnabled()


def test_gui_list_instances_failure_returns_empty_list():
    class Broken(FakeWinIDEAAdapter):
        def list_instances(self):
            raise OSError("isystem.connect not loadable")

    assert safe_list_instances(Broken()) == []


def test_gui_flash_happy_path(qtbot, tmp_path):
    adapter = FakeWinIDEAAdapter(download_seconds=0.2)
    w = make_host(qtbot, tmp_path, adapter)
    assert w.ui.pushButton_flash.isEnabled()
    assert w.ui.label_flashStats.text() == IDLE_TEXT and w.ui.label_step.text() == "Step: Idle"
    qtbot.mouseClick(w.ui.pushButton_flash, Qt.MouseButton.LeftButton)
    assert w.flash_active()
    # The same button is now a red Cancel.
    assert w.ui.pushButton_flash.isEnabled() and w.ui.pushButton_flash.text() == "Cancel"
    assert w.ui.pushButton_flash.property("state") == "flashing"
    assert not w.ui.tableWidget_mapping.isEnabled() and not w.ui.pushButton_exportBundle.isEnabled()
    assert not w.ui.pushButton_loadFromGitlab.isEnabled() and not w.ui.pushButton_preferences.isEnabled()
    qtbot.waitUntil(lambda: w.current_step() == Step.DONE.value, timeout=5000)
    wait_idle(w, qtbot)
    assert adapter.programs["App"] == str((tmp_path / "art" / "out" / "App.s3").resolve())
    assert adapter.target_state == "halted"
    assert w.ui.progressBar_flash.value() == 100
    assert w.ui.progressBar_flash.property("state") == "done"
    assert w.ui.label_flashStats.text().startswith("100% | Time: ")
    assert w.ui.label_flashStats.text().endswith(" KB/s")
    assert w.ui.pushButton_flash.text() == "Flash" and w.ui.pushButton_flash.property("state") == "idle"
    assert w.errors_shown == []
    assert not w.ui.label_rollbackWarning.isVisibleTo(w)


def test_gui_flash_run_after_reset(qtbot, tmp_path):
    adapter = FakeWinIDEAAdapter(download_seconds=0.05)
    w = make_host(qtbot, tmp_path, adapter)
    w.ui.checkBox_run.setChecked(True)
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DONE.value, timeout=5000)
    assert adapter.target_state == "running"


def test_gui_flash_download_failure_rolls_back_and_shows_error(qtbot, tmp_path):
    adapter = FakeWinIDEAAdapter(download_seconds=0.1, fail_on={"download"})
    w = make_host(qtbot, tmp_path, adapter)
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == "Failed", timeout=5000)
    wait_idle(w, qtbot)
    assert isinstance(w.errors_shown[0], FlashError)
    assert w.ui.label_flashStats.text().startswith("Failed | Time: ")
    assert w.ui.progressBar_flash.property("state") == "failed"
    assert adapter.programs["App"] == OLD_APP
    assert adapter.applications["CM7_0"] == OLD_CM7_0
    assert not w.ui.label_rollbackWarning.isVisibleTo(w)
    assert any("Fake failure" in e for e in w.ctx.errors)
    assert "after_rollback" in w.ctx.snapshots


def test_gui_missing_workspace_entry_is_a_mapping_error(qtbot, tmp_path):
    adapter = FakeWinIDEAAdapter(download_seconds=0.1, programs={"Other": r"C:\x.s3"})
    w = make_host(qtbot, tmp_path, adapter)
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == "Failed", timeout=5000)
    assert isinstance(w.errors_shown[0], MappingError)
    assert "Other" in w.errors_shown[0].hint


def test_gui_flash_rollback_failure_is_shown_to_the_user(qtbot, tmp_path):
    adapter = RestoreFails(download_seconds=0.1, fail_on={"download"})
    w = make_host(qtbot, tmp_path, adapter)
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == "Failed", timeout=5000)
    wait_idle(w, qtbot)
    assert w.ui.label_rollbackWarning.isVisibleTo(w)
    exc = w.errors_shown[0]
    assert getattr(exc, "rollback_failed", False) is True
    assert exc.hint.startswith("ROLLBACK FAILED")
    # The next flash hides the warning again until a new failure.
    adapter.fail_on = set()
    w.start_flash()
    assert not w.ui.label_rollbackWarning.isVisibleTo(w)
    qtbot.waitUntil(lambda: w.current_step() == Step.DONE.value, timeout=5000)


def test_gui_thread_cancel_flash_mid_download_rolls_back(qtbot, tmp_path):
    adapter = FakeWinIDEAAdapter(download_seconds=5)
    w = make_host(qtbot, tmp_path, adapter)
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DOWNLOAD.value, timeout=3000)
    qtbot.mouseClick(w.ui.pushButton_flash, Qt.MouseButton.LeftButton)  # "Cancel"
    assert not w.ui.pushButton_flash.isEnabled()  # one cancel; now it waits for the rollback
    w.cancel_flash()  # a second cancel is harmless
    qtbot.waitUntil(lambda: w.current_step() == "Cancelled", timeout=3000)
    wait_idle(w, qtbot)
    assert adapter.programs["App"] == OLD_APP
    assert adapter.connected_to is None
    assert w.errors_shown == []
    assert w.ui.label_flashStats.text().startswith("Cancelled | Time: ")
    assert w.ui.pushButton_flash.text() == "Flash"


def test_gui_thread_double_flash_starts_one_worker(qtbot, tmp_path):
    adapter = FakeWinIDEAAdapter(download_seconds=0.3)
    w = make_host(qtbot, tmp_path, adapter)
    w.start_flash()
    w.start_flash()
    assert [k for k in w._workers.running_keys() if k.startswith("flash")] == [w._flash_key]
    qtbot.waitUntil(lambda: w.current_step() == Step.DONE.value, timeout=5000)
    assert adapter.calls.count("download") == 1


def test_gui_incomplete_mapping_blocks_flash(qtbot, tmp_path):
    w = make_host(qtbot, tmp_path, FakeWinIDEAAdapter(download_seconds=0.1))
    combo = w.mapping_combo(0)
    combo.setCurrentIndex(0)
    assert not w.ui.pushButton_flash.isEnabled()
    w.start_flash()
    assert not w.flash_active()


def test_gui_thread_cancel_during_download_with_failed_restore_warns(qtbot, tmp_path, caplog):
    adapter = RestoreFails(download_seconds=5)
    w = make_host(qtbot, tmp_path, adapter)
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DOWNLOAD.value, timeout=3000)
    with caplog.at_level(logging.CRITICAL):
        w.cancel_flash()
        qtbot.waitUntil(lambda: bool(w.errors_shown), timeout=5000)
        wait_idle(w, qtbot)
    assert w.ui.label_rollbackWarning.isVisibleTo(w)
    assert any(r.levelno == logging.CRITICAL for r in caplog.records)
    assert getattr(w.errors_shown[0], "rollback_failed", False) is True


def test_gui_thread_flash_refused_while_instances_worker_runs(qtbot, tmp_path):
    gate = threading.Event()

    class Gated(FakeWinIDEAAdapter):
        def list_instances(self):
            gate.wait(5)
            return super().list_instances()

    adapter = Gated(download_seconds=0.1)
    gate.set()
    w = make_host(qtbot, tmp_path, adapter)
    gate.clear()
    w.refresh_instances()
    assert w._workers.is_running(w._instances_key)
    assert not w.ui.pushButton_flash.isEnabled()
    w.start_flash()
    assert not w.flash_active()
    assert "download" not in adapter.calls
    gate.set()
    qtbot.waitUntil(lambda: not w._workers.is_running(w._instances_key), timeout=3000)
    qtbot.waitUntil(w.ui.pushButton_flash.isEnabled, timeout=3000)


def test_gui_thread_second_cancel_keeps_label_step(qtbot, tmp_path):
    w = make_host(qtbot, tmp_path, FakeWinIDEAAdapter(download_seconds=5))
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DOWNLOAD.value, timeout=3000)
    w.cancel_flash()
    w._set_step("sentinel")
    w.cancel_flash()
    assert w.current_step() == "sentinel"
    qtbot.waitUntil(lambda: w.current_step() == "Cancelled", timeout=3000)
    wait_idle(w, qtbot)


def test_gui_thread_eta_and_speed_shown_while_downloading(qtbot, tmp_path):
    w = make_host(qtbot, tmp_path, FakeWinIDEAAdapter(download_seconds=1.0))
    w.start_flash()
    assert w.ui.label_flashStats.text() == "ETA: calculating\u2026 | Speed: --"
    qtbot.waitUntil(lambda: "ETA: 0" in w.ui.label_flashStats.text(), timeout=3000)
    text = w.ui.label_flashStats.text()
    assert text.split("%")[0].isdigit() and "KB/s" in text
    qtbot.waitUntil(lambda: w.current_step() == Step.DONE.value, timeout=5000)
    wait_idle(w, qtbot)


def test_gui_program_bytes_counts_only_mapped_program_files(qtbot, tmp_path):
    w = make_host(qtbot, tmp_path, FakeWinIDEAAdapter(download_seconds=0.1))
    assert program_bytes(w.mapping_rows()) == len(b"S0")
    rows = w.mapping_rows()
    rows[0].selected.unlink()
    assert program_bytes(rows) == 0
```

Replace `tests/test_gui_main_window.py` with:

```python
import json
import zipfile
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from tests.gui_stubs import (
    GITLAB_URL,
    OLD_APP,
    PKG_NAME,
    PKG_PROJECT,
    SOURCE,
    TOKEN,
    FakeGitLabSession,
    SessionClientFactory,
    make_artifact_tree,
    patch_keyring,
    write_profiles,
)
from wflash import APP_AUTHOR, __version__
from wflash.core.errors import GitLabError, WinIDEAError
from wflash.core.fake_adapter import FakeWinIDEAAdapter
from wflash.core.flash_workflow import Step
from wflash.core.settings import AppSettings
from wflash.gui import main_window as main_window_module
from wflash.gui.flash_mixin import FlashMixin
from wflash.gui.log_panel import LogPanelMixin
from wflash.gui.main_window import MainWindow
from wflash.gui.mapping_table import NO_FIRMWARE_TITLE, MappingTableMixin
from wflash.gui.style import apply_theme
from wflash.gui.theme import THEMES, current_theme_name

pytestmark = pytest.mark.gui


@pytest.fixture
def env(qtbot, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda parent, title, text: shown.append((title, text)))
    patch_keyring(monkeypatch)
    profiles = write_profiles(tmp_path / "profiles")
    settings = AppSettings(gitlab_url=GITLAB_URL, profiles_dir=str(profiles), cache_dir=str(tmp_path / "cache"))
    adapter = FakeWinIDEAAdapter(download_seconds=0.2)
    session = FakeGitLabSession()
    window = MainWindow(
        settings,
        adapter,
        client_factory=SessionClientFactory(session),
        settings_path=tmp_path / "settings.json",
    )
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: window.ui.comboBox_instance.count() == 1, timeout=3000)
    yield SimpleNamespace(window=window, adapter=adapter, session=session, shown=shown, tmp=tmp_path)
    apply_theme(QApplication.instance(), False)
    QApplication.instance().setStyleSheet("")


class FakePreferences:
    """Stands in for PreferencesDialog: accepts with the settings given to `result`."""

    result = None
    cache_cleared = False

    def __init__(self, settings, parent):
        self._settings = settings

    def exec(self):
        return QDialog.DialogCode.Accepted

    def result_settings(self):
        return FakePreferences.result(self._settings)


def test_gui_main_window_is_composed_from_three_mixins():
    for mixin in (MappingTableMixin, FlashMixin, LogPanelMixin):
        assert issubclass(MainWindow, mixin)
    assert not hasattr(main_window_module, "GitlabBrowserMixin")


def test_gui_profile_loaded_on_start(env):
    w = env.window
    assert w.profile.name == "SAF85xx_Radar"
    assert json.loads((env.tmp / "settings.json").read_text())["last_profile"] == "saf.yaml"
    assert w.ui.pushButton_loadFromGitlab.isEnabled()
    assert not w.ui.pushButton_flash.isEnabled()
    assert w.ui.checkBox_reset.isChecked() and not w.ui.checkBox_run.isChecked()
    assert w.ui.label_sourceTitle.text() == NO_FIRMWARE_TITLE


def test_gui_title_and_status_bar_show_version_and_author(env):
    w = env.window
    assert w.windowTitle() == f"WFlash v{__version__}"
    assert w.label_version.text() == f"Version: v{__version__}"
    assert w.label_author.text() == f"Author: {APP_AUTHOR}"


def test_gui_full_chain_gitlab_dialog_to_flash(env, qtbot):
    w = env.window
    qtbot.mouseClick(w.ui.pushButton_loadFromGitlab, Qt.MouseButton.LeftButton)
    dialog = w._gitlab_dialog
    assert dialog.isVisible() and dialog.isModal()
    dialog.load_refs()
    qtbot.waitUntil(lambda: not dialog.busy(), timeout=3000)
    dialog.browse_jobs()
    qtbot.waitUntil(lambda: dialog.ui.tableWidget_jobs.rowCount() == 1, timeout=3000)
    qtbot.waitUntil(lambda: not dialog.busy(), timeout=3000)
    qtbot.mouseClick(dialog.job_button(0), Qt.MouseButton.LeftButton)
    qtbot.waitUntil(w.mapping_complete, timeout=5000)
    assert not dialog.isVisible()
    assert w.ui.label_sourceTitle.text().endswith("job #7 build_app")
    qtbot.waitUntil(w.ui.pushButton_flash.isEnabled, timeout=3000)
    qtbot.mouseClick(w.ui.pushButton_flash, Qt.MouseButton.LeftButton)
    assert not w.ui.pushButton_preferences.isEnabled() and not w.ui.pushButton_loadFromGitlab.isEnabled()
    w.open_gitlab_dialog()  # refused while flashing
    assert not dialog.isVisible()
    qtbot.waitUntil(lambda: w.current_step() == Step.DONE.value, timeout=5000)
    qtbot.waitUntil(lambda: w.ui.pushButton_flash.text() == "Flash", timeout=3000)
    assert env.adapter.programs["App"].endswith("App.s3") and env.adapter.programs["App"] != OLD_APP
    assert env.adapter.target_state == "halted"
    assert env.shown == []
    assert "Flash completed successfully" in w.log_visible_text()


def test_gui_package_registry_firmware_fills_the_mapping(env, qtbot):
    w = env.window
    w.open_gitlab_dialog()
    dialog = w._gitlab_dialog
    dialog.ui.lineEdit_pkgProject.setText(PKG_PROJECT)
    dialog.ui.lineEdit_packageName.setText(PKG_NAME)
    dialog.fetch_latest()
    qtbot.waitUntil(w.mapping_complete, timeout=5000)
    assert w.ui.label_sourceTitle.text() == f"Package · {PKG_NAME} 1.4.0"
    assert w.ctx.source["kind"] == "package"


def test_gui_ambiguous_mapping_blocks_flash(env):
    root = make_artifact_tree(env.tmp / "art")
    (root / "out" / "y_cm7_0.elf").write_bytes(b"x")
    env.window.on_firmware_ready(root, SOURCE)
    assert not env.window.ui.pushButton_flash.isEnabled()


def test_gui_failure_shows_hint_and_bundle_has_rollback_and_source(env, qtbot):
    env.adapter.fail_on = {"download"}
    w = env.window
    w.on_firmware_ready(make_artifact_tree(env.tmp / "art"), SOURCE)
    w.start_flash()
    qtbot.waitUntil(lambda: bool(env.shown), timeout=5000)
    title, text = env.shown[0]
    assert title == "WFlash error"
    assert "Fake failure" in text and "Hint:" in text and "Export debug bundle" in text
    qtbot.waitUntil(w.ui.pushButton_flash.isEnabled, timeout=3000)
    assert env.adapter.programs["App"] == OLD_APP
    bundle = w.export_bundle(env.tmp / "bundle")
    with zipfile.ZipFile(bundle) as zf:
        assert "Fake failure" in zf.read("errors.txt").decode()
        assert "after_rollback" in zf.read("workspace_snapshots.json").decode()
        assert json.loads(zf.read("source.json"))["title"] == SOURCE.title


def test_gui_rollback_failure_uses_its_own_title(env, qtbot):
    class RestoreFails(FakeWinIDEAAdapter):
        def set_program_path(self, name, path):
            if path == OLD_APP:
                raise WinIDEAError("restore App failed")
            super().set_program_path(name, path)

    w = env.window
    w.adapter = RestoreFails(download_seconds=0.1, fail_on={"download"})
    w.on_firmware_ready(make_artifact_tree(env.tmp / "art"), SOURCE)
    w.start_flash()
    qtbot.waitUntil(lambda: bool(env.shown), timeout=5000)
    assert env.shown[0][0] == "WFlash — rollback failed"
    assert "ROLLBACK FAILED" in env.shown[0][1]
    assert w.ui.label_rollbackWarning.isVisibleTo(w)


def test_gui_bad_profile_shows_error_and_disables_load(qtbot, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda parent, title, text: shown.append(text))
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "bad.yaml").write_text("name: [unclosed", encoding="utf-8")
    w = MainWindow(AppSettings(profiles_dir=str(profiles)), FakeWinIDEAAdapter(), settings_path=tmp_path / "s.json")
    qtbot.addWidget(w)
    assert w.profile is None
    assert shown and "Invalid YAML" in shown[0]
    assert not w.ui.pushButton_loadFromGitlab.isEnabled()
    w.open_gitlab_dialog()
    assert not w._gitlab_dialog.isVisible()


def test_gui_preferences_saved_without_any_token(env, monkeypatch, qtbot):
    from dataclasses import replace

    FakePreferences.result = staticmethod(lambda s: replace(s, verbose=True, max_cached_jobs=3))
    monkeypatch.setattr(main_window_module, "PreferencesDialog", FakePreferences)
    w = env.window
    w.open_preferences()
    assert w.settings.verbose is True and w.settings.max_cached_jobs == 3
    saved = json.loads((env.tmp / "settings.json").read_text())
    assert saved["verbose"] is True and saved["gitlab_url"] == GITLAB_URL
    assert TOKEN not in (env.tmp / "settings.json").read_text()
    main_window_module.log.info("echo %s", TOKEN)
    qtbot.waitUntil(lambda: "echo ***" in w.log_visible_text(), timeout=1000)
    assert TOKEN not in w.log_visible_text()


def test_gui_dark_mode_applies_immediately_and_is_saved(env, monkeypatch, qtbot):
    from dataclasses import replace

    w = env.window
    w.on_firmware_ready(make_artifact_tree(env.tmp / "art", {"x_cm7_0.elf": b"3"}), SOURCE)
    FakePreferences.result = staticmethod(lambda s: replace(s, dark_mode=True))
    monkeypatch.setattr(main_window_module, "PreferencesDialog", FakePreferences)
    w.open_preferences()
    assert current_theme_name() == "dark"
    assert THEMES["dark"]["primary"] in QApplication.instance().styleSheet()
    assert json.loads((env.tmp / "settings.json").read_text())["dark_mode"] is True
    assert "Theme: dark" in w.log_visible_text()
    FakePreferences.result = staticmethod(lambda s: replace(s, dark_mode=False))
    w.open_preferences()
    assert current_theme_name() == "light"
    assert THEMES["light"]["primary"] in QApplication.instance().styleSheet()


def test_gui_preferences_cache_cleared_unloads_the_firmware(env, monkeypatch):
    class ClearingPreferences(FakePreferences):
        cache_cleared = True

        def exec(self):
            return QDialog.DialogCode.Rejected

    w = env.window
    w.on_firmware_ready(make_artifact_tree(env.tmp / "art"), SOURCE)
    monkeypatch.setattr(main_window_module, "PreferencesDialog", ClearingPreferences)
    w.open_preferences()
    assert w.mapping_rows() == [] and w.ui.label_sourceTitle.text() == NO_FIRMWARE_TITLE


def test_gui_show_error_redacts_unregistered_token(env):
    token = "glpat-" + "Ab3dEf6hIj9kLm2nOp5q"
    env.shown.clear()
    env.window.show_error(GitLabError(f"401 for {token}", hint=f"retry with {token}"))
    title, text = env.shown[0]
    assert "***" in text and token not in text


def test_gui_profile_path_recorded_even_when_profile_is_broken(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    bad = profiles / "bad.yaml"
    bad.write_text("name: [unclosed", encoding="utf-8")
    w = MainWindow(AppSettings(profiles_dir=str(profiles)), FakeWinIDEAAdapter(), settings_path=tmp_path / "s.json")
    qtbot.addWidget(w)
    assert w.profile is None
    assert w.ctx.profile_path == bad
```

Replace `tests/test_gui_close_window.py` with:

```python
"""closeEvent while work is running: bounded, no deadlock, rollback finished before close returns."""
import logging
import threading
import time
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMessageBox

from tests.gui_stubs import (
    GITLAB_URL,
    OLD_APP,
    OLD_CM7_0,
    SOURCE,
    FakeGitLabSession,
    SessionClientFactory,
    make_artifact_tree,
    patch_keyring,
    write_profiles,
)
from wflash.core.errors import WinIDEAError
from wflash.core.fake_adapter import FakeWinIDEAAdapter
from wflash.core.flash_workflow import Step
from wflash.core.settings import AppSettings
from wflash.gui import main_window as main_window_module
from wflash.gui.main_window import MainWindow

pytestmark = pytest.mark.gui

THREADING_WARNINGS = ("QThread: Destroyed", "Signal source has been deleted", "QObject::", "Cannot queue")


@pytest.fixture
def make(qtbot, tmp_path, monkeypatch):
    shown, questions = [], []
    monkeypatch.setattr(QMessageBox, "critical", lambda parent, title, text: shown.append((title, text)))

    def question(parent, title, text, *args):
        questions.append(text)
        return env.answer

    monkeypatch.setattr(QMessageBox, "question", question)
    patch_keyring(monkeypatch)
    env = SimpleNamespace(shown=shown, questions=questions, answer=QMessageBox.StandardButton.Yes)

    def factory(adapter, session=None):
        profiles = write_profiles(tmp_path / "profiles")
        window = MainWindow(
            AppSettings(gitlab_url=GITLAB_URL, profiles_dir=str(profiles), cache_dir=str(tmp_path / "cache")),
            adapter,
            client_factory=SessionClientFactory(session or FakeGitLabSession()),
            settings_path=tmp_path / "settings.json",
        )
        qtbot.addWidget(window)
        qtbot.waitUntil(lambda: window.ui.comboBox_instance.count() == 1, timeout=3000)
        window.on_firmware_ready(make_artifact_tree(tmp_path / "art"), SOURCE)
        env.window = window
        return window

    env.factory = factory
    return env


def no_threading_warnings(qtlog):
    return [r.message for r in qtlog.records if any(p in r.message for p in THREADING_WARNINGS)] == []


def test_gui_thread_close_during_flash_cancels_and_rolls_back_before_returning(make, qtbot, qtlog):
    adapter = FakeWinIDEAAdapter(download_seconds=10)
    w = make.factory(adapter)
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DOWNLOAD.value, timeout=3000)
    t0 = time.monotonic()
    w.close()
    elapsed = time.monotonic() - t0
    assert elapsed < 3.0, f"close took {elapsed:.1f}s (deadlock?)"
    assert make.questions and "flash is in progress" in make.questions[0]
    assert w._closing
    # Rollback ran to completion before close() returned.
    assert adapter.programs["App"] == OLD_APP and adapter.applications["CM7_0"] == OLD_CM7_0
    assert adapter.connected_to is None
    assert w._workers.running_keys() == []
    assert make.shown == []  # no dialogs from completion slots while closing
    assert w.log_handler not in logging.getLogger("wflash").handlers
    assert no_threading_warnings(qtlog)


def test_gui_thread_close_declined_keeps_flashing(make, qtbot):
    adapter = FakeWinIDEAAdapter(download_seconds=0.5)
    w = make.factory(adapter)
    make.answer = QMessageBox.StandardButton.No
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DOWNLOAD.value, timeout=3000)
    w.close()
    assert not w._closing and w.flash_active()
    qtbot.waitUntil(lambda: w.current_step() == Step.DONE.value, timeout=5000)
    assert adapter.programs["App"] != OLD_APP
    make.answer = QMessageBox.StandardButton.Yes


def test_gui_thread_close_during_gitlab_fetch_before_any_flash(make, qtbot, qtlog):
    session = FakeGitLabSession(delay_s=0.5)
    w = make.factory(FakeWinIDEAAdapter(), session)
    w.clear_mapping()
    w.open_gitlab_dialog()
    dialog = w._gitlab_dialog
    dialog.load_refs()
    assert w.gitlab_busy() and not w.flash_active()
    t0 = time.monotonic()
    w.close()
    assert time.monotonic() - t0 < 3.0
    assert make.questions == []  # nothing to confirm without a flash
    assert w._workers.running_keys() == []
    assert dialog.ui.comboBox_ref.count() == 0  # the late refs result was settled, not shown
    assert not dialog.isVisible()
    assert make.shown == []
    assert no_threading_warnings(qtlog)


def test_gui_thread_close_during_dialog_download_loads_nothing(make, qtbot, qtlog):
    session = FakeGitLabSession(chunk_delay_s=0.02)
    w = make.factory(FakeWinIDEAAdapter(), session)
    w.clear_mapping()
    w.open_gitlab_dialog()
    dialog = w._gitlab_dialog
    dialog.ui.comboBox_ref.setEditText("main")
    dialog.download_selected()
    qtbot.waitUntil(lambda: dialog.ui.progressBar_download.value() > 0, timeout=3000)
    t0 = time.monotonic()
    w.close()
    assert time.monotonic() - t0 < 3.0
    assert w._workers.running_keys() == []
    assert w.mapping_rows() == []
    assert not dialog.isVisible()
    assert make.shown == []
    assert no_threading_warnings(qtlog)


def test_gui_thread_close_reports_rollback_failure_after_the_wait(make, qtbot):
    class RestoreFails(FakeWinIDEAAdapter):
        def set_program_path(self, name, path):
            if path == OLD_APP:
                raise WinIDEAError("restore App failed")
            super().set_program_path(name, path)

    w = make.factory(RestoreFails(download_seconds=10))
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DOWNLOAD.value, timeout=3000)
    w.close()
    assert len(make.shown) == 1
    assert make.shown[0][0] == "WFlash — rollback failed"


def test_gui_thread_close_wait_is_bounded_when_a_worker_ignores_cancel(make, qtbot, monkeypatch, caplog):
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: warnings.append((title, text)))
    release = threading.Event()

    class Stuck(FakeWinIDEAAdapter):
        def download(self, progress, cancel, timeout_s):
            release.wait(5)  # ignores the cancel token on purpose

    monkeypatch.setattr(main_window_module, "CLOSE_TIMEOUT_S", 0.5)
    w = make.factory(Stuck())
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DOWNLOAD.value, timeout=3000)
    worker = w._workers.worker(w._flash_key)
    w._flash_key_for_test = w._flash_key
    t0 = time.monotonic()
    with caplog.at_level(logging.CRITICAL, logger="wflash"):
        w.close()
    assert time.monotonic() - t0 < 2.0
    assert w._workers.running_keys() == []  # parked in workers._ABANDONED, not dropped
    assert any(r.levelno == logging.CRITICAL and w._flash_key_for_test in r.message for r in caplog.records)
    assert len(warnings) == 1 and warnings[0][0] == "WFlash — flash still running"
    assert "winIDEA" in warnings[0][1]
    release.set()
    assert worker.done.wait(5)


def test_gui_thread_close_logs_rollback_failure_critical_and_records_it(make, qtbot, caplog):
    class RestoreFails(FakeWinIDEAAdapter):
        def set_program_path(self, name, path):
            if path == OLD_APP:
                raise WinIDEAError("restore App failed")
            super().set_program_path(name, path)

    w = make.factory(RestoreFails(download_seconds=10))
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DOWNLOAD.value, timeout=3000)
    with caplog.at_level(logging.CRITICAL, logger="wflash"):
        w.close()
    assert any(r.levelno == logging.CRITICAL and "Rollback failed" in r.message for r in caplog.records)
    assert any("restore App failed" in e for e in w.ctx.errors)


def test_gui_thread_close_records_non_rollback_error_without_dialog(make, qtbot):
    w = make.factory(FakeWinIDEAAdapter())
    w._closing = True
    w._flash_error_during_close = WinIDEAError("boom")
    w.close()
    assert make.shown == []
    assert w._flash_error_during_close is None
    assert any("boom" in e for e in w.ctx.errors)


def test_gui_thread_close_disables_ui_and_ignores_reentrant_close_during_wait(make, qtbot):
    class SlowToStop(FakeWinIDEAAdapter):
        def download(self, progress, cancel, timeout_s):
            time.sleep(0.5)  # keeps the close wait open long enough for the probe
            super().download(progress, cancel, timeout_s)

    w = make.factory(SlowToStop(download_seconds=10))
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DOWNLOAD.value, timeout=3000)
    seen = {}

    def probe():
        seen["enabled"] = w.centralWidget().isEnabled()
        seen["status"] = w.statusBar().currentMessage()
        nested = QCloseEvent()  # Qt's own close() guard hides re-entry, so call closeEvent directly
        w.closeEvent(nested)
        seen["nested_accepted"] = nested.isAccepted()

    QTimer.singleShot(50, probe)
    w.close()
    assert seen["enabled"] is False
    assert "Closing" in seen["status"]
    assert seen["nested_accepted"] is False
    assert make.questions.count(make.questions[0]) == 1  # the nested close did not ask again


def test_gui_thread_close_after_confirmed_cancel_logs_warning_not_error(make, qtbot, caplog):
    w = make.factory(FakeWinIDEAAdapter(download_seconds=10))
    w.start_flash()
    qtbot.waitUntil(lambda: w.current_step() == Step.DOWNLOAD.value, timeout=3000)
    with caplog.at_level(logging.INFO, logger="wflash"):
        w.close()
    assert any(r.levelno == logging.WARNING and "cancelled by closing" in r.message for r in caplog.records)
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []
    assert any("Cancelled" in e for e in w.ctx.errors)
    assert make.shown == []
```

In `tests/gui_stubs.py` (`HostWindow`) delete the line

```python
        self.artifacts_loaded: list[tuple[Path, str]] = []
```

and the method

```python
    def on_artifact_ready(self, path: Path, label: str) -> None:
        self.artifacts_loaded.append((path, label))
```

Delete the replaced test modules:

```bash
git rm tests/test_gui_gitlab_browser.py tests/test_gui_settings_dialog.py
```

- [ ] **Step 2: Run them to verify they fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_gui_ui_files.py tests/test_gui_mapping_table.py tests/test_gui_flash.py tests/test_gui_main_window.py tests/test_gui_close_window.py -v`
Expected: `3 errors` during collection — `ImportError: cannot import name 'HINT_COMPLETE' from 'wflash.gui.mapping_table'`, `… 'program_bytes' from 'wflash.gui.flash_mixin'`, `… 'APP_AUTHOR' from 'wflash'`.

- [ ] **Step 3: Rewrite `wflash/gui/main_window.ui`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>MainWindow</class>
 <widget class="QMainWindow" name="MainWindow">
  <property name="geometry">
   <rect>
    <x>0</x>
    <y>0</y>
    <width>1280</width>
    <height>820</height>
   </rect>
  </property>
  <property name="windowTitle">
   <string>WFlash</string>
  </property>
  <widget class="QWidget" name="centralWidget_main">
   <layout class="QVBoxLayout" name="verticalLayout_main" stretch="0,0,3,2">
    <item>
     <layout class="QHBoxLayout" name="horizontalLayout_flashHeader">
      <item>
       <widget class="QPushButton" name="pushButton_flash">
        <property name="minimumSize">
         <size>
          <width>90</width>
          <height>70</height>
         </size>
        </property>
        <property name="maximumSize">
         <size>
          <width>90</width>
          <height>70</height>
         </size>
        </property>
        <property name="text">
         <string>Flash</string>
        </property>
        <property name="state" stdset="0">
         <string>idle</string>
        </property>
       </widget>
      </item>
      <item>
       <layout class="QVBoxLayout" name="verticalLayout_flashProgress">
        <item>
         <layout class="QHBoxLayout" name="horizontalLayout_progressRow">
          <item>
           <widget class="QProgressBar" name="progressBar_flash">
            <property name="sizePolicy">
             <sizepolicy hsizetype="Expanding" vsizetype="Fixed">
              <horstretch>1</horstretch>
              <verstretch>0</verstretch>
             </sizepolicy>
            </property>
            <property name="minimumSize">
             <size>
              <width>0</width>
              <height>20</height>
             </size>
            </property>
            <property name="maximumSize">
             <size>
              <width>16777215</width>
              <height>20</height>
             </size>
            </property>
            <property name="value">
             <number>0</number>
            </property>
            <property name="textVisible">
             <bool>false</bool>
            </property>
           </widget>
          </item>
          <item>
           <widget class="QLabel" name="label_flashStats">
            <property name="minimumSize">
             <size>
              <width>280</width>
              <height>0</height>
             </size>
            </property>
            <property name="text">
             <string>ETA: -- | Speed: --</string>
            </property>
           </widget>
          </item>
         </layout>
        </item>
        <item>
         <widget class="QLabel" name="label_step">
          <property name="text">
           <string>Step: Idle</string>
          </property>
         </widget>
        </item>
       </layout>
      </item>
     </layout>
    </item>
    <item>
     <widget class="QLabel" name="label_rollbackWarning">
      <property name="visible">
       <bool>false</bool>
      </property>
      <property name="text">
       <string>ROLLBACK FAILED — the winIDEA workspace may still point to the new files. Check the download and symbol file list in winIDEA before flashing again.</string>
      </property>
      <property name="wordWrap">
       <bool>true</bool>
      </property>
     </widget>
    </item>
    <item>
     <layout class="QHBoxLayout" name="horizontalLayout_workArea">
      <item>
       <widget class="QFrame" name="frame_settingPanel">
        <property name="minimumSize">
         <size>
          <width>360</width>
          <height>0</height>
         </size>
        </property>
        <property name="maximumSize">
         <size>
          <width>360</width>
          <height>16777215</height>
         </size>
        </property>
        <property name="frameShape">
         <enum>QFrame::Shape::StyledPanel</enum>
        </property>
        <layout class="QVBoxLayout" name="verticalLayout_settingPanel">
         <property name="spacing">
          <number>0</number>
         </property>
         <property name="leftMargin">
          <number>0</number>
         </property>
         <property name="topMargin">
          <number>0</number>
         </property>
         <property name="rightMargin">
          <number>0</number>
         </property>
         <property name="bottomMargin">
          <number>0</number>
         </property>
         <item>
          <widget class="QLabel" name="label_settingHeader">
           <property name="text">
            <string>Setting</string>
           </property>
          </widget>
         </item>
         <item>
          <layout class="QGridLayout" name="gridLayout_setting">
           <property name="leftMargin">
            <number>10</number>
           </property>
           <property name="topMargin">
            <number>10</number>
           </property>
           <property name="rightMargin">
            <number>10</number>
           </property>
           <property name="bottomMargin">
            <number>6</number>
           </property>
           <property name="verticalSpacing">
            <number>8</number>
           </property>
           <item row="0" column="0">
            <widget class="QLabel" name="label_profile">
             <property name="text">
              <string>Profile</string>
             </property>
             <property name="buddy">
              <cstring>comboBox_profile</cstring>
             </property>
            </widget>
           </item>
           <item row="0" column="1">
            <layout class="QHBoxLayout" name="horizontalLayout_profile">
             <item>
              <widget class="QComboBox" name="comboBox_profile">
               <property name="sizePolicy">
                <sizepolicy hsizetype="Expanding" vsizetype="Fixed">
                 <horstretch>1</horstretch>
                 <verstretch>0</verstretch>
                </sizepolicy>
               </property>
              </widget>
             </item>
             <item>
              <widget class="QPushButton" name="pushButton_reloadProfiles">
               <property name="text">
                <string>Reload</string>
               </property>
              </widget>
             </item>
            </layout>
           </item>
           <item row="1" column="0">
            <widget class="QLabel" name="label_firmwareSource">
             <property name="text">
              <string>Firmware source</string>
             </property>
             <property name="buddy">
              <cstring>pushButton_loadFromGitlab</cstring>
             </property>
            </widget>
           </item>
           <item row="1" column="1">
            <widget class="QPushButton" name="pushButton_loadFromGitlab">
             <property name="text">
              <string>Load from GitLab…</string>
             </property>
            </widget>
           </item>
           <item row="2" column="0" colspan="2">
            <widget class="QFrame" name="frame_sourceCard">
             <property name="frameShape">
              <enum>QFrame::Shape::StyledPanel</enum>
             </property>
             <layout class="QVBoxLayout" name="verticalLayout_sourceCard">
              <property name="spacing">
               <number>2</number>
              </property>
              <item>
               <widget class="QLabel" name="label_sourceTitle">
                <property name="text">
                 <string>No firmware loaded — use Load from GitLab…</string>
                </property>
                <property name="wordWrap">
                 <bool>true</bool>
                </property>
               </widget>
              </item>
              <item>
               <widget class="QLabel" name="label_sourceDetail">
                <property name="text">
                 <string/>
                </property>
                <property name="wordWrap">
                 <bool>true</bool>
                </property>
                <property name="textInteractionFlags">
                 <set>Qt::TextInteractionFlag::TextSelectableByMouse</set>
                </property>
               </widget>
              </item>
              <item>
               <widget class="QLabel" name="label_sourceCache">
                <property name="text">
                 <string/>
                </property>
               </widget>
              </item>
             </layout>
            </widget>
           </item>
           <item row="3" column="0">
            <widget class="QLabel" name="label_instance">
             <property name="text">
              <string>winIDEA</string>
             </property>
             <property name="buddy">
              <cstring>comboBox_instance</cstring>
             </property>
            </widget>
           </item>
           <item row="3" column="1">
            <layout class="QHBoxLayout" name="horizontalLayout_instance">
             <item>
              <widget class="QComboBox" name="comboBox_instance">
               <property name="sizePolicy">
                <sizepolicy hsizetype="Expanding" vsizetype="Fixed">
                 <horstretch>1</horstretch>
                 <verstretch>0</verstretch>
                </sizepolicy>
               </property>
              </widget>
             </item>
             <item>
              <widget class="QPushButton" name="pushButton_refreshInstances">
               <property name="text">
                <string>Refresh</string>
               </property>
              </widget>
             </item>
            </layout>
           </item>
           <item row="4" column="0">
            <widget class="QLabel" name="label_afterFlash">
             <property name="text">
              <string>After flash</string>
             </property>
            </widget>
           </item>
           <item row="4" column="1">
            <layout class="QHBoxLayout" name="horizontalLayout_afterFlash">
             <item>
              <widget class="QCheckBox" name="checkBox_reset">
               <property name="text">
                <string>Reset target</string>
               </property>
               <property name="checked">
                <bool>true</bool>
               </property>
              </widget>
             </item>
             <item>
              <widget class="QCheckBox" name="checkBox_run">
               <property name="text">
                <string>Run after reset</string>
               </property>
              </widget>
             </item>
            </layout>
           </item>
          </layout>
         </item>
         <item>
          <spacer name="verticalSpacer_settingPanel">
           <property name="orientation">
            <enum>Qt::Orientation::Vertical</enum>
           </property>
           <property name="sizeHint" stdset="0">
            <size>
             <width>20</width>
             <height>40</height>
            </size>
           </property>
          </spacer>
         </item>
         <item>
          <layout class="QHBoxLayout" name="horizontalLayout_preferences">
           <property name="leftMargin">
            <number>10</number>
           </property>
           <property name="rightMargin">
            <number>10</number>
           </property>
           <property name="bottomMargin">
            <number>10</number>
           </property>
           <item>
            <spacer name="horizontalSpacer_preferences">
             <property name="orientation">
              <enum>Qt::Orientation::Horizontal</enum>
             </property>
             <property name="sizeHint" stdset="0">
              <size>
               <width>40</width>
               <height>20</height>
              </size>
             </property>
            </spacer>
           </item>
           <item>
            <widget class="QPushButton" name="pushButton_preferences">
             <property name="text">
              <string>Preferences…</string>
             </property>
            </widget>
           </item>
          </layout>
         </item>
        </layout>
       </widget>
      </item>
      <item>
       <layout class="QVBoxLayout" name="verticalLayout_mapping">
        <item>
         <widget class="QTableWidget" name="tableWidget_mapping">
          <property name="editTriggers">
           <set>QAbstractItemView::EditTrigger::NoEditTriggers</set>
          </property>
          <property name="selectionMode">
           <enum>QAbstractItemView::SelectionMode::NoSelection</enum>
          </property>
          <attribute name="horizontalHeaderStretchLastSection">
           <bool>true</bool>
          </attribute>
          <attribute name="verticalHeaderVisible">
           <bool>false</bool>
          </attribute>
          <column>
           <property name="text">
            <string>#</string>
           </property>
          </column>
          <column>
           <property name="text">
            <string>Type</string>
           </property>
          </column>
          <column>
           <property name="text">
            <string>winIDEA target</string>
           </property>
          </column>
          <column>
           <property name="text">
            <string>Pattern</string>
           </property>
          </column>
          <column>
           <property name="text">
            <string>File</string>
           </property>
          </column>
         </widget>
        </item>
        <item>
         <widget class="QLabel" name="label_mappingHint">
          <property name="text">
           <string>Load firmware to fill the mapping.</string>
          </property>
         </widget>
        </item>
       </layout>
      </item>
     </layout>
    </item>
    <item>
     <widget class="QTabWidget" name="tabWidget_output">
      <property name="currentIndex">
       <number>0</number>
      </property>
      <widget class="QWidget" name="tab_information">
       <attribute name="title">
        <string>Information</string>
       </attribute>
       <layout class="QVBoxLayout" name="verticalLayout_information">
        <item>
         <layout class="QHBoxLayout" name="horizontalLayout_logBar">
          <item>
           <widget class="QLabel" name="label_logLevel">
            <property name="text">
             <string>Log level</string>
            </property>
            <property name="buddy">
             <cstring>comboBox_logLevel</cstring>
            </property>
           </widget>
          </item>
          <item>
           <widget class="QComboBox" name="comboBox_logLevel">
            <property name="currentIndex">
             <number>1</number>
            </property>
            <item>
             <property name="text">
              <string>DEBUG</string>
             </property>
            </item>
            <item>
             <property name="text">
              <string>INFO</string>
             </property>
            </item>
            <item>
             <property name="text">
              <string>WARNING</string>
             </property>
            </item>
            <item>
             <property name="text">
              <string>ERROR</string>
             </property>
            </item>
           </widget>
          </item>
          <item>
           <spacer name="horizontalSpacer_logBar">
            <property name="orientation">
             <enum>Qt::Orientation::Horizontal</enum>
            </property>
            <property name="sizeHint" stdset="0">
             <size>
              <width>40</width>
              <height>20</height>
             </size>
            </property>
           </spacer>
          </item>
          <item>
           <widget class="QPushButton" name="pushButton_copyLog">
            <property name="text">
             <string>Copy</string>
            </property>
           </widget>
          </item>
          <item>
           <widget class="QPushButton" name="pushButton_clearLog">
            <property name="text">
             <string>Clear</string>
            </property>
           </widget>
          </item>
          <item>
           <widget class="QPushButton" name="pushButton_exportBundle">
            <property name="text">
             <string>Export debug bundle…</string>
            </property>
           </widget>
          </item>
         </layout>
        </item>
        <item>
         <widget class="QPlainTextEdit" name="plainTextEdit_log">
          <property name="lineWrapMode">
           <enum>QPlainTextEdit::LineWrapMode::NoWrap</enum>
          </property>
          <property name="readOnly">
           <bool>true</bool>
          </property>
          <property name="maximumBlockCount">
           <number>20000</number>
          </property>
         </widget>
        </item>
       </layout>
      </widget>
     </widget>
    </item>
   </layout>
  </widget>
  <widget class="QStatusBar" name="statusBar_main"/>
 </widget>
 <resources/>
 <connections/>
</ui>
```

- [ ] **Step 4: Regenerate the Python module (regenerate-ui skill)**

Run: `~/.venvs/wflash/bin/pyside6-uic wflash/gui/main_window.ui -o wflash/gui/ui_main_window.py`

- [ ] **Step 5: Implement**

`wflash/__init__.py`:

```python
"""WFlash: flash ECU via winIDEA from GitLab artifacts."""
__version__ = "0.1.0"
APP_AUTHOR = "tranph9 (TRAN Phuc)"
```

Replace `wflash/gui/mapping_table.py` with:

```python
"""Mapping table mixin: which firmware file goes to which winIDEA entry, plus the source card.

A row whose pattern matched zero or several files is red and has no file selected; the
user must choose one (spec §5). Nothing here ever picks a file on the user's behalf.

Host contract: `self.ui`, `self.profile` (Profile | None), `self.ctx` (DebugContext),
`self._closing`, `self._update_flash_controls()`. The rows are dynamic content, so they
are built here; the table, its columns, the source card and the hint live in main_window.ui.
"""
from __future__ import annotations

from functools import partial
from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QFontDatabase
from PySide6.QtWidgets import QComboBox, QHeaderView, QTableWidgetItem

from wflash.core.file_matcher import MappingRow, build_mapping, candidates_for_kind
from wflash.core.firmware_source import FirmwareSource
from wflash.core.logging_setup import get_logger
from wflash.gui.theme import current_theme

log = get_logger("ui.mapping")

NUMBER_COLUMN, TYPE_COLUMN, TARGET_COLUMN, PATTERN_COLUMN, FILE_COLUMN = range(5)
NONE_TEXT = "-- select file --"
NO_FIRMWARE_TITLE = "No firmware loaded — use Load from GitLab…"
HINT_NO_FIRMWARE = "Load firmware to fill the mapping."
HINT_INCOMPLETE = "Red rows need a file before Flash is enabled."
HINT_COMPLETE = "All rows mapped — Flash enabled."


def missing_style() -> str:
    """Stylesheet of a row combo that still needs a file, in the current theme's colours."""
    t = current_theme()
    return (
        f"QComboBox {{ background-color: {t['missing_bg']}; border: 1px solid {t['missing_border']}; "
        f"color: {t['text']}; }}"
    )


class MappingTableMixin:
    def _init_mapping_table(self) -> None:
        self._mapping_rows: list[MappingRow] = []
        self.artifact_root: Path | None = None
        self.firmware_source: FirmwareSource | None = None
        header = self.ui.tableWidget_mapping.horizontalHeader()
        for column in (NUMBER_COLUMN, TYPE_COLUMN, TARGET_COLUMN, PATTERN_COLUMN):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(FILE_COLUMN, QHeaderView.ResizeMode.Stretch)
        self._show_firmware_source(None, None)
        self._update_mapping_hint()

    def on_firmware_ready(self, path: Path, source: FirmwareSource) -> None:
        """Build the mapping for freshly downloaded (or cached) firmware from Load from GitLab."""
        if self.profile is None or self._closing:
            return
        rows = build_mapping(self.profile, path)
        self.firmware_source = source
        self.ctx.source = source.to_dict()  # no flash runs while firmware is being loaded
        self._show_firmware_source(source, path)
        self.set_mapping_rows(rows, path)
        log.info("Firmware loaded: %s (%s) from %s", source.title, source.cache_note, path)
        for row in rows:
            if row.ok:
                log.info("%s '%s' -> %s", row.kind, row.target, row.selected.relative_to(path).as_posix())
            else:
                log.warning(
                    "%s '%s': %d file(s) match '%s'; choose a file manually",
                    row.kind, row.target, len(row.candidates), row.pattern,
                )

    def _show_firmware_source(self, source: FirmwareSource | None, path: Path | None) -> None:
        if source is None:
            self.ui.label_sourceTitle.setText(NO_FIRMWARE_TITLE)
            self.ui.label_sourceDetail.setText("")
            self.ui.label_sourceCache.setText("")
            self.ui.frame_sourceCard.setToolTip("")
            return
        self.ui.label_sourceTitle.setText(source.title)
        self.ui.label_sourceDetail.setText(source.detail)
        self.ui.label_sourceCache.setText(source.cache_note)
        self.ui.frame_sourceCard.setToolTip(str(path) if path else "")

    def set_mapping_rows(self, rows: list[MappingRow], root: Path) -> None:
        table = self.ui.tableWidget_mapping
        fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self._mapping_rows = rows
        self.artifact_root = root
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            number = QTableWidgetItem(str(index + 1))
            number.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(index, NUMBER_COLUMN, number)
            kind_text = "Program" if row.kind == "program" else "Symbols"
            table.setItem(index, TYPE_COLUMN, QTableWidgetItem(kind_text))
            table.setItem(index, TARGET_COLUMN, QTableWidgetItem(row.target))
            pattern = QTableWidgetItem(row.pattern)
            pattern.setFont(fixed)
            table.setItem(index, PATTERN_COLUMN, pattern)
            combo = QComboBox()
            combo.installEventFilter(self)  # swallow wheel events, see eventFilter
            combo.addItem(NONE_TEXT, None)
            options = row.candidates or candidates_for_kind(root, row.kind)
            for option in options:
                combo.addItem(option.relative_to(root).as_posix(), str(option))
            if row.selected is not None:
                combo.setCurrentIndex(options.index(row.selected) + 1)
            # GUI-thread signal from a GUI-thread widget: a partial is safe here. The
            # lambda/partial ban (threading rule 8) is about signals emitted from pool threads.
            combo.currentIndexChanged.connect(partial(self._on_mapping_choice, index))
            table.setCellWidget(index, FILE_COLUMN, combo)
            self._paint_mapping_row(index)
        self._update_mapping_hint()
        self._update_flash_controls()

    def eventFilter(self, watched, event) -> bool:
        # Scrolling the table must never silently change which file gets flashed.
        if event.type() == QEvent.Type.Wheel and isinstance(watched, QComboBox):
            return True
        return super().eventFilter(watched, event)

    def clear_mapping(self) -> None:
        self._mapping_rows = []
        self.artifact_root = None
        self.firmware_source = None
        self.ctx.source = {}
        self.ui.tableWidget_mapping.setRowCount(0)
        self._show_firmware_source(None, None)
        self._update_mapping_hint()
        self._update_flash_controls()

    def mapping_combo(self, index: int) -> QComboBox:
        return self.ui.tableWidget_mapping.cellWidget(index, FILE_COLUMN)

    def _on_mapping_choice(self, index: int, _combo_index: int) -> None:
        data = self.mapping_combo(index).currentData()
        self._mapping_rows[index].selected = Path(data) if data else None
        self._paint_mapping_row(index)
        self._update_mapping_hint()
        self._update_flash_controls()

    def _paint_mapping_row(self, index: int) -> None:
        ok = self._mapping_rows[index].ok
        combo = self.mapping_combo(index)
        combo.setProperty("missing", not ok)
        combo.setStyleSheet("" if ok else missing_style())
        number = self.ui.tableWidget_mapping.item(index, NUMBER_COLUMN)
        if number is not None:
            number.setBackground(QColor(current_theme()["soft"]))

    def refresh_mapping_theme(self) -> None:
        """Repaint the dynamic row colours after the theme changed."""
        for index in range(len(self._mapping_rows)):
            self._paint_mapping_row(index)

    def _update_mapping_hint(self) -> None:
        if not self._mapping_rows:
            text = HINT_NO_FIRMWARE
        elif self.mapping_complete():
            text = HINT_COMPLETE
        else:
            text = HINT_INCOMPLETE
        self.ui.label_mappingHint.setText(text)

    def mapping_rows(self) -> list[MappingRow]:
        return list(self._mapping_rows)

    def mapping_complete(self) -> bool:
        return bool(self._mapping_rows) and all(row.ok for row in self._mapping_rows)
```

Replace `wflash/gui/flash_mixin.py` with:

```python
"""Flash mixin: winIDEA instance list, the Flash/Cancel button, step, progress, ETA/speed.

The flash runs `FlashWorkflow` (core) in one worker named "flash". The workflow already
guarantees the rollback (Approach A); this mixin only has to start it, honour Cancel, and
show the outcome — including a failed rollback, which the user must never miss.

One button does both jobs: "Flash" when idle, a red "Cancel" (dynamic property
state="flashing", styled by the theme) while the worker runs.

Host contract: `self.ui`, `self.adapter`, `self.profile`, `self.ctx`, `self._workers`,
`self._closing`, `self.show_error()`, `self.statusBar()`, `self.mapping_rows()` and
`self.mapping_complete()` (MappingTableMixin), `self.gitlab_busy()` (MainWindow).
"""
from __future__ import annotations

import dataclasses
import time

from wflash.core.errors import CancelledError, WinIDEAError
from wflash.core.flash_workflow import FlashRequest, FlashWorkflow, Step
from wflash.core.logging_setup import get_logger
from wflash.core.progress import CALCULATING_TEXT, IDLE_TEXT, ProgressEstimator
from wflash.core.winidea_adapter import InstanceInfo, WinIDEAAdapter
from wflash.gui.style import repolish
from wflash.gui.workers import WorkerContext

log = get_logger("ui.flash")

STEP_PREFIX = "Step: "


def safe_list_instances(adapter: WinIDEAAdapter) -> list[InstanceInfo]:
    """No winIDEA, no running instance and no probe are normal states, never exceptions."""
    try:
        return list(adapter.list_instances())
    except Exception as exc:
        log.warning("Listing winIDEA instances failed: %s", exc, exc_info=True)
        return []


def instance_data(info: InstanceInfo) -> dict:
    """What the instance combo stores; read back with currentData(), never from the text."""
    return {"instance_id": info.instance_id, "workspace": info.workspace, "tcp_port": info.tcp_port}


def program_bytes(rows) -> int:
    """Size of the mapped program files: the (estimated) amount the download moves."""
    total = 0
    for row in rows:
        if row.kind == "program" and row.selected is not None:
            try:
                total += row.selected.stat().st_size
            except OSError:
                pass  # FlashWorkflow reports a missing file with its own MappingError
    return total


class FlashMixin:
    def _init_flash(self) -> None:
        self._flash_key: str | None = None
        self._flash_cancel_requested = False
        self._flash_error_during_close: BaseException | None = None
        self._instances_key: str | None = None
        self._estimator: ProgressEstimator | None = None
        self._flash_total_bytes = 0
        self._flash_button_state = ""
        self.ui.progressBar_flash.setRange(0, 100)
        self.ui.progressBar_flash.setValue(0)
        self._set_step("Idle")
        self.ui.label_flashStats.setText(IDLE_TEXT)
        self._set_bar_state("")
        self._set_flash_button(flashing=False)
        self.ui.pushButton_flash.clicked.connect(self._on_flash_button_clicked)
        self.ui.pushButton_refreshInstances.clicked.connect(self.refresh_instances)
        self.ui.comboBox_instance.currentIndexChanged.connect(self._update_flash_controls)
        self.ui.checkBox_reset.toggled.connect(self._update_flash_controls)

    # -- state ------------------------------------------------------------------------
    def flash_active(self) -> bool:
        return self._workers.is_running(self._flash_key)

    def selected_instance(self) -> dict | None:
        data = self.ui.comboBox_instance.currentData()
        return data if isinstance(data, dict) else None

    def current_step(self) -> str:
        return self.ui.label_step.text().removeprefix(STEP_PREFIX)

    def _set_step(self, text: str) -> None:
        self.ui.label_step.setText(STEP_PREFIX + text)

    def _set_bar_state(self, state: str) -> None:
        bar = self.ui.progressBar_flash
        if bar.property("state") != state:
            bar.setProperty("state", state)
            repolish(bar)

    def _set_flash_button(self, flashing: bool) -> None:
        state = "flashing" if flashing else "idle"
        if state == self._flash_button_state:
            return
        self._flash_button_state = state
        button = self.ui.pushButton_flash
        button.setText("Cancel" if flashing else "Flash")
        button.setProperty("state", state)
        repolish(button)

    def _update_flash_controls(self, *_args) -> None:
        flashing = self.flash_active()
        can_flash = (
            not flashing
            and not self._closing
            and not self.gitlab_busy()
            and not self._workers.is_running(self._instances_key)  # the real adapter may not be thread-safe
            and self.profile is not None
            and self.mapping_complete()
            and self.selected_instance() is not None
        )
        self._set_flash_button(flashing)
        # While flashing the same button cancels; after one cancel it waits for the rollback.
        self.ui.pushButton_flash.setEnabled(can_flash or (flashing and not self._flash_cancel_requested))
        for widget in (
            self.ui.comboBox_profile,
            self.ui.pushButton_reloadProfiles,
            self.ui.pushButton_preferences,
            self.ui.tableWidget_mapping,
            self.ui.comboBox_instance,
            self.ui.pushButton_refreshInstances,
            self.ui.checkBox_reset,
            self.ui.pushButton_exportBundle,
        ):
            widget.setEnabled(not flashing)
        self.ui.pushButton_loadFromGitlab.setEnabled(not flashing and self.profile is not None)
        self.ui.checkBox_run.setEnabled(not flashing and self.ui.checkBox_reset.isChecked())

    # -- instances --------------------------------------------------------------------
    def refresh_instances(self, *_args) -> None:
        if self._workers.is_running(self._instances_key) or self.flash_active() or self._closing:
            return
        adapter = self.adapter

        def job(ctx: WorkerContext) -> list[InstanceInfo]:
            return safe_list_instances(adapter)

        self._instances_key = self._workers.start(
            "winidea-instances",
            job,
            on_succeeded=self._on_instances_loaded,
            on_failed=self._on_instances_failed,
            on_finished=self._on_instances_finished,
        )
        self._update_flash_controls()

    def _on_instances_loaded(self, _key: str, instances: list[InstanceInfo]) -> None:
        if self._closing:
            return
        combo = self.ui.comboBox_instance
        previous = self.selected_instance()
        combo.blockSignals(True)
        combo.clear()
        for info in instances:
            combo.addItem(info.label(), instance_data(info))
        if previous is not None:
            for index in range(combo.count()):
                if combo.itemData(index)["instance_id"] == previous["instance_id"]:
                    combo.setCurrentIndex(index)
        combo.blockSignals(False)
        if instances:
            log.info("Found %d winIDEA instance(s)", len(instances))
        else:
            log.warning("No running winIDEA instance found. Open winIDEA with the SAF85xx workspace and click Refresh.")
        self._update_flash_controls()

    def _on_instances_finished(self, _key: str) -> None:
        if not self._closing:
            self._update_flash_controls()  # the worker only stops counting as running now

    def _on_instances_failed(self, _key: str, exc: BaseException) -> None:
        # safe_list_instances never raises; this only catches a bug in the job itself.
        if self._closing:
            return
        log.error("Instance refresh failed: %s", exc)

    # -- flash ------------------------------------------------------------------------
    def _on_flash_button_clicked(self, *_args) -> None:
        if self.flash_active():
            self.cancel_flash()
        else:
            self.start_flash()

    def start_flash(self, *_args) -> None:
        if (
            self.flash_active()
            or self._closing
            or self._workers.is_running(self._instances_key)
            or not self.ui.pushButton_flash.isEnabled()
        ):
            return
        instance = self.selected_instance()
        if instance is None:
            self.show_error(WinIDEAError("No winIDEA instance selected"))
            return
        request = FlashRequest(
            instance_id=instance["instance_id"],
            # Copies: the worker must not share mutable rows with the table.
            mapping=[dataclasses.replace(row) for row in self.mapping_rows()],
            reset=self.ui.checkBox_reset.isChecked(),
            run=self.ui.checkBox_reset.isChecked() and self.ui.checkBox_run.isChecked(),
            timeout_s=self.profile.timeouts.download_s,
        )
        adapter, debug_ctx = self.adapter, self.ctx

        def job(wctx: WorkerContext) -> None:
            def on_step(step: Step) -> None:
                wctx.step(step.value)

            FlashWorkflow(adapter, debug_ctx, on_step=on_step, on_progress=wctx.progress).run(request, wctx.cancel)

        self._flash_cancel_requested = False
        self._flash_total_bytes = program_bytes(request.mapping)
        self._estimator = ProgressEstimator(time.monotonic())
        self.ui.label_rollbackWarning.setVisible(False)
        self._set_step("Starting")
        self.ui.label_flashStats.setText(CALCULATING_TEXT)
        self.ui.progressBar_flash.setRange(0, 100)
        self.ui.progressBar_flash.setValue(0)
        self._set_bar_state("")
        log.info("Flash requested on %s (%d file(s))", instance["instance_id"], len(request.mapping))
        self._flash_key = self._workers.start(
            "flash",
            job,
            on_succeeded=self._on_flash_succeeded,
            on_failed=self._on_flash_failed,
            on_finished=self._on_flash_finished,
            on_progress=self._on_flash_progress,
            on_step=self._on_flash_step,
        )
        self._update_flash_controls()

    def cancel_flash(self, *_args) -> None:
        if not self.flash_active() or self._flash_cancel_requested:
            return
        # Guard first (threading rule 4), then the token the workflow checks inside download().
        self._flash_cancel_requested = True
        log.warning("Flash cancel requested; the workspace paths will be restored")
        self._set_step("Cancelling")
        self._workers.cancel(self._flash_key)
        self._update_flash_controls()

    def _on_flash_step(self, text: str) -> None:
        if self._closing:
            return
        if text == Step.DOWNLOAD.value and self._estimator is not None:
            self._estimator.start(self._flash_total_bytes, time.monotonic())
            self.ui.label_flashStats.setText(self._estimator.running_text())
        if self._flash_cancel_requested and text != Step.ROLLBACK.value:
            return  # keep "Cancelling" visible until the workflow reports the rollback
        self._set_step(text)

    def _on_flash_progress(self, percent, message: str) -> None:
        if self._closing:
            return
        bar = self.ui.progressBar_flash
        bar.setToolTip(message)
        if percent is None:
            bar.setRange(0, 0)  # busy: winIDEA does not say how far it is
        else:
            bar.setRange(0, 100)
            bar.setValue(percent)
        if self._estimator is not None and self._estimator.transferring:
            self._estimator.update(percent, time.monotonic())
            self.ui.label_flashStats.setText(self._estimator.running_text())

    def _on_flash_succeeded(self, _key: str, _result) -> None:
        if self._closing:
            return
        if self._flash_cancel_requested:
            log.warning("The flash completed before the cancel took effect")
        self._set_step(Step.DONE.value)
        self.ui.progressBar_flash.setRange(0, 100)
        self.ui.progressBar_flash.setValue(100)
        self._set_bar_state("done")
        if self._estimator is not None:
            self.ui.label_flashStats.setText(self._estimator.done_text(time.monotonic()))
        log.info("Flash completed successfully")
        self.statusBar().showMessage("Flash completed", 10000)

    def _on_flash_failed(self, _key: str, exc: BaseException) -> None:
        if self._closing:
            # No dialogs while closing; closeEvent reports a failed rollback after the wait.
            self._flash_error_during_close = exc
            return
        rollback_failed = getattr(exc, "rollback_failed", False)
        self.ctx.add_error(exc)  # the workflow has returned; nothing else writes ctx now
        self.ui.progressBar_flash.setRange(0, 100)
        now = time.monotonic()
        cancelled = isinstance(exc, CancelledError)
        self._set_bar_state("cancelled" if cancelled else "failed")
        if self._estimator is not None:
            text = self._estimator.cancelled_text(now) if cancelled else self._estimator.failed_text(now)
            self.ui.label_flashStats.setText(text)
        if rollback_failed:
            self.ui.label_rollbackWarning.setVisible(True)
            log.critical("Rollback failed: the winIDEA workspace may still point to the new files")
        if cancelled:
            self._set_step("Cancelled")
            if not rollback_failed:
                return
        else:
            self._set_step("Failed")
        self.show_error(exc)

    def _on_flash_finished(self, key: str) -> None:
        if key == self._flash_key:
            self._flash_key = None
        if self._closing:
            return
        self._update_flash_controls()
```

Replace `wflash/gui/main_window.py` with:

```python
"""Main window: composed from the mixins, all sharing one `self.ui` built from main_window.ui.

This module owns the state the mixins share (settings, adapter, debug context, worker
registry, closing guard), the profile selector, the Load from GitLab popup, the
Preferences dialog, the theme switch and the shutdown path.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMainWindow, QMessageBox

from wflash import APP_AUTHOR, __version__
from wflash.core.debug_bundle import DebugContext
from wflash.core.errors import CancelledError, ProfileError
from wflash.core.logging_setup import get_logger, redact, set_verbose
from wflash.core.profile import Profile, list_profiles, load_profile
from wflash.core.settings import AppSettings
from wflash.core.winidea_adapter import WinIDEAAdapter
from wflash.gui.flash_mixin import FlashMixin
from wflash.gui.gitlab_dialog import WORKER_PREFIX, ClientFactory, GitlabDialog, default_client_factory
from wflash.gui.log_panel import LogPanelMixin
from wflash.gui.mapping_table import MappingTableMixin
from wflash.gui.preferences_dialog import PreferencesDialog
from wflash.gui.style import apply_theme, repolish
from wflash.gui.ui_main_window import Ui_MainWindow
from wflash.gui.workers import WorkerRegistry

log = get_logger("ui")

# Bounded wait in closeEvent: long enough for a cancelled flash to roll back, short
# enough that a hung worker cannot freeze the app forever (threading rule 3).
CLOSE_TIMEOUT_S = 15.0


class MainWindow(MappingTableMixin, FlashMixin, LogPanelMixin, QMainWindow):
    def __init__(
        self,
        settings: AppSettings,
        adapter: WinIDEAAdapter,
        client_factory: ClientFactory = default_client_factory,
        log_file: Path | None = None,
        settings_path: Path | None = None,
        pool: QThreadPool | None = None,
    ) -> None:
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle(f"WFlash v{__version__}")  # the version only exists at runtime
        self.settings = settings
        self.adapter = adapter
        self.log_file = log_file
        self._client_factory = client_factory
        self._settings_path = settings_path
        self.ctx = DebugContext()
        self.profile: Profile | None = None
        self._closing = False
        self._close_in_progress = False  # re-entrancy guard for closeEvent
        self._pool = pool or QThreadPool(self)
        self._workers = WorkerRegistry(self._pool, self)  # main thread, in __init__ (rule 6)

        self._init_log_panel()  # first, so the other parts' start-up is logged
        self._init_mapping_table()
        self._init_flash()
        self._init_status_bar()
        # One dialog for the window's whole life: it is never deleted while one of its
        # workers could still report to it (CLAUDE.md threading rules 1 and 4).
        self._gitlab_dialog = GitlabDialog(self)
        self._gitlab_dialog.firmwareReady.connect(self.on_firmware_ready)
        self.ui.comboBox_profile.currentIndexChanged.connect(self._on_profile_selected)
        self.ui.pushButton_reloadProfiles.clicked.connect(self.reload_profiles)
        self.ui.pushButton_loadFromGitlab.clicked.connect(self.open_gitlab_dialog)
        self.ui.pushButton_preferences.clicked.connect(self.open_preferences)

        self.reload_profiles()
        self.refresh_instances()
        self._update_flash_controls()

    def _init_status_bar(self) -> None:
        # Designer cannot put widgets into a status bar; these two are fixed text.
        self.label_version = QLabel(f"Version: v{__version__}")
        self.label_author = QLabel(f"Author: {APP_AUTHOR}")
        self.statusBar().addWidget(self.label_version)
        self.statusBar().addPermanentWidget(self.label_author)

    # -- shared helpers -------------------------------------------------------------
    def show_error(self, exc: BaseException) -> None:
        text = redact(str(exc))
        hint = getattr(exc, "hint", "")
        if hint:
            text += f"\n\nHint: {redact(hint)}"
        text += "\n\nUse 'Export debug bundle…' in the Information tab to collect logs for support."
        title = "WFlash — rollback failed" if getattr(exc, "rollback_failed", False) else "WFlash error"
        QMessageBox.critical(self, title, text)

    def _save_settings(self) -> None:
        try:
            self.settings.save(self._settings_path)
        except OSError as exc:
            log.warning("Cannot save settings: %s", exc)

    def gitlab_busy(self) -> bool:
        return self._workers.has_running(WORKER_PREFIX)

    # -- profiles -------------------------------------------------------------------
    def reload_profiles(self, *_args) -> None:
        directory = self.settings.resolved_profiles_dir()
        paths = list_profiles(directory)
        combo = self.ui.comboBox_profile
        combo.blockSignals(True)
        combo.clear()
        for path in paths:
            combo.addItem(path.stem, str(path))
        if paths:
            index = next((i for i, p in enumerate(paths) if p.name == self.settings.last_profile), 0)
            combo.setCurrentIndex(index)
        combo.blockSignals(False)
        if not paths:
            log.warning("No profiles found in %s", directory)
        self._on_profile_selected()

    def _on_profile_selected(self, *_args) -> None:
        data = self.ui.comboBox_profile.currentData()
        self.profile = None
        self.clear_mapping()
        if data is None:
            self._update_flash_controls()
            return
        path = Path(data)
        self.ctx.profile_path = path  # before loading: a bundle after a ProfileError needs the broken file
        try:
            profile = load_profile(path)
        except ProfileError as exc:
            log.error("%s", exc)
            self.ctx.add_error(exc)
            self.show_error(exc)
            self._update_flash_controls()
            return
        self.profile = profile
        self.ui.checkBox_reset.setChecked(profile.post_flash.reset)
        self.ui.checkBox_run.setChecked(profile.post_flash.run)
        self.settings.last_profile = path.name
        self._save_settings()
        log.info("Profile loaded: %s (%s)", profile.name, path)
        self._update_flash_controls()

    # -- Load from GitLab -----------------------------------------------------------
    def open_gitlab_dialog(self, *_args) -> None:
        # Never while flashing: the button is disabled then, this is the second guard.
        if self.flash_active() or self._closing or self.profile is None:
            return
        self._gitlab_dialog.prepare()
        self._gitlab_dialog.open()  # window-modal: Flash cannot be pressed while it is open

    # -- preferences and theme --------------------------------------------------------
    def open_preferences(self, *_args) -> None:
        if self.flash_active() or self.gitlab_busy():
            return
        dialog = PreferencesDialog(self.settings, self)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        if dialog.cache_cleared:
            self.clear_mapping()  # the loaded firmware's files may be gone
        if not accepted:
            return
        dark_before = self.settings.dark_mode
        self.settings = dialog.result_settings()
        set_verbose(self.settings.verbose)
        self._save_settings()
        log.info("Preferences saved")
        if self.settings.dark_mode != dark_before:
            self.apply_dark_mode(self.settings.dark_mode)
        self.reload_profiles()

    def apply_dark_mode(self, dark: bool) -> None:
        """Switch the theme now: application stylesheet plus the colours code paints itself."""
        apply_theme(QApplication.instance(), dark)
        self.refresh_mapping_theme()
        self.refresh_log_theme()
        repolish(self.ui.pushButton_flash)
        repolish(self.ui.progressBar_flash)
        log.info("Theme: %s", "dark" if dark else "light")

    # -- shutdown -------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        if self._close_in_progress:
            event.ignore()  # a nested close() from inside the wait's event pumping
            return
        if self.flash_active() and not self._closing:
            answer = QMessageBox.question(
                self,
                "WFlash",
                "A flash is in progress. Cancel it (the previous workspace paths will be restored) and quit?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        # Threading rule 4: the guards go up before anything is cancelled, so completion
        # signals still queued are settled by the slots instead of starting more work.
        self._closing = True
        self._close_in_progress = True
        self._gitlab_dialog.abort_for_close()
        flash_key = self._flash_key
        # The wait pumps events: lock the UI so no modal dialog (Preferences, file dialogs)
        # can open nested inside it and break the bound.
        self.centralWidget().setEnabled(False)
        self.statusBar().showMessage("Closing — waiting for the flash to cancel and restore paths…")
        self._workers.cancel_all()
        if not self._workers.wait_idle(CLOSE_TIMEOUT_S):
            keys = self._workers.abandon_running()
            log.critical(
                "Workers still running after %.0f s: %s. If a flash was running, check the "
                "winIDEA download/symbol paths before flashing again.",
                CLOSE_TIMEOUT_S,
                keys,
            )
            if flash_key is not None and flash_key in keys:
                QMessageBox.warning(
                    self,
                    "WFlash — flash still running",
                    "The flash did not stop in time. The winIDEA workspace may still point to "
                    "the new files — check the download/symbol file list in winIDEA before "
                    "flashing again.",
                )
        if self._gitlab_dialog.isVisible():
            self._gitlab_dialog.reject()  # its workers were cancelled and waited for above
        exc, self._flash_error_during_close = self._flash_error_during_close, None
        if exc is not None:
            # _on_flash_failed only stored it (no dialogs while closing); record it now.
            self.ctx.add_error(exc)
            if getattr(exc, "rollback_failed", False):
                log.critical("Rollback failed: the winIDEA workspace may still point to the new files")
                self.show_error(exc)
            elif isinstance(exc, CancelledError):
                log.warning("Flash cancelled by closing; previous paths restored")
            else:
                log.error("Flash error while closing: %s", exc)
        self._detach_log_panel()
        super().closeEvent(event)
```

Delete the GUI code nothing uses any more (grep first: `grep -rn "gitlab_browser\|settings_dialog\|SettingsDialog\|GitlabBrowserMixin\|on_artifact_ready\|pushButton_cancelFlash\|pushButton_settings" wflash tests` must print nothing except these files themselves):

```bash
git rm wflash/gui/gitlab_browser.py wflash/gui/settings_dialog.py wflash/gui/settings_dialog.ui wflash/gui/ui_settings_dialog.py
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_gui_ui_files.py tests/test_gui_mapping_table.py tests/test_gui_flash.py tests/test_gui_main_window.py tests/test_gui_close_window.py -v` → Expected: `56 passed`.
Run: `~/.venvs/wflash/bin/pytest -k thread -v` → Expected: `38 passed`.
Run: `~/.venvs/wflash/bin/pytest -q` → Expected: `304 passed`.
Run: `QT_QPA_PLATFORM=offscreen ~/.venvs/wflash/bin/python -m wflash --adapter fake --smoke` → Expected: exit code 0.
`tools/stress_test.py` is expected to fail until Task 13 (`AttributeError: 'MainWindow' object has no attribute 'refresh_gitlab'`) — do not push in between.

- [ ] **Step 7: Walkthrough entry**

```markdown
## Phase 1.38: Cửa sổ chính mới — một cửa sổ, nút Flash/Cancel, vùng Setting, tab Information

Cửa sổ chính chuyển sang bố cục SFlash (spec redesign §2): phần đầu có nút Flash 90×70 — khi đang flash chính nút đó thành Cancel màu đỏ (dynamic property `state="flashing"`, màu từ QSS), thanh tiến trình không chữ, nhãn `phần trăm | ETA | Speed` từ `ProgressEstimator`, nhãn `Step: …`. Bên trái là vùng Setting rộng 360 px (profile, Load from GitLab… với thẻ nguồn firmware, instance winIDEA, Reset/Run, Preferences…), bên phải bảng mapping có cột `#` và dòng gợi ý; dưới cùng chỉ một tab Information; thanh trạng thái ghi version và tác giả. `GitlabBrowserMixin` và `SettingsDialog` bị xóa trong cùng commit với các test thay thế. Cửa sổ giữ một `GitlabDialog` suốt đời; `closeEvent` hạ cờ của dialog trước khi hủy worker (quy tắc 4) rồi mới đóng nó.

### Thay đổi

- **`wflash/gui/main_window.ui`** (viết lại) + **`ui_main_window.py`** (sinh lại).
- **`wflash/gui/main_window.py`**: 3 mixin, popup GitLab, Preferences, `apply_dark_mode`, status bar, `closeEvent` có dialog.
- **`wflash/gui/mapping_table.py`**: `on_firmware_ready`, cột `#`, thẻ nguồn, gợi ý, màu dòng đỏ theo theme.
- **`wflash/gui/flash_mixin.py`**: một nút Flash/Cancel, ETA/Speed, `Step: …`, màu thanh theo trạng thái.
- **`wflash/__init__.py`**: `APP_AUTHOR`.
- Xóa **`wflash/gui/gitlab_browser.py`**, **`wflash/gui/settings_dialog.*`**, **`wflash/gui/ui_settings_dialog.py`**, **`tests/test_gui_gitlab_browser.py`**, **`tests/test_gui_settings_dialog.py`**.
- Test viết lại: **`test_gui_ui_files.py`**, **`test_gui_mapping_table.py`**, **`test_gui_flash.py`**, **`test_gui_main_window.py`**, **`test_gui_close_window.py`**; **`tests/gui_stubs.py`** bỏ `on_artifact_ready`.

### Đã kiểm tra

- RED / GREEN, `pytest -k thread -v`, `pytest -q`, smoke `--adapter fake --smoke`: <kết quả thật>
- `tools/stress_test.py` chưa chạy được (còn gọi GitLab browser cũ) — sửa ở Phase 1.39, chưa push.
```

- [ ] **Step 8: Commit**

```bash
git add wflash/__init__.py wflash/gui/main_window.ui wflash/gui/ui_main_window.py wflash/gui/main_window.py wflash/gui/mapping_table.py wflash/gui/flash_mixin.py tests/gui_stubs.py tests/test_gui_ui_files.py tests/test_gui_mapping_table.py tests/test_gui_flash.py tests/test_gui_main_window.py tests/test_gui_close_window.py docs/walkthrough.md
git commit -m "feat(gui): single-window layout with Flash/Cancel button, Setting panel and Information tab" -m "$TRAILER"
```

(The `git rm` commands above already staged the six deletions.)

---

### Task 13: Stress test drives GitLab through the popup, adds packages and a theme section

**Files:**
- Modify: `tools/stress_test.py`

**Interfaces:**
- Consumes: `MainWindow.open_gitlab_dialog()`, `_gitlab_dialog` (`GitlabDialog`: `load_refs`, `browse_jobs`, `download_selected`, `fetch_latest`, `browse_versions`, `stop`, `reject`, `busy`, `job_button`, `version_button`, `_note`), `MainWindow.current_step()`, `apply_dark_mode(dark)`, `on_firmware_ready(path, source)`; `tests.gui_stubs` (`GITLAB_URL`, `PKG_PROJECT`, `PKG_NAME`, `SOURCE`, …); `gitlab_dialog.get_token/set_token` (replaced by an in-memory dict for the whole run).
- Produces: sections `flash`, `rollback`, `gitlab` (dialog: CI + package, 401/403/404/connection, double-click, Stop, dialog closed mid-download at 0/50/200 ms, window closed mid-fetch at 0/5/20/60/150 ms and mid-download at 0/50/200 ms), `races`, **`theme`** (light/dark switched three times during a live flash and once with the dialog open), `secrets` (plus: token typed in the dialog reaches the fake keyring only, never `settings.json`; the dialog log is redacted). Still fails on any checkpoint **and** on any Qt threading warning.

- [ ] **Step 1: Run the current stress test to see it fail**

Run: `~/.venvs/wflash/bin/python tools/stress_test.py`
Expected: `STRESS_RESULT=FAIL`, exit 1 — `flash` and `gitlab` raise `AttributeError: 'MainWindow' object has no attribute 'refresh_gitlab'`, `rollback` and `races` raise `AttributeError: 'MainWindow' object has no attribute 'on_artifact_ready'` (`FAILED=4`).

- [ ] **Step 2: Replace `tools/stress_test.py` with:**

```python
#!/usr/bin/env python3
"""Headless end-to-end stress test for WFlash (see .claude/skills/stress-test/SKILL.md).

Drives the real MainWindow against FakeWinIDEAAdapter and a fake GitLab network
(tests/gui_stubs.py), chaining many actions in one process. Fails on its own checkpoints
AND on Qt threading warnings / uncaught exceptions, which raise no Python exception in
the code under test and would otherwise scroll past in stderr.

    ~/.venvs/wflash/bin/python tools/stress_test.py
    ~/.venvs/wflash/bin/python tools/stress_test.py --list
    ~/.venvs/wflash/bin/python tools/stress_test.py --section flash --section races

Prints `STRESS_RESULT=PASS` or `STRESS_RESULT=FAIL` and the checkpoint count; exit code 0/1.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import argparse  # noqa: E402
import faulthandler  # noqa: E402
import logging  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
import zipfile  # noqa: E402
from pathlib import Path  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

faulthandler.enable()  # a hard crash still prints every thread's Python stack

from PySide6.QtCore import QtMsgType, qInstallMessageHandler  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from tests.gui_stubs import (  # noqa: E402
    GITLAB_URL,
    JOB_ID,
    OLD_APP,
    OLD_CM7_0,
    OLD_CM7_1,
    PKG_NAME,
    PKG_PROJECT,
    SOURCE,
    TOKEN,
    FakeGitLabSession,
    SessionClientFactory,
    make_artifact_tree,
    write_profiles,
)
from wflash.core.errors import WinIDEAError  # noqa: E402
from wflash.core.fake_adapter import FakeWinIDEAAdapter  # noqa: E402
from wflash.core.flash_workflow import Step  # noqa: E402
from wflash.core.logging_setup import close_file_handler, get_logger, setup_logging  # noqa: E402
from wflash.core.settings import AppSettings  # noqa: E402
from wflash.gui import gitlab_dialog, workers  # noqa: E402
from wflash.gui.main_window import MainWindow  # noqa: E402
from wflash.gui.style import apply_theme  # noqa: E402
from wflash.gui.theme import THEMES, current_theme_name  # noqa: E402

log = get_logger("stress")

# Qt messages that mean a threading bug. Any of them fails the run.
THREADING_PATTERNS = (
    "QThread: Destroyed while thread",
    "Signal source has been deleted",
    "QObject: Cannot create children for a parent that is in a different thread",
    "QObject::killTimer",
    "QObject::startTimer",
    "Timers cannot be",
    "QBasicTimer",
    "Cannot queue arguments",
    "QSocketNotifier: Socket notifiers cannot be enabled or disabled from another thread",
    "QObject::setParent: Cannot set parent",
    "moveToThread",
    "different thread",
    "another thread",
    "outside the GUI thread",
)
CANCEL_DELAYS_S = (0.0, 0.005, 0.02, 0.06, 0.15, 0.4)
NEW_APP_SUFFIX = "App.s3"


class DropsMidTransfer(FakeWinIDEAAdapter):
    """Connection drops at 30 % of the download; winIDEA is back for the rollback."""

    def download(self, progress, cancel, timeout_s):
        progress(30, "Programming external flash (fake)")
        raise WinIDEAError("Connection to winIDEA lost during download")


class DropsAndStaysDown(DropsMidTransfer):
    """Connection drops mid-transfer and never comes back: the rollback must fail visibly."""

    lost = False

    def download(self, progress, cancel, timeout_s):
        self.lost = True
        super().download(progress, cancel, timeout_s)

    def set_program_path(self, name, path):
        if self.lost:
            raise WinIDEAError("Connection to winIDEA lost")
        super().set_program_path(name, path)

    def set_symbol_path(self, name, path):
        if self.lost:
            raise WinIDEAError("Connection to winIDEA lost")
        super().set_symbol_path(name, path)


class Stress:
    def __init__(self, workdir: Path, log_file: Path, iterations: int) -> None:
        self.workdir = workdir
        self.log_file = log_file
        self.iterations = iterations
        self.checkpoints = 0
        self.failures: list[str] = []
        self.qt_problems: list[str] = []
        self.qt_other: list[str] = []
        self.dialogs: list[tuple[str, str]] = []
        self.questions: list[str] = []
        self.answer = QMessageBox.StandardButton.Yes
        self._window_count = 0
        self.keyring: dict[str, str] = {}

    # -- infrastructure ---------------------------------------------------------------
    def check(self, condition: bool, label: str) -> bool:
        self.checkpoints += 1
        if not condition:
            self.failures.append(label)
            print(f"  FAIL: {label}", flush=True)
        return condition

    def pump(self, seconds: float) -> None:
        # Never app.quit() to end a wait (stress-test trap 1): just process events.
        deadline = time.monotonic() + seconds
        while True:
            QApplication.processEvents()
            if time.monotonic() >= deadline:
                return
            time.sleep(0.002)

    def pump_until(self, predicate, timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        while not predicate():
            if time.monotonic() >= deadline:
                return False
            QApplication.processEvents()
            time.sleep(0.002)
        return True

    def new_window(self, adapter, session: FakeGitLabSession | None = None, download_s: int | None = None):
        self._window_count += 1
        folder = self.workdir / f"window{self._window_count}"
        profiles = write_profiles(folder / "profiles", download_s)
        settings = AppSettings(gitlab_url=GITLAB_URL, profiles_dir=str(profiles), cache_dir=str(folder / "cache"))
        window = MainWindow(
            settings,
            adapter,
            client_factory=SessionClientFactory(session or FakeGitLabSession()),
            log_file=self.log_file,
            settings_path=folder / "settings.json",
        )
        window.resize(1280, 820)
        window.show()
        self.check(
            self.pump_until(lambda: window.ui.comboBox_instance.count() == 1, 5.0),
            f"window{self._window_count}: fake winIDEA instance listed",
        )
        return window

    def artifact(self, name: str) -> Path:
        return make_artifact_tree(self.workdir / f"artifact_{name}")

    def close_window(self, window, label: str, max_s: float = 5.0) -> None:
        t0 = time.monotonic()
        window.close()
        elapsed = time.monotonic() - t0
        self.check(elapsed < max_s, f"{label}: close() took {elapsed:.2f}s (deadlock?)")
        self.check(window._workers.running_keys() == [], f"{label}: no worker left running after close")
        self.check(window.log_handler not in logging.getLogger("wflash").handlers, f"{label}: log handler detached")
        window.deleteLater()
        self.pump(0.05)

    def wait_step(self, window, text: str, timeout_s: float) -> bool:
        return self.pump_until(lambda: window.current_step() == text, timeout_s)

    def wait_flash_idle(self, window, timeout_s: float = 10.0) -> bool:
        return self.pump_until(lambda: not window.flash_active(), timeout_s)

    def open_dialog(self, window):
        window.open_gitlab_dialog()
        dialog = window._gitlab_dialog
        self.check(dialog.isVisible(), "dialog: Load from GitLab opened")
        return dialog

    def browse_to_job(self, window, label: str):
        """Open Load from GitLab, load the refs, list the jobs (no download). Returns the dialog."""
        dialog = self.open_dialog(window)
        dialog.load_refs()
        ok = self.pump_until(lambda: not dialog.busy() and dialog.ui.comboBox_ref.count() == 2, 5.0)
        if ok:
            dialog.browse_jobs()
            ok = self.pump_until(lambda: not dialog.busy() and dialog.ui.tableWidget_jobs.rowCount() == 1, 5.0)
        self.check(ok, f"{label}: dialog listed refs and the job")
        return dialog if ok else None

    def load_artifact_via_gitlab(self, window, label: str) -> bool:
        dialog = self.browse_to_job(window, label)
        ok = dialog is not None
        if ok:
            dialog.job_button(0).click()
            ok = self.pump_until(window.mapping_complete, 10.0)
        if ok:
            ok = self.pump_until(lambda: not window.gitlab_busy() and not dialog.isVisible(), 5.0)
        return self.check(ok, f"{label}: dialog download -> mapping complete -> dialog closed")

    def start_slow_download(self, window, label: str):
        """Browse to the job, start its download and prove it is in flight (progress moved)."""
        dialog = self.browse_to_job(window, label)
        if dialog is None:
            return None
        dialog.job_button(0).click()
        started = self.pump_until(
            lambda: dialog.busy() and dialog.ui.progressBar_download.value() > 0, 5.0
        )
        self.check(started, f"{label}: artifact download in flight (worker running, progress > 0)")
        return dialog if started else None

    # -- sections ---------------------------------------------------------------------
    def section_flash(self) -> None:
        for i in range(self.iterations):
            label = f"flash[{i}]"
            adapter = FakeWinIDEAAdapter(download_seconds=0.3)
            window = self.new_window(adapter)
            if not self.load_artifact_via_gitlab(window, label):
                self.close_window(window, label)
                continue
            self.dialogs.clear()

            window.start_flash()
            self.check(self.wait_step(window, Step.DONE.value, 10.0), f"{label}: flash reached Done")
            self.check(self.wait_flash_idle(window), f"{label}: flash worker released")
            self.check(adapter.programs["App"].endswith(NEW_APP_SUFFIX) and adapter.programs["App"] != OLD_APP,
                       f"{label}: App path points to the artifact")
            self.check(adapter.target_state == "halted", f"{label}: target halted after reset")

            programs_after_first = dict(adapter.programs)
            applications_after_first = dict(adapter.applications)
            adapter.download_seconds = 3.0
            window.start_flash()
            self.check(self.wait_step(window, Step.DOWNLOAD.value, 5.0), f"{label}: second flash downloading")
            window.cancel_flash()
            self.check(self.wait_step(window, "Cancelled", 5.0), f"{label}: cancelled flash settled")
            self.check(self.wait_flash_idle(window), f"{label}: cancelled worker released")
            self.check(adapter.programs == programs_after_first,
                       f"{label}: cancel restored exactly the program paths of the first flash")
            self.check(adapter.applications == applications_after_first,
                       f"{label}: cancel restored exactly the symbol paths of the first flash")
            self.check(adapter.connected_to is None, f"{label}: disconnected after cancel")

            adapter.download_seconds = 1.0
            window.start_flash()
            levels = window.ui.comboBox_logLevel
            for n, size in enumerate(((800, 600), (1600, 1000), (1024, 700), (1280, 820))):
                window.resize(*size)
                levels.setCurrentIndex(n % levels.count())
                self.pump(0.05)
            self.check(self.wait_step(window, Step.DONE.value, 10.0), f"{label}: flash with resize/filter reached Done")
            self.check(self.wait_flash_idle(window), f"{label}: third worker released")
            self.check(self.dialogs == [], f"{label}: no error dialog in the happy paths: {self.dialogs}")
            self.close_window(window, label)

    def section_rollback(self) -> None:
        originals_programs = {"App": OLD_APP}
        originals_apps = {"CM7_0": OLD_CM7_0, "CM7_1": OLD_CM7_1}
        cases = [
            # label, adapter, profile download_s, expected rollback_failed
            ("missing entry", FakeWinIDEAAdapter(download_seconds=0.2, programs={"Other": OLD_APP}), None, False),
            ("set path refused", FakeWinIDEAAdapter(download_seconds=0.2, fail_on={"set_path"}), None, True),
            ("download fails at 50%", FakeWinIDEAAdapter(download_seconds=0.4, fail_on={"download"}), None, False),
            ("download timeout", FakeWinIDEAAdapter(download_seconds=3.0), 1, False),
            ("connection dropped mid-transfer", DropsMidTransfer(download_seconds=0.2), None, False),
            ("connection dropped for good", DropsAndStaysDown(download_seconds=0.2), None, True),
        ]
        for name, adapter, download_s, rollback_failed in cases:
            label = f"rollback[{name}]"
            programs_before = dict(adapter.programs)
            window = self.new_window(adapter, download_s=download_s)
            window.on_firmware_ready(self.artifact(name.replace(" ", "_")), SOURCE)
            self.dialogs.clear()
            window.start_flash()
            self.check(self.wait_step(window, "Failed", 10.0), f"{label}: flash failed")
            self.check(self.wait_flash_idle(window), f"{label}: worker released")
            self.check(len(self.dialogs) == 1, f"{label}: exactly one error dialog, got {len(self.dialogs)}")
            self.check(adapter.connected_to is None, f"{label}: disconnected")
            warning_shown = window.ui.label_rollbackWarning.isVisibleTo(window)
            self.check(warning_shown == rollback_failed, f"{label}: rollback warning shown={warning_shown}")
            if rollback_failed and self.dialogs:
                self.check("ROLLBACK FAILED" in self.dialogs[0][1], f"{label}: dialog says ROLLBACK FAILED")
            if name == "connection dropped for good":
                self.check(adapter.programs["App"] != OLD_APP, f"{label}: (expected) App still points to the new file")
            else:
                self.check(adapter.programs == programs_before, f"{label}: program paths back to the originals")
                if name != "missing entry":
                    self.check(adapter.programs == originals_programs, f"{label}: App == original")
                self.check(adapter.applications == originals_apps, f"{label}: symbol paths back to the originals")
            self.close_window(window, label)

    def section_gitlab(self) -> None:
        session = FakeGitLabSession()
        window = self.new_window(FakeWinIDEAAdapter(), session)
        dialog = self.open_dialog(window)
        for _ in range(5):
            dialog.load_refs()  # every click after the first is refused while busy
            self.pump(0.01)
        self.check(self.pump_until(lambda: not dialog.busy(), 5.0), "gitlab: repeated Load branches/tags settled")
        self.check(dialog.ui.comboBox_ref.count() == 2, "gitlab: refs listed once")
        self.check(session.count("/repository/branches") <= 5, "gitlab: no request storm")
        dialog.reject()
        self.check(self.load_artifact_via_gitlab(window, "gitlab"), "gitlab: browse to artifact")

        dialog = self.browse_to_job(window, "gitlab-cached")
        if dialog is not None:
            self.check(dialog.job_button(0).text() == "Cached", "gitlab: the downloaded job is shown as Cached")
            dialog.job_button(0).click()  # same job again: served from the cache
            self.check(self.pump_until(lambda: not dialog.isVisible() and not window.gitlab_busy(), 5.0),
                       "gitlab: cached download settled")
        self.check(session.count(f"/jobs/{JOB_ID}/artifacts") == 1, "gitlab: one network download, then cache")

        self.dialogs.clear()
        dialog = self.open_dialog(window)
        for status, needle in ((401, "expired"), (403, "access"), (404, "expired")):
            session.fail_status = status
            dialog.load_refs()
            ok = self.pump_until(lambda: len(self.dialogs) == 1, 5.0)
            self.check(ok and f"HTTP {status}" in self.dialogs[0][1] and needle in self.dialogs[0][1],
                       f"gitlab: HTTP {status} shows its specific hint")
            self.pump_until(lambda: not dialog.busy(), 5.0)
            self.check(dialog.isVisible(), f"gitlab: dialog stays open after HTTP {status}")
            self.dialogs.clear()
        session.fail_status = None
        session.connection_error = True
        dialog.load_refs()
        ok = self.pump_until(lambda: len(self.dialogs) == 1, 5.0)
        self.check(ok and "Cannot reach GitLab" in self.dialogs[0][1], "gitlab: connection error reported")
        session.connection_error = False
        self.pump_until(lambda: not dialog.busy(), 5.0)
        self.dialogs.clear()
        dialog.reject()
        self.close_window(window, "gitlab")

        # Package Registry: newest version (zip), then an older plain-file version.
        session = FakeGitLabSession()
        window = self.new_window(FakeWinIDEAAdapter(), session)
        dialog = self.open_dialog(window)
        dialog.ui.tabWidget_source.setCurrentWidget(dialog.ui.tab_packageRegistry)
        dialog.ui.lineEdit_pkgProject.setText(PKG_PROJECT)
        dialog.ui.lineEdit_packageName.setText(PKG_NAME)
        dialog.fetch_latest()
        ok = self.pump_until(lambda: window.mapping_complete() and not dialog.isVisible(), 10.0)
        self.check(ok, "gitlab-package: latest version downloaded and mapped")
        self.check(window.ui.label_sourceTitle.text() == f"Package \u00b7 {PKG_NAME} 1.4.0",
                   f"gitlab-package: source card names the package: {window.ui.label_sourceTitle.text()!r}")
        dialog = self.open_dialog(window)
        dialog.browse_versions()
        ok = self.pump_until(lambda: not dialog.busy() and dialog.ui.tableWidget_versions.rowCount() == 2, 5.0)
        self.check(ok, "gitlab-package: two versions listed (prefix match dropped)")
        if ok:
            dialog.version_button(1).click()
            ok = self.pump_until(lambda: not dialog.isVisible() and not window.gitlab_busy(), 10.0)
            self.check(ok and "1.3.0" in window.ui.label_sourceTitle.text(), "gitlab-package: plain-file version loaded")
            self.check(not window.mapping_complete(), "gitlab-package: missing symbols leave red rows (no guessing)")
        self.check(self.dialogs == [], f"gitlab-package: no error dialogs: {self.dialogs}")
        self.close_window(window, "gitlab-package")

        # Double-click on an UNCACHED job while the first download is in flight: refused.
        slow_dc = FakeGitLabSession(chunk_delay_s=0.02)
        window = self.new_window(FakeWinIDEAAdapter(), slow_dc)
        dialog = self.start_slow_download(window, "gitlab-double-click")
        if dialog is not None:
            dialog.job_button(0).click()
            dialog.download_selected()
            running = [k for k in window._workers.running_keys() if "download" in k]
            self.check(len(running) == 1, f"gitlab: double-click runs one download worker, got {running}")
            self.check(self.pump_until(window.mapping_complete, 10.0), "gitlab: double-click download finished")
            self.check(self.pump_until(lambda: not window.gitlab_busy(), 5.0), "gitlab: double-click settled")
            self.check(slow_dc.count(f"/jobs/{JOB_ID}/artifacts") == 1,
                       f"gitlab: double-click made exactly one artifact request, got "
                       f"{slow_dc.count(f'/jobs/{JOB_ID}/artifacts')}")
        self.close_window(window, "gitlab-double-click")

        # Stop an artifact download: dialog stays open, nothing loaded afterwards.
        self.dialogs.clear()
        slow = FakeGitLabSession(chunk_delay_s=0.02)
        window = self.new_window(FakeWinIDEAAdapter(), slow)
        dialog = self.start_slow_download(window, "gitlab-stop")
        if dialog is not None:
            dialog.stop()
            self.check(self.pump_until(lambda: not dialog.busy(), 5.0), "gitlab: stopped download settled")
            self.check(dialog.isVisible(), "gitlab: dialog still open after Stop")
            self.check(dialog.ui.label_downloadStatus.text() == "Cancelled", "gitlab: status says Cancelled")
            self.check(not window.mapping_rows(), "gitlab: no artifact loaded after Stop")
            self.check(self.dialogs == [], "gitlab: Stop shows no error dialog")
            dialog.reject()
        self.close_window(window, "gitlab-stop")

        # Dialog closed mid-download at several delays: bounded, nothing loaded.
        for delay in (0.0, 0.05, 0.2):
            dl = FakeGitLabSession(chunk_delay_s=0.02)
            window = self.new_window(FakeWinIDEAAdapter(), dl)
            dialog = self.browse_to_job(window, f"gitlab: dialog-close {delay}s")
            if dialog is not None:
                dialog.job_button(0).click()
                self.check(dialog.busy(), f"gitlab: download in flight before dialog close at {delay}s")
                self.pump(delay)
                t0 = time.monotonic()
                dialog.reject()
                self.check(time.monotonic() - t0 < 3.0, f"gitlab: dialog close at {delay}s is bounded")
                self.check(not dialog.busy() and not window.gitlab_busy(), f"gitlab: no worker after dialog close at {delay}s")
                self.pump(0.1)
                self.check(not window.mapping_rows(), f"gitlab: nothing loaded after dialog close at {delay}s")
            self.close_window(window, f"gitlab: dialog-close {delay}s")

        # Window closed mid-fetch / mid-download at several delays.
        for delay in CANCEL_DELAYS_S[:5]:
            fetch = FakeGitLabSession(delay_s=0.3)
            window = self.new_window(FakeWinIDEAAdapter(), fetch)
            dialog = self.open_dialog(window)
            dialog.load_refs()
            self.pump(delay)
            self.close_window(window, f"gitlab: closed {delay * 1000:.0f} ms into a fetch", max_s=3.0)
            self.check(dialog.ui.comboBox_ref.count() == 0, f"gitlab: nothing shown after close at {delay}s")
            self.check(not dialog.isVisible(), f"gitlab: dialog closed with the window at {delay}s")
        for delay in (0.0, 0.05, 0.2):
            dl = FakeGitLabSession(chunk_delay_s=0.02)
            window = self.new_window(FakeWinIDEAAdapter(), dl)
            dialog = self.browse_to_job(window, f"gitlab: close-in-download {delay}s")
            if dialog is not None:
                dialog.job_button(0).click()
                self.check(dialog.busy(), f"gitlab: download in flight before close at {delay}s")
                self.pump(delay)
            self.close_window(window, f"gitlab: closed {delay * 1000:.0f} ms into a download", max_s=3.0)
            self.check(not window.mapping_rows(), f"gitlab: no artifact loaded after close at {delay}s")
        self.check(self.dialogs == [], f"gitlab: no dialogs from closing windows: {self.dialogs}")

    def section_races(self) -> None:
        adapter = FakeWinIDEAAdapter(download_seconds=0.5)
        window = self.new_window(adapter)
        window.on_firmware_ready(self.artifact("races"), SOURCE)
        self.dialogs.clear()
        for delay in CANCEL_DELAYS_S:
            label = f"races: cancel {delay * 1000:.0f} ms after Flash"
            before = dict(adapter.programs)
            before_apps = dict(adapter.applications)
            window.start_flash()
            self.pump(delay)
            window.cancel_flash()
            window.cancel_flash()  # double Cancel
            self.check(self.wait_flash_idle(window), f"{label}: settled")
            final = window.current_step()
            self.check(final in ("Cancelled", Step.DONE.value), f"{label}: final state {final!r}")
            if final == "Cancelled":
                self.check(adapter.programs == before, f"{label}: program paths restored")
                self.check(adapter.applications == before_apps, f"{label}: symbol paths restored")
            self.check(adapter.connected_to is None, f"{label}: disconnected")
        self.check(self.dialogs == [], f"races: cancels show no error dialog: {self.dialogs}")

        downloads = adapter.calls.count("download")
        window.start_flash()
        window.start_flash()  # double Flash
        running = [k for k in window._workers.running_keys() if k.startswith("flash")]
        self.check(len(running) == 1, f"races: double Flash runs one worker, got {running}")
        try:
            window.export_bundle(self.workdir / "bundle_during_flash")
            refused = False
        except RuntimeError:
            refused = True
        self.check(refused, "races: debug bundle export refused while flashing")
        self.check(self.wait_step(window, Step.DONE.value, 10.0), "races: double-Flash run completed")
        self.check(self.wait_flash_idle(window), "races: double-Flash worker released")
        self.check(adapter.calls.count("download") == downloads + 1, "races: exactly one download for double Flash")
        self.close_window(window, "races")

        # Window closed mid-download: rollback finished before close() returns.
        adapter = FakeWinIDEAAdapter(download_seconds=10.0)
        window = self.new_window(adapter)
        window.on_firmware_ready(self.artifact("close"), SOURCE)
        window.start_flash()
        in_flight = self.wait_step(window, Step.DOWNLOAD.value, 5.0) and window.flash_active()
        self.check(in_flight, "races: long flash downloading (worker running) before close")
        self.questions.clear()
        self.close_window(window, "races: closed mid-download", max_s=3.0)
        if in_flight:
            self.check(len(self.questions) == 1, "races: close asked for confirmation once")
            self.check(adapter.programs["App"] == OLD_APP, "races: close rolled back App")
            self.check(adapter.applications == {"CM7_0": OLD_CM7_0, "CM7_1": OLD_CM7_1},
                       "races: close rolled back symbol paths")
            self.check(adapter.connected_to is None, "races: close disconnected")

        # Closed during the GitLab fetch, before any flash worker exists.
        window = self.new_window(FakeWinIDEAAdapter(), FakeGitLabSession(delay_s=0.4))
        self.open_dialog(window).load_refs()
        self.check(self.pump_until(window.gitlab_busy, 2.0), "races: GitLab fetch in flight before close")
        self.check(not window.flash_active(), "races: no flash worker before close")
        self.close_window(window, "races: closed during GitLab fetch", max_s=3.0)

    def section_theme(self) -> None:
        app = QApplication.instance()
        adapter = FakeWinIDEAAdapter(download_seconds=6.0)
        window = self.new_window(adapter)
        window.on_firmware_ready(self.artifact("theme"), SOURCE)
        self.dialogs.clear()
        window.start_flash()
        self.check(self.wait_step(window, Step.DOWNLOAD.value, 5.0), "theme: flash downloading")
        for dark in (True, False, True):
            t0 = time.monotonic()
            window.apply_dark_mode(dark)
            log.info("Theme switch took %.2f s (%d top-level widgets)", time.monotonic() - t0, len(app.topLevelWidgets()))
            name = "dark" if dark else "light"
            self.check(current_theme_name() == name and THEMES[name]["primary"] in app.styleSheet(),
                       f"theme: switched to {name} while flashing")
            self.pump(0.1)
        self.check(window.flash_active() and window.ui.pushButton_flash.property("state") == "flashing",
                   "theme: button still Cancel while flashing")
        self.check(self.wait_step(window, Step.DONE.value, 10.0), "theme: flash reached Done in dark mode")
        self.check(self.wait_flash_idle(window), "theme: flash worker released")
        dialog = self.open_dialog(window)
        window.apply_dark_mode(False)
        self.check(dialog.isVisible() and current_theme_name() == "light", "theme: switched back with the dialog open")
        dialog.reject()
        self.check(self.dialogs == [], f"theme: no error dialogs: {self.dialogs}")
        self.close_window(window, "theme")
        apply_theme(app, False)

    def section_secrets(self) -> None:
        window = self.new_window(FakeWinIDEAAdapter(download_seconds=0.1))
        window.ui.comboBox_logLevel.setCurrentIndex(0)  # DEBUG: show everything
        log.info("token in a message: %s", TOKEN)
        log.error("request headers {'PRIVATE-TOKEN': '%s'}", TOKEN)
        log.debug("url https://gitlab.example.com/api/v4/projects?private_token=%s", TOKEN)
        window.ctx.add_error(RuntimeError(f"authentication failed for {TOKEN}"))
        self.check(self.pump_until(lambda: "token in a message" in window.log_visible_text(), 3.0),
                   "secrets: log lines reached the panel")
        panel = window.log_visible_text()
        self.check(TOKEN not in panel, "secrets: token absent from the log panel")
        self.check("***" in panel, "secrets: panel shows the masked token")
        for handler in logging.getLogger("wflash").handlers:
            handler.flush()
        file_text = self.log_file.read_text(encoding="utf-8")
        self.check(TOKEN not in file_text, "secrets: token absent from the log file")
        self.check("token in a message: ***" in file_text, "secrets: log file has the masked line")
        dialog = self.open_dialog(window)
        dialog.ui.lineEdit_token.setText(TOKEN)
        dialog.load_refs()  # the typed token goes to the (fake) keyring, never to the settings
        self.pump_until(lambda: not dialog.busy(), 5.0)
        dialog._note(logging.INFO, f"PRIVATE-TOKEN: {TOKEN}")
        self.check(TOKEN not in dialog.ui.plainTextEdit_gitlabLog.toPlainText(), "secrets: token absent from the GitLab log")
        dialog.reject()
        settings_file = self.workdir / f"window{self._window_count}" / "settings.json"
        self.check(settings_file.is_file() and TOKEN not in settings_file.read_text(encoding="utf-8"),
                   "secrets: token absent from settings.json")
        self.check(self.keyring.get(GITLAB_URL) == TOKEN, "secrets: token stored in the keyring")
        bundle = window.export_bundle(self.workdir / "bundle")
        with zipfile.ZipFile(bundle) as zf:
            contents = {name: zf.read(name).decode("utf-8", "replace") for name in zf.namelist()}
        leaked = [name for name, text in contents.items() if TOKEN in text]
        self.check(leaked == [], f"secrets: token absent from every bundle file (leaked in {leaked})")
        self.check("authentication failed for ***" in contents.get("errors.txt", ""), "secrets: bundle errors masked")
        self.close_window(window, "secrets")


SECTIONS = {
    "flash": ("full fetch->map->flash, cancel mid-download, resize + log filter while live", Stress.section_flash),
    "rollback": ("every failure branch; workspace paths restored, failed rollback shown", Stress.section_rollback),
    "gitlab": ("dialog: CI + package, 401/403/404/connection, double-click, Stop, close mid-fetch",
               Stress.section_gitlab),
    "races": ("cancel at 0..400 ms, double Flash/Cancel, close mid-download / mid-fetch", Stress.section_races),
    "theme": ("light/dark switched while flashing and with the dialog open", Stress.section_theme),
    "secrets": ("a realistic PAT through panel, log file and debug bundle", Stress.section_secrets),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="list the sections and exit")
    parser.add_argument("--section", action="append", choices=sorted(SECTIONS), help="run only these (repeatable)")
    parser.add_argument("--iterations", type=int, default=2, help="repetitions of the flash section")
    parser.add_argument("--keep", action="store_true", help="keep the temporary work folder")
    args = parser.parse_args(argv)
    if args.list:
        for name, (description, _) in SECTIONS.items():
            print(f"{name:<9} {description}")
        return 0

    app = QApplication.instance() or QApplication([sys.argv[0]])
    workdir = Path(tempfile.mkdtemp(prefix="wflash_stress_"))
    log_file = setup_logging(log_dir=workdir / "logs")
    stress = Stress(workdir, log_file, args.iterations)

    def qt_handler(mode, context, message) -> None:
        if mode in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            if any(pattern in message for pattern in THREADING_PATTERNS):
                stress.qt_problems.append(message)
                print(f"  QT THREADING WARNING: {message}", flush=True)
            else:
                stress.qt_other.append(message)

    def excepthook(exc_type, exc, tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        stress.failures.append(f"uncaught exception: {text}")
        print(f"  UNCAUGHT: {text}", flush=True)

    def thread_excepthook(hook_args) -> None:
        excepthook(hook_args.exc_type, hook_args.exc_value, hook_args.exc_traceback)

    def unraisablehook(unraisable) -> None:
        stress.failures.append(f"unraisable: {unraisable.exc_value!r} in {unraisable.object!r}")

    previous_handler = qInstallMessageHandler(qt_handler)
    sys.excepthook = excepthook
    threading.excepthook = thread_excepthook
    sys.unraisablehook = unraisablehook

    def critical(parent, title, text, *rest):
        stress.dialogs.append((title, text))
        return QMessageBox.StandardButton.Ok

    def question(parent, title, text, *rest):
        stress.questions.append(text)
        return stress.answer

    QMessageBox.critical = staticmethod(critical)
    QMessageBox.warning = staticmethod(critical)
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(question)
    # The GitLab dialog reads/writes the token through these; keep the real keyring out of it.
    gitlab_dialog.get_token = stress.keyring.get
    gitlab_dialog.set_token = stress.keyring.__setitem__

    selected = args.section or list(SECTIONS)
    started = time.monotonic()
    for name in selected:
        print(f"== {name}: {SECTIONS[name][0]}", flush=True)
        t0 = time.monotonic()
        try:
            SECTIONS[name][1](stress)
        except Exception:
            stress.failures.append(f"section {name} raised:\n{traceback.format_exc()}")
            print(traceback.format_exc(), flush=True)
        print(f"   {name} done in {time.monotonic() - t0:.1f}s", flush=True)

    stress.pump(0.3)  # let late queued signals arrive while the handlers still listen
    stress.check(workers._ABANDONED == [], f"no worker was abandoned: {[w.key for w in workers._ABANDONED]}")
    stray = [t.name for t in threading.enumerate()
             if t is not threading.main_thread() and not isinstance(t, threading._DummyThread)]
    stress.check(stray == [], f"no Python worker threads left: {stray}")
    close_file_handler()
    del app
    stress.pump(0.0)
    qInstallMessageHandler(previous_handler)  # after teardown, so teardown warnings are seen

    passed = not stress.failures and not stress.qt_problems
    print(f"CHECKPOINTS={stress.checkpoints} FAILED={len(stress.failures)} "
          f"QT_THREADING_WARNINGS={len(stress.qt_problems)} OTHER_QT_WARNINGS={len(stress.qt_other)} "
          f"TIME={time.monotonic() - started:.1f}s")
    for failure in stress.failures:
        print(f"  - {failure.splitlines()[0]}")
    for message in sorted(set(stress.qt_other)):
        print(f"  other Qt warning (not a failure): {message}")
    print(f"STRESS_RESULT={'PASS' if passed else 'FAIL'}")
    if passed and not args.keep:
        shutil.rmtree(workdir, ignore_errors=True)
    else:
        print(f"work folder kept: {workdir}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run it to verify it passes**

Run: `~/.venvs/wflash/bin/python tools/stress_test.py --list` → Expected: six lines `flash`, `rollback`, `gitlab`, `races`, `theme`, `secrets`.
Run: `~/.venvs/wflash/bin/python tools/stress_test.py` → Expected: `CHECKPOINTS=348 FAILED=0 QT_THREADING_WARNINGS=0 …`, `STRESS_RESULT=PASS`, exit 0 (about 25 s; "other Qt warnings" are only the offscreen font/`propagateSizeHints()` notices).
Run: `~/.venvs/wflash/bin/pytest -k thread -v` → Expected: `38 passed`; `~/.venvs/wflash/bin/pytest -q` → Expected: `304 passed`.

Note for the theme section: the run keeps every closed window's widgets alive until the end of the process (pre-existing behaviour of `close_window`), so `app.setStyleSheet()` repolishes ~230 top-level widgets and takes about 1 s in the full run (0.02 s alone); the flash there lasts 6 s so the switches certainly happen while it runs. The log line `Theme switch took … (N top-level widgets)` records it.

- [ ] **Step 4: Walkthrough entry**

```markdown
## Phase 1.39: Stress test đi qua popup GitLab, thêm package và theme

Stress test phải chạy đúng đường người dùng: GitLab giờ nằm trong popup. Section `gitlab` mở popup, nạp ref, liệt kê job, tải (và tải lại từ cache), thử 401/403/404/mất kết nối, double-click, Stop (popup vẫn mở), đóng popup giữa lúc tải và đóng cửa sổ giữa lúc fetch/tải ở nhiều độ trễ; thêm Package Registry (bản mới nhất là zip, bản cũ là file thường để lại dòng đỏ). Section mới `theme` đổi sáng/tối ba lần khi đang flash và một lần khi popup mở. `secrets` kiểm thêm token gõ trong popup chỉ vào keyring giả, không vào `settings.json`, và log của popup đã che token. Keyring thật không bao giờ bị chạm.

### Thay đổi

- **`tools/stress_test.py`**: helper đi qua `GitlabDialog`, section `gitlab` viết lại, section `theme` mới, `secrets` mở rộng, keyring giả.

### Đã kiểm tra

- Trước khi sửa: `STRESS_RESULT=FAIL` (`refresh_gitlab` không còn). Sau khi sửa, `--list`, chạy đủ, `pytest -k thread -v`, `pytest -q`: <kết quả thật>
```

- [ ] **Step 5: Commit**

```bash
git add tools/stress_test.py docs/walkthrough.md
git commit -m "test: stress test drives GitLab through the popup and switches themes mid-flash" -m "$TRAILER"
```

---

### Task 14: Packaging and README

**Files:**
- Modify: `wflash.spec`, `README.md`
- Test: `tests/test_packaging.py`

**Interfaces:**
- Consumes: `wflash/resources/*.qss` (Task 8), `pyproject.toml` package-data (Task 8).
- Produces: the PyInstaller build ships `wflash/resources` at the same relative place `style.py` resolves (`Path(__file__).parents[1] / "resources"` → `_MEIPASS/wflash/resources` in a frozen build).

- [ ] **Step 1: Write the failing test `tests/test_packaging.py`**

```python
"""The build must ship everything the app reads at runtime."""
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_pyinstaller_spec_bundles_the_stylesheets():
    spec = (REPO / "wflash.spec").read_text(encoding="utf-8")
    assert '("wflash/resources", "wflash/resources")' in spec
    assert '("profiles", "profiles")' in spec


def test_package_data_includes_the_stylesheets():
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    assert "resources/*.qss" in data["tool"]["setuptools"]["package-data"]["wflash"]
    for name in ("style.qss", "style_dark.qss"):
        assert (REPO / "wflash" / "resources" / name).is_file()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `~/.venvs/wflash/bin/pytest tests/test_packaging.py -v`
Expected: `1 failed, 1 passed` — `assert '("wflash/resources", "wflash/resources")' in …` (the package-data half already passes since Task 8).

- [ ] **Step 3: Implement**

In `wflash.spec` replace the `datas = …` line with:

```python
# wflash/resources holds the Teal stylesheets; wflash/gui/style.py finds them next to the
# package (__file__-relative), so they keep the same relative place inside the bundle.
datas = [("profiles", "profiles"), ("wflash/resources", "wflash/resources")]
```

Replace the content of `README.md` (keep the file mode — edit in place) with:

```markdown
# WFlash Tool

Tool desktop (Python + PySide6) để flash ECU **NXP SAF85xx** qua **winIDEA 9.21** (`isystem.connect`):
chọn artifact từ GitLab CI, tự map file `.s3`/`.elf` vào workspace winIDEA đang mở, download vào external flash Winbond, reset + halt.

> Trạng thái: GUI, GitLab, cache, mapping, workflow (kèm rollback) và log đã chạy với **fake adapter**.
> Adapter winIDEA thật (Plan 2) sẽ được viết sau khi có kết quả spike (`spike/README.md`).

## Chạy từ source

macOS (dev, fake adapter) — venv nằm **ngoài** OneDrive:

    python3 -m venv ~/.venvs/wflash          # Python 3.11 trở lên
    ~/.venvs/wflash/bin/pip install -e ".[dev]"
    ~/.venvs/wflash/bin/python -m wflash --adapter fake

Windows (Python cùng bitness với winIDEA, thường là 64-bit):

    py -3 -m venv %USERPROFILE%\.venvs\wflash
    %USERPROFILE%\.venvs\wflash\Scripts\python -m pip install -e ".[dev]"
    %USERPROFILE%\.venvs\wflash\Scripts\python -m wflash            (mặc định --adapter real: chưa dùng được, xem lưu ý dưới)
    %USERPROFILE%\.venvs\wflash\Scripts\python -m wflash --adapter fake

> **Lưu ý:** adapter winIDEA thật **chưa có** (Plan 2, viết sau spike), nên chạy `python -m wflash` không tham số (mặc định `--adapter real`) hiện sẽ báo lỗi. Tạm thời dùng `python -m wflash --adapter fake`. Với bản `WFlash.exe` đã build, tạo shortcut với tham số `--adapter fake` (Target: `...\WFlash.exe --adapter fake`).

`isystem.connect` **không** cài từ PyPI: cài từ thư mục cài đặt winIDEA 9.21 (xem `spike/README.md`) để version khớp với winIDEA.

Cũng có thể chạy bằng file `main.py` ở thư mục gốc repo (cùng app, cùng tham số; chạy được cả khi đứng ở thư mục khác):

    ~/.venvs/wflash/bin/python main.py --adapter fake                          (macOS)
    %USERPROFILE%\.venvs\wflash\Scripts\python main.py --adapter fake          (Windows)

Tham số: `--adapter real|fake`, `--verbose` (log mọi lời gọi winIDEA), `--smoke` (mở rồi tự đóng sau 1,5 s, để kiểm tra khởi động).

Fake adapter giả lập lỗi qua biến môi trường `WFLASH_FAKE_FAIL` (nối bằng dấu phẩy):
`list_instances` (không có instance), `connect`, `connection_lost`, `read_programs`, `read_applications`,
`set_path` (đổi path bị từ chối — cả lúc rollback, nên GUI hiện cảnh báo ROLLBACK FAILED), `download` (lỗi ở 50%), `reset`.
`WFLASH_FAKE_DOWNLOAD_S=10` đổi thời gian download giả lập.

## Cấu hình

1. **Load from GitLab…** (popup, mở từ vùng *Setting*): GitLab URL, Personal Access Token (scope `read_api`, lưu trong Windows Credential Manager / keychain, không bao giờ ghi ra file), ô **Verify TLS certificate** (mặc định bật; chỉ tắt khi ở mạng tin cậy — app ghi một dòng WARNING mỗi phiên), CA bundle nếu GitLab dùng chứng chỉ nội bộ.
2. **Preferences…**: thư mục cache + số bản tải giữ lại + nút **Clear cache** (xóa cả artifact CI lẫn package), thư mục profile, verbose, **Dark mode** (áp dụng ngay và được lưu lại).
3. **Profile** (`profiles/*.yaml`): project GitLab, filter tên job, tên entry download và tên Application trong winIDEA, pattern file. Xem `profiles/saf85xx_example.yaml`.

## Giao diện

- Một cửa sổ duy nhất. Phần đầu: nút **Flash** lớn (khi đang flash, chính nút đó thành **Cancel** màu đỏ), thanh tiến trình, nhãn `phần trăm | ETA | Speed` và `Step: …`.
- Vùng **Setting** (trái): profile, nguồn firmware (**Load from GitLab…** và thẻ cho biết đang dùng artifact/package nào), instance winIDEA, Reset/Run sau khi flash, **Preferences…**.
- Bảng mapping (phải) có cột `#`; dòng đỏ là dòng chưa có file. Dưới cùng là tab **Information** (log). Thanh trạng thái hiện version và tác giả.
- Theme **Teal** sáng (mặc định) hoặc tối. Speed/ETA chỉ là **ước lượng**: winIDEA chỉ báo phần trăm, còn số byte lấy từ kích thước file `.s3` trên đĩa.

## Quy trình

1. Chọn profile → **Load from GitLab…**:
   - Tab **CI Artifact**: project (mặc định lấy từ profile; sửa thì app nhớ theo từng profile) → **Load branches/tags** → chọn branch/tag → **Browse jobs…** rồi bấm **Download** ở dòng muốn tải (hoặc nhấp đúp), hoặc bấm **Download Selected Artifact**: tải job đang chọn, nếu chưa chọn dòng nào thì tải job thành công mới nhất khớp branch/tag + job name.
   - Tab **Package Registry**: project + tên package → **Fetch Latest Version**, hoặc **Browse versions…** rồi tải một version (file đầu tiên của version; zip được giải nén, file thường được giữ nguyên).
   - **Stop** hủy lần tải đang chạy (popup vẫn mở); **Cancel** hủy rồi đóng popup. Tải xong popup tự đóng, cửa sổ chính dựng bảng mapping. Có cache theo job/version (nút ghi **Cached**).
2. Kiểm tra bảng mapping; dòng đỏ (0 hoặc nhiều file khớp) phải chọn file thủ công — nút Flash chỉ bật khi mọi dòng đã có file.
3. Chọn instance winIDEA đang mở → **Flash**. Lỗi hoặc **Cancel** trong lúc đổi path/download sẽ khôi phục đường dẫn cũ trong workspace. Nếu chính việc khôi phục thất bại, cửa sổ hiện dải đỏ **ROLLBACK FAILED**: kiểm tra lại danh sách download/symbol file trong winIDEA trước khi flash tiếp.
4. Đóng cửa sổ khi đang flash: tool hỏi xác nhận, hủy flash, chờ rollback xong rồi mới đóng.

## Log và gửi lỗi

- Tab **Information** ở dưới cửa sổ (màu theo level và theo theme, lọc level, Copy, Clear). Popup GitLab có ô **GitLab log** riêng; các dòng đó cũng nằm trong log file.
- Log file: `%LOCALAPPDATA%\WFlash\logs\` (Windows), `~/Library/Logs/WFlash/` (macOS), giữ 20 file gần nhất.
- **Export debug bundle…**: tạo `wflash_debug_<thời gian>.zip` gồm log, môi trường, profile, mapping, nguồn firmware (`source.json`), trạng thái workspace trước/sau và traceback. Token đã được che (`***`). Không xuất được trong lúc đang flash.

## Phát triển

- Layout GUI nằm trong các file Qt Designer `wflash/gui/main_window.ui`, `wflash/gui/gitlab_dialog.ui`, `wflash/gui/preferences_dialog.ui`. Sau khi sửa `.ui`:

      ~/.venvs/wflash/bin/pyside6-uic wflash/gui/main_window.ui -o wflash/gui/ui_main_window.py
      ~/.venvs/wflash/bin/pyside6-uic wflash/gui/gitlab_dialog.ui -o wflash/gui/ui_gitlab_dialog.py
      ~/.venvs/wflash/bin/pyside6-uic wflash/gui/preferences_dialog.ui -o wflash/gui/ui_preferences_dialog.py

  Không sửa tay `ui_*.py`.
- Theme: `wflash/resources/style.qss` (sáng) và `style_dark.qss` (tối) dùng đúng các màu trong `wflash/gui/theme.py` (`THEMES`); sửa màu thì sửa cả ba.
- Test:

      ~/.venvs/wflash/bin/pytest -q
      ~/.venvs/wflash/bin/pytest -k thread -v        # vòng đời worker — không bao giờ bỏ qua
      ~/.venvs/wflash/bin/pytest -k "not gui" -q     # chỉ core
      ~/.venvs/wflash/bin/python tools/stress_test.py   # stress test headless, in STRESS_RESULT=PASS/FAIL

## Build .exe (Windows)

    scripts\build_windows.bat

Script chạy toàn bộ test, `-k thread`, stress test rồi PyInstaller. Kết quả: `dist\WFlash\WFlash.exe` (copy cả thư mục `dist\WFlash`; thư mục `wflash\resources` chứa theme đã được gói kèm).
```

- [ ] **Step 4: Run everything (CLAUDE.md pre-push protocol)**

Run: `~/.venvs/wflash/bin/pytest tests/test_packaging.py -v` → Expected: `2 passed`.
Run: `~/.venvs/wflash/bin/pytest -q` → Expected: `306 passed`.
Run: `~/.venvs/wflash/bin/pytest -k thread -v` → Expected: `38 passed`.
Run: `~/.venvs/wflash/bin/pytest -k "not gui" -q` → Expected: `173 passed`.
Run: `~/.venvs/wflash/bin/python tools/stress_test.py` → Expected: `STRESS_RESULT=PASS`.
Run: `QT_QPA_PLATFORM=offscreen ~/.venvs/wflash/bin/python main.py --adapter fake --smoke` → Expected: exit 0.
Dark-mode smoke without touching your own settings (macOS; on Windows `test_gui_root_main_smoke_in_dark_mode` covers it):

```bash
H=$(mktemp -d); mkdir -p "$H/Library/Application Support/WFlash"
echo '{"dark_mode": true}' > "$H/Library/Application Support/WFlash/settings.json"
HOME=$H QT_QPA_PLATFORM=offscreen ~/.venvs/wflash/bin/python main.py --adapter fake --smoke; echo "exit=$?"
grep -h "Theme:" "$H"/Library/Logs/WFlash/*.log; rm -rf "$H"
```

Expected: `exit=0` and a line `wflash.main: Theme: dark`.

- [ ] **Step 5: Walkthrough entry**

```markdown
## Phase 1.40: Đóng gói theme và cập nhật README

Bản `.exe` phải mang theo hai file theme; `style.py` tìm chúng theo vị trí package nên spec PyInstaller chép `wflash/resources` vào đúng chỗ tương ứng. README mô tả giao diện mới (một cửa sổ, popup Load from GitLab với CI Artifact và Package Registry, Preferences, theme), cách cấu hình TLS/CA, và các file Designer cần sinh lại.

### Thay đổi

- **`wflash.spec`**: thêm `("wflash/resources", "wflash/resources")` vào `datas`.
- **`README.md`**: cấu hình, giao diện, quy trình mới, log/bundle (`source.json`), phát triển (3 file `.ui`, theme).
- **`tests/test_packaging.py`** (mới): 2 test.

### Đã kiểm tra

- RED / GREEN, `pytest -q`, `pytest -k thread -v`, `pytest -k "not gui" -q`, `tools/stress_test.py`, smoke sáng và tối: <kết quả thật>
```

- [ ] **Step 6: Commit**

```bash
git add wflash.spec README.md tests/test_packaging.py docs/walkthrough.md
git commit -m "build: bundle the theme stylesheets; README for the redesigned UI" -m "$TRAILER"
```

---

## Spec coverage

| Spec section | Task(s) |
|---|---|
| §1 goals (one window, SFlash header, Setting panel, one Information tab, GitLab popup, Teal light/dark) | 8, 10, 11, 12 |
| §1 out of scope (no menu bar, no OS-driven theme, no local file pick, core workflow unchanged) | nothing added; `FlashWorkflow` untouched |
| §2.1 flash header, one Flash/Cancel button, stats/step texts, rollback banner | 1 (texts), 12 |
| §2.1 ETA/Speed (`ProgressEstimator`, `.s3` size estimate, `None` = busy) | 1, 12 |
| §2.2 Setting panel widgets and source card texts | 2, 12 |
| §2.3 mapping table `#` column, red rows, hint label | 12 |
| §2.4 Information tab, themed log colours | 8, 12 |
| §2.5 status bar version/author, `APP_AUTHOR` | 12 |
| §2.6 removed widgets | 12 (`test_gui_old_widgets_are_gone`) |
| §3 popup, connection box, TLS warning once, CA, keyring, settings saved on close/operation | 10, 11 |
| §3.2 CI tab (project default + per-profile override, refs, job name, Download Selected rule, Browse jobs table, Cached/Downloading…, double-click) | 6, 10, 11 |
| §3.3 Package Registry (`PackageVersion`, `list_package_versions`, `download_package`, errors, `store_file`, `packages` cache) | 3, 4, 5, 6, 11 |
| §3.4 progress/status/Stop, GitLab log, Cancel, `firmwareReady` → `on_firmware_ready`, `FirmwareSource` in bundle, errors, threading | 2, 7, 11, 12 |
| §4 Preferences (no GitLab fields, dark mode applied on OK and saved) | 9, 12 |
| §5 `AppSettings` fields and dict type check | 3 |
| §6 Teal tokens, `.qss` files, `load_stylesheet`, `theme.py`, dynamic properties, PyInstaller datas | 8, 12, 14 |
| §7 GUI architecture after the change | 12 |
| §8 error handling (taxonomy unchanged, package errors with hints, dialog closed mid-way, missing theme file) | 5, 6, 8, 11 |
| §9 tests (core, GUI, `-k thread`, stress test, light/dark smoke) | every task; 13, 14 |
| §10 risks (package token scope on real GitLab, speed is an estimate) | README (14); real-GitLab check stays for the Windows test (Plan 1b Task 25) |
