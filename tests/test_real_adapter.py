import logging
import sys

import pytest

from tests.fake_isystem import WORKSPACE, World, install
from wflash.core.errors import WinIDEAError
from wflash.core.winidea_adapter import RealWinIDEAAdapter


@pytest.fixture
def world(monkeypatch):
    world = World()
    install(monkeypatch, world)
    return world


@pytest.fixture
def adapter(world):
    adapter = RealWinIDEAAdapter()
    adapter.list_instances()
    return adapter


@pytest.fixture
def connected(adapter):
    adapter.connect("5315")
    yield adapter
    adapter.disconnect()


def test_list_instances_uses_the_port_as_id_because_winidea_gives_an_empty_id(world):
    [info] = RealWinIDEAAdapter().list_instances()
    assert (info.instance_id, info.workspace, info.tcp_port) == ("5315", WORKSPACE, 5315)
    assert info.label() == "SUZ_7G5_M7.xjrf (5315)"


def test_list_instances_returns_empty_when_the_module_is_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "isystem.connect", None)
    assert RealWinIDEAAdapter().list_instances() == []


def test_connect_reports_the_root_cause_when_the_module_cannot_load(monkeypatch):
    monkeypatch.setitem(sys.modules, "isystem.connect", None)
    with pytest.raises(WinIDEAError) as err:
        RealWinIDEAAdapter().connect("5315")
    assert "isystem.connect" in str(err.value)
    assert "bitness" in err.value.hint
    assert isinstance(err.value.__cause__, ImportError)


def test_connect_refuses_when_winidea_attached_to_another_workspace(adapter, world):
    world.workspace = "C:/other/Other.xjrf"
    with pytest.raises(WinIDEAError) as err:
        adapter.connect("5315")
    assert "Other.xjrf" in str(err.value)
    assert "Close" in err.value.hint
    with pytest.raises(WinIDEAError):
        adapter.get_info()  # the session was dropped


def test_connect_accepts_the_same_workspace_written_with_other_slashes(adapter, world):
    world.workspace = "C:\\WS\\suz_7g5_m7.xjrf"
    adapter.connect("5315")
    assert adapter.get_info()["workspace"] == "C:\\WS\\suz_7g5_m7.xjrf"


def test_connect_fails_when_not_attached(adapter, world):
    world.attached = False
    with pytest.raises(WinIDEAError):
        adapter.connect("5315")


def test_connect_wraps_a_connection_failure(adapter, world):
    world.connect_error = OSError("no winIDEA")
    with pytest.raises(WinIDEAError) as err:
        adapter.connect("5315")
    assert isinstance(err.value.__cause__, OSError)


def test_connect_to_an_unknown_instance_fails(adapter):
    with pytest.raises(WinIDEAError):
        adapter.connect("9999")


def test_get_info_reports_versions(connected):
    info = connected.get_info()
    assert info["winidea_version"] == "9.21.408.1.260751"
    assert info["isystem_connect"] == "9.21.408.1"
    assert info["adapter"] == "real"


def test_version_mismatch_is_a_warning_not_a_block(adapter, world, caplog):
    world.module_version = "9.26.11.2"
    with caplog.at_level(logging.WARNING):
        adapter.connect("5315")
        adapter.get_info()
    assert any("does not match" in r.getMessage() and r.levelno == logging.WARNING for r in caplog.records)


def test_download_is_not_cancellable():
    assert RealWinIDEAAdapter.download_cancellable is False
