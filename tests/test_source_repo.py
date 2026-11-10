import subprocess

import pytest

from wflash.core.errors import SourceRepoError
from wflash.core.source_repo import (
    checkout_branch, checkout_commit, fetch, list_branches, list_commits, read_state,
)


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


@pytest.fixture
def clone(repo, tmp_path_factory):
    path = tmp_path_factory.mktemp("clone")
    subprocess.run(["git", "clone", "-q", str(repo), str(path)], check=True, capture_output=True)
    return path


def test_checkout_a_branch_only_on_the_remote_creates_a_local_branch(clone):
    checkout_branch(clone, "origin/other")
    assert read_state(clone).branch == "other"


def test_checkout_a_remote_name_uses_the_existing_local_branch(clone):
    checkout_branch(clone, "origin/other")
    checkout_branch(clone, "origin/main")
    assert read_state(clone).branch == "main"
    checkout_branch(clone, "origin/other")
    assert read_state(clone).branch == "other"


def test_checkout_a_local_branch_with_a_slash(repo):
    git(repo, "branch", "feature/x")
    checkout_branch(repo, "feature/x")
    assert read_state(repo).branch == "feature/x"


def _advance_remote(repo, text):
    (repo / "a.txt").write_text(text)
    git(repo, "commit", "-qam", f"remote {text}")
    return list_commits(repo, "main")[0].commit


def test_checkout_a_remote_name_brings_the_local_branch_up_to_the_remote(repo, clone):
    newest = _advance_remote(repo, "3")
    fetch(clone)
    checkout_branch(clone, "origin/main")
    state = read_state(clone)
    assert state.branch == "main" and state.commit == newest


def test_checkout_a_remote_name_from_another_branch_also_brings_it_up(repo, clone):
    checkout_branch(clone, "origin/other")
    newest = _advance_remote(repo, "3")
    fetch(clone)
    checkout_branch(clone, "origin/main")
    assert read_state(clone).commit == newest


def test_checkout_the_local_name_keeps_the_local_branch_where_it_is(repo, clone):
    before = read_state(clone).commit
    _advance_remote(repo, "3")
    fetch(clone)
    checkout_branch(clone, "main")
    assert read_state(clone).commit == before


def test_checkout_a_remote_name_keeps_unpushed_local_commits(clone):
    (clone / "a.txt").write_text("local")
    git(clone, "-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-qam", "local")
    mine = read_state(clone).commit
    checkout_branch(clone, "origin/main")
    assert read_state(clone).commit == mine


def test_checkout_a_remote_name_refuses_a_diverged_local_branch_and_moves_nothing(repo, clone):
    _advance_remote(repo, "3")
    checkout_branch(clone, "origin/other")
    git(clone, "checkout", "-q", "main")
    (clone / "a.txt").write_text("local")
    git(clone, "-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-qam", "local")
    mine = read_state(clone).commit
    git(clone, "checkout", "-q", "other")
    fetch(clone)
    with pytest.raises(SourceRepoError) as err:
        checkout_branch(clone, "origin/main")
    assert "main" in str(err.value) and err.value.hint
    state = read_state(clone)
    assert state.branch == "other"
    git(clone, "checkout", "-q", "main")
    assert read_state(clone).commit == mine
