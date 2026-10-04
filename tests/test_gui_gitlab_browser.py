import pytest

from tests.gui_stubs import (
    EXAMPLE_PROFILE,
    JOB_ID,
    PROJECT_ID,
    TOKEN,
    FakeGitLabSession,
    HostWindow,
    SessionClientFactory,
)
from wflash.core.errors import GitLabError
from wflash.core.profile import load_profile
from wflash.core.settings import AppSettings
from wflash.gui import gitlab_browser
from wflash.gui.gitlab_browser import GitlabBrowserMixin, default_client_factory

pytestmark = pytest.mark.gui


class GitlabHost(GitlabBrowserMixin, HostWindow):
    def __init__(self, tmp, session):
        super().__init__(tmp, client_factory=SessionClientFactory(session))
        self._init_gitlab_browser()
        self.profile = load_profile(EXAMPLE_PROFILE)
        self.set_gitlab_profile(self.profile)


@pytest.fixture
def session():
    return FakeGitLabSession()


@pytest.fixture
def host(qtbot, tmp_path, session):
    window = GitlabHost(tmp_path, session)
    qtbot.addWidget(window)
    return window


def browse_to_job(w, qtbot):
    w.refresh_gitlab()
    qtbot.waitUntil(lambda: w.ui.listWidget_pipelines.count() == 1, timeout=3000)
    w.ui.listWidget_pipelines.setCurrentRow(0)
    qtbot.waitUntil(lambda: w.ui.listWidget_jobs.count() == 1, timeout=3000)
    w.ui.listWidget_jobs.setCurrentRow(0)
    qtbot.waitUntil(w.ui.pushButton_downloadArtifact.isEnabled, timeout=3000)


def test_gui_browse_and_download(host, qtbot):
    browse_to_job(host, qtbot)
    assert [host.ui.comboBox_ref.itemText(i) for i in range(2)] == ["main", "v1.0 (tag)"]
    assert "build_app" in host.ui.listWidget_jobs.item(0).text()  # "lint" has no archive
    host.ui.pushButton_downloadArtifact.click()
    assert host.ui.pushButton_cancelArtifact.isEnabled()
    assert not host.ui.pushButton_downloadArtifact.isEnabled()
    qtbot.waitUntil(lambda: len(host.artifacts_loaded) == 1, timeout=5000)
    path, label = host.artifacts_loaded[0]
    assert (path / "out" / "App.s3").read_bytes() == b"S0"
    assert f"#{JOB_ID}" in label and "build_app" in label
    qtbot.waitUntil(lambda: not host.gitlab_busy(), timeout=3000)
    assert host.ui.progressBar_artifact.format() == "Ready"
    assert not host.ui.pushButton_cancelArtifact.isEnabled()


def test_gui_second_download_uses_cache(host, session, qtbot):
    browse_to_job(host, qtbot)
    for expected in (1, 2):
        host.download_selected_artifact()
        qtbot.waitUntil(lambda: len(host.artifacts_loaded) == expected, timeout=5000)
        qtbot.waitUntil(lambda: not host.gitlab_busy(), timeout=3000)
    assert session.count(f"/jobs/{JOB_ID}/artifacts") == 1


def test_gui_double_click_download_is_refused(host, session, qtbot):
    session.chunk_delay_s = 0.01
    browse_to_job(host, qtbot)
    host.download_selected_artifact()
    key = host._gl_download_key
    host.download_selected_artifact()
    assert host._gl_download_key == key
    qtbot.waitUntil(lambda: len(host.artifacts_loaded) == 1, timeout=10000)
    qtbot.waitUntil(lambda: not host.gitlab_busy(), timeout=3000)
    assert session.count(f"/jobs/{JOB_ID}/artifacts") == 1


def test_gui_cancel_download_never_loads_artifact(host, session, qtbot, tmp_path):
    session.chunk_delay_s = 0.02  # 64 KiB in 4 KiB chunks: ~0.4 s
    browse_to_job(host, qtbot)
    host.download_selected_artifact()
    qtbot.waitUntil(lambda: host.ui.progressBar_artifact.value() > 0, timeout=3000)
    host.ui.pushButton_cancelArtifact.click()
    qtbot.waitUntil(lambda: not host.gitlab_busy(), timeout=5000)
    assert host.artifacts_loaded == []
    assert host.errors_shown == []
    assert host.ui.progressBar_artifact.format() == "Cancelled"
    assert not (tmp_path / "cache" / str(PROJECT_ID) / str(JOB_ID)).exists()


def test_gui_completion_queued_before_cancel_is_dropped(host, qtbot):
    browse_to_job(host, qtbot)
    host.download_selected_artifact()
    # Let the worker finish but do not process its queued signals yet.
    worker = host._workers.worker(host._gl_download_key)
    assert worker.done.wait(5)
    host.cancel_artifact_download()  # guard set although the worker already completed
    qtbot.waitUntil(lambda: not host.gitlab_busy(), timeout=3000)
    assert host.artifacts_loaded == []


@pytest.mark.parametrize("status, hint_word", [(401, "expired"), (403, "access"), (404, "expired")])
def test_gui_http_errors_show_specific_hints(qtbot, tmp_path, status, hint_word):
    w = GitlabHost(tmp_path, FakeGitLabSession(fail_status=status))
    qtbot.addWidget(w)
    w.refresh_gitlab()
    qtbot.waitUntil(lambda: len(w.errors_shown) == 1, timeout=3000)
    exc = w.errors_shown[0]
    assert isinstance(exc, GitLabError) and f"HTTP {status}" in str(exc)
    assert hint_word in exc.hint
    assert len(w.ctx.errors) == 1


def test_gui_connection_error(qtbot, tmp_path):
    w = GitlabHost(tmp_path, FakeGitLabSession(connection_error=True))
    qtbot.addWidget(w)
    w.refresh_gitlab()
    qtbot.waitUntil(lambda: len(w.errors_shown) == 1, timeout=3000)
    assert "Cannot reach GitLab" in str(w.errors_shown[0])


def test_gui_profile_change_drops_stale_results(host, session, qtbot):
    session.delay_s = 0.2
    host.refresh_gitlab()
    host.set_gitlab_profile(host.profile)  # bumps the generation while refs are in flight
    qtbot.waitUntil(lambda: not host.gitlab_busy(), timeout=3000)
    assert host.ui.comboBox_ref.count() == 0


def test_gui_default_client_factory_requires_url_and_token(monkeypatch):
    monkeypatch.setattr(gitlab_browser, "get_token", lambda url: None)
    with pytest.raises(GitLabError, match="not configured") as info:
        default_client_factory(AppSettings(gitlab_url="https://gl"))
    assert "Settings" in info.value.hint
    monkeypatch.setattr(gitlab_browser, "get_token", lambda url: TOKEN)
    client = default_client_factory(AppSettings(gitlab_url="https://gl/", ca_bundle=""))
    assert client.base == "https://gl/api/v4"
    assert client.verify is True
