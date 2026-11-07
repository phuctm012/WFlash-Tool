# WFlash Developer Debugging (Plan 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a developer load firmware matching their source commit, check out from the app, cache by branch, optionally flash BM and FBL, and find the CAL file automatically.

**Architecture:** New pure-Python units (`source_repo`, `flash_plan`, `NamedArtifactCache`) hold the logic and are tested without winIDEA or Qt. `FlashWorkflow` gains a planned path used by profiles with `builds`; profiles without it keep today's path. The adapter gains row-level path and tick calls, added only after a spike has observed them.

**Tech Stack:** Python 3.11+, PySide6, pytest + pytest-qt, `git` CLI through `subprocess`, GitLab REST v4, `isystem.connect`.

**Spec:** `docs/superpowers/specs/2026-11-07-wflash-developer-debug-design.md`. API authority: `docs/winidea_api_notes.md`. Mockup: `docs/superpowers/mockups/developer-ui/`.

## Global Constraints

- Program only with `CSessionCtrl.begin_program()`. Never call `umi.write`, `erase`, `flush` or `getOptionJSON`. Keep the read that confirms programming.
- Never create a Download Files or Symbol Files row. Never change offsets, mass erase, verify or device options.
- Git commands never use `--force`, `stash`, `reset` or `clean`. The GitLab token never goes into a git command.
- `wflash/core/**` does not import PySide6. Only `wflash/core/winidea_adapter.py` imports `isystem.connect`, lazily.
- GUI layout goes in `.ui` first, regenerated with `pyside6-uic`; never hand-edit `ui_*.py`. Widgets are named `<kind>_<what>`. GUI text is English.
- Exception messages are short; technical detail goes to `log.error` and `__cause__`. Every error has a `hint`.
- Threading rules in `CLAUDE.md` apply: GitLab and git calls run in `WorkerRegistry` workers, with bound-method slots.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` as a second `-m`. Add a `## Phase 3.N` entry to `docs/walkthrough.md` in Vietnamese with each task.
- Tests: `~/.venvs/wflash/bin/pytest`. Before a push: full suite, `-k thread`, `tools/stress_test.py`.

## File Structure

- Create `spike/14_tick_options.py`, `spike/15_pipeline_sha.py`: hardware and GitLab probes.
- Create `wflash/core/source_repo.py`: read state, list, fetch, check out.
- Create `wflash/core/flash_plan.py`: workspace checks and the flash plan, pure logic.
- Modify `wflash/core/profile.py`, `artifact_cache.py`, `gitlab_client.py`, `firmware_fetch.py`, `srec.py`, `errors.py`, `settings.py`.
- Modify `wflash/core/winidea_adapter.py`, `fake_adapter.py`, `flash_workflow.py`.
- Create `wflash/gui/source_panel.py`: mixin for the source repo, Build, Advanced Debug and the two file tables.
- Create `wflash/gui/checkout_dialog.ui`, `checkout_dialog.py`.
- Modify `wflash/gui/main_window.ui`, `main_window.py`, `flash_mixin.py`, `gitlab_dialog.py`.
- Modify `profiles/suz05_m7_ffi.yaml`, `README.md`, `docs/windows_test_guide.md`, `docs/winidea_api_notes.md`.

---

### Task 1: Spikes. Stop here until the user sends results.

**Files:**
- Create: `spike/14_tick_options.py`, `spike/15_pipeline_sha.py`
- Modify: `spike/README.md`, `docs/windows_test_guide.md`, `docs/winidea_api_notes.md`

**Interfaces:**
- Produces: the observed option name for a symbol file's tick, recorded in `docs/winidea_api_notes.md`, used as `SYMBOL_TICK_FIELD` in Task 7.

- [ ] **Step 1: Write `spike/14_tick_options.py`**

```python
"""Spike 14: tìm và thử ghi dấu tick của Download Files và Symbol Files. KHÔNG flash.

Không tham số: chỉ đọc. --toggle-row i / --toggle-symbol j --field F: đảo giá trị, đọc lại, rồi khôi phục.
"""
from _common import Report, base_args, connect, try_call

DOWNLOAD = "/iOPEN/UMIConfig.Devices.Devices[0].DownloadFiles"
SYMBOLS = "/IDE/System.Debug.Applications[0].SymbolFiles.File"
FIELDS = ["Path", "Load", "Enabled", "Enable", "Use", "Used", "Active", "Checked",
          "Options.Load", "Options.LoadSymbols", "Options.LoadCode"]


def flip(report, ide, url):
    old = try_call(report, f"read {url}", lambda: ide.getOptionStr(url))
    if old not in ("true", "false"):
        report.line(f"{url}: not a true/false option -> skipped")
        return
    new = "false" if old == "true" else "true"
    try_call(report, f"setOption {url} = {new}", lambda: ide.setOption(url, new))
    try_call(report, "read back", lambda: ide.getOptionStr(url))
    try_call(report, f"restore {old}", lambda: ide.setOption(url, old))
    try_call(report, "read after restore", lambda: ide.getOptionStr(url))


def main() -> None:
    parser = base_args(__doc__)
    parser.add_argument("--toggle-row", type=int)
    parser.add_argument("--toggle-symbol", type=int)
    parser.add_argument("--field", default="Load")
    args = parser.parse_args()
    report = Report("14_tick_options")
    try:
        ic, cmgr = connect(report, args.instance)
        ide = ic.CIDEController(cmgr)
        report.section("download rows")
        for i in range(ide.getDynamicOptionSize(DOWNLOAD)):
            for field in ("Path", "Enabled", "Offset"):
                try_call(report, f"[{i}] {field}", lambda f=field, n=i: ide.getOptionStr(f"{DOWNLOAD}[{n}].{f}"))
        report.section("symbol files of application 0")
        for j in range(10):
            if not ide.optionExists(f"{SYMBOLS}[{j}].Path"):
                break
            for field in FIELDS:
                try_call(report, f"[{j}] {field}", lambda f=field, n=j: ide.getOptionStr(f"{SYMBOLS}[{n}].{f}"))
        if args.toggle_row is not None:
            report.section("toggle download row")
            flip(report, ide, f"{DOWNLOAD}[{args.toggle_row}].Enabled")
        if args.toggle_symbol is not None:
            report.section("toggle symbol file")
            flip(report, ide, f"{SYMBOLS}[{args.toggle_symbol}].{args.field}")
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write `spike/15_pipeline_sha.py`**

```python
"""Spike 15: tìm pipeline theo commit trên GitLab thật. Chỉ đọc, không cần winIDEA.

Token lấy từ biến môi trường GITLAB_TOKEN, không ghi ra file kết quả.
"""
import argparse
import os
from urllib.parse import quote

import requests
from _common import Report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://gitlab.hella.com")
    parser.add_argument("--project", required=True)
    parser.add_argument("--sha", required=True, help="Commit đầy đủ (git rev-parse HEAD)")
    parser.add_argument("--ca-bundle")
    args = parser.parse_args()
    report = Report("15_pipeline_sha")
    try:
        session = requests.Session()
        session.headers["PRIVATE-TOKEN"] = os.environ["GITLAB_TOKEN"]
        session.verify = args.ca_bundle or True
        base = f"{args.url}/api/v4/projects/{quote(args.project, safe='')}"
        resp = session.get(f"{base}/pipelines", params={"sha": args.sha, "per_page": 20}, timeout=30)
        report.line(f"pipelines: HTTP {resp.status_code}")
        for pipeline in resp.json():
            report.line(f"pipeline {pipeline['id']} ref={pipeline['ref']} status={pipeline['status']} sha={pipeline['sha']}")
            jobs = session.get(f"{base}/pipelines/{pipeline['id']}/jobs", params={"per_page": 100}, timeout=30).json()
            for job in jobs:
                report.line(f"    {job['name']}: {job['status']} archive={bool(job.get('artifacts_file'))}")
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Test both against stand-ins**

Run each with a stub `isystem.connect` or a local stub of `requests` from the scratchpad, as earlier spikes were tested. Expected: reads print, flip restores, no traceback. A stand-in proves only the script's logic.

- [ ] **Step 4: Write "Vòng 8" in `docs/windows_test_guide.md`, in Vietnamese**

Non-writing steps first: run 14 read-only; 14 with `--toggle-row` on the BM row; 14 with `--toggle-symbol` on the BM ELF using the field that read as true/false; 15 for the app project with a full commit.

Then the two steps that write flash, each stating the risk and the recovery (Debug → Download by hand with only FFI and CAL ticked; power cycle first if `Error loading monitor` appears):
1. Tick BM and FBL in winIDEA, order FFI, CAL, BM, FBL. Debug → Download by hand. Save Output. Power cycle, check the ECU. Run `python 09_flash_compare.py` (not `--full`) and send the result; FFI samples overlapped by BM or FBL are expected to differ.
2. `python 12_begin_program.py` with the same ticks. Same checks.

- [ ] **Step 5: Commit, push, and wait**

```bash
git add spike docs/windows_test_guide.md docs/walkthrough.md
git commit -m "spike: probe row and symbol ticks and pipelines by commit" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push -u origin feat/developer-debug
```

Tasks 2 to 5 may go on meanwhile; they do not depend on hardware. **Do not start Task 7 before the results are recorded in `docs/winidea_api_notes.md`.** If overlapping rows do not flash in order, or `.Enabled` cannot be written, stop and revisit the design with the user.

---

### Task 2: `source_repo`

**Files:**
- Create: `wflash/core/source_repo.py`, `tests/test_source_repo.py`
- Modify: `wflash/core/errors.py`

**Interfaces:**
- Produces: `SourceRepoError(WFlashError)`; `RepoState(branch: str, commit: str, changes: list[str])`, with `branch == ""` when detached and property `dirty`; `read_state(path) -> RepoState`; `list_branches(path) -> list[str]`; `list_commits(path, ref, limit=50) -> list[CommitInfo]`; `CommitInfo(commit, date, subject)`; `fetch(path)`; `checkout_branch(path, branch)`; `checkout_commit(path, commit)`.

- [ ] **Step 1: Write the failing test**

```python
import subprocess

import pytest

from wflash.core.errors import SourceRepoError
from wflash.core.source_repo import checkout_branch, checkout_commit, list_branches, list_commits, read_state


def git(path, *args):
    subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "T")
    (tmp_path / "a.txt").write_text("1")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "first")
    (tmp_path / "a.txt").write_text("2")
    git(tmp_path, "commit", "-qam", "second")
    git(tmp_path, "branch", "other", "HEAD~1")
    return tmp_path


def test_read_state_reports_branch_commit_and_no_changes(repo):
    state = read_state(repo)
    assert state.branch == "main" and len(state.commit) == 40 and not state.dirty


def test_read_state_lists_local_changes(repo):
    (repo / "a.txt").write_text("3")
    (repo / "new.txt").write_text("x")
    assert sorted(read_state(repo).changes) == ["a.txt", "new.txt"]


def test_not_a_repo_is_a_short_error_with_a_hint(tmp_path):
    with pytest.raises(SourceRepoError) as err:
        read_state(tmp_path)
    assert "not a git repo" in str(err.value).lower() and err.value.hint


def test_checkout_branch_and_commit(repo):
    first = list_commits(repo, "main")[-1].commit
    checkout_branch(repo, "other")
    assert read_state(repo).branch == "other"
    checkout_commit(repo, first)
    state = read_state(repo)
    assert state.branch == "" and state.commit == first


def test_checkout_refuses_local_changes_and_keeps_them(repo):
    (repo / "a.txt").write_text("mine")
    with pytest.raises(SourceRepoError) as err:
        checkout_branch(repo, "other")
    assert "a.txt" in str(err.value)
    assert (repo / "a.txt").read_text() == "mine" and read_state(repo).branch == "main"


def test_list_branches_and_commits(repo):
    assert list_branches(repo) == ["main", "other"]
    assert [c.subject for c in list_commits(repo, "main")] == ["second", "first"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `~/.venvs/wflash/bin/pytest tests/test_source_repo.py -q`
Expected: collection error, no module `source_repo`.

- [ ] **Step 3: Implement**

In `errors.py`:

```python
class SourceRepoError(WFlashError):
    default_hint = "Check the source repo path, and that git is installed."
```

`wflash/core/source_repo.py`:

```python
"""The developer's source repo, through the git command line. Never stashes, resets or forces."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from wflash.core.errors import SourceRepoError
from wflash.core.logging_setup import get_logger

log = get_logger("source")
TIMEOUT_S = 15
FETCH_TIMEOUT_S = 120
MAX_LISTED_CHANGES = 5


@dataclass(frozen=True)
class RepoState:
    branch: str  # "" when HEAD is detached
    commit: str
    changes: list[str] = field(default_factory=list)

    @property
    def dirty(self) -> bool:
        return bool(self.changes)


@dataclass(frozen=True)
class CommitInfo:
    commit: str
    date: str
    subject: str


def _git(path: Path, *args: str, timeout: int = TIMEOUT_S) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no console window on Windows
    try:
        done = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, env=env, creationflags=flags,
        )
    except FileNotFoundError as exc:
        raise SourceRepoError("Git was not found.", hint="Install git and make sure it is on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise SourceRepoError("Git did not answer in time.", hint="Check the network, then try again.") from exc
    if done.returncode != 0:
        log.error("git %s failed: %s", " ".join(args), done.stderr.strip())
        if "not a git repository" in done.stderr.lower():
            raise SourceRepoError("This folder is not a git repo.", hint="Choose the root folder of your source.")
        raise SourceRepoError(f"Git failed: {args[0]}.", hint="See the Information tab for details.")
    return done.stdout


def read_state(path: Path) -> RepoState:
    commit = _git(path, "rev-parse", "HEAD").strip()
    branch = _git(path, "branch", "--show-current").strip()
    changes = [line[3:].strip('"') for line in _git(path, "status", "--porcelain").splitlines() if line]
    return RepoState(branch, commit, changes)


def list_branches(path: Path) -> list[str]:
    names = _git(path, "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes").split()
    return sorted(n for n in names if not n.endswith("/HEAD"))


def list_commits(path: Path, ref: str, limit: int = 50) -> list[CommitInfo]:
    lines = _git(path, "log", f"-{limit}", "--format=%H%x09%cs%x09%s", ref, "--").splitlines()
    return [CommitInfo(*line.split("\t", 2)) for line in lines]


def fetch(path: Path) -> None:
    _git(path, "fetch", "--prune", timeout=FETCH_TIMEOUT_S)


def _refuse_changes(path: Path) -> None:
    changes = read_state(path).changes
    if changes:
        listed = ", ".join(changes[:MAX_LISTED_CHANGES])
        raise SourceRepoError(
            f"Checkout refused: {len(changes)} file(s) have local changes ({listed}).",
            hint="Commit or stash your changes yourself, then try again.",
        )


def checkout_branch(path: Path, branch: str) -> None:
    _refuse_changes(path)
    remote, _, local = branch.partition("/")
    if local and branch not in _git(path, "for-each-ref", "--format=%(refname:short)", "refs/heads").split():
        _git(path, "checkout", "--track", branch)  # a branch only on the remote
    else:
        _git(path, "checkout", branch)


def checkout_commit(path: Path, commit: str) -> None:
    _refuse_changes(path)
    _git(path, "checkout", "--detach", commit)
```

- [ ] **Step 4: Run to verify it passes**

Run: `~/.venvs/wflash/bin/pytest tests/test_source_repo.py -q`
Expected: 6 passed.

- [ ] **Step 5: Walkthrough entry and commit**

```bash
git add wflash/core/source_repo.py wflash/core/errors.py tests/test_source_repo.py docs/walkthrough.md
git commit -m "feat(core): read and check out the developer's source repo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Profile with builds, roles and debug sources

**Files:**
- Modify: `wflash/core/profile.py`, `profiles/suz05_m7_ffi.yaml`, `tests/test_profile.py`

**Interfaces:**
- Produces: `Profile.builds: list[BuildSpec]`, `BuildSpec(name, ffi_job, elf_job, bm_job)`; `Profile.debug_sources: dict[str, DebugSourceSpec]`, `DebugSourceSpec(project, job=None)`; `ProgramSpec.role`, `ProgramSpec.offset`, `ApplicationSpec.role`; `Profile.build(name) -> BuildSpec`; `Profile.programs_with_role(role)`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_profile.py`:

```python
def test_suz05_profile_declares_builds_in_flash_order():
    profile = load_profile(ROOT / "profiles" / "suz05_m7_ffi.yaml")
    assert [p.role for p in profile.programs] == ["ffi", "cal", "bm", "fbl"]
    assert profile.programs[3].offset == 0xF1000
    assert profile.build("strx_3p5mb_no_HTSM").bm_job == "build_STRX_3P5MB"
    assert profile.build("stingray_uds27_bypass").elf_job == "build_STINGRAY_3P5MB_UDS27_BYPASS"
    assert profile.debug_sources["fbl"].job == "build"
    assert len(profile.builds) == 4


BUILDS = """
name: b
gitlab: {project: g/a}
builds:
  - {name: one, ffi_job: f, elf_job: e, bm_job: m}
programs:
  - {role: ffi, winidea_entry: a.s3, pattern: "**/a.s3"}
  - {role: cal, pattern: "*_CAL_*.sre"}
applications:
  - {role: elf, winidea_app: "App/b.elf", pattern: "**/b.elf"}
"""


def test_only_a_cal_row_may_omit_its_entry(tmp_path):
    with pytest.raises(ProfileError, match="winidea_entry"):
        _load(tmp_path, BUILDS.replace('winidea_entry: a.s3, ', ""))


def test_builds_require_ffi_cal_and_elf_roles(tmp_path):
    with pytest.raises(ProfileError, match="cal"):
        _load(tmp_path, BUILDS.replace('  - {role: cal, pattern: "*_CAL_*.sre"}\n', ""))


def test_unknown_build_is_a_profile_error(tmp_path):
    with pytest.raises(ProfileError):
        _load(tmp_path, BUILDS).build("nope")
```

- [ ] **Step 2: Run to verify it fails**

Run: `~/.venvs/wflash/bin/pytest tests/test_profile.py -q`
Expected: failures on `role` and `builds`.

- [ ] **Step 3: Implement**

In `profile.py`, make `winidea_entry` optional, and add:

```python
Role = Literal["ffi", "cal", "bm", "fbl", "elf"]


class BuildSpec(_Strict):
    name: str = Field(min_length=1)
    ffi_job: str = Field(min_length=1)
    elf_job: str = Field(min_length=1)
    bm_job: str = Field(min_length=1)


class DebugSourceSpec(_Strict):
    project: str = Field(min_length=1)
    job: str | None = None
```

On `ProgramSpec`: `winidea_entry: str | None = None`, `role: Role | None = None`, `offset: int | None = None`. On `ApplicationSpec`: `role: Role | None = None`. On `Profile`: `builds: list[BuildSpec] = Field(default_factory=list)`, `debug_sources: dict[str, DebugSourceSpec] = Field(default_factory=dict)`.

Add a validator, and fix `_unique_targets` and `_targets` in `file_matcher.py` to skip a `None` entry:

```python
    @model_validator(mode="after")
    def _consistent_builds(self) -> "Profile":
        for program in self.programs:
            if program.winidea_entry is None and program.role != "cal":
                raise ValueError("Only a cal row may omit winidea_entry")
        if self.builds:
            roles = {p.role for p in self.programs} | {a.role for a in self.applications}
            missing = {"ffi", "cal", "elf"} - roles
            if missing:
                raise ValueError(f"A profile with builds needs the roles: {', '.join(sorted(missing))}")
        return self

    def build(self, name: str) -> BuildSpec:
        for build in self.builds:
            if build.name == name:
                return build
        raise ProfileError(f"Unknown build '{name}' in profile {self.name}")
```

Write `profiles/suz05_m7_ffi.yaml` exactly as in spec section 4, removing `sources`.

- [ ] **Step 4: Run to verify it passes**

Run: `~/.venvs/wflash/bin/pytest -q`
Expected: all pass. Tests that loaded the old `sources` form of this profile move to their own inline profile text.

- [ ] **Step 5: Walkthrough entry and commit**

```bash
git add wflash/core/profile.py wflash/core/file_matcher.py profiles/suz05_m7_ffi.yaml tests docs/walkthrough.md
git commit -m "feat(core): profiles declare builds, roles and debug sources" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Find a build's jobs by commit

**Files:**
- Modify: `wflash/core/gitlab_client.py`, `wflash/core/firmware_fetch.py`, `tests/test_firmware_fetch.py`, `tests/test_gitlab_client.py`

**Interfaces:**
- Consumes: `BuildSpec`, the spike 15 result.
- Produces: `GitLabClient.list_pipelines_for_commit(project_id, sha, limit=10) -> list[Pipeline]`; `GitLabClient.list_jobs(project_id, pipeline_id, name_glob="*", archived_only=True)`; `find_build_jobs(client, project_id, sha, ffi_job, elf_job, cancel=None) -> tuple[JobRow, JobRow]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_firmware_fetch.py`:

```python
class ShaClient(StubClient):
    def __init__(self, by_pipeline):
        super().__init__(pipelines=[Pipeline(p, "main", "success", "s" * 8, "2026-10-03T09:00:00Z") for p in by_pipeline], jobs=by_pipeline)

    def list_pipelines_for_commit(self, project_id, sha, limit=10):
        return self.pipelines

    def list_jobs(self, project_id, pipeline_id, name_glob="*", archived_only=True):
        return self.jobs[pipeline_id]


def job(id_, name, status="success"):
    return Job(id_, name, "build", status, "")


def test_find_build_jobs_returns_the_pair_of_the_newest_complete_pipeline():
    client = ShaClient({200: [job(1, "ffi", "failed"), job(2, "elf")], 100: [job(3, "ffi"), job(4, "elf")]})
    ffi, elf = find_build_jobs(client, 42, "s" * 40, "ffi", "elf")
    assert (ffi.job_id, elf.job_id) == (3, 4)
    assert ffi.commit == "s" * 8


def test_find_build_jobs_without_a_pipeline_suggests_a_push():
    with pytest.raises(GitLabError) as err:
        find_build_jobs(ShaClient({}), 42, "abcdef1234", "ffi", "elf")
    assert "abcdef12" in str(err.value) and "push" in err.value.hint.lower()


def test_find_build_jobs_names_a_job_that_has_not_run():
    client = ShaClient({100: [job(3, "ffi", "manual"), job(4, "elf")]})
    with pytest.raises(GitLabError) as err:
        find_build_jobs(client, 42, "abcdef1234", "ffi", "elf")
    assert "ffi" in str(err.value) and "manual" in str(err.value)
```

Add to `tests/test_gitlab_client.py`, following its `responses` style, a test that `list_pipelines_for_commit` sends `sha` as a query parameter and parses a `Pipeline`, and that `list_jobs(..., archived_only=False)` keeps a job with no archive.

- [ ] **Step 2: Run to verify it fails**

Run: `~/.venvs/wflash/bin/pytest tests/test_firmware_fetch.py tests/test_gitlab_client.py -q`
Expected: failures on the new names.

- [ ] **Step 3: Implement**

`list_jobs` gains `archived_only: bool = True`; its filter becomes `(not archived_only or _has_archive(j)) and fnmatch...`. `list_pipelines_for_commit` mirrors `list_pipelines` with `params={"sha": sha, "per_page": limit}`.

In `firmware_fetch.py`:

```python
def find_build_jobs(
    client: GitLabClient,
    project_id: int,
    sha: str,
    ffi_job: str,
    elf_job: str,
    cancel: CancelToken | None = None,
) -> tuple[JobRow, JobRow]:
    """The FFI and ELF jobs of the newest pipeline of `sha` where both succeeded. Never another commit."""
    pipelines = client.list_pipelines_for_commit(project_id, sha)
    if not pipelines:
        raise GitLabError(
            f"Commit {sha[:8]} has no pipeline.",
            hint="Push the commit and wait for its pipeline, or use Choose job in GitLab…",
        )
    problems: list[str] = []
    for pipeline in pipelines:
        _check(cancel)
        jobs = {job.name: job for job in client.list_jobs(project_id, pipeline.id, archived_only=False)}
        wanted = [jobs.get(ffi_job), jobs.get(elf_job)]
        if all(job is not None and job.status == "success" for job in wanted):
            return tuple(_job_row(pipeline, job) for job in wanted)
        if not problems:
            for name, job in zip((ffi_job, elf_job), wanted):
                if job is None or job.status != "success":
                    problems.append(f"{name}: {job.status if job else 'not in the pipeline'}")
    raise GitLabError(
        f"Commit {sha[:8]} has no finished build: {'; '.join(problems)}.",
        hint="Run the job in GitLab, then load again.",
    )


def _job_row(pipeline, job) -> JobRow:
    when = short_timestamp(job.finished_at or pipeline.created_at)
    return JobRow(pipeline.id, job.id, job.name, pipeline.ref, job.status, when, pipeline.sha)
```

Use `_job_row` in `browse_jobs` and `find_latest_job` where the `pipeline.ref or ref` expression allows it; keep that expression there.

- [ ] **Step 4: Run to verify it passes**

Run: `~/.venvs/wflash/bin/pytest tests/test_firmware_fetch.py tests/test_gitlab_client.py -q`
Expected: all pass.

- [ ] **Step 5: Walkthrough entry and commit**

```bash
git add wflash/core/gitlab_client.py wflash/core/firmware_fetch.py tests docs/walkthrough.md
git commit -m "feat(core): find a build's FFI and ELF jobs by commit" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Cache folders named after the branch

**Files:**
- Modify: `wflash/core/artifact_cache.py`, `wflash/core/firmware_fetch.py`, `wflash/gui/preferences_dialog.py`, `tests/test_artifact_cache.py`

**Interfaces:**
- Produces: `safe_segment(text) -> str`; `build_cache_path(branch, commit, build, part) -> PurePath`; `debug_cache_path(role, ref, commit, job) -> PurePath`; `NamedArtifactCache(root, max_entries=10)` with `get(rel) -> Path | None`, `has(rel) -> bool`, `store_zip(rel, zip_path) -> Path`, `prune(keep=())`, `clear()`; `fetch_named_artifact(client, project, project_id, job, cache, rel, progress=None, cancel=None) -> tuple[Path, FirmwareSource]`.

- [ ] **Step 1: Write the failing test**

```python
def test_safe_segment_replaces_characters_windows_refuses():
    assert safe_segment("feature/rfe:clock") == "feature_rfe_clock"
    assert safe_segment("..") == "_"


def test_build_cache_path_uses_branch_commit_and_build():
    assert build_cache_path("Release/1", "8ebd595dabc", "strx", "FFI").as_posix() == "Release_1/8ebd595d_strx/FFI"
    assert build_cache_path("", "8ebd595dabc", "strx", "ELF").as_posix() == "detached/8ebd595d_strx/ELF"


def test_build_cache_path_shortens_a_very_long_branch():
    path = build_cache_path("x" * 300, "8ebd595d", "b", "FFI")
    assert len(path.parts[0]) <= 60
    assert path != build_cache_path("x" * 301, "8ebd595d", "b", "FFI")


def test_named_cache_stores_and_finds_an_entry(tmp_path):
    cache = NamedArtifactCache(tmp_path)
    rel = build_cache_path("main", "abcdef12", "b", "FFI")
    path = cache.store_zip(rel, make_zip(tmp_path))
    assert path == tmp_path / rel and cache.get(rel) == path


def test_named_cache_prunes_the_oldest_but_keeps_what_is_asked(tmp_path):
    cache = NamedArtifactCache(tmp_path, max_entries=1)
    first = build_cache_path("main", "11111111", "b", "FFI")
    second = build_cache_path("main", "22222222", "b", "FFI")
    cache.store_zip(first, make_zip(tmp_path))
    cache.store_zip(second, make_zip(tmp_path), keep=[first])
    assert cache.has(first) and cache.has(second)
    cache.prune()
    assert not cache.has(first) and cache.has(second)


def test_named_cache_clear_removes_entries_and_the_old_layout_only(tmp_path):
    cache = NamedArtifactCache(tmp_path)
    cache.store_zip(build_cache_path("main", "11111111", "b", "FFI"), make_zip(tmp_path))
    (tmp_path / "42" / "7" / "files").mkdir(parents=True)
    (tmp_path / "42" / "7" / ".complete").write_text("x")
    (tmp_path / "keep.txt").write_text("not ours")
    cache.clear()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["keep.txt"]
```

`make_zip(tmp_path)` writes a small zip; reuse the helper already in `tests/test_artifact_cache.py`, or add one with `zipfile`.

- [ ] **Step 2: Run to verify it fails**

Run: `~/.venvs/wflash/bin/pytest tests/test_artifact_cache.py -q`
Expected: import errors on the new names.

- [ ] **Step 3: Implement**

```python
BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MAX_SEGMENT = 60


def safe_segment(text: str) -> str:
    cleaned = BAD_CHARS.sub("_", text).strip(" .") or "_"
    if len(cleaned) > MAX_SEGMENT:  # Windows limits the whole path
        digest = hashlib.sha1(cleaned.encode("utf-8")).hexdigest()[:8]
        cleaned = f"{cleaned[:MAX_SEGMENT - 9]}_{digest}"
    return cleaned


def build_cache_path(branch: str, commit: str, build: str, part: str) -> PurePath:
    return PurePath(safe_segment(branch or "detached"), safe_segment(f"{commit[:8]}_{build}"), part)


def debug_cache_path(role: str, ref: str, commit: str, job: str) -> PurePath:
    return PurePath(role.upper(), safe_segment(ref), safe_segment(f"{commit[:8]}_{job}"))


class NamedArtifactCache:
    """<root>/<rel>/ holds the extracted files and a marker; the name says what is in it."""

    def __init__(self, root: Path, max_entries: int = 10) -> None:
        self.root = root
        self.max_entries = max_entries

    def has(self, rel: PurePath) -> bool:
        return (self.root / rel / MARKER).is_file()

    def get(self, rel: PurePath) -> Path | None:
        if not self.has(rel):
            return None
        os.utime(self.root / rel / MARKER)
        return self.root / rel

    def store_zip(self, rel: PurePath, zip_path: Path, keep: Iterable[PurePath] = ()) -> Path:
        final = self.root / rel
        tmp = final.with_name(final.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            tmp.mkdir(parents=True)
            with zipfile.ZipFile(zip_path) as zf:
                _safe_extract(zf, tmp)
            (tmp / MARKER).write_text(datetime.datetime.now().isoformat(), encoding="utf-8")
            shutil.rmtree(final, ignore_errors=True)
            tmp.rename(final)
        except zipfile.BadZipFile as exc:
            shutil.rmtree(tmp, ignore_errors=True)
            raise ArtifactError("The artifact is not a valid zip file.", hint="Download it again.") from exc
        except OSError as exc:
            shutil.rmtree(tmp, ignore_errors=True)
            log.error("Failed to cache %s: %s", rel, exc)
            raise ArtifactError(
                "Failed to store the artifact.",
                hint="Check free disk space, and close programs that hold files in the cache folder.",
            ) from exc
        self.prune(keep=[rel, *keep])
        return final

    def entries(self) -> list[Path]:
        return [marker.parent for marker in self.root.rglob(MARKER)] if self.root.is_dir() else []

    def prune(self, keep: Iterable[PurePath] = ()) -> None:
        kept = {self.root / rel for rel in keep}
        ordered = sorted(self.entries(), key=lambda d: (d / MARKER).stat().st_mtime, reverse=True)
        for old in ordered[self.max_entries:]:
            if old not in kept:
                log.info("Pruning cached artifact %s", old)
                shutil.rmtree(old, ignore_errors=True)

    def clear(self) -> None:
        """Remove every entry, then the folders left empty. Anything else in the root stays."""
        for entry in self.entries():
            shutil.rmtree(entry, ignore_errors=True)
        ArtifactCache(self.root).clear()
        for folder in sorted((p for p in self.root.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
            if not any(folder.iterdir()):
                folder.rmdir()
```

`fetch_named_artifact` follows `fetch_ci_artifact`, using `cache.get(rel)` and `cache.store_zip(rel, zip_path)`. `PreferencesDialog._clear_cache` calls `NamedArtifactCache(root).clear()` in place of `ArtifactCache(root).clear()`. Prune counts one entry per part, so a build with FFI and ELF counts two; `max_cached_jobs` default stays 10.

- [ ] **Step 4: Run to verify it passes**

Run: `~/.venvs/wflash/bin/pytest tests/test_artifact_cache.py tests/test_gui_preferences_dialog.py -q`
Expected: all pass.

- [ ] **Step 5: Walkthrough entry and commit**

```bash
git add wflash/core/artifact_cache.py wflash/core/firmware_fetch.py wflash/gui/preferences_dialog.py tests docs/walkthrough.md
git commit -m "feat(core): cache firmware in folders named after branch, commit and build" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Flash plan and workspace checks

**Files:**
- Create: `wflash/core/flash_plan.py`, `tests/test_flash_plan.py`

**Interfaces:**
- Consumes: `Profile`, `ProgramSpec`, `ApplicationSpec`.
- Produces: `ProgramRow(index, name, path, enabled, offset)`; `SymbolRow(app_index, file_index, name, path, enabled)`, with `name` like `App_M7/x.elf`; `RowChange(row, new_path, tick)`; `FlashPlan(programs: list[RowChange], symbols: list[RowChange])`; `make_plan(profile, advanced, program_rows, symbol_rows, files: dict[str, Path], cal_file: str) -> FlashPlan`; `find_cal_files(workspace_dir, pattern) -> list[Path]`. `files` maps a target to the selected file: `winidea_entry` for programs, `winidea_app` for symbols.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pytest

from wflash.core.errors import MappingError
from wflash.core.flash_plan import ProgramRow, SymbolRow, find_cal_files, make_plan
from wflash.core.profile import load_profile

PROFILE = load_profile(Path(__file__).resolve().parents[1] / "profiles" / "suz05_m7_ffi.yaml")
CAL = "20260623_142557_2018688_CAL_T008_v0_0.sre"
BM, FBL = "FBL_M7_LIP_RfeClock_Image.bin", "Radar_SUZ05_Gen7_FBL.bin"


def rows(**over):
    data = [
        ProgramRow(0, "Radar_SUZ05_Gen7.s3", "Radar_SUZ05_Gen7.s3", False, 0x1AA000),
        ProgramRow(1, "RAD_SUZ05_FFI.s3", "old/RAD_SUZ05_FFI.s3", True, 0),
        ProgramRow(2, CAL, CAL, True, 0),
        ProgramRow(3, BM, f"old/{BM}", False, over.get("bm_offset", 0)),
        ProgramRow(4, FBL, f"old/{FBL}", False, 0xF1000),
    ]
    return data


def symbols():
    return [
        SymbolRow(0, 0, "App_M7/Radar_SUZ05_Gen7.elf", "old/a.elf", True),
        SymbolRow(0, 1, "App_M7/Radar_SUZ05_Gen7_BM.elf", "old/b.elf", False),
        SymbolRow(0, 2, "App_M7/Radar_SUZ05_Gen7_FBL.elf", "old/c.elf", False),
    ]


FILES = {
    "RAD_SUZ05_FFI.s3": Path("c/RAD_SUZ05_FFI.s3"),
    "App_M7/Radar_SUZ05_Gen7.elf": Path("c/Radar_SUZ05_Gen7.elf"),
    BM: Path(f"c/{BM}"),
    FBL: Path(f"c/{FBL}"),
    "App_M7/Radar_SUZ05_Gen7_BM.elf": Path("c/Radar_SUZ05_Gen7_BM.elf"),
    "App_M7/Radar_SUZ05_Gen7_FBL.elf": Path("c/Radar_SUZ05_Gen7_FBL.elf"),
}


def ticks(changes):
    return {c.row.name: c.tick for c in changes}


def test_advanced_on_ticks_and_replaces_everything():
    plan = make_plan(PROFILE, True, rows(), symbols(), FILES, CAL)
    assert ticks(plan.programs) == {"RAD_SUZ05_FFI.s3": True, CAL: True, BM: True, FBL: True}
    assert all(ticks(plan.symbols).values())
    assert next(c for c in plan.programs if c.row.name == BM).new_path == str(FILES[BM])


def test_advanced_off_unticks_bm_and_fbl_and_leaves_their_paths():
    plan = make_plan(PROFILE, False, rows(), symbols(), FILES, CAL)
    assert ticks(plan.programs)[BM] is False and ticks(plan.symbols)["App_M7/Radar_SUZ05_Gen7_BM.elf"] is False
    assert next(c for c in plan.programs if c.row.name == BM).new_path is None


def test_missing_row_names_the_file_and_the_offset():
    data = [r for r in rows() if r.name != FBL]
    with pytest.raises(MappingError) as err:
        make_plan(PROFILE, False, data, symbols(), FILES, CAL)
    assert FBL in str(err.value) and "0xF1000" in err.value.hint


def test_wrong_order_is_refused():
    data = rows()
    data[3], data[4] = ProgramRow(3, FBL, FBL, False, 0xF1000), ProgramRow(4, BM, BM, False, 0)
    with pytest.raises(MappingError, match="order"):
        make_plan(PROFILE, False, data, symbols(), FILES, CAL)


def test_wrong_offset_is_refused():
    with pytest.raises(MappingError, match="offset"):
        make_plan(PROFILE, False, rows(bm_offset=0x1000), symbols(), FILES, CAL)


def test_another_ticked_row_is_refused():
    data = rows()
    data[0] = ProgramRow(0, "Radar_SUZ05_Gen7.s3", "Radar_SUZ05_Gen7.s3", True, 0x1AA000)
    with pytest.raises(MappingError, match="Radar_SUZ05_Gen7.s3"):
        make_plan(PROFILE, False, data, symbols(), FILES, CAL)


def test_a_new_cal_replaces_the_old_row_with_a_relative_name():
    data = rows()
    data[2] = ProgramRow(2, "20250101_CAL_T008_v0.sre", "20250101_CAL_T008_v0.sre", True, 0)
    plan = make_plan(PROFILE, False, data, symbols(), FILES, CAL)
    assert next(c for c in plan.programs if c.row.index == 2).new_path == CAL


def test_missing_cal_is_refused():
    with pytest.raises(MappingError, match="CAL"):
        make_plan(PROFILE, False, rows(), symbols(), FILES, "")


def test_find_cal_files_looks_only_next_to_the_workspace(tmp_path):
    (tmp_path / CAL).write_text("x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "1_CAL_T008_x.sre").write_text("x")
    assert find_cal_files(tmp_path, "*_CAL_T008_*.sre") == [tmp_path / CAL]
```

- [ ] **Step 2: Run to verify it fails**

Run: `~/.venvs/wflash/bin/pytest tests/test_flash_plan.py -q`
Expected: collection error.

- [ ] **Step 3: Implement**

```python
"""What a flash will change in the workspace, decided before anything is changed. No winIDEA here."""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

from wflash.core.errors import MappingError
from wflash.core.profile import Profile

DEBUG_ROLES = {"bm", "fbl"}


@dataclass(frozen=True)
class ProgramRow:
    index: int
    name: str
    path: str
    enabled: bool
    offset: int


@dataclass(frozen=True)
class SymbolRow:
    app_index: int
    file_index: int
    name: str
    path: str
    enabled: bool


@dataclass(frozen=True)
class RowChange:
    row: ProgramRow | SymbolRow
    new_path: str | None  # None: the path stays
    tick: bool


@dataclass(frozen=True)
class FlashPlan:
    programs: list[RowChange]
    symbols: list[RowChange]


def find_cal_files(workspace_dir: Path, pattern: str) -> list[Path]:
    return sorted(p for p in workspace_dir.glob(pattern) if p.is_file())


def _find_program(rows, spec) -> ProgramRow:
    if spec.role == "cal":
        found = [r for r in rows if fnmatch.fnmatch(r.name.lower(), spec.pattern.lower())]
        label = spec.pattern
    else:
        found = [r for r in rows if r.name.casefold() == spec.winidea_entry.casefold()]
        label = spec.winidea_entry
    if len(found) != 1:
        where = f" at offset 0x{spec.offset:X}" if spec.offset is not None else ""
        raise MappingError(
            f"The workspace needs exactly one Download Files row for {label}; it has {len(found)}.",
            hint=f"Fix it in Hardware > (your flash device) > Configure…: {label}{where}, in flash order.",
        )
    return found[0]


def make_plan(profile: Profile, advanced: bool, program_rows, symbol_rows, files: dict[str, Path], cal_file: str) -> FlashPlan:
    programs: list[RowChange] = []
    last_index = -1
    for spec in profile.programs:
        row = _find_program(program_rows, spec)
        if row.index < last_index:
            order = " > ".join(str(p.role).upper() for p in profile.programs)
            raise MappingError(f"Download Files are in the wrong order; WFlash needs {order}.", hint="Reorder the rows in winIDEA.")
        last_index = row.index
        if spec.offset is not None and row.offset != spec.offset:
            raise MappingError(
                f"{row.name} has offset 0x{row.offset:X}, but it must be 0x{spec.offset:X}.",
                hint="Correct the offset in winIDEA.",
            )
        off = spec.role in DEBUG_ROLES and not advanced
        if spec.role == "cal":
            if not cal_file:
                raise MappingError("No CAL file was found next to the workspace.", hint=f"Copy a {spec.pattern} file there.")
            new_path = None if row.path == cal_file else cal_file
        else:
            new_path = None if off else str(files[spec.winidea_entry])
        programs.append(RowChange(row, new_path, not off))

    managed = {change.row.index for change in programs}
    extra = [r.name for r in program_rows if r.enabled and r.index not in managed]
    if extra:
        raise MappingError(
            f"Other rows are ticked and would be flashed too: {', '.join(extra)}.",
            hint="Untick them in winIDEA, or add them to the profile.",
        )

    symbols: list[RowChange] = []
    by_name = {r.name: r for r in symbol_rows}
    for spec in profile.applications:
        off = spec.role in DEBUG_ROLES and not advanced
        row = by_name.get(spec.winidea_app)
        if row is None:
            if off:
                continue  # nothing to untick
            raise MappingError(f"Symbol Files has no {spec.winidea_app}.", hint="Add it in Debug > Configure Session.")
        symbols.append(RowChange(row, None if off else str(files[spec.winidea_app]), not off))
    return FlashPlan(programs, symbols)
```

- [ ] **Step 4: Run to verify it passes**

Run: `~/.venvs/wflash/bin/pytest tests/test_flash_plan.py -q`
Expected: all pass.

- [ ] **Step 5: Walkthrough entry and commit**

```bash
git add wflash/core/flash_plan.py tests/test_flash_plan.py docs/walkthrough.md
git commit -m "feat(core): decide and check the flash plan before changing the workspace" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Adapter ticks and the planned flash. Needs the Task 1 results.

**Files:**
- Modify: `wflash/core/winidea_adapter.py`, `wflash/core/fake_adapter.py`, `wflash/core/flash_workflow.py`, `tests/fake_isystem.py`, `tests/test_real_adapter.py`, `tests/test_fake_adapter.py`, `tests/test_flash_workflow.py`, `docs/winidea_api_notes.md`

**Interfaces:**
- Consumes: `make_plan`, `FlashPlan`, `find_cal_files`, the observed `SYMBOL_TICK_FIELD`.
- Produces on the Protocol and both adapters: `workspace_dir() -> Path`, `read_program_rows() -> list[ProgramRow]`, `read_symbol_rows() -> list[SymbolRow]`, `set_program_row(index, path=None, tick=None)`, `set_symbol_row(app_index, file_index, path=None, tick=None)`.
- Produces on `FlashRequest`: `profile: Profile | None = None`, `advanced: bool = False`, `cal_file: str = ""`. `FlashRequest.mapping` still holds the rows, and `files` is derived from it.

- [ ] **Step 1: Write the failing workflow tests**

Using the fake with rows like Task 6's fixture and `profiles/suz05_m7_ffi.yaml`:

```python
def planned(tmp_path, advanced=False, fail_on=()):
    profile = load_profile(ROOT / "profiles" / "suz05_m7_ffi.yaml")
    adapter = FakeWinIDEAAdapter(download_seconds=0.01, fail_on=fail_on, rows=suz05_rows())
    mapping = suz05_mapping(tmp_path, advanced)
    return adapter, FlashWorkflow(adapter, DebugContext()), FlashRequest(
        INSTANCE_ID, mapping, profile=profile, advanced=advanced, cal_file=CAL
    )


def test_planned_flash_with_advanced_off_unticks_bm_and_fbl_and_keeps_it(tmp_path):
    adapter, flow, req = planned(tmp_path)
    adapter.program_rows[3] = dataclasses.replace(adapter.program_rows[3], enabled=True)
    flow.run(req, CancelToken())
    assert adapter.program_rows[3].enabled is False


def test_planned_flash_with_advanced_on_ticks_and_replaces(tmp_path):
    adapter, flow, req = planned(tmp_path, advanced=True)
    flow.run(req, CancelToken())
    assert adapter.program_rows[3].enabled and adapter.program_rows[3].path.endswith(BM)
    assert adapter.symbol_rows[1].enabled


def test_planned_check_failure_changes_nothing(tmp_path):
    adapter, flow, req = planned(tmp_path)
    adapter.program_rows.pop(4)
    before = list(adapter.program_rows)
    with pytest.raises(MappingError):
        flow.run(req, CancelToken())
    assert adapter.program_rows == before and "download" not in adapter.calls


def test_failed_flash_restores_paths_but_keeps_ticks(tmp_path):
    adapter, flow, req = planned(tmp_path, advanced=True, fail_on=["download"])
    old_path = adapter.program_rows[3].path
    with pytest.raises(FlashError):
        flow.run(req, CancelToken())
    assert adapter.program_rows[3].path == old_path
    assert adapter.program_rows[3].enabled is True
```

`suz05_rows()` and `suz05_mapping()` go in `tests/gui_stubs.py` so the stress test and GUI tests share them.

Add to `tests/test_real_adapter.py`: reading rows returns offsets parsed with `int(text, 16)`; `set_program_row(1, path="p", tick=False)` writes `.Path` and `.Enabled`, each read back; `set_symbol_row` writes the observed field. `tests/fake_isystem.py` gains the observed symbol field.

- [ ] **Step 2: Run to verify they fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_flash_workflow.py tests/test_real_adapter.py tests/test_fake_adapter.py -q`
Expected: failures on the new names.

- [ ] **Step 3: Implement in the adapters**

Real adapter, with `SYMBOL_TICK_FIELD` set to what spike 14 observed:

```python
    def workspace_dir(self) -> Path:
        ic, _cmgr, ide = self._session()
        return Path(ide.getPath(ic.CIDEController.WORKSPACE_DIR))

    def read_program_rows(self) -> list[ProgramRow]:
        self._check_device()
        ide = self._session()[2]
        rows = []
        for i in range(ide.getDynamicOptionSize(DOWNLOAD_FILES)):
            path = self._read(f"{DOWNLOAD_FILES}[{i}].Path")
            rows.append(ProgramRow(
                i, PureWindowsPath(path).name, path,
                self._read(f"{DOWNLOAD_FILES}[{i}].Enabled") == "true",
                int(self._read(f"{DOWNLOAD_FILES}[{i}].Offset"), 16),
            ))
        return rows

    def read_symbol_rows(self) -> list[SymbolRow]:
        rows = []
        for i in range(1000):
            try:
                app = self._read(f"{APPLICATIONS}[{i}].Name")
            except ValueError as exc:
                if _is_out_of_range(exc):
                    return rows
                raise
            for j, path in enumerate(self._read_symbol_paths(i)):
                url = f"{APPLICATIONS}[{i}].SymbolFiles.File[{j}].{SYMBOL_TICK_FIELD}"
                rows.append(SymbolRow(i, j, f"{app}/{PureWindowsPath(path).name}", path, self._read(url) == "true"))
        return rows

    def _write_option(self, url: str, value: str, label: str) -> None:
        ide = self._session()[2]
        calls_log.debug("setOption %s = %s", url, value)
        try:
            ide.setOption(url, value)
            stored = ide.getOptionStr(url)
        except Exception as exc:
            raise self._fail(f"changing {label}", exc) from exc
        if stored != value:
            log.error("winIDEA stored %r instead of %r for %s", stored, value, url)
            raise WinIDEAError(f"winIDEA did not accept the change to {label}.")

    def set_program_row(self, index: int, path: str | None = None, tick: bool | None = None) -> None:
        row = f"{DOWNLOAD_FILES}[{index}]"
        if path is not None:
            self._write_option(f"{row}.Path", path, f"download row {index}")
        if tick is not None:
            self._write_option(f"{row}.Enabled", "true" if tick else "false", f"download row {index}")

    def set_symbol_row(self, app_index: int, file_index: int, path: str | None = None, tick: bool | None = None) -> None:
        row = f"{APPLICATIONS}[{app_index}].SymbolFiles.File[{file_index}]"
        if path is not None:
            self._write_option(f"{row}.Path", path, f"symbol file {file_index}")
        if tick is not None:
            self._write_option(f"{row}.{SYMBOL_TICK_FIELD}", "true" if tick else "false", f"symbol file {file_index}")
```

The fake keeps `program_rows` and `symbol_rows` lists, default from today's `programs` and `applications`, with the same methods, and honours `fail_on` `set_path` and `connection_lost`.

- [ ] **Step 4: Implement in `FlashWorkflow`**

In `_run_connected`, first line after the `VALIDATE` step: `if req.profile is not None and req.profile.builds: self._run_planned(req, cancel); return`.

```python
    def _run_planned(self, req: FlashRequest, cancel: CancelToken) -> None:
        program_rows = self.adapter.read_program_rows()
        symbol_rows = self.adapter.read_symbol_rows()
        self.ctx.snapshot_rows("before", program_rows, symbol_rows)
        files = {row.target: row.selected for row in req.mapping if row.selected is not None}
        plan = make_plan(req.profile, req.advanced, program_rows, symbol_rows, files, req.cal_file)
        cancel.raise_if_cancelled()
        restore: list[tuple] = []
        try:
            self._step(Step.SET_PATHS)
            for change in plan.programs:
                if change.new_path is not None:
                    restore.append(("program", change.row))  # before the call: a failed set may have applied
                self.adapter.set_program_row(change.row.index, change.new_path, change.tick)
            for change in plan.symbols:
                if change.new_path is not None:
                    restore.append(("symbol", change.row))
                self.adapter.set_symbol_row(change.row.app_index, change.row.file_index, change.new_path, change.tick)
            cancel.raise_if_cancelled()
            self._step(Step.DOWNLOAD)
            self.adapter.download(self._on_progress, cancel, req.timeout_s)
        except BaseException:
            self._restore_row_paths(restore)  # ticks stay as WFlash set them (user decision)
            raise
        self._finish(req)
```

`_finish(req)` holds today's verify and reset lines, used by both paths. `_restore_row_paths` follows `_rollback`: it steps `Step.ROLLBACK`, writes each old `row.path`, sets `self._rollback_failed` and adds the error on failure. Add `DebugContext.snapshot_rows(label, programs, symbols)`, storing `asdict` of each row.

- [ ] **Step 5: Run to verify it passes**

Run: `~/.venvs/wflash/bin/pytest -k "not gui" -q`
Expected: all pass.

- [ ] **Step 6: Record and commit**

Add the row and tick calls to `docs/winidea_api_notes.md`, citing the spike file.

```bash
git add wflash/core tests docs/winidea_api_notes.md docs/walkthrough.md
git commit -m "feat(core): planned flash sets paths and ticks; a failure restores paths only" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Verify with overlapping files

**Files:**
- Modify: `wflash/core/srec.py`, `wflash/core/winidea_adapter.py`, `tests/test_srec.py`, `tests/test_real_adapter.py`

**Interfaces:**
- Produces: `read_image(path, offset) -> list[tuple[int, bytes]]`, which reads S-records or a `.bin`; `visible_segments(images: list[list[tuple[int, bytes]]]) -> list[list[tuple[int, bytes]]]`, which drops from each image what a later image overwrites.

- [ ] **Step 1: Write the failing test**

```python
def test_visible_segments_removes_what_a_later_image_overwrites():
    ffi = [(0x0, b"A" * 100)]
    bm = [(0x10, b"B" * 10)]
    assert visible_segments([ffi, bm]) == [[(0x0, b"A" * 16), (0x1A, b"A" * 74)], [(0x10, b"B" * 10)]]


def test_visible_segments_can_remove_a_whole_segment():
    assert visible_segments([[(0x10, b"A" * 4)], [(0x0, b"B" * 100)]]) == [[], [(0x0, b"B" * 100)]]


def test_read_image_applies_the_offset_to_a_bin(tmp_path):
    path = tmp_path / "x.bin"
    path.write_bytes(b"abc")
    assert read_image(path, 0xF1000) == [(0xF1000, b"abc")]


def test_read_image_applies_the_offset_to_srecords(tmp_path):
    path = tmp_path / "x.s3"
    path.write_text(record(0x100, b"\x11") + "\n")
    assert read_image(path, 0x1000) == [(0x1100, b"\x11")]
```

In `tests/test_real_adapter.py`: with rows FFI at `0x0` and a `.bin` at `0x4` covering part of it, `verify_flash` passes when the flash holds the `.bin` bytes over the FFI, and it no longer raises a false difference in that range.

- [ ] **Step 2: Run to verify it fails**

Run: `~/.venvs/wflash/bin/pytest tests/test_srec.py tests/test_real_adapter.py -q`
Expected: import errors.

- [ ] **Step 3: Implement**

```python
BINARY_SUFFIXES = {".bin"}


def read_image(path: Path, offset: int) -> list[tuple[int, bytes]]:
    if Path(path).suffix.lower() in BINARY_SUFFIXES:
        return [(offset, Path(path).read_bytes())]
    return [(address + offset, data) for address, data in parse_srec(path)]


def visible_segments(images: list[list[tuple[int, bytes]]]) -> list[list[tuple[int, bytes]]]:
    """Later images are written over earlier ones, so compare each only where it stays on the flash."""
    result = []
    for i, image in enumerate(images):
        later = [(a, a + len(d)) for other in images[i + 1:] for a, d in other]
        kept: list[tuple[int, bytes]] = []
        for address, data in image:
            pieces = [(address, address + len(data))]
            for start, end in later:
                next_pieces = []
                for low, high in pieces:
                    if end <= low or start >= high:
                        next_pieces.append((low, high))
                        continue
                    if low < start:
                        next_pieces.append((low, start))
                    if end < high:
                        next_pieces.append((end, high))
                pieces = next_pieces
            kept += [(low, data[low - address:high - address]) for low, high in pieces]
        result.append(kept)
    return result
```

`verify_flash` reads enabled rows in row order with `read_image`, skips unknown suffixes with the existing warning, applies `visible_segments`, then `sample_ranges` per image. Row names travel with the samples for the error message.

- [ ] **Step 4: Run to verify it passes**

Run: `~/.venvs/wflash/bin/pytest -k "not gui" -q`
Expected: all pass.

- [ ] **Step 5: Walkthrough entry and commit**

```bash
git add wflash/core/srec.py wflash/core/winidea_adapter.py tests docs/walkthrough.md
git commit -m "feat(core): verify compares each file only where it stays on the flash" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Source panel in the main window

**Files:**
- Modify: `wflash/gui/main_window.ui`, `wflash/gui/main_window.py`, `wflash/gui/flash_mixin.py`, `wflash/core/settings.py`, `wflash/core/source_repo.py` usage
- Create: `wflash/gui/source_panel.py`, `tests/test_gui_source_panel.py`

**Interfaces:**
- Consumes: `read_state`, `find_build_jobs`, `fetch_named_artifact`, `build_cache_path`, `Profile.builds`.
- Produces: `SourcePanelMixin` with `refresh_source_repo()`, `load_build_firmware()`, `advanced_debug() -> bool`, `flash_block_reason() -> str`; widgets `scrollArea_setting`, `lineEdit_sourceRepo`, `pushButton_browseRepo`, `pushButton_checkout`, `label_repoBranch`, `label_repoCommit`, `label_repoChanges`, `frame_application`, `comboBox_build`, `pushButton_loadBuild`, `label_loadStatus`, `pushButton_chooseJob`, `frame_advancedDebug`, `checkBox_advancedDebug`, `label_bmSource`, `pushButton_loadBm`, `label_fblSource`, `pushButton_loadFbl`, `label_flashBlocked`; `AppSettings.source_repos: dict[str, str]`, `AppSettings.last_build: dict[str, str]`.

- [ ] **Step 1: Write the failing test**

Reuse `env`, `FakeGitLabSession` and `make_artifact_tree` from `tests/gui_stubs.py`. Extend `FakeGitLabSession` with `/pipelines?sha=` answering the existing pipeline, and with jobs named after the SUZ05 profile. Use a real temp git repo, as in Task 2.

```python
def test_gui_repo_shows_branch_commit_and_load_button_names_the_commit(env, qtbot, repo):
    w = select_suz05(env)
    w.ui.lineEdit_sourceRepo.setText(str(repo))
    w.refresh_source_repo()
    qtbot.waitUntil(lambda: w.ui.label_repoBranch.text().endswith("main"), timeout=3000)
    commit = read_state(repo).commit[:8]
    assert w.ui.pushButton_loadBuild.text() == f"Load firmware for {commit}"


def test_gui_local_changes_warn_but_do_not_block(env, qtbot, repo):
    (repo / "a.txt").write_text("mine")
    w = select_suz05(env)
    w.ui.lineEdit_sourceRepo.setText(str(repo))
    w.refresh_source_repo()
    qtbot.waitUntil(lambda: "local changes" in w.ui.label_repoChanges.text(), timeout=3000)
    assert w.ui.pushButton_loadBuild.isEnabled()


def test_gui_load_build_fills_the_tables_from_the_commit(env, qtbot, repo):
    w = select_suz05(env, repo)
    w.load_build_firmware()
    qtbot.waitUntil(lambda: w.ui.label_loadStatus.text().startswith("FFI:"), timeout=5000)
    assert [r.ok for r in w.mapping_rows() if r.target in ("RAD_SUZ05_FFI.s3", "App_M7/Radar_SUZ05_Gen7.elf")] == [True, True]
    assert "main" in str(w.mapping_rows()[0].selected)


def test_gui_commit_without_a_pipeline_shows_the_reason(env, qtbot, repo):
    env.session.commit_has_pipeline = False
    w = select_suz05(env, repo)
    w.load_build_firmware()
    qtbot.waitUntil(lambda: "no pipeline" in w.ui.label_loadStatus.text(), timeout=5000)
    assert not w.mapping_complete()


def test_gui_advanced_debug_hides_bm_and_fbl_rows(env, repo):
    w = select_suz05(env, repo)
    w.ui.checkBox_advancedDebug.setChecked(False)
    assert [r for r in w.mapping_rows() if r.role in ("bm", "fbl")] == []
    w.ui.checkBox_advancedDebug.setChecked(True)
    assert len([r for r in w.mapping_rows() if r.role in ("bm", "fbl")]) == 4  # two programs, two symbol files


def test_gui_wrong_bm_job_blocks_flash(env, qtbot, repo):
    w = load_ready(env, qtbot, repo, build="strx_3p5mb_no_HTSM", bm_job="build_STINGRAY_3P5MB")
    assert "build_STRX_3P5MB" in w.flash_block_reason()
    assert not w.ui.pushButton_flash.isEnabled()


def test_gui_missing_cal_blocks_flash(env, qtbot, repo):
    w = load_ready(env, qtbot, repo, cal=False)
    assert "CAL" in w.flash_block_reason()
    assert not w.ui.pushButton_flash.isEnabled()
```

`select_suz05` and `load_ready` go in this test file; `load_ready` loads a build and, when asked, delivers BM and FBL through `_gitlab_dialog.firmwareReady`, like `load_source` in `tests/test_gui_main_window.py`.

- [ ] **Step 2: Run to verify it fails**

Run: `~/.venvs/wflash/bin/pytest tests/test_gui_source_panel.py -q`
Expected: failures on the new widgets.

- [ ] **Step 3: Edit the `.ui` and regenerate**

Wrap the content of `frame_settingPanel` in a `QScrollArea` named `scrollArea_setting` with `widgetResizable` true. Add the widgets named above in the order of the mockup. Replace the single mapping table's row with two group boxes, `groupBox_programFiles` with `tableWidget_programFiles` (columns `#`, Source, File, Offset) and `groupBox_symbolFiles` with `tableWidget_symbolFiles` (columns `#`, Source, File), each with stretch 1. Keep the `tableWidget_mapping` name for one release only if tests still need it; prefer moving them. Add `label_flashBlocked` below `label_commitWarning`, hidden by default, styled like it in both `.qss` files. In `frame_sourceCard` keep today's widgets for profiles without `builds`.

Run: `~/.venvs/wflash/bin/pyside6-uic wflash/gui/main_window.ui -o wflash/gui/ui_main_window.py`

- [ ] **Step 4: Implement `source_panel.py`**

```python
"""Source repo, Build and Advanced Debug: which firmware belongs to the source being debugged."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from wflash.core.artifact_cache import NamedArtifactCache, build_cache_path
from wflash.core.errors import WFlashError
from wflash.core.firmware_fetch import fetch_named_artifact, find_build_jobs
from wflash.core.flash_plan import find_cal_files
from wflash.core.logging_setup import get_logger
from wflash.core.source_repo import RepoState, read_state
from wflash.gui.workers import WorkerContext

log = get_logger("ui.source")
WORKER_PREFIX = "source-"


class SourcePanelMixin:
    def _init_source_panel(self) -> None:
        self.repo_state: RepoState | None = None
        self._source_key: str | None = None
        self._debug_jobs: dict[str, str] = {}
        ui = self.ui
        ui.pushButton_browseRepo.clicked.connect(self._browse_repo)
        ui.lineEdit_sourceRepo.editingFinished.connect(self.refresh_source_repo)
        ui.pushButton_loadBuild.clicked.connect(self.load_build_firmware)
        ui.comboBox_build.currentIndexChanged.connect(self._on_build_changed)
        ui.checkBox_advancedDebug.toggled.connect(self._on_advanced_toggled)
        ui.pushButton_chooseJob.clicked.connect(self.open_gitlab_dialog)

    def refresh_source_repo(self, *_args) -> None:
        path = self.ui.lineEdit_sourceRepo.text().strip()
        if not path or self._workers.has_running(WORKER_PREFIX + "repo"):
            return
        self._workers.start(
            WORKER_PREFIX + "repo", self._read_repo_job(Path(path)),
            on_succeeded=self._on_repo_read, on_failed=self._on_repo_failed,
        )

    @staticmethod
    def _read_repo_job(path: Path):
        def job(ctx: WorkerContext) -> RepoState:
            return read_state(path)
        return job

    def _on_repo_read(self, _key: str, state: RepoState) -> None:
        if self._closing:
            return
        self.repo_state = state
        self.ui.label_repoBranch.setText(f"Branch: {state.branch or '(detached)'}")
        self.ui.label_repoCommit.setText(f"Commit: {state.commit[:8]}")
        changes = f"{len(state.changes)} file(s) have local changes: the build will not match your source exactly."
        self.ui.label_repoChanges.setText(changes if state.dirty else "no local changes")
        self.ui.pushButton_loadBuild.setText(f"Load firmware for {state.commit[:8]}")
        self._update_flash_controls()
```

The rest of the mixin, in the same style:

- `load_build_firmware()` starts a `source-load` worker. It calls `find_build_jobs` for the selected build and `repo_state.commit`, then `fetch_named_artifact` for FFI and ELF with `build_cache_path(branch, commit, build, "FFI"|"ELF")`, reporting through `ctx.progress`. `_on_build_loaded` builds rows with `build_mapping_for_role` and updates `label_loadStatus`; `_on_build_failed` shows `str(exc)` and the hint in `label_loadStatus`, never a dialog.
- `_on_advanced_toggled` rebuilds the tables through `rebuild_file_tables()`.
- `flash_block_reason()` returns the first of: repo or build missing, CAL missing (`find_cal_files` over the workspace folder of the selected instance, `workspace` in `selected_instance()`), BM or FBL not loaded with Advanced Debug on, `self._debug_jobs["bm"] != build.bm_job`. `""` means none. `label_flashBlocked` shows it.

In `flash_mixin._update_flash_controls`, `can_flash` gains `and not self.flash_block_reason()`, and the new controls are disabled while flashing. In `start_flash`, `FlashRequest` gains `profile=self.profile if self.profile.builds else None`, `advanced=self.advanced_debug()`, `cal_file=self.cal_file_name()`. `file_matcher.py`: `MappingRow` gains `role: str | None = None`, and gains `build_mapping_for_role(profile, roles, root)`, mirroring `build_mapping_for_source`. The CAL row is a `MappingRow` with `role="cal"`, `target` the file name from `find_cal_files`, its candidates being those files; several candidates make it a red row for the user to choose, and `cal_file_name()` returns the selected name.

`MappingTableMixin` renders rows into the two tables by `row.kind`, keeping `mapping_rows()` and `mapping_combo(index)`; the row's `role` gives the Source tag. BM and FBL load through `open_gitlab_dialog_for` with a project override from `debug_sources`; the dialog's `prepare` gains `project: str | None`, and job filter is `debug_sources[role].job` or the set of `bm_job`s.

Settings: `source_repos` and `last_build` are keyed by profile file name and saved like `ci_project_overrides`.

- [ ] **Step 5: Run to verify it passes**

Run: `~/.venvs/wflash/bin/pytest -q && ~/.venvs/wflash/bin/pytest -k thread -q`
Expected: all pass. Update existing tests that referred to `tableWidget_mapping`. A native screenshot through a real event loop, as in the earlier layout fixes, must show nothing clipped at 1280×820 with the scroll area working.

- [ ] **Step 6: Walkthrough entry and commit**

```bash
git add wflash tests docs/walkthrough.md
git commit -m "feat(gui): source repo, build, Advanced Debug and separate file tables" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Checkout dialog

**Files:**
- Create: `wflash/gui/checkout_dialog.ui`, `wflash/gui/checkout_dialog.py`, `wflash/gui/ui_checkout_dialog.py` (generated), `tests/test_gui_checkout_dialog.py`
- Modify: `wflash/gui/source_panel.py`

**Interfaces:**
- Consumes: `read_state`, `list_branches`, `list_commits`, `fetch`, `checkout_branch`, `checkout_commit`.
- Produces: `CheckoutDialog(host, repo_path)`; signal `checkedOut`; widgets `comboBox_branch`, `pushButton_fetch`, `tableWidget_commits` (columns Commit, Date, Message, Pipeline), `pushButton_checkout`, `label_checkoutError`.

- [ ] **Step 1: Write the failing test**

```python
def test_gui_checkout_lists_commits_and_switches(qtbot, host, repo):
    dialog = open_dialog(qtbot, host, repo)
    qtbot.waitUntil(lambda: dialog.ui.tableWidget_commits.rowCount() == 2, timeout=3000)
    dialog.ui.comboBox_branch.setCurrentText("other")
    qtbot.waitUntil(lambda: dialog.ui.tableWidget_commits.rowCount() == 1, timeout=3000)
    dialog.ui.tableWidget_commits.selectRow(0)
    with qtbot.waitSignal(dialog.checkedOut, timeout=3000):
        dialog.ui.pushButton_checkout.click()
    assert read_state(repo).branch == "other"


def test_gui_checkout_is_refused_with_local_changes_and_keeps_them(qtbot, host, repo):
    (repo / "a.txt").write_text("mine")
    dialog = open_dialog(qtbot, host, repo)
    qtbot.waitUntil(lambda: dialog.ui.tableWidget_commits.rowCount() == 2, timeout=3000)
    dialog.ui.comboBox_branch.setCurrentText("other")
    qtbot.waitUntil(lambda: dialog.ui.tableWidget_commits.rowCount() == 1, timeout=3000)
    dialog.ui.tableWidget_commits.selectRow(0)
    dialog.ui.pushButton_checkout.click()
    qtbot.waitUntil(lambda: "local changes" in dialog.ui.label_checkoutError.text(), timeout=3000)
    assert read_state(repo).branch == "main" and (repo / "a.txt").read_text() == "mine"


def test_gui_thread_closing_during_fetch_waits_and_drops_the_result(qtbot, host, repo, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(checkout_dialog, "fetch", lambda path: release.wait(5))
    dialog = open_dialog(qtbot, host, repo)
    dialog.ui.pushButton_fetch.click()
    dialog.reject()
    release.set()
    assert not dialog.isVisible()
```

- [ ] **Step 2: Run to verify it fails**

Run: `~/.venvs/wflash/bin/pytest tests/test_gui_checkout_dialog.py -q`
Expected: collection error.

- [ ] **Step 3: Implement**

Build `checkout_dialog.ui` from the Checkout board in the mockup; regenerate with `pyside6-uic`. Model `checkout_dialog.py` on `GitlabDialog`'s worker handling: a `_generation` guard set before any cancel, bound-method slots, `done()` waiting with a bound. Every git and GitLab call runs in a `checkout-` worker. Choosing the first commit of a branch calls `checkout_branch(path, branch)`; any other commit calls `checkout_commit(path, commit)`. The Pipeline column comes from `client.list_pipelines_for_commit`, limited to the listed commits' branch; when GitLab fails or is not configured, the column shows `-` and nothing else breaks. `SourceRepoError` goes to `label_checkoutError`, with its hint.

`pushButton_checkout` in the main window opens the dialog and is disabled while flashing. `checkedOut` calls `refresh_source_repo`. If `repo_state.commit` then differs from the loaded firmware's commit, `flash_block_reason` is not affected; `label_repoChanges` adds "Loaded firmware is from another commit."

- [ ] **Step 4: Run to verify it passes**

Run: `~/.venvs/wflash/bin/pytest tests/test_gui_checkout_dialog.py -q && ~/.venvs/wflash/bin/pytest -k thread -q`
Expected: all pass.

- [ ] **Step 5: Walkthrough entry and commit**

```bash
git add wflash tests docs/walkthrough.md
git commit -m "feat(gui): check out a branch or commit of the source repo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Stress test, docs and Windows acceptance

**Files:**
- Modify: `tools/stress_test.py`, `README.md`, `CLAUDE.md`, `docs/windows_test_guide.md`, `docs/winidea_api_notes.md`, `wflash.spec` if `checkout_dialog` needs it

- [ ] **Step 1: Extend the stress test**

Add `check_developer_flow(label)` to `section_flash`: a window on an inline SUZ05 profile with a real temp git repo; refresh repo; load a build through the fake session; toggle Advanced Debug three times while idle; flash; assert `Done`, BM unticked with Advanced Debug off and ticked with it on. Then in `races`: close the window during `load_build_firmware`, and during a repo read.

Run: `~/.venvs/wflash/bin/python tools/stress_test.py`
Expected: `STRESS_RESULT=PASS`.

- [ ] **Step 2: Update the docs**

`README.md`: the developer flow, profile `builds` and `debug_sources`. `CLAUDE.md`: Approach A now includes managed ticks and the CAL path; ticks are not restored; never stash or force in `source_repo`. `docs/windows_test_guide.md`: "Vòng 9", marking every step that writes flash, covering each row of spec section 2, Checkout refused and allowed, a build whose job has not run, Advanced Debug on and off, missing CAL, wrong BM job, and a flash of a different firmware with a check on the ECU that it runs.

- [ ] **Step 3: Run everything**

Run: `~/.venvs/wflash/bin/pytest -q && ~/.venvs/wflash/bin/pytest -k thread -q && ~/.venvs/wflash/bin/python tools/stress_test.py && QT_QPA_PLATFORM=offscreen ~/.venvs/wflash/bin/python main.py --adapter fake --smoke`
Expected: all pass, exit 0.

- [ ] **Step 4: Commit and push**

```bash
git add tools README.md CLAUDE.md docs wflash.spec
git commit -m "test: stress the developer flow; docs and Windows acceptance" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push
```

Nothing is claimed to work on hardware until the user reports Vòng 9. The branch merges to `main` only after that.
