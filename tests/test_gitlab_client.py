import pytest
import requests
import responses
from responses import matchers

from wflash.core.cancel import CancelToken
from wflash.core.errors import ArtifactError, CancelledError, GitLabError
from wflash.core.gitlab_client import GitLabClient, Job, PackageVersion, Pipeline, Ref
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


@responses.activate
def test_download_malformed_content_length_is_treated_as_unknown(client, tmp_path):
    body = b"PK" + b"x" * 100
    responses.get(f"{API}/projects/42/jobs/8/artifacts", body=body, headers={"Content-Length": "abc"})
    seen = []
    path = client.download_artifacts(42, 8, tmp_path, progress_cb=lambda d, t: seen.append((d, t)))
    assert path.read_bytes() == body
    assert seen and seen[-1][1] == 0


# -- TLS verification ------------------------------------------------------------------


def test_verify_defaults_to_true_or_ca_bundle():
    assert GitLabClient(BASE, TOKEN).verify is True
    assert GitLabClient(BASE, TOKEN, ca_bundle="/ca.pem").verify == "/ca.pem"
    clear_secrets()


@responses.activate
def test_verify_false_is_passed_to_requests():
    client = GitLabClient(BASE, TOKEN, ca_bundle="/ca.pem", verify=False)
    assert client.verify is False
    responses.get(f"{API}/projects/42/repository/branches", json=[])
    responses.get(f"{API}/projects/42/repository/tags", json=[])
    assert client.list_refs(42) == []
    assert all(call.request.req_kwargs["verify"] is False for call in responses.calls)
    clear_secrets()


# -- Package Registry ------------------------------------------------------------------

PKG_LIST = f"{API}/projects/43/packages"


def pkg(id_, name, version, created="2026-10-04T09:20:00Z"):
    return {"id": id_, "name": name, "version": version, "package_type": "generic", "created_at": created}


@responses.activate
def test_list_package_versions_keeps_exact_name_newest_first(client):
    responses.get(
        PKG_LIST,
        match=[matchers.query_param_matcher({
            "package_type": "generic", "package_name": "fw", "order_by": "created_at", "sort": "desc",
            "per_page": "100", "page": "1",
        })],
        json=[pkg(502, "fw", "1.4.0"), pkg(503, "fw-debug", "9.9.9"), pkg(501, "fw", "1.3.0", "2026-10-01T08:00:00Z")],
    )
    assert client.list_package_versions(43, "fw") == [
        PackageVersion(502, "fw", "1.4.0", "2026-10-04T09:20:00Z"),
        PackageVersion(501, "fw", "1.3.0", "2026-10-01T08:00:00Z"),
    ]


@responses.activate
def test_list_package_versions_follows_pages_until_limit(client):
    def page(p, nxt):
        return dict(
            match=[matchers.query_param_matcher({
                "package_type": "generic", "package_name": "fw", "order_by": "created_at", "sort": "desc",
                "per_page": "100", "page": p,
            })],
            headers={"X-Next-Page": nxt},
        )

    responses.get(PKG_LIST, json=[pkg(3, "fw-x", "0")], **page("1", "2"))
    responses.get(PKG_LIST, json=[pkg(2, "fw", "2.0"), pkg(1, "fw", "1.0")], **page("2", "3"))
    versions = client.list_package_versions(43, "fw", limit=1)
    assert [v.version for v in versions] == ["2.0"]
    assert len(responses.calls) == 2  # page 3 is never requested once the limit is reached


@responses.activate
def test_no_package_versions_is_a_gitlab_error_with_hint(client):
    responses.get(PKG_LIST, json=[pkg(9, "fw-debug", "1.0")])
    with pytest.raises(GitLabError, match="No versions of package 'fw' found") as info:
        client.list_package_versions(43, "fw")
    assert "package project and name" in info.value.hint


@responses.activate
def test_download_package_fetches_the_first_file(client, tmp_path):
    version = PackageVersion(502, "fw", "1.4.0", "")
    responses.get(
        f"{API}/projects/43/packages/502/package_files",
        json=[{"id": 1, "file_name": "fw-1.4.0.zip"}, {"id": 2, "file_name": "notes.txt"}],
    )
    body = b"PK" + b"z" * 3000
    responses.get(f"{API}/projects/43/packages/generic/fw/1.4.0/fw-1.4.0.zip", body=body,
                  auto_calculate_content_length=True)
    seen = []
    path = client.download_package(43, version, tmp_path, progress_cb=lambda d, t: seen.append((d, t)))
    assert path == tmp_path / "fw-1.4.0.zip"
    assert path.read_bytes() == body
    assert seen[-1] == (len(body), len(body))
    assert responses.calls[1].request.headers["PRIVATE-TOKEN"] == TOKEN


@responses.activate
def test_download_package_quotes_name_version_and_file(client, tmp_path):
    version = PackageVersion(7, "fw pkg", "1.0+b1", "")
    responses.get(f"{API}/projects/43/packages/7/package_files", json=[{"file_name": "a b.s3"}])
    responses.get(f"{API}/projects/43/packages/generic/fw%20pkg/1.0%2Bb1/a%20b.s3", body=b"S0")
    assert client.download_package(43, version, tmp_path).read_bytes() == b"S0"


@responses.activate
def test_download_package_never_writes_outside_dest(client, tmp_path):
    version = PackageVersion(7, "fw", "1.0", "")
    responses.get(f"{API}/projects/43/packages/7/package_files", json=[{"file_name": "../../evil.bin"}])
    responses.get(f"{API}/projects/43/packages/generic/fw/1.0/..%2F..%2Fevil.bin", body=b"x")
    path = client.download_package(43, version, tmp_path / "dl")
    assert path == tmp_path / "dl" / "evil.bin"


@responses.activate
def test_download_package_without_files_is_a_gitlab_error(client, tmp_path):
    version = PackageVersion(7, "fw", "1.0", "")
    responses.get(f"{API}/projects/43/packages/7/package_files", json=[])
    with pytest.raises(GitLabError, match="Version '1.0' of package 'fw' has no files") as info:
        client.download_package(43, version, tmp_path)
    assert "another version" in info.value.hint


@responses.activate
def test_download_package_cancel_removes_partial_file(client, tmp_path):
    version = PackageVersion(7, "fw", "1.0", "")
    responses.get(f"{API}/projects/43/packages/7/package_files", json=[{"file_name": "fw.zip"}])
    responses.get(f"{API}/projects/43/packages/generic/fw/1.0/fw.zip", body=b"x" * 10)
    token = CancelToken()
    token.cancel()
    with pytest.raises(CancelledError):
        client.download_package(43, version, tmp_path, cancel=token)
    assert list(tmp_path.iterdir()) == []


@responses.activate
def test_download_package_disk_error_is_an_artifact_error(client, tmp_path, monkeypatch):
    version = PackageVersion(7, "fw", "1.0", "")
    responses.get(f"{API}/projects/43/packages/7/package_files", json=[{"file_name": "fw.zip"}])
    responses.get(f"{API}/projects/43/packages/generic/fw/1.0/fw.zip", body=b"x" * 10)

    def boom(self, *a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(type(tmp_path), "open", boom)
    with pytest.raises(ArtifactError, match="Cannot write package") as info:
        client.download_package(43, version, tmp_path)
    assert "disk space" in info.value.hint
    assert list(tmp_path.iterdir()) == []


@responses.activate
def test_download_package_interrupted_is_a_gitlab_error(client, tmp_path):
    version = PackageVersion(7, "fw", "1.0", "")
    responses.get(f"{API}/projects/43/packages/7/package_files", json=[{"file_name": "fw.zip"}])
    responses.get(
        f"{API}/projects/43/packages/generic/fw/1.0/fw.zip",
        body=requests.exceptions.ConnectionError("reset by peer"),
    )
    with pytest.raises(GitLabError, match="Cannot reach GitLab"):
        client.download_package(43, version, tmp_path)
