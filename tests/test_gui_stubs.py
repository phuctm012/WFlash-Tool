"""The fake GitLab network must behave like GitLab for the real GitLabClient."""
import zipfile

import pytest

from tests.gui_stubs import (
    JOB_ID,
    PIPELINE_ID,
    PROJECT,
    PROJECT_ID,
    TOKEN,
    FakeGitLabSession,
    SessionClientFactory,
    write_profiles,
)
from wflash.core.cancel import CancelToken
from wflash.core.errors import CancelledError, GitLabError
from wflash.core.profile import load_profile
from wflash.core.settings import AppSettings

pytestmark = pytest.mark.gui


def client(session):
    return SessionClientFactory(session)(AppSettings())


def test_gui_stub_session_serves_the_browse_chain():
    session = FakeGitLabSession()
    c = client(session)
    assert session.headers["PRIVATE-TOKEN"] == TOKEN
    assert c.get_project_id(PROJECT) == PROJECT_ID
    assert [(r.name, r.kind) for r in c.list_refs(PROJECT_ID)] == [("main", "branch"), ("v1.0", "tag")]
    assert [p.id for p in c.list_pipelines(PROJECT_ID, "main")] == [PIPELINE_ID]
    assert [j.name for j in c.list_jobs(PROJECT_ID, PIPELINE_ID, "build_*")] == ["build_app"]


def test_gui_stub_session_streams_a_valid_zip_in_chunks(tmp_path):
    session = FakeGitLabSession()
    seen = []
    path = client(session).download_artifacts(PROJECT_ID, JOB_ID, tmp_path, lambda d, t: seen.append((d, t)))
    with zipfile.ZipFile(path) as zf:
        assert zf.read("out/App.s3") == b"S0"
    assert len(seen) > 10 and seen[-1][0] == seen[-1][1] == len(session.zip_bytes)


def test_gui_stub_session_download_honours_cancel(tmp_path):
    token = CancelToken()

    def progress(done, total):
        token.cancel()

    with pytest.raises(CancelledError):
        client(FakeGitLabSession()).download_artifacts(PROJECT_ID, JOB_ID, tmp_path, progress, token)
    assert list(tmp_path.iterdir()) == []


def test_gui_stub_session_errors_go_through_the_real_classification():
    with pytest.raises(GitLabError, match="HTTP 401") as info:
        client(FakeGitLabSession(fail_status=401)).list_refs(PROJECT_ID)
    assert "expired" in info.value.hint
    with pytest.raises(GitLabError, match="Cannot reach GitLab"):
        client(FakeGitLabSession(connection_error=True)).get_project_id(PROJECT)


def test_gui_write_profiles_can_shorten_the_timeout(tmp_path):
    folder = write_profiles(tmp_path / "p", download_s=1)
    assert load_profile(folder / "saf.yaml").timeouts.download_s == 1
