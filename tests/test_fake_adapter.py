import pytest

from wflash.core.cancel import CancelToken
from wflash.core.errors import CancelledError, FlashError, WinIDEAError
from wflash.core.fake_adapter import FakeWinIDEAAdapter
from wflash.core.winidea_adapter import FileEntry, InstanceInfo, create_adapter


def connected(**kwargs):
    adapter = FakeWinIDEAAdapter(download_seconds=0.02, **kwargs)
    adapter.connect("fake-1")
    return adapter


def test_instance_label_uses_workspace_file_name():
    info = InstanceInfo("id-7", r"C:\ws\SAF85xx.xjrf", 5313)
    assert info.label() == "SAF85xx.xjrf (id-7)"


def test_requires_connection():
    with pytest.raises(WinIDEAError, match="Not connected"):
        FakeWinIDEAAdapter().read_programs()


def test_connect_unknown_instance():
    with pytest.raises(WinIDEAError, match="No winIDEA instance"):
        FakeWinIDEAAdapter().connect("other")


def test_list_and_read_defaults():
    adapter = FakeWinIDEAAdapter()
    assert [i.instance_id for i in adapter.list_instances()] == ["fake-1"]
    adapter.connect("fake-1")
    assert [e.name for e in adapter.read_programs()] == ["App"]
    assert [e.name for e in adapter.read_applications()] == ["CM7_0", "CM7_1"]
    assert adapter.get_info()["adapter"] == "fake"


def test_set_paths_download_reset():
    adapter = connected()
    adapter.set_program_path("App", "/new/App.s3")
    adapter.set_symbol_path("CM7_0", "/new/a.elf")
    assert FileEntry("App", "/new/App.s3") in adapter.read_programs()
    progress = []
    adapter.download(lambda p, m: progress.append(p), CancelToken(), timeout_s=60)
    assert progress[-1] == 100
    adapter.reset(run=False)
    assert adapter.target_state == "halted"
    adapter.reset(run=True)
    assert adapter.target_state == "running"


def test_set_unknown_entry():
    with pytest.raises(WinIDEAError, match="Unknown program entry"):
        connected().set_program_path("Nope", "/x")


def test_injected_download_failure_mid_way():
    adapter = connected(fail_on={"download"})
    progress = []
    with pytest.raises(FlashError, match="injected"):
        adapter.download(lambda p, m: progress.append(p), CancelToken(), timeout_s=60)
    assert progress and progress[-1] < 100


def test_injected_reset_failure():
    with pytest.raises(WinIDEAError, match="injected in 'reset'"):
        connected(fail_on={"reset"}).reset(run=False)


def test_cancel_during_download():
    adapter = connected()
    token = CancelToken()
    with pytest.raises(CancelledError):
        adapter.download(lambda p, m: token.cancel(), token, timeout_s=60)


def test_timeout():
    with pytest.raises(FlashError, match="timed out"):
        connected().download(lambda p, m: None, CancelToken(), timeout_s=0)


def test_from_env(monkeypatch):
    monkeypatch.setenv("WFLASH_FAKE_FAIL", "download, reset")
    monkeypatch.setenv("WFLASH_FAKE_DOWNLOAD_S", "0.5")
    adapter = FakeWinIDEAAdapter.from_env()
    assert adapter.fail_on == {"download", "reset"}
    assert adapter.download_seconds == 0.5


def test_create_adapter():
    assert isinstance(create_adapter("fake"), FakeWinIDEAAdapter)
    with pytest.raises(WinIDEAError):
        create_adapter("real")
    with pytest.raises(ValueError):
        create_adapter("other")


def test_list_instances_failure_returns_empty():
    adapter = FakeWinIDEAAdapter(fail_on={"list_instances"})
    assert adapter.list_instances() == []


def test_connection_lost_after_successful_connect():
    adapter = connected(fail_on={"connection_lost"})
    assert adapter.connected_to == "fake-1"
    lost = "Connection to winIDEA lost"
    with pytest.raises(WinIDEAError, match=lost):
        adapter.get_info()
    with pytest.raises(WinIDEAError, match=lost):
        adapter.read_programs()
    with pytest.raises(WinIDEAError, match=lost):
        adapter.read_applications()
    with pytest.raises(WinIDEAError, match=lost):
        adapter.set_program_path("App", "/x")
    with pytest.raises(WinIDEAError, match=lost):
        adapter.set_symbol_path("CM7_0", "/x")
    with pytest.raises(WinIDEAError, match=lost):
        adapter.download(lambda p, m: None, CancelToken(), timeout_s=60)
    with pytest.raises(WinIDEAError, match=lost):
        adapter.reset(run=True)
    adapter.disconnect()
    assert adapter.connected_to is None
