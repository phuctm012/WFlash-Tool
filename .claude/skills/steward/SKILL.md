# PR Steward

Repo-specific guidance for driving changes to green on WFlash.

## Before pushing a fix

- Run the full suite: `~/.venvs/wflash/bin/pytest -q`.
- Run `~/.venvs/wflash/bin/pytest -k thread -v` explicitly — worker-lifecycle bugs are timing-dependent and easy to miss.
- If a `.ui` changed, regenerate with `pyside6-uic` and verify the import (see the regenerate-ui skill).
- Re-read the diff for the five things that have gone wrong in this family of projects:
  - a leftover `print()` where `get_logger(...)` belongs;
  - an early return in a worker's `run()` that skips cleanup or the workspace-path rollback;
  - a new widget still carrying a generic Designer name, or a widget built in Python that belongs in the `.ui`;
  - an `isystem.connect` call not backed by `docs/winidea_api_notes.md`;
  - a log/bundle path that bypasses `RedactingFormatter`.

## Conventions

- Merge the base branch in; no rebase/force-push on a branch someone else may have.
- Every commit ends with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (second `-m`).
- Regenerate `ui_main_window.py` with `pyside6-uic` whenever a `.ui` changes — never hand-edit it.
- No linter/formatter is configured — don't add lint-fix commits.
- Every notable change gets a `## Phase X.Y` entry in `docs/walkthrough.md`, in Vietnamese, in that file's format.
- Don't commit a mode change on the pre-existing `README.md` unless the task is about the README.

## Never

- Skip or disable a test to get a green run.
- Push without running the full suite first.
- Commit a GitLab token, a customer `.xjrf` workspace, or a real artifact binary.
- Claim real-hardware behaviour from a macOS run — the real adapter is only ever verified on Windows.
