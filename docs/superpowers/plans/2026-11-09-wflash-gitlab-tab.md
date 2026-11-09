# GitLab tab, Setting tab and menu bar — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the developer panel and the Preferences dialog with a GitLab tab (App, Boot Manager, Flash Bootloader, each from its checked-out commit or manual), a three-group Setting tab and a menu bar; add pipeline waiting, finish notifications, a flash history CSV and an English user guide.

**Architecture:** Core gains small pure helpers (GitLab URL split, commit job lookup with a "not ready" error, flash history writer, `core_states`, `program_stats`). The GUI gets one reusable `PartController` per part (App, BM, FBL) that owns the repo read, checkout, mode, auto-load, manual load and pipeline wait of that part, drawn into three identically named frames of `main_window.ui`. The flash path (`flash_workflow`, `flash_plan`, `download`) is untouched apart from reporting stats.

**Tech Stack:** Python 3.11+, PySide6 (Designer `.ui` + `pyside6-uic`), requests, pydantic v2, keyring, truststore, pytest, pytest-qt.

**Spec:** `docs/superpowers/specs/2026-11-09-wflash-gitlab-tab-design.md`

## Global Constraints

- GUI text English; documentation (walkthrough, README, Windows guide) Vietnamese.
- `.ui` first, regenerate with `~/.venvs/wflash/bin/pyside6-uic`; never hand-edit `ui_*.py`; meaningful widget names.
- `wflash/core/**` imports no Qt; only `winidea_adapter.py` imports `isystem.connect`, lazily.
- Every business error inherits `WFlashError` and has a `hint`.
- Threading rules of `CLAUDE.md`: workers via `WorkerRegistry`, slots are bound methods, generation guard before cancel, nothing waits on the GUI thread without a bound.
- Never auto-flash. Flash path behaviour unchanged.
- Settings stay `dict[str, str]` / scalar fields (the loader's type check); per-part values use keys `"<profile file>#<part>"`.
- Commit trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Before pushing: full suite, `pytest -k thread`, `tools/stress_test.py`.

---

### Task 1: Settings, profile and GitLab URL helpers

**Files:**
- Modify: `wflash/core/settings.py`, `wflash/core/profile.py`
- Create: `wflash/core/gitlab_url.py`
- Rename: `profiles/suz05_m7_ffi.yaml` → `profiles/suz05.yaml` (`name: SUZ05`, `gitlab.url`, short project names)
- Test: `tests/test_gitlab_url.py`, `tests/test_settings.py`, `tests/test_profile.py`

**Interfaces (produces):**
- `gitlab_url.split_gitlab_url(url: str) -> tuple[str, str]` → `(host_url, group_path)`; `("https://gitlab.hella.com", "alm/.../e-ad_radar_cust_suz05_group")`; trailing `/` and `/-/…` tails removed; no path → `""`.
- `gitlab_url.project_path(group: str, project: str) -> str`: `project` if it contains `/` or `group` is empty, else `f"{group}/{project}"`.
- `GitLabSpec.url: str | None = None`; `Profile.display_name` = `name`.
- `AppSettings` new fields: `gitlab_urls: dict[str,str]` (profile file → URL override), `part_repos`, `part_projects`, `part_modes` (`"commit"`/`"manual"`), `part_manual` (JSON string of the manual choice) — all `dict[str,str]` keyed `"<profile file>#<part>"`; `reset_target: bool = True`, `run_after_reset: bool = False`, `verify_samples: bool = False`, `advanced_debug: bool = False`, `window_geometry: str = ""` (base64), `last_tab: int = 0`, `settings_version: int = 2`.
- `AppSettings.migrate()`: copies keys `suz05_m7_ffi.yaml` → `suz05.yaml` in `source_repos`, `last_build`, `ci_project_overrides`, `last_profile`, and `source_repos[p]` → `part_repos[f"{p}#app"]`, when the new key is missing. Called by `load()`.
- `AppSettings.gitlab_url_for(profile_file: str, profile_url: str | None) -> str`: override, else profile URL, else legacy `gitlab_url`.

- [ ] Write tests: split/join cases (with group, no group, trailing slash, `/-/tree/x`, project with `/`); migration copies once and never overwrites; `gitlab_url_for` precedence; profile with `gitlab.url` loads; `suz05.yaml` loads with `name: SUZ05`.
- [ ] Run them, see them fail; implement; run green.
- [ ] Rename the profile with `git mv`, update tests that load `suz05_m7_ffi.yaml` (`tests/test_gui_source_panel.py`, `tools/stress_test.py`).
- [ ] Commit `feat(core): GitLab URL with group, per-part settings, SUZ05 profile`.

### Task 2: GitLab client by host, token by host, commit jobs that may not be ready

**Files:**
- Modify: `wflash/core/settings.py` (`get_token`/`set_token` by host with legacy fallback), `wflash/core/firmware_fetch.py`, `wflash/core/errors.py`, `wflash/gui/gitlab_dialog.py` (`default_client_factory`)
- Test: `tests/test_firmware_fetch.py`, `tests/test_settings.py`, `tests/test_gui_gitlab_dialog.py`

**Interfaces (produces):**
- `get_token(url)` looks up `split_gitlab_url(url)[0]` first, then the full URL (tokens saved by older versions); `set_token(url, token)` stores under the host.
- `default_client_factory(settings, url)` → `GitLabClient(host, token)`; client always verifies TLS.
- `errors.PipelineNotReady(GitLabError)` with `.waiting: bool` (True for `created`, `pending`, `running`, `preparing`, `waiting_for_resource`, `scheduled`).
- `firmware_fetch.find_commit_jobs(client, project_id, sha, names: list[str], cancel=None) -> list[JobRow]`: newest pipeline of `sha` where every named job succeeded; no pipeline → `PipelineNotReady(waiting=False, "No pipeline for <sha8> yet.")`; any named job in a waiting state in the newest pipeline → `PipelineNotReady(waiting=True, "Waiting for pipeline: <job> is <status>…")`; otherwise `PipelineNotReady(waiting=False, "Job <name> of <sha8> is <status>.")`. `find_build_jobs` becomes a thin wrapper.

- [ ] Tests with the fake GitLab session: success; running → waiting; manual → not waiting; no pipeline; token host fallback.
- [ ] Implement; green; commit `feat(core): commit jobs that are not ready yet, token per GitLab host`.

### Task 3: Adapter `core_states`, `program_stats`, flash history, always-on call log

**Files:**
- Modify: `wflash/core/winidea_adapter.py` (Protocol + real), `wflash/core/fake_adapter.py`, `tests/fake_isystem.py`, `wflash/core/logging_setup.py`, `wflash/main.py`, `wflash/core/debug_bundle.py`
- Create: `wflash/core/flash_history.py`
- Test: `tests/test_real_adapter.py`, `tests/test_fake_adapter.py`, `tests/test_flash_history.py`, `tests/test_debug_bundle.py`

**Interfaces (produces):**
- `WinIDEAAdapter.core_states() -> list[tuple[str, str]]` (name, status text); real: `_core_states` over the session (connected), fake: fixed list; raises `WinIDEAError` on failure.
- `adapter.program_stats: dict[str, float | int]` with `resets`, `tries`, `program_s`; reset to zeros at the start of `download()`; fake fills `1, 1, download_seconds`.
- `flash_history.HISTORY_COLUMNS` (spec 4.10), `history_path() -> Path` (`%LOCALAPPDATA%\WFlash\flash_history.csv`, macOS cache dir), `append_flash(row: dict[str, str], path=None, keep=5000) -> None` (UTF-8 with BOM, header once, trims to `keep` rows, `redact` every value, errors only logged).
- `set_verbose` removed from use: `setup_logging` always sets the calls logger to DEBUG; `--verbose` still parsed.
- Debug bundle adds `flash_history.csv` when it exists.

- [ ] Tests, implement, green, commit `feat(core): core states, program stats, flash history`.

### Task 4: Main window `.ui`: menu bar, three tabs, Setting groups; drop Preferences; GitLab dialog without connection

**Files:**
- Modify: `wflash/gui/main_window.ui` (→ `ui_main_window.py`), `wflash/gui/gitlab_dialog.ui` (→ `ui_gitlab_dialog.py`), `wflash/resources/style*.qss`
- Delete: `wflash/gui/preferences_dialog.py`, `preferences_dialog.ui`, `ui_preferences_dialog.py`, `tests/test_gui_preferences_dialog.py`
- Test: `tests/test_gui_ui_files.py`, `tests/test_gui_window_min_size.py`

**Interfaces (produces) — widget names:**
- Menu: `menuBar_main`, `menu_file` (`action_exportBundle` Ctrl+E, `action_openHistory`, `action_openLogFolder`, `action_openDownloadFolder`, `action_exit` Ctrl+Q), `menu_view` (`action_darkMode` checkable, `action_tabFlash` Ctrl+1, `action_tabGitlab` Ctrl+2, `action_tabSetting` Ctrl+3), `menu_tools` (`action_testGitlab`, `action_checkCores`, `action_refreshInstances` F5), `menu_help` (`action_userGuide` F1, `action_about`).
- Tabs: `tabWidget_main` with `tab_flash`, `tab_gitlab`, `tab_setting`.
- Flash tab: `frame_firmwareSummary` with `label_summaryApp`, `label_summaryBm`, `label_summaryFbl`, `label_summaryAdvanced` (rich text filled in code); non-developer `frame_gitlabSource` (unchanged); tables unchanged.
- GitLab tab: for each part `p` in `app`, `bm`, `fbl`: `groupBox_<p>`, `lineEdit_<p>Project`, `lineEdit_<p>Repo`, `pushButton_<p>Browse`, `label_<p>Branch`, `pushButton_<p>Checkout`, `label_<p>Commit`, `pushButton_<p>Reload`, build widget (`comboBox_appBuild`, `label_bmBuild`, `label_fblBuild`), `radioButton_<p>Commit`, `radioButton_<p>Manual`, `pushButton_<p>ChooseJob`, `label_<p>Status`; `checkBox_advancedDebug` (styled as a switch); `widget_debugParts` (BM + FBL, hidden when off).
- Setting tab: `groupBox_profile` (`comboBox_profile`, `pushButton_reloadProfiles`, `lineEdit_profilesDir`, `pushButton_browseProfilesDir`, `lineEdit_downloadDir`, `pushButton_browseDownloadDir`, `label_settingError`), `groupBox_gitlab` (`lineEdit_gitlabUrl`, `lineEdit_token`), `groupBox_winidea` (`comboBox_instance`, `pushButton_refreshInstances`, `checkBox_reset`, `checkBox_run`, `checkBox_verifyFlash`).
- Removed: old developer widgets on the Flash tab and Setting (`frame_developer`, `frame_sourceRepoSetting`, `lineEdit_sourceRepo`, `comboBox_build`, `pushButton_loadBuild`, `label_loadStatus`, `pushButton_chooseJob`, `pushButton_loadBm/Fbl`, `label_bmSource/FblSource`, `label_repo*`, `pushButton_preferences`, hint labels).
- GitLab dialog: connection group removed (`lineEdit_gitlabUrl`, `lineEdit_token`, `checkBox_verifyTls`, `label_connectionHint`).

- [ ] Restructure with a scripted ElementTree edit, regenerate, update ui tests (tab names, menus, widget parents), commit with Task 5 (code depends on names).

### Task 5: `PartController` and the GitLab tab

**Files:**
- Create: `wflash/gui/part_controller.py`, `wflash/gui/gitlab_tab.py` (mixin, replaces `source_panel.py`)
- Modify: `wflash/gui/main_window.py`, `wflash/gui/checkout_dialog.py` (part label, progress), `wflash/gui/mapping_table.py`, `wflash/gui/flash_mixin.py`, `wflash/gui/gitlab_dialog.py` (`prepare(label, job, project=, cache=)` unchanged; connection from settings)
- Delete: `wflash/gui/source_panel.py`
- Test: `tests/test_gui_gitlab_tab.py` (replaces `tests/test_gui_source_panel.py`), `tests/test_gui_checkout_dialog.py`

**Interfaces (produces):**
- `PartController(QObject)`: `name` (`"app"|"bm"|"fbl"`), `label` ("App", "Boot Manager", "Flash Bootloader"), `short` ("App", "BM", "FBL"), widgets bound by name; state `repo_state: RepoState|None`, `mode: str`, `source: dict[role, (Path, FirmwareSource)]`; methods `configure(profile, settings_key)`, `refresh_repo()`, `on_window_activated()`, `load_for_commit()`, `choose_job()`, `take_firmware(role, path, source)`, `busy() -> bool`, `abort_for_close()`; signals `firmwareChanged`, `busyChanged`, `progress(int|None, str)`.
- Jobs of a part: app → `[build.ffi_job, build.elf_job]` (roles `ffi`, `elf`), bm → `[build.bm_job]` (role `bm`), fbl → `[debug_sources.fbl.job]` (role `fbl`).
- Auto-load runs when mode is `commit`, a repo state is known, flash is not active, and the loaded commit differs (or nothing is loaded); it never runs twice for the same `(commit, build)` while one runs.
- Status text format: `<SHORT>: <job> · <branch> · <commit8> · Cached|Downloaded` per role; errors show `str(exc)`.
- `GitlabTabMixin`: builds the three controllers in `_init_gitlab_tab()`, `developer_mode()`, `advanced_debug()`, `flash_request_extras()`, `flash_block_reason()`, `rebuild_developer_rows()`, `on_developer_firmware()`; `changeEvent` activation calls each controller's `on_window_activated`.

- [ ] Tests (fake git repo + fake GitLab session as in `test_gui_source_panel.py`): app commit mode loads FFI+ELF; manual mode keeps choice when commit changes; BM without repo forces Manual; BM job follows App build; advanced off hides BM/FBL and rows; checkout per part; activation reloads repo; no load while flashing; close while loading.
- [ ] Implement, green, commit `feat(gui): GitLab tab with App, Boot Manager and Flash Bootloader parts`.

### Task 6: Pipeline wait

**Files:** `wflash/gui/part_controller.py`; Test: `tests/test_gui_gitlab_tab.py`

**Interfaces:** `PartController` keeps `_wait_until: float|None`, a `QTimer` (`POLL_S = 30`, `WAIT_LIMIT_S = 3600`) started on `PipelineNotReady(waiting=True)`; stops on commit/mode/profile/build change, close, limit (status "Stopped waiting after 60 min."); a poll that would load while flashing defers until `flashFinished`.

- [ ] Tests with patched poll interval: running → success loads; commit change stops; close stops timer; flash active defers.
- [ ] Implement, green, commit `feat(gui): wait for a running pipeline`.

### Task 7: Flash tab summary, progress on the Flash bar

**Files:** `wflash/gui/flash_mixin.py`, `wflash/gui/gitlab_tab.py`; Test: `tests/test_gui_flash.py`, `tests/test_gui_gitlab_tab.py`

**Interfaces:** `FlashMixin.show_side_progress(percent: int|None, text: str)` / `clear_side_progress()` used only while no flash runs; Flash button disabled while any part is busy; summary labels rendered by `GitlabTabMixin.render_summary()` (title + pill + key/value lines, no CAL).

- [ ] Tests, implement, green, commit `feat(gui): firmware summary and download progress on the Flash bar`.

### Task 8: Setting tab, persistence and restore

**Files:** `wflash/gui/main_window.py` (setting wiring), `wflash/gui/gitlab_tab.py`; Test: `tests/test_gui_setting_tab.py`

**Interfaces:** URL and token saved on `editingFinished` (token → keyring by host); folders validated (`label_settingError`), profiles folder change reloads profiles; reset/run/verify/advanced saved on toggle; window geometry and tab saved in `closeEvent`; restore at start; manual choice stored as JSON `{"project","job_id","job_name","ref","commit","path"}` and restored when `path` still holds the cache marker; profile combo shows `profile.name` (file name added on duplicates).

- [ ] Tests, implement, green, commit `feat(gui): Setting tab saves at once; restore the last session`.

### Task 9: Menu actions, notifications, flash history, user guide

**Files:** create `wflash/gui/menu_actions.py`; modify `main_window.py`, `flash_mixin.py`, `pyproject.toml` (`resources/help/*`); Test: `tests/test_gui_menu.py`

**Interfaces:** `MenuActionsMixin._init_menu()` connects every action; `open_path(path)` via `QDesktopServices.openUrl`; `test_gitlab_connection()` worker (`get_project_id` of the App project); `check_cores()` worker (connect selected instance, `core_states`, disconnect); About via `QMessageBox.about`; notifications via a `QSystemTrayIcon` built in `__init__` (shown only while notifying) + `QApplication.alert`, only when `not isActiveWindow()`; history row written in the flash finished slot.

- [ ] Tests, implement, green, commit `feat(gui): menu bar, notifications, flash history`.

### Task 10: Stress test, docs, walkthrough

**Files:** `tools/stress_test.py`, `README.md`, `CLAUDE.md`, `docs/walkthrough.md`, `docs/windows_test_guide.md` (Vòng 13), `wflash/resources/help/user_guide.html` (match final names).

- [ ] Stress: three parts, advanced toggles, activation spam, menu actions, pipeline wait then close.
- [ ] Full suite, `-k thread`, stress; app launches; commit and push.
