"""Bench power and JTAG through Switch Debugger: protocol lines, polarity, power cycle, TCP errors."""
from __future__ import annotations

import socket
import threading

import pytest

from wflash.core import bench_switch
from wflash.core.bench_switch import BenchConfig, BenchSwitch, command
from wflash.core.errors import BenchSwitchError


def make(**kw):
    sent: list[tuple[str, int, str]] = []
    sleeps: list[float] = []
    switch = BenchSwitch(BenchConfig(**kw), send=lambda h, p, line: sent.append((h, p, line)), sleep=sleeps.append)
    return switch, sent, sleeps


def lines(sent):
    return [line for _h, _p, line in sent]


def test_command_matches_the_users_script():
    assert command(True, "Sensor", 3) == "SwitchDebugger6Sensor4Relay;On;Sensor;3\n"
    assert command(False, "Relay", 1) == "SwitchDebugger6Sensor4Relay;Off;Relay;1\n"


def test_jtag_port_d_is_sensor_3():
    switch, sent, _ = make(jtag_port="D")
    switch.jtag(True)
    switch.jtag(False)
    assert lines(sent) == ["SwitchDebugger6Sensor4Relay;On;Sensor;3\n", "SwitchDebugger6Sensor4Relay;Off;Sensor;3\n"]


def test_power_relay_is_inverted_and_zero_based():
    switch, sent, _ = make(power_relay=2)
    switch.power(True)   # relay 2 Off = power on
    switch.power(False)  # relay 2 On = power off
    assert lines(sent) == ["SwitchDebugger6Sensor4Relay;Off;Relay;1\n", "SwitchDebugger6Sensor4Relay;On;Relay;1\n"]


def test_host_and_port_come_from_the_config():
    switch, sent, _ = make(host="10.0.0.5", port=2000)
    switch.jtag(True)
    assert sent[0][:2] == ("10.0.0.5", 2000)


def test_never_sends_off_all():
    switch, sent, _ = make()
    switch.jtag(True)
    switch.jtag(False)
    switch.power_cycle()
    assert not any("Off_All" in line for line in lines(sent))


def test_power_cycle_off_wait_on_wait():
    switch, sent, sleeps = make(power_relay=2, off_s=3, boot_s=5)
    switch.power_cycle()
    assert lines(sent) == ["SwitchDebugger6Sensor4Relay;On;Relay;1\n", "SwitchDebugger6Sensor4Relay;Off;Relay;1\n"]
    assert sum(sleeps) == pytest.approx(8)


def test_power_comes_back_on_when_cancelled_while_off():
    switch, sent, sleeps = make(off_s=3, boot_s=5)
    switch.power_cycle(is_cancelled=lambda: True)
    assert lines(sent)[-1] == "SwitchDebugger6Sensor4Relay;Off;Relay;1\n"  # power on
    assert sleeps == []


def test_power_comes_back_on_when_the_wait_raises():
    sent = []

    def sleep(_s):
        raise KeyboardInterrupt

    switch = BenchSwitch(BenchConfig(), send=lambda h, p, line: sent.append(line), sleep=sleep)
    with pytest.raises(KeyboardInterrupt):
        switch.power_cycle()
    assert sent[-1] == "SwitchDebugger6Sensor4Relay;Off;Relay;1\n"


@pytest.mark.parametrize("kw", [{"jtag_port": "G"}, {"jtag_port": "CD"}, {"power_relay": 0}, {"power_relay": 7}])
def test_bad_config_is_refused(kw):
    with pytest.raises(BenchSwitchError) as info:
        BenchSwitch(BenchConfig(**kw), send=lambda *a: None)
    assert info.value.hint


def test_send_tcp_delivers_the_line(monkeypatch):
    monkeypatch.setattr(bench_switch, "SEND_DELAY_S", 0)
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    received = []

    def serve():
        conn, _ = server.accept()
        with conn:
            data = b""
            while chunk := conn.recv(1024):
                data += chunk
            received.append(data)

    thread = threading.Thread(target=serve)
    thread.start()
    bench_switch.send_tcp("127.0.0.1", server.getsockname()[1], "SwitchDebugger6Sensor4Relay;On;Sensor;3\n")
    thread.join(5)
    server.close()
    assert received == [b"SwitchDebugger6Sensor4Relay;On;Sensor;3\n"]


def test_send_tcp_refused_has_an_actionable_hint(monkeypatch):
    monkeypatch.setattr(bench_switch, "SEND_DELAY_S", 0)
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    port = server.getsockname()[1]
    server.close()  # nothing listens there now
    with pytest.raises(BenchSwitchError) as info:
        bench_switch.send_tcp("127.0.0.1", port, "x\n")
    assert "Start" in info.value.hint
    assert isinstance(info.value.__cause__, OSError)


def test_settings_default_to_off_and_the_users_bench(tmp_path):
    from wflash.core.settings import AppSettings

    settings = AppSettings()
    assert settings.bench_enabled is False
    assert settings.bench_config() == BenchConfig("127.11.0.1", 1101, "D", 2, 3, 5)
    settings.bench_enabled, settings.bench_jtag_port, settings.bench_power_relay = True, "C", 1
    path = tmp_path / "settings.json"
    settings.save(path)
    loaded = AppSettings.load(path)
    assert loaded.bench_enabled is True
    assert loaded.bench_config().jtag_port == "C" and loaded.bench_config().power_relay == 1
