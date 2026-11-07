"""Logging setup: per-session DEBUG log file, secret redaction, verbose call logging."""
from __future__ import annotations

import datetime
import logging
import os
import re
import sys
from pathlib import Path

LOGGER_NAME = "wflash"
CALLS_LOGGER = "wflash.calls"
LOG_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-7s [%(threadName)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_SECRETS: set[str] = set()
_HEADER_RE = re.compile(r"(PRIVATE-TOKEN['\"]?\s*[:=]\s*['\"]?)([^'\"\s,}]+)", re.IGNORECASE)
_GLPAT_RE = re.compile(r"glpat-[A-Za-z0-9_-]{20,}")
_BEARER_RE = re.compile(r"(bearer\s+)[^\s]+", re.IGNORECASE)
_PRIVATE_TOKEN_RE = re.compile(r"(private_token\s*=\s*)([^&\s\"']+)", re.IGNORECASE)
_file_handler: logging.Handler | None = None


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def register_secret(value: str | None) -> None:
    if value and len(value) >= 4:
        _SECRETS.add(value)


def clear_secrets() -> None:
    _SECRETS.clear()


def redact(text: str) -> str:
    text = _HEADER_RE.sub(r"\1***", text)
    text = _GLPAT_RE.sub("***", text)
    text = _BEARER_RE.sub(r"\1***", text)
    text = _PRIVATE_TOKEN_RE.sub(r"\1***", text)
    for secret in sorted(tuple(_SECRETS), key=len, reverse=True):
        text = text.replace(secret, "***")
    return text


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def default_log_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "WFlash" / "logs"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "WFlash"
    return Path.home() / ".local" / "state" / "wflash" / "logs"


def _prune(log_dir: Path, keep: int) -> None:
    files = sorted(log_dir.glob("wflash_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def close_file_handler() -> None:
    global _file_handler
    if _file_handler is not None:
        logging.getLogger(LOGGER_NAME).removeHandler(_file_handler)
        _file_handler.close()
        _file_handler = None


def set_verbose(enabled: bool) -> None:
    logging.getLogger(CALLS_LOGGER).setLevel(logging.DEBUG if enabled else logging.INFO)


def setup_logging(log_dir: Path | None = None, keep: int = 20, verbose: bool = False) -> Path:
    """Attach a fresh DEBUG file handler to the `wflash` logger and return the log path."""
    global _file_handler
    log_dir = log_dir or default_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    _prune(log_dir, keep - 1)

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = log_dir / f"wflash_{stamp}.log"
    counter = 1
    while path.exists():
        path = log_dir / f"wflash_{stamp}_{counter}.log"
        counter += 1

    close_file_handler()
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(RedactingFormatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(handler)
    _file_handler = handler
    set_verbose(verbose)
    return path
