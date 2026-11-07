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
