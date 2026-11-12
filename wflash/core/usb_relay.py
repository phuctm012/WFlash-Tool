"""USB HID relay board (dcttech "USBRelay8") that powers the ECUs of benches 1 and 4 (user, 2026-11-12).

Calls, from spike 18 on bench 4 (hidapi 0.15.0, Python 3.12, `docs/winidea_api_notes.md` round 20):

- `hid.enumerate()` lists the board as vid 0x16C0, pid 0x05DF, product "USBRelay8",
  manufacturer "www.dcttech.com", with an empty HID serial.
- `hid.device().open_path(path)` opened it at once while the user's USB Relay Control window was
  open: that tool opens and closes the board for every command and every 1 s status poll.
- `get_feature_report(0, 9)` -> `[00, s1..s5, 00, 00, mask]`: report id, the board's own serial
  ("6QMBS" on bench 4), and the relay bitmask in the last byte (bit 0 = relay 1). Report id 1
  returned a short reply and `read()` failed, so neither is used.

Switching: `send_feature_report([0x00, 0xFF, n, 0x01])` turns relay n (1-based) on, `0xFD` off. That
is what the user's `usb_relay_control.py` sends; spike 18 did not switch anything, so every switch
is checked by reading the mask back. Relay **ON = ECU powered** (user), unlike Switch Debugger.
"All on/off" (0xFE / 0xFC) is never sent: it would switch the other ECU's power too.

`hid` (package `hidapi`) is imported lazily, like `isystem.connect`, so nothing else needs it.
"""
from __future__ import annotations

import time
from typing import Callable

from wflash.core.errors import BenchSwitchError
from wflash.core.logging_setup import get_logger

log = get_logger("bench.usb")

VID_PID = ((0x16C0, 0x05DF),)  # spike 18; the user's tool also tries 0x5131/0x2007, never seen here
RELAY_COUNT = 8
OPEN_TRIES = 8  # the user's tool: 8 retries, 0.25 s apart, when the board is busy
OPEN_RETRY_S = 0.25
ON, OFF = 0xFF, 0xFD


def _import_hid():
    try:
        import hid  # type: ignore
    except Exception as exc:  # noqa: BLE001 - any failure to load the native module means the same
        raise BenchSwitchError(
            "The USB relay library (hidapi) is not available.",
            hint="Install it in WFlash's Python environment: python -m pip install hidapi",
        ) from exc
    return hid


class UsbRelayBoard:
    """The one relay board on this PC. `hid_module` and `sleep` are injectable for tests."""

    def __init__(self, hid_module=None, sleep: Callable[[float], None] = time.sleep) -> None:
        self._hid = hid_module
        self._sleep = sleep

    def _module(self):
        if self._hid is None:
            self._hid = _import_hid()
        return self._hid

    def _path(self) -> bytes:
        boards = [d for d in self._module().enumerate()
                  if (int(d.get("vendor_id") or 0), int(d.get("product_id") or 0)) in VID_PID and d.get("path")]
        if not boards:
            raise BenchSwitchError("No USB relay board found.",
                                   hint="Check the USB cable of the relay board, then try again.")
        if len(boards) > 1:
            raise BenchSwitchError(f"{len(boards)} USB relay boards found; WFlash supports one per PC.",
                                   hint="Unplug the relay boards that do not power this ECU.")
        return boards[0]["path"]

    def _open(self):
        path = self._path()
        last: Exception | None = None
        for attempt in range(OPEN_TRIES):
            dev = self._module().device()
            try:
                dev.open_path(path)
                return dev
            except Exception as exc:  # noqa: BLE001 - busy: another program has it open right now
                last = exc
                if attempt < OPEN_TRIES - 1:
                    self._sleep(OPEN_RETRY_S)
        raise BenchSwitchError(
            "Could not open the USB relay board.",
            hint="Close USB Relay Manager if it is open (USB Relay Control can stay open), then try again.",
        ) from last

    def status(self) -> int:
        """The relay bitmask, bit 0 = relay 1 (spike 18: report id 0, last of 9 bytes)."""
        dev = self._open()
        try:
            data = dev.get_feature_report(0, 9)
        except Exception as exc:  # noqa: BLE001
            raise BenchSwitchError("Could not read the USB relay board.",
                                   hint="Unplug and plug in the relay board's USB cable, then try again.") from exc
        finally:
            dev.close()
        if not data or len(data) < 9:
            raise BenchSwitchError(f"Unexpected reply from the USB relay board: {list(data or [])}",
                                   hint="Check that the board is the 8-relay USBRelay8 used on this bench.")
        return int(data[-1]) & 0xFF

    def set(self, relay: int, on: bool) -> None:
        """Switch one relay, then read the mask back: the switch command was never observed by a spike."""
        if relay not in range(1, RELAY_COUNT + 1):
            raise BenchSwitchError(f"Unknown USB relay {relay}.", hint="Choose the bench in the Setting tab.")
        dev = self._open()
        try:
            sent = dev.send_feature_report([0x00, ON if on else OFF, relay, 0x01])
        except Exception as exc:  # noqa: BLE001
            raise BenchSwitchError(f"Could not switch USB relay {relay}.",
                                   hint="Unplug and plug in the relay board's USB cable, then try again.") from exc
        finally:
            dev.close()
        log.debug("USB relay %d %s: send_feature_report -> %s", relay, "on" if on else "off", sent)
        mask = self.status()
        if bool(mask & (1 << (relay - 1))) != on:
            raise BenchSwitchError(
                f"USB relay {relay} did not switch {'on' if on else 'off'} (relays now 0x{mask:02X}).",
                hint="Check the relay in USB Relay Control, then try again.",
            )
