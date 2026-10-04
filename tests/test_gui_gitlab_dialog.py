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
