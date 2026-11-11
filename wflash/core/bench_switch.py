"""Bench power and JTAG through the Switch Debugger box's TCP service (user's bench tool, 2026-11-11).

Protocol, from the user's `switch_debugger.py` and the Switch Debugger window:

    SwitchDebugger6Sensor4Relay;<On|Off>;<Sensor|Relay>;<0-based id>\\n

- A "Sensor" is a JTAG port, A-F = 0-5. On connects the debugger to that port, Off disconnects it.
- A "Relay" is numbered 1-6 on the box and 0-based in the protocol. For the ECU's power relay the
  polarity is inverted: relay **Off = power ON**, relay **On = power OFF** (user's bench: Port D,
  Relay 2; the other relays stay On).

Only the configured port and relay are ever switched. `Off_All` is never sent: "Disconnect All
Relay" would also switch the relays of other ECUs on the same box.

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
DEFAULT_HOST = "127.11.0.1"
DEFAULT_PORT = 1101


@dataclass(frozen=True)
class BenchConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    jtag_port: str = "D"  # A-F
    power_relay: int = 2  # 1-6, as labelled on the box
    off_s: int = 3  # power off this long during a power cycle
    boot_s: int = 5  # wait this long after power on

    def check(self) -> None:
        if self.jtag_port.upper() not in PORTS or len(self.jtag_port) != 1:
            raise BenchSwitchError(f"Unknown JTAG port {self.jtag_port!r}.", hint="Choose a port from A to F in the Setting tab.")
        if self.power_relay not in RELAYS:
            raise BenchSwitchError(f"Unknown power relay {self.power_relay}.", hint="Choose a relay from 1 to 6 in the Setting tab.")


def command(on: bool, kind: str, index: int) -> str:
    """The protocol line for one port ("Sensor") or relay, by its 0-based index."""
    return f"{PREFIX};{'On' if on else 'Off'};{kind};{index}\n"


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
            hint="Check the Switch Debugger IP and port in the Setting tab.",
        ) from exc


class BenchSwitch:
    """Switches one ECU's JTAG port and power relay. `send` and `sleep` are injectable for tests."""

    def __init__(self, config: BenchConfig, send: Callable[[str, int, str], None] = send_tcp,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        config.check()
        self.config = config
        self._send = send
        self._sleep = sleep

    def _do(self, line: str, what: str) -> None:
        log.info("Switch Debugger: %s", what)
        log.debug("Switch Debugger %s:%s <- %s", self.config.host, self.config.port, line.strip())
        self._send(self.config.host, self.config.port, line)

    def jtag(self, connected: bool) -> None:
        port = self.config.jtag_port.upper()
        self._do(command(connected, "Sensor", PORTS.index(port)),
                 f"{'connect' if connected else 'disconnect'} JTAG port {port}")

    def power(self, on: bool) -> None:
        relay = self.config.power_relay
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
