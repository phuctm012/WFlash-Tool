"""WFlash entry point: parse args, set up logging and crash hooks, start the GUI."""
from __future__ import annotations

import argparse
import sys
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from wflash import __version__
from wflash.core.errors import WFlashError
from wflash.core.logging_setup import get_logger, redact, setup_logging
from wflash.core.settings import AppSettings
from wflash.core.winidea_adapter import create_adapter

SMOKE_CLOSE_MS = 1500


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="wflash", description="Flash ECU via winIDEA from GitLab artifacts")
    parser.add_argument(
        "--adapter",
        choices=["real", "fake"],
        default="real" if sys.platform == "win32" else "fake",
        help="winIDEA adapter (default: real on Windows, fake elsewhere)",
    )
    parser.add_argument("--verbose", action="store_true", help="Log every winIDEA call")
    parser.add_argument("--smoke", action="store_true", help="Start, then close the window after 1.5 s (launch check)")
    return parser.parse_args(argv)


def install_excepthooks() -> None:
    log = get_logger("crash")

    def excepthook(exc_type, exc, tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log.critical("Unhandled exception", exc_info=(exc_type, exc, tb))
        # A dialog only from the GUI thread; anywhere else the log entry is the report.
        if QApplication.instance() is not None and threading.current_thread() is threading.main_thread():
            QMessageBox.critical(
                None,
                "WFlash crashed",
                redact(f"{exc_type.__name__}: {exc}") + "\n\nDetails are in the log. Use 'Export debug bundle…' to send them.",
            )

    def thread_excepthook(args: threading.ExceptHookArgs) -> None:
        name = args.thread.name if args.thread is not None else "?"
        log.critical(
            "Unhandled exception in thread %s", name, exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
        )

    sys.excepthook = excepthook
    threading.excepthook = thread_excepthook


def init_logging(verbose: bool) -> tuple[Path | None, Path | None]:
    """Set up file logging. Returns (log_file, fallback_dir); fallback_dir is set when the default dir failed."""
    try:
        return setup_logging(verbose=verbose), None
    except OSError:
        pass
    fallback = Path(tempfile.gettempdir()) / "WFlash" / "logs"
    try:
        return setup_logging(fallback, verbose=verbose), fallback
    except OSError:
        return None, fallback


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = AppSettings.load()
    log_file, fallback_dir = init_logging(args.verbose or settings.verbose)
    log = get_logger("main")
    log.info("WFlash %s starting (adapter=%s, log=%s)", __version__, args.adapter, log_file)
    install_excepthooks()
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("WFlash")
    if fallback_dir is not None:
        where = f"Logs are written to {fallback_dir}." if log_file else "File logging is disabled."
        log.warning("Default log directory is not writable. %s", where)
        QMessageBox.warning(None, "WFlash", f"The default log directory is not writable.\n{where}")

    try:
        adapter = create_adapter(args.adapter)
    except WFlashError as exc:
        log.error("%s", exc)
        QMessageBox.critical(None, "WFlash", f"{exc}\n\n{exc.hint}")
        return 1

    from wflash.gui.main_window import MainWindow

    window = MainWindow(settings, adapter, log_file=log_file)
    window.show()
    if args.smoke:
        # close(), not app.quit(): the normal shutdown path (closeEvent) must run.
        QTimer.singleShot(SMOKE_CLOSE_MS, window.close)
    code = app.exec()
    log.info("WFlash exiting (code %s)", code)
    return code
