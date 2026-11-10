"""The developer's source repo, through the git command line. Never stashes, resets or forces.

The only way it moves a branch is a fast-forward (`merge --ff-only`) to its remote, when the
developer checks out the remote name of a branch they already have locally.
"""
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
    local_branches = _git(path, "for-each-ref", "--format=%(refname:short)", "refs/heads").split()
    if branch in local_branches:
        _git(path, "checkout", branch)
        return
    remotes = _git(path, "remote").split()
    remote, _, name = branch.partition("/")
    if remote in remotes and name in local_branches:
        # The remote name means "the remote's newest": fast-forward only, decided before moving anything.
        ahead = int(_git(path, "rev-list", "--count", f"{branch}..{name}").strip())
        behind = int(_git(path, "rev-list", "--count", f"{name}..{branch}").strip())
        if ahead and behind:
            raise SourceRepoError(
                f"Checkout refused: local branch {name} and {branch} have both moved on.",
                hint=f"Select {name} to check out your local branch as it is, or merge {branch} into it yourself.",
            )
        _git(path, "checkout", name)
        if behind:
            _git(path, "merge", "--ff-only", branch)
            log.info("Brought %s up to %s (%d new commit(s))", name, branch, behind)
    else:
        _git(path, "checkout", "--track", branch)  # a branch only on the remote


def checkout_commit(path: Path, commit: str) -> None:
    _refuse_changes(path)
    _git(path, "checkout", "--detach", commit)
