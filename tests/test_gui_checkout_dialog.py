"""Checkout popup: list branches and commits, switch, refuse with local changes, close while busy."""
import subprocess
import threading

import pytest
from PySide6.QtCore import Qt, QTimer

from tests.gui_stubs import PROJECT, FakeGitLabSession, HostWindow, SessionClientFactory, patch_keyring
from wflash.core.source_repo import read_state
from wflash.gui import checkout_dialog
from wflash.gui.checkout_dialog import CheckoutDialog

pytestmark = pytest.mark.gui


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path):
    """main has two commits; `other` branches off the first and has one more."""
    path = tmp_path / "src"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "t@example.com")
    git(path, "config", "user.name", "T")
    (path / "a.txt").write_text("1")
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", "first")
    git(path, "branch", "other")
    (path / "a.txt").write_text("2")
    git(path, "commit", "-q", "-am", "second")
    git(path, "checkout", "-q", "other")
    (path / "b.txt").write_text("x")
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", "on other")
    git(path, "checkout", "-q", "main")
    return path


@pytest.fixture
def host(qtbot, tmp_path, monkeypatch):
    patch_keyring(monkeypatch)
    window = HostWindow(tmp_path, client_factory=SessionClientFactory(FakeGitLabSession()))
    qtbot.addWidget(window)
    return window


def open_dialog(qtbot, host, repo, project=""):
    dialog = CheckoutDialog(host)
    dialog.prepare(repo, project)
    dialog.open()
    qtbot.waitUntil(lambda: not dialog.busy() and dialog.ui.tableWidget_commits.rowCount() > 0, timeout=5000)
    return dialog


def choose_branch(qtbot, dialog, name, rows):
    """Type the full name and press Enter, as a user does in the editable branch field."""
    edit = dialog.ui.comboBox_branch.lineEdit()
    edit.setText(name)
    qtbot.keyClick(edit, Qt.Key.Key_Return)
    qtbot.waitUntil(
        lambda: not dialog.busy() and dialog._chosen_branch() == name
        and dialog.ui.tableWidget_commits.rowCount() == rows,
        timeout=5000,
    )


def test_gui_checkout_shows_the_current_state_and_branches(qtbot, host, repo):
    dialog = open_dialog(qtbot, host, repo)
    assert dialog.ui.comboBox_branch.currentText() == "main"
    assert {dialog.ui.comboBox_branch.itemText(i) for i in range(dialog.ui.comboBox_branch.count())} == {"main", "other"}
    assert dialog.ui.tableWidget_commits.rowCount() == 2
    assert dialog.ui.tableWidget_commits.item(0, 2).text() == "second"
    assert "main" in dialog.ui.label_currentState.text() and "no local changes" in dialog.ui.label_currentState.text()
    assert dialog.ui.tableWidget_commits.item(0, 3).text() == "-"  # no GitLab project given
    assert not dialog.ui.pushButton_checkout.isEnabled()  # nothing selected yet


def test_gui_checkout_first_commit_switches_the_branch(qtbot, host, repo):
    dialog = open_dialog(qtbot, host, repo)
    choose_branch(qtbot, dialog, "other", 2)
    dialog.ui.tableWidget_commits.selectRow(0)
    with qtbot.waitSignal(dialog.checkedOut, timeout=5000):
        dialog.ui.pushButton_checkout.click()
    qtbot.waitUntil(lambda: not dialog.isVisible(), timeout=5000)
    assert read_state(repo).branch == "other"


def test_gui_checkout_an_older_commit_detaches(qtbot, host, repo):
    dialog = open_dialog(qtbot, host, repo)
    first = git(repo, "rev-parse", "HEAD~1").strip()
    dialog.ui.tableWidget_commits.selectRow(1)
    with qtbot.waitSignal(dialog.checkedOut, timeout=5000):
        dialog.ui.pushButton_checkout.click()
    state = read_state(repo)
    assert state.branch == "" and state.commit == first


def test_gui_checkout_is_refused_with_local_changes_and_keeps_them(qtbot, host, repo):
    (repo / "a.txt").write_text("mine")
    dialog = open_dialog(qtbot, host, repo)
    assert "1 file(s) with local changes" in dialog.ui.label_currentState.text()
    choose_branch(qtbot, dialog, "other", 2)
    dialog.ui.tableWidget_commits.selectRow(0)
    dialog.ui.pushButton_checkout.click()
    qtbot.waitUntil(lambda: "local changes" in dialog.ui.label_checkoutError.text(), timeout=5000)
    assert dialog.isVisible()
    assert read_state(repo).branch == "main" and (repo / "a.txt").read_text() == "mine"


def test_gui_checkout_pipeline_column_comes_from_gitlab(qtbot, host, repo):
    dialog = open_dialog(qtbot, host, repo, project=PROJECT)
    assert dialog.ui.tableWidget_commits.item(0, 3).text() == "Manual"


def test_gui_checkout_pipeline_column_survives_a_gitlab_failure(qtbot, host, repo):
    def broken(_settings):
        raise RuntimeError("no network")

    host._client_factory = broken
    dialog = open_dialog(qtbot, host, repo, project=PROJECT)
    assert dialog.ui.tableWidget_commits.item(0, 3).text() == "-"
    assert dialog.ui.tableWidget_commits.rowCount() == 2


def test_gui_thread_closing_during_fetch_waits_and_drops_the_result(qtbot, host, repo, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(checkout_dialog, "fetch", lambda path: release.wait(5))
    dialog = open_dialog(qtbot, host, repo)
    dialog.ui.pushButton_fetch.click()
    assert dialog.busy()
    QTimer.singleShot(200, release.set)
    dialog.reject()  # waits, pumping events, until the fetch worker is done
    assert not dialog.isVisible() and not dialog.busy()
    assert not host._workers.has_running("checkout-")
    qtbot.wait(100)  # a queued result, if any, is dropped as stale
    assert dialog.ui.label_checkoutError.text() == ""


def test_gui_checkout_branch_field_filters_by_any_part_of_the_name(qtbot, host, repo):
    dialog = open_dialog(qtbot, host, repo)
    combo = dialog.ui.comboBox_branch
    assert combo.isEditable()
    completer = combo.completer()
    completer.setCompletionPrefix("THE")  # "other", any case, not at the start
    names = [completer.completionModel().index(i, 0).data() for i in range(completer.completionCount())]
    assert names == ["other"]


def test_gui_checkout_typed_text_that_names_no_branch_turns_checkout_off(qtbot, host, repo):
    dialog = open_dialog(qtbot, host, repo)
    dialog.ui.tableWidget_commits.selectRow(0)
    assert dialog.ui.pushButton_checkout.isEnabled()
    edit = dialog.ui.comboBox_branch.lineEdit()
    edit.setText("oth")  # half typed: the table still shows main, Checkout must not act on it
    assert not dialog.ui.pushButton_checkout.isEnabled()
    qtbot.keyClick(edit, Qt.Key.Key_Return)
    assert "No branch named 'oth'" in dialog.ui.label_checkoutError.text()
    dialog.checkout_selected()  # ignored
    assert read_state(repo).branch == "main"
    choose_branch(qtbot, dialog, "other", 2)
    assert dialog.ui.label_checkoutError.text() == ""


@pytest.fixture
def clone(repo, tmp_path_factory):
    """A clone whose origin is `repo`: local main exists, other is only on origin."""
    path = tmp_path_factory.mktemp("clone") / "src"
    subprocess.run(["git", "clone", "-q", str(repo), str(path)], check=True, capture_output=True)
    return path


def test_gui_checkout_newest_commit_of_origin_of_a_local_branch_is_pull_changes(qtbot, host, repo, clone):
    (repo / "a.txt").write_text("3")
    git(repo, "commit", "-q", "-am", "third")
    newest = git(repo, "rev-parse", "HEAD").strip()
    git(clone, "fetch", "-q")
    dialog = open_dialog(qtbot, host, clone)
    button = dialog.ui.pushButton_checkout
    choose_branch(qtbot, dialog, "origin/main", 3)
    dialog.ui.tableWidget_commits.selectRow(0)
    assert button.text() == "Pull changes" and button.isEnabled()
    dialog.ui.tableWidget_commits.selectRow(1)  # an older commit: a detached checkout, not a pull
    assert button.text() == "Checkout"
    choose_branch(qtbot, dialog, "main", 2)  # the local name: checkout as it is
    dialog.ui.tableWidget_commits.selectRow(0)
    assert button.text() == "Checkout"
    choose_branch(qtbot, dialog, "origin/other", 2)  # only on origin: a new local branch, not a pull
    dialog.ui.tableWidget_commits.selectRow(0)
    assert button.text() == "Checkout"
    choose_branch(qtbot, dialog, "origin/main", 3)
    dialog.ui.tableWidget_commits.selectRow(0)
    with qtbot.waitSignal(dialog.checkedOut, timeout=5000):
        button.click()
    state = read_state(clone)
    assert state.branch == "main" and state.commit == newest
