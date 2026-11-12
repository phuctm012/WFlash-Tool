"""USB HID relay board of benches 1 and 4, against a stand-in built from spike 18 (2026-11-12)."""
from __future__ import annotations

import pytest

from wflash.core import bench_switch, usb_relay
from wflash.core.bench_switch import BenchConfig, BenchSwitch
from wflash.core.errors import BenchSwitchError
from wflash.core.usb_relay import UsbRelayBoard

PATH = b"\\\\?\\HID#VID_16C0&PID_05DF#6&34a37147&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}"


class FakeHid:
    """Spike 18: one USBRelay8, empty HID serial, report 0 = [00, serial x5, 00, 00, mask]."""

    def __init__(self, mask=0x01, boards=1, busy=0, stuck=False):
        self.mask, self.boards, self.busy, self.stuck = mask, boards, busy, stuck
        self.sent: list[list[int]] = []
        self.opened = 0
        hid = self

        class device:  # noqa: N801 - the hid module's own name
            def open_path(self, path):
                assert path == PATH
                if hid.busy:
                    hid.busy -= 1
                    raise OSError("open failed")
                hid.opened += 1

            def close(self):
                pass

            def send_feature_report(self, data):
                data = list(data)
                hid.sent.append(data)
                if data[1] in (0xFE, 0xFC):
                    raise AssertionError("all on/off must never be sent")
                if not hid.stuck and data[1] in (0xFF, 0xFD):
                    bit = 1 << (data[2] - 1)
                    hid.mask = hid.mask | bit if data[1] == 0xFF else hid.mask & ~bit
                return len(data)

            def get_feature_report(self, report_id, size):
                assert (report_id, size) == (0, 9)
                return [0x00, 0x36, 0x51, 0x4D, 0x42, 0x53, 0x00, 0x00, hid.mask]

        self.device = device

    def enumerate(self):
        board = {"vendor_id": 0x16C0, "product_id": 0x05DF, "serial_number": "", "product_string": "USBRelay8",
                 "manufacturer_string": "www.dcttech.com", "path": PATH}
        other = {"vendor_id": 0x046D, "product_id": 0xC52B, "path": b"mouse"}
        return [other] + [dict(board) for _ in range(self.boards)]


def board(hid):
    return UsbRelayBoard(hid_module=hid, sleep=lambda s: None)


def test_status_reads_the_last_byte_of_report_0():
    assert board(FakeHid(mask=0x05)).status() == 0x05


@pytest.mark.parametrize("relay, on, packet", [(1, True, [0x00, 0xFF, 1, 0x01]), (2, False, [0x00, 0xFD, 2, 0x01])])
def test_set_sends_the_users_command_and_checks_it(relay, on, packet):
    hid = FakeHid(mask=0x02)
    board(hid).set(relay, on)
    assert hid.sent == [packet]
    assert bool(hid.mask & (1 << (relay - 1))) == on


def test_a_relay_that_does_not_switch_is_an_error():
    hid = FakeHid(mask=0x00, stuck=True)
    with pytest.raises(BenchSwitchError) as err:
        board(hid).set(1, True)
    assert "did not switch on" in str(err.value)


def test_busy_board_is_retried_then_refused():
    hid = FakeHid(busy=3)
    assert board(hid).status() == 0x01  # opened on the 4th try
    with pytest.raises(BenchSwitchError) as err:
        board(FakeHid(busy=usb_relay.OPEN_TRIES)).status()
    assert "USB Relay Manager" in err.value.hint


def test_no_board_and_two_boards_are_refused():
    with pytest.raises(BenchSwitchError, match="No USB relay board"):
        board(FakeHid(boards=0)).status()
    with pytest.raises(BenchSwitchError, match="2 USB relay boards"):
        board(FakeHid(boards=2)).status()


def test_missing_hidapi_has_an_install_hint(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def no_hid(name, *args, **kwargs):
        if name == "hid":
            raise ImportError("No module named 'hid'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_hid)
    with pytest.raises(BenchSwitchError) as err:
        UsbRelayBoard().status()
    assert "pip install hidapi" in err.value.hint


@pytest.mark.parametrize("bench", ["Bench 1", "Bench 4"])
@pytest.mark.parametrize("ecu, port, relay", [(0, "A", 1), (1, "B", 2)])
def test_usb_relay_benches(bench, ecu, port, relay):
    config = BenchConfig.for_ecu(ecu, bench)
    assert (config.jtag_port, config.power_relay, config.power_via) == (port, relay, bench_switch.USB_RELAY)


def test_power_cycle_on_a_usb_relay_bench_switches_only_that_relay_and_keeps_jtag_on_switch_debugger():
    hid = FakeHid(mask=0x03)  # both ECUs powered
    sent_tcp = []
    switch = BenchSwitch(BenchConfig.for_ecu(1, "Bench 4"), send=lambda h, p, line: sent_tcp.append(line),
                         sleep=lambda s: None, relay_board=board(hid))
    switch.jtag(True)
    switch.power_cycle()
    assert sent_tcp == ["SwitchDebugger6Sensor4Relay;On;Sensor;1\n"]  # CH-B; no Switch Debugger relay
    assert hid.sent == [[0x00, 0xFD, 2, 0x01], [0x00, 0xFF, 2, 0x01]]  # off, then on: relay on = power on
    assert hid.mask == 0x03  # ECU 0's relay untouched


def test_usb_power_comes_back_on_when_the_off_wait_is_cut_short():
    hid = FakeHid(mask=0x01)
    switch = BenchSwitch(BenchConfig.for_ecu(0, "Bench 1"), send=lambda *a: None, sleep=lambda s: None,
                         relay_board=board(hid))
    switch.power_cycle(is_cancelled=lambda: True)
    assert hid.sent[-1] == [0x00, 0xFF, 1, 0x01] and hid.mask & 0x01


def test_bench_labels_name_the_usb_relay():
    assert bench_switch.bench_label("Bench 1") == "Bench 1 (ECU 0: CH-A + USB relay 1, ECU 1: CH-B + USB relay 2)"
    assert bench_switch.ecu_label(0, "Bench 4") == "ECU 0 (CH-A, USB relay 1)"
    assert bench_switch.bench_label("Bench 2") == "Bench 2 (ECU 0: CH-C + relay 1, ECU 1: CH-D + relay 2)"
