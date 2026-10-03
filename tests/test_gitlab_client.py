import pytest
import requests
import responses
from responses import matchers

from wflash.core.cancel import CancelToken
from wflash.core.errors import ArtifactError, CancelledError, GitLabError
from wflash.core.gitlab_client import GitLabClient, Job, Pipeline, Ref
from wflash.core.logging_setup import clear_secrets, redact

BASE = "https://gitlab.example.com"
API = BASE + "/api/v4"
TOKEN = "glpat-secret-token"


@pytest.fixture
def client():
    yield GitLabClient(BASE + "/", TOKEN)
    clear_secrets()


@responses.activate
def test_project_id_lookup_encodes_path_and_sends_token(client):
    responses.get(f"{API}/projects/group%2Fsaf85xx-sw", json={"id": 42})
    assert client.get_project_id("group/saf85xx-sw") == 42
    assert responses.calls[0].request.headers["PRIVATE-TOKEN"] == TOKEN


def test_numeric_project_id_needs_no_request(client):
    assert client.get_project_id("42") == 42


@responses.activate
def test_list_refs(client):
    responses.get(f"{API}/projects/42/repository/branches", json=[{"name": "main"}, {"name": "dev"}])
    responses.get(f"{API}/projects/42/repository/tags", json=[{"name": "v1.0"}])
    assert client.list_refs(42) == [Ref("main", "branch"), Ref("dev", "branch"), Ref("v1.0", "tag")]


@responses.activate
def test_list_pipelines_passes_ref_and_order(client):
    responses.get(
        f"{API}/projects/42/pipelines",
        match=[matchers.query_param_matcher({"ref": "main", "per_page": "20", "order_by": "id", "sort": "desc"})],
        json=[{"id": 100, "ref": "main", "status": "success", "sha": "abcdef123456", "created_at": "2026-10-01T10:00:00Z"}],
    )
    assert client.list_pipelines(42, "main") == [
        Pipeline(100, "main", "success", "abcdef123456", "2026-10-01T10:00:00Z")
    ]


@responses.activate
def test_list_jobs_filters_by_glob_and_artifacts(client):
    archive = [{"file_type": "archive"}, {"file_type": "trace"}]
    responses.get(
        f"{API}/projects/42/pipelines/100/jobs",
        json=[
            {"id": 3, "name": "build_app", "stage": "build", "status": "success", "artifacts": archive},
            {"id": 4, "name": "build_docs", "stage": "build", "status": "success", "artifacts": [{"file_type": "trace"}]},
            {"id": 5, "name": "test_unit", "stage": "test", "status": "success", "artifacts": archive},
            {"id": 6, "name": "build_boot", "stage": "build", "status": "success", "artifacts_file": {"filename": "a.zip"}},
        ],
    )
    jobs = client.list_jobs(42, 100, "build_*")
    assert [j.name for j in jobs] == ["build_app", "build_boot"]
    assert jobs[0] == Job(3, "build_app", "build", "success", "")


@responses.activate
def test_download_artifacts_streams_to_file(client, tmp_path):
    body = b"PK" + b"x" * 5000
    responses.get(f"{API}/projects/42/jobs/7/artifacts", body=body, auto_calculate_content_length=True)
    seen = []
    path = client.download_artifacts(42, 7, tmp_path, progress_cb=lambda d, t: seen.append((d, t)))
    assert path == tmp_path / "artifacts_7.zip"
    assert path.read_bytes() == body
    assert seen[-1] == (len(body), len(body))


@responses.activate
def test_download_cancel_removes_partial_file(client, tmp_path):
    responses.get(f"{API}/projects/42/jobs/7/artifacts", body=b"x" * 10)
    token = CancelToken()
    token.cancel()
    with pytest.raises(CancelledError):
        client.download_artifacts(42, 7, tmp_path, cancel=token)
    assert list(tmp_path.iterdir()) == []


@responses.activate
def test_http_401_has_token_hint(client):
    responses.get(f"{API}/projects/42/repository/branches", status=401, json={"message": "401 Unauthorized"})
    with pytest.raises(GitLabError) as info:
        client.list_refs(42)
    assert "401" in str(info.value)
    assert "token" in info.value.hint.lower()


@responses.activate
def test_http_404_has_expired_hint(client, tmp_path):
    responses.get(f"{API}/projects/42/jobs/7/artifacts", status=404, json={"message": "404 Not Found"})
    with pytest.raises(GitLabError) as info:
        client.download_artifacts(42, 7, tmp_path / "unused")
    assert "expired" in info.value.hint


@responses.activate
def test_connection_error(client):
    responses.get(f"{API}/projects/42/repository/branches", body=requests.exceptions.ConnectionError("refused"))
    with pytest.raises(GitLabError, match="Cannot reach"):
        client.list_refs(42)


@responses.activate
def test_ssl_error_suggests_ca_bundle(client):
    responses.get(f"{API}/projects/42/repository/branches", body=requests.exceptions.SSLError("bad cert"))
    with pytest.raises(GitLabError) as info:
        client.list_refs(42)
    assert "CA bundle" in info.value.hint


def test_token_is_registered_for_redaction(client):
    assert redact(f"header {TOKEN}") == "header ***"


@responses.activate
def test_html_200_response_is_gitlab_error(client):
    responses.get(f"{API}/projects/42/repository/branches", body="<html>login</html>", content_type="text/html")
    with pytest.raises(GitLabError, match="Unexpected response") as info:
        client.list_refs(42)
    assert "proxy" in info.value.hint


@responses.activate
def test_json_missing_id_is_gitlab_error(client):
    responses.get(f"{API}/projects/group%2Fx", json={"name": "x"})
    with pytest.raises(GitLabError, match="Unexpected response"):
        client.get_project_id("group/x")


@responses.activate
def test_download_write_error_raises_artifact_error_and_cleans_part(client, tmp_path, monkeypatch):
    responses.get(f"{API}/projects/42/jobs/7/artifacts", body=b"x" * 10)

    def boom(self, *a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(type(tmp_path), "open", boom)
    with pytest.raises(ArtifactError) as info:
        client.download_artifacts(42, 7, tmp_path)
    assert "disk space" in info.value.hint
    assert list(tmp_path.iterdir()) == []


@responses.activate
def test_download_mkdir_error_raises_artifact_error(client, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    responses.get(f"{API}/projects/42/jobs/7/artifacts", body=b"x")
    with pytest.raises(ArtifactError):
        client.download_artifacts(42, 7, blocker / "sub")


@responses.activate
def test_list_refs_follows_pagination(client):
    def page(p, nxt):
        return dict(
            match=[matchers.query_param_matcher({"per_page": "100", "page": p})],
            headers={"X-Next-Page": nxt},
        )

    responses.get(f"{API}/projects/42/repository/branches", json=[{"name": "a"}], **page("1", "2"))
    responses.get(f"{API}/projects/42/repository/branches", json=[{"name": "b"}], **page("2", ""))
    responses.get(f"{API}/projects/42/repository/tags", json=[{"name": "t"}], **page("1", ""))
    assert client.list_refs(42) == [Ref("a", "branch"), Ref("b", "branch"), Ref("t", "tag")]


@responses.activate
def test_list_pipelines_clamps_limit(client):
    responses.get(
        f"{API}/projects/42/pipelines",
        match=[matchers.query_param_matcher({"ref": "main", "per_page": "100", "order_by": "id", "sort": "desc"})],
        json=[],
    )
    assert client.list_pipelines(42, "main", limit=500) == []
