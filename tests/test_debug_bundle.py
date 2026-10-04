import json
import zipfile

from wflash.core.debug_bundle import DebugContext, collect_env_info, create_debug_bundle
from wflash.core.logging_setup import clear_secrets, register_secret
from wflash.core.winidea_adapter import FileEntry


def test_env_info_has_versions():
    info = collect_env_info()
    for key in ("wflash", "python", "platform", "PySide6", "isystem.connect"):
        assert key in info


def test_snapshot_and_error_recorded():
    ctx = DebugContext()
    ctx.snapshot("before", [FileEntry("App", "a.s3")], [FileEntry("CM7_0", "a.elf")])
    assert ctx.snapshots["before"] == {
        "programs": [{"name": "App", "path": "a.s3"}],
        "applications": [{"name": "CM7_0", "path": "a.elf"}],
    }
    try:
        raise ValueError("bad thing")
    except ValueError as exc:
        ctx.add_error(exc)
    assert "Traceback" in ctx.errors[0] and "bad thing" in ctx.errors[0]


def test_bundle_contents_and_redaction(tmp_path):
    register_secret("glpat-SECRET-1")
    log_file = tmp_path / "w.log"
    log_file.write_text("line with glpat-SECRET-1\n", encoding="utf-8")
    profile = tmp_path / "p.yaml"
    profile.write_text("name: P\n", encoding="utf-8")
    ctx = DebugContext(profile_path=profile, mapping=[{"target": "App"}], adapter_info={"adapter": "fake"})
    ctx.snapshot("before", [FileEntry("App", "a.s3")], [])
    path = create_debug_bundle(ctx, tmp_path / "out", log_file)
    clear_secrets()
    assert path.parent == tmp_path / "out" and path.name.startswith("wflash_debug_")
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        assert names == {
            "log.txt", "environment.json", "profile.yaml", "mapping.json", "workspace_snapshots.json", "errors.txt",
        }
        assert "glpat-SECRET-1" not in zf.read("log.txt").decode()
        env = json.loads(zf.read("environment.json"))
        assert env["winidea.adapter"] == "fake"
        assert json.loads(zf.read("workspace_snapshots.json"))["before"]["programs"][0]["name"] == "App"
        assert zf.read("errors.txt").decode() == "(no errors recorded)"


def test_bundle_without_log_or_profile(tmp_path):
    path = create_debug_bundle(DebugContext(), tmp_path, None)
    with zipfile.ZipFile(path) as zf:
        assert "log.txt" not in zf.namelist()
        assert "profile.yaml" not in zf.namelist()


def test_env_info_pyside6_version_falls_back_to_module_when_metadata_missing(monkeypatch):
    import importlib.metadata

    import PySide6

    def missing(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", missing)
    assert collect_env_info()["PySide6"] == PySide6.__version__


def test_env_info_pyside6_version_reported():
    assert collect_env_info()["PySide6"] != "not installed"
