"""Cooperative cancellation shared between GUI and worker threads."""
from __future__ import annotations

import threading

from wflash.core.errors import CancelledError


class CancelToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise CancelledError("Operation cancelled by user")

    def wait(self, timeout: float) -> bool:
        """Sleep up to `timeout` seconds; return True as soon as cancelled."""
        return self._event.wait(timeout)
