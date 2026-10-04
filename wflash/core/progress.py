"""ETA / speed estimate for the flash header (pure Python, no Qt).

winIDEA only reports a percentage, so the speed shown is an *estimate*: the byte total is
the on-disk size of the mapped program files (`.s3` is S-record text, roughly twice the
size of the binary that actually reaches the flash). It is still useful to see that the
download moves and roughly how long it will take — the same trade-off SFlash makes.

Time is always passed in (`now`, e.g. `time.monotonic()`), so the arithmetic is tested
with fake clocks.
"""
from __future__ import annotations

IDLE_TEXT = "ETA: -- | Speed: --"
CALCULATING_TEXT = "ETA: calculating… | Speed: --"


def format_mmss(seconds: float) -> str:
    """`75.4` -> `"01:15"`; minutes are not capped at 59 (`3725` -> `"62:05"`)."""
    total = max(0, int(round(seconds)))
    return f"{total // 60:02d}:{total % 60:02d}"


class ProgressEstimator:
    """One flash: `started_at` is when Flash was pressed, `start()` when DOWNLOAD began."""

    def __init__(self, started_at: float) -> None:
        self.started_at = started_at
        self.total_bytes = 0
        self.transfer_started_at: float | None = None
        self.percent: int | None = None
        self.eta_s: float | None = None
        self.speed_kbps: float | None = None

    @property
    def transferring(self) -> bool:
        return self.transfer_started_at is not None

    def start(self, total_bytes: int, now: float) -> None:
        self.total_bytes = max(0, int(total_bytes))
        self.transfer_started_at = now
        self.percent = None
        self.eta_s = None
        self.speed_kbps = None

    def update(self, percent: int | None, now: float) -> None:
        """`None` means "busy, amount unknown": the previous ETA/speed stay as they were."""
        if percent is None or self.transfer_started_at is None:
            return
        p = max(0, min(100, int(percent)))
        self.percent = p
        elapsed = now - self.transfer_started_at
        if p <= 0 or elapsed <= 0:
            return
        self.eta_s = elapsed * (100 - p) / p
        if self.total_bytes > 0:
            self.speed_kbps = self.total_bytes * p / 100 / 1024 / elapsed

    def elapsed(self, now: float) -> float:
        return max(0.0, now - self.started_at)

    def running_text(self) -> str:
        if not self.percent or self.eta_s is None:
            return CALCULATING_TEXT
        speed = f"{self.speed_kbps:.1f} KB/s" if self.speed_kbps is not None else "--"
        return f"{self.percent}% | ETA: {format_mmss(self.eta_s)} | Speed: {speed}"

    def done_text(self, now: float) -> str:
        speed = f"{self.speed_kbps:.1f} KB/s" if self.speed_kbps is not None else "--"
        return f"100% | Time: {format_mmss(self.elapsed(now))} | Speed: {speed}"

    def failed_text(self, now: float) -> str:
        return f"Failed | Time: {format_mmss(self.elapsed(now))} | Speed: --"

    def cancelled_text(self, now: float) -> str:
        return f"Cancelled | Time: {format_mmss(self.elapsed(now))}"
