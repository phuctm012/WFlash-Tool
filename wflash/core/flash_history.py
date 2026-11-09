"""One CSV line per press of Flash (spec 2026-11-09, 4.10). Not shown in WFlash itself.

The file opens in Excel (UTF-8 with BOM) from File > Open flash history, and the debug
bundle carries it. Every value goes through `redact`; a failure to write only logs.
"""
from __future__ import annotations

import csv
import io
import os
import sys
from pathlib import Path

from wflash.core.logging_setup import get_logger, redact
from wflash.core.settings import config_dir

log = get_logger("history")

HISTORY_COLUMNS = (
    "time", "profile", "winidea", "app", "app_mode", "bm", "bm_mode", "fbl", "fbl_mode",
    "cal", "advanced_debug", "resets", "tries", "program_s", "verify", "result", "error",
)
KEEP_ROWS = 5000


def history_path() -> Path:
    override = os.environ.get("WFLASH_HISTORY_FILE")  # tests and the stress test keep the real file clean
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "WFlash"
    else:
        base = config_dir()
    return base / "flash_history.csv"


def _read_rows(path: Path) -> list[list[str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    return rows[1:] if rows and rows[0] == list(HISTORY_COLUMNS) else rows


def append_flash(row: dict[str, object], path: Path | None = None, keep: int = KEEP_ROWS) -> None:
    """Add one flash; keeps the newest `keep` lines. Never raises: history must not break a flash."""
    path = path or history_path()
    try:
        values = [redact(str(row.get(column, "") or "")) for column in HISTORY_COLUMNS]
        rows = (_read_rows(path) + [values])[-keep:]
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\r\n")
        writer.writerow(HISTORY_COLUMNS)
        writer.writerows(rows)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")
        tmp.replace(path)
    except (OSError, csv.Error, UnicodeError) as exc:
        log.warning("Cannot write the flash history %s: %s", path, exc)
