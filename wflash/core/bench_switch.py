"""Bench power and JTAG through the Switch Debugger box's TCP service (user's bench tool, 2026-11-11).

Protocol, from the user's `switch_debugger.py` and the Switch Debugger window:

    SwitchDebugger6Sensor4Relay;<On|Off>;<Sensor|Relay>;<0-based id>\\n

- A "Sensor" is a JTAG port, A-F = 0-5. `On` connects the debugger to that port. The box connects
  one port at a time, and it treats `Off;Sensor;<id>` like `On` (bench, 2026-11-12: C stayed green,
  the box logged "Send Switch to Port 3" for both, the user's own script did the same, and pressing
  C by hand does not release it). Only `Off_All;Sensor;_` disconnects, so Disconnect JTAG sends
  that. It cannot cut another ECU's JTAG: no second port can be connected at the same time.
- A "Relay" is numbered 1-6 on the box and 0-based in the protocol. For the ECU's power relay the
  polarity is inverted: relay **Off = power ON**, relay **On = power OFF** (user, 2026-11-11; the
  other relays stay On). Each bench wires its two ECUs to its own ports and relays (`BENCHES`, user,
  2026-11-12). A power cycle keeps JTAG connected (user decision). Benches 1 and 4 power their ECUs
  through a USB relay board instead (`usb_relay.py`, relay ON = power on); their JTAG still goes
  through Switch Debugger.

Only the configured port and relay are ever switched, apart from that `Off_All` for the ports.
`Off_All` is never sent for the relays: "Disconnect All Relay" would also switch the relays, and so
the power, of other ECUs on the same box.

Each command opens a connection, waits, sends, waits and closes, as the user's script does (it
mirrors the C# tool's `Execution.Wait(2000)`); no reply is read. Nothing here imports Qt.
"""
from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from typing import Callable

from wflash.core.errors import BenchSwitchError
from wflash.core.logging_setup import get_logger

log = get_logger("bench")

PREFIX = "SwitchDebugger6Sensor4Relay"
PORTS = "ABCDEF"
RELAYS = range(1, 7)
SEND_DELAY_S = 2.0
CONNECT_TIMEOUT_S = 5.0
DEFAULT_HOST = "127.11.0.1"  # the same on every bench (user, 2026-11-12): not in the GUI
DEFAULT_PORT = 1101
# User, 2026-11-12: 1 s each works on the bench, so they are fixed and not in the GUI.
OFF_S = 1
BOOT_S = 1
# The benches (user, 2026-11-12): ECU -> (JTAG channel of Switch Debugger, power relay). Benches alike in
# wiring are all listed so the user picks the bench by its name.
BENCHES: dict[str, dict[int, tuple[str, int]]] = {
    "Bench 1": {0: ("A", 1), 1: ("B", 2)},
    "Bench 2": {0: ("C", 1), 1: ("D", 2)},  # the bench WFlash was tested on (rounds 16-19)
    "Bench 3": {0: ("A", 1), 1: ("B", 2)},
    "Bench 4": {0: ("A", 1), 1: ("B", 2)},
    "Bench 5": {0: ("A", 1), 1: ("B", 2)},
}
SWITCH_DEBUGGER, USB_RELAY = "switch_debugger", "usb_relay"
# Where the power relay is; every other bench uses Switch Debugger's relays.
BENCH_POWER = {"Bench 1": USB_RELAY, "Bench 4": USB_RELAY}


def power_of(bench: str) -> str:
    return BENCH_POWER.get(bench, SWITCH_DEBUGGER)


def relay_name(power_via: str, relay: int) -> str:
    return f"USB relay {relay}" if power_via == USB_RELAY else f"relay {relay}"


def polarity_text(bench: str) -> str:
    if power_of(bench) == USB_RELAY:
        return "USB relay on = power on"
    return "Relay off = power on"
DEFAULT_BENCH = "Bench 2"
DEFAULT_ECU = 1


def ecus_of(bench: str) -> dict[int, tuple[str, int]]:
    return BENCHES.get(bench, BENCHES[DEFAULT_BENCH])


def ecu_label(ecu: int, bench: str = DEFAULT_BENCH) -> str:
    port, relay = ecus_of(bench)[ecu]
    return f"ECU {ecu} (CH-{port}, {relay_name(power_of(bench), relay)})"


def bench_label(bench: str) -> str:
    """The Bench combo's item text: the bench and how its ECUs are wired."""
    via = power_of(bench)
    wiring = ", ".join(f"ECU {ecu}: CH-{port} + {relay_name(via, relay)}"
                       for ecu, (port, relay) in sorted(BENCHES[bench].items()))
    return f"{bench} ({wiring})"


@dataclass(frozen=True)
class BenchConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    jtag_port: str = "D"  # A-F
    power_relay: int = 2  # 1-6, as labelled on the box
    off_s: int = OFF_S  # power off this long during a power cycle
    boot_s: int = BOOT_S  # wait this long after power on
    power_via: str = SWITCH_DEBUGGER  # or USB_RELAY (benches 1 and 4)

    @classmethod
    def for_ecu(cls, ecu: int, bench: str = DEFAULT_BENCH) -> "BenchConfig":
        if bench not in BENCHES:
            raise BenchSwitchError(f"Unknown bench {bench!r}.", hint="Choose the bench in the Setting tab.")
        if ecu not in BENCHES[bench]:
            raise BenchSwitchError(f"Unknown ECU {ecu}.", hint="Choose the ECU in the Setting tab.")
        jtag_port, relay = BENCHES[bench][ecu]
        return cls(DEFAULT_HOST, DEFAULT_PORT, jtag_port, relay, power_via=power_of(bench))

    def check(self) -> None:
        if self.jtag_port.upper() not in PORTS or len(self.jtag_port) != 1:
            raise BenchSwitchError(f"Unknown JTAG port {self.jtag_port!r}.", hint="Choose a port from A to F in the Setting tab.")
        if self.power_via == USB_RELAY:
            if self.power_relay not in range(1, 9):
                raise BenchSwitchError(f"Unknown USB relay {self.power_relay}.", hint="Choose the bench in the Setting tab.")
        elif self.power_via != SWITCH_DEBUGGER:
            raise BenchSwitchError(f"Unknown power switch {self.power_via!r}.", hint="Choose the bench in the Setting tab.")
        elif self.power_relay not in RELAYS:
            raise BenchSwitchError(f"Unknown power relay {self.power_relay}.", hint="Choose a relay from 1 to 6 in the Setting tab.")


def command(on: bool, kind: str, index: int) -> str:
    """The protocol line for one port ("Sensor") or relay, by its 0-based index."""
    return f"{PREFIX};{'On' if on else 'Off'};{kind};{index}\n"


def disconnect_all_ports() -> str:
    """The only line that makes the box release a JTAG port. Ports only, never relays."""
    return f"{PREFIX};Off_All;Sensor;_\n"


def send_tcp(host: str, port: int, line: str) -> None:
    """Send one line the way the Switch Debugger expects it; raise BenchSwitchError on failure."""
    try:
        with socket.create_connection((host, port), timeout=CONNECT_TIMEOUT_S) as sock:
            time.sleep(SEND_DELAY_S)
            sock.sendall(line.encode("ascii"))
            time.sleep(SEND_DELAY_S)
    except ConnectionRefusedError as exc:
        raise BenchSwitchError(
            f"Switch Debugger refused the connection at {host}:{port}.",
            hint="Open Switch Debugger and press Start in its TCP/IP box, then try again.",
        ) from exc
    except OSError as exc:
        raise BenchSwitchError(
            f"Could not reach Switch Debugger at {host}:{port}.",
            hint="Check that Switch Debugger's TCP/IP box shows 127.11.0.1, port 1101, and that it is started.",
        ) from exc


class BenchSwitch:
    """Switches one ECU's JTAG port and power relay. `send` and `sleep` are injectable for tests."""

    def __init__(self, config: BenchConfig, send: Callable[[str, int, str], None] | None = None,
                 sleep: Callable[[float], None] = time.sleep, relay_board=None) -> None:
        config.check()
        self.config = config
        self._send = send  # None: the module's send_tcp, looked up at each call (tests patch it)
        self._sleep = sleep
        self._board = relay_board  # USB relay benches: made at first use, so hidapi loads only there

    def _do(self, line: str, what: str) -> None:
        log.info("Switch Debugger: %s", what)
        log.debug("Switch Debugger %s:%s <- %s", self.config.host, self.config.port, line.strip())
        (self._send or send_tcp)(self.config.host, self.config.port, line)

    def jtag(self, connected: bool) -> None:
        port = self.config.jtag_port.upper()
        if connected:
            self._do(command(True, "Sensor", PORTS.index(port)), f"connect JTAG port {port}")
        else:  # Off for one port does nothing on this box: see the module docstring
            self._do(disconnect_all_ports(), "disconnect JTAG (all ports: the box connects one at a time)")

    def power(self, on: bool) -> None:
        relay = self.config.power_relay
        if self.config.power_via == USB_RELAY:
            from wflash.core.usb_relay import UsbRelayBoard

            log.info("USB relay: power %s (relay %d %s)", "ON" if on else "OFF", relay, "on" if on else "off")
            if self._board is None:
                self._board = UsbRelayBoard()
            self._board.set(relay, on)  # relay on = power on; checked by reading the relays back
            return
        # Inverted: the relay On cuts the ECU's power.
        self._do(command(not on, "Relay", relay - 1), f"power {'ON' if on else 'OFF'} (relay {relay} {'Off' if on else 'On'})")

    def power_cycle(self, is_cancelled: Callable[[], bool] = lambda: False) -> None:
        """Power off, wait, power on, wait for the ECU to boot. Power always comes back on."""
        self.power(False)
        try:
            self._wait(self.config.off_s, is_cancelled)
        finally:
            self.power(True)  # never leave the ECU unpowered, not even on cancel
        self._wait(self.config.boot_s, is_cancelled)

    def _wait(self, seconds: float, is_cancelled: Callable[[], bool]) -> None:
        end = seconds
        while end > 0 and not is_cancelled():
            step = min(0.5, end)
            self._sleep(step)
            end -= step
