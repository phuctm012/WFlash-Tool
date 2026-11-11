"""Setting tab Switch Debugger group and the Tools menu power/JTAG actions."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from tests.gui_stubs import GITLAB_URL, TOKEN, FakeGitLabSession, SessionClientFactory, patch_keyring, write_profiles
from wflash.core import bench_switch
from wflash.core.errors import BenchSwitchError
from wflash.core.fake_adapter import FakeWinIDEAAdapter
from wflash.core.settings import AppSettings
from wflash.gui.main_window import MainWindow
from wflash.gui.style import apply_theme

pytestmark = pytest.mark.gui


@pytest.fixture
def env(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: None)
    patch_keyring(monkeypatch, {GITLAB_URL: TOKEN})
    sent = []
    monkeypatch.setattr(bench_switch, "send_tcp", lambda host, port, line: sent.append((host, port, line)))
    monkeypatch.setattr(bench_switch.BenchSwitch, "_wait", lambda self, seconds, is_cancelled: None)
    settings = AppSettings(gitlab_url=GITLAB_URL, profiles_dir=str(write_profiles(tmp_path / "profiles")),
                           cache_dir=str(tmp_path / "cache"))
    window = MainWindow(settings, FakeWinIDEAAdapter(download_seconds=0.2),
                        client_factory=SessionClientFactory(FakeGitLabSession()), settings_path=tmp_path / "settings.json")
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: window.ui.comboBox_instance.count() == 1, timeout=3000)
    yield SimpleNamespace(window=window, sent=sent, tmp=tmp_path)
    apply_theme(QApplication.instance(), False)
    QApplication.instance().setStyleSheet("")


def lines(env):
    return [line for _h, _p, line in env.sent]


def test_gui_bench_is_off_by_default(env):
    ui = env.window.ui
    assert not ui.checkBox_benchEnabled.isChecked()
    assert not ui.comboBox_benchEcu.isEnabled()
    for action in (ui.action_powerCycle, ui.action_jtagConnect, ui.action_jtagDisconnect):
        assert not action.isEnabled()
    assert ui.comboBox_benchEcu.currentIndex() == 1
    assert ui.spinBox_benchBoot.value() == 4


def test_gui_bench_combo_items_match_the_bench(env):
    combo = env.window.ui.comboBox_benchEcu
    assert [combo.itemText(i) for i in range(combo.count())] == [bench_switch.ecu_label(e) for e in sorted(bench_switch.ECUS)]


def test_gui_bench_settings_save_at_once(env):
    ui = env.window.ui
    ui.checkBox_benchEnabled.setChecked(True)
    ui.comboBox_benchEcu.setCurrentIndex(0)
    ui.spinBox_benchBoot.setValue(6)
    saved = json.loads((env.tmp / "settings.json").read_text())
    assert saved["bench_enabled"] is True and saved["bench_ecu"] == 0 and saved["bench_boot_s"] == 6
    assert ui.action_powerCycle.isEnabled()


def test_gui_power_cycle_switches_only_the_chosen_ecu(env, qtbot):
    w = env.window
    w.ui.checkBox_benchEnabled.setChecked(True)
    w.ui.comboBox_benchEcu.setCurrentIndex(0)  # port C, relay 1
    w.ui.action_powerCycle.trigger()
    qtbot.waitUntil(lambda: not w.tools_busy(), timeout=3000)
    assert lines(env) == ["SwitchDebugger6Sensor4Relay;On;Relay;0\n", "SwitchDebugger6Sensor4Relay;Off;Relay;0\n"]
    assert env.sent[0][:2] == ("127.11.0.1", 1101)


def test_gui_jtag_connect_and_disconnect(env, qtbot):
    w = env.window
    w.ui.checkBox_benchEnabled.setChecked(True)
    w.ui.action_jtagConnect.trigger()
    qtbot.waitUntil(lambda: not w.tools_busy(), timeout=3000)
    w.ui.action_jtagDisconnect.trigger()
    qtbot.waitUntil(lambda: not w.tools_busy(), timeout=3000)
    assert lines(env) == ["SwitchDebugger6Sensor4Relay;On;Sensor;3\n", "SwitchDebugger6Sensor4Relay;Off;Sensor;3\n"]


def test_gui_bench_does_nothing_while_off(env):
    env.window.power_cycle_ecu()
    assert env.sent == []


def test_gui_bench_does_nothing_while_flashing(env, monkeypatch):
    w = env.window
    w.ui.checkBox_benchEnabled.setChecked(True)
    monkeypatch.setattr(w, "flash_active", lambda: True)
    w._update_flash_controls()
    assert not w.ui.action_powerCycle.isEnabled() and not w.ui.groupBox_bench.isEnabled()
    w.power_cycle_ecu()
    assert env.sent == []
    monkeypatch.setattr(w, "flash_active", lambda: False)  # else closing the window asks "Quit anyway?"


def test_gui_bench_failure_is_logged_with_its_hint(env, qtbot, monkeypatch, caplog):
    def refuse(host, port, line):
        raise BenchSwitchError("Switch Debugger refused the connection.", hint="Open Switch Debugger and press Start.")

    monkeypatch.setattr(bench_switch, "send_tcp", refuse)
    w = env.window
    w.ui.checkBox_benchEnabled.setChecked(True)
    w.ui.action_jtagConnect.trigger()
    qtbot.waitUntil(lambda: not w.tools_busy(), timeout=3000)
    assert "press Start" in caplog.text
