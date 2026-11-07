"""Log panel mixin: coloured, filterable view of the `wflash` log, Copy/Clear, debug bundle export.

Host contract (provided by MainWindow): `self.ui` (Ui_MainWindow), `self.ctx` (DebugContext),
`self.log_file` (Path | None), `self.flash_active()` (FlashMixin), `self.statusBar()`.
"""
from __future__ import annotations

import logging
from collections import deque
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QFontDatabase, QGuiApplication, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QFileDialog, QMessageBox

from wflash.core.debug_bundle import create_debug_bundle
from wflash.core.logging_setup import LOGGER_NAME, RedactingFormatter, get_logger, redact
from wflash.gui.theme import current_theme

log = get_logger("ui.log")

PANEL_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
MAX_RECORDS = 20000
# Theme token per level; INFO uses the widget's normal text colour.
LEVEL_TOKENS = {
    logging.DEBUG: "log_debug",
    logging.WARNING: "log_warn",
    logging.ERROR: "log_error",
    logging.CRITICAL: "log_error",
}


def level_color(level: int) -> str | None:
    token = LEVEL_TOKENS.get(level)
    return current_theme()[token] if token else None


class LogEmitter(QObject):
    """Carries formatted records to the GUI thread. Created on the main thread."""

    record = Signal(int, str)


class QtLogHandler(logging.Handler):
    """logging.Handler usable from any thread: it only emits a queued Qt signal."""

    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.emitter = LogEmitter()
        self.setFormatter(RedactingFormatter(PANEL_FORMAT, "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            text = self.format(record)
        except Exception:
            self.handleError(record)
            return
        self.emitter.record.emit(record.levelno, text)


class LogPanelMixin:
    def _init_log_panel(self) -> None:
        self._log_records: deque[tuple[int, str]] = deque(maxlen=MAX_RECORDS)
        # The system fixed-pitch font differs per OS; Designer cannot express "system font".
        self.ui.plainTextEdit_log.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.log_handler = QtLogHandler()
        # Bound method of this QMainWindow: queued onto the GUI thread (threading rule 8).
        self.log_handler.emitter.record.connect(self._append_log_record)
        logger = logging.getLogger(LOGGER_NAME)
        if logger.level == logging.NOTSET:
            logger.setLevel(logging.DEBUG)  # main() does this via setup_logging; tests may not
        logger.addHandler(self.log_handler)
        self.ui.comboBox_logLevel.currentIndexChanged.connect(self._refilter_log)
        self.ui.pushButton_copyLog.clicked.connect(self.copy_log)
        self.ui.pushButton_clearLog.clicked.connect(self.clear_log)
        self.ui.pushButton_exportBundle.clicked.connect(self._on_export_bundle_clicked)

    def _detach_log_panel(self) -> None:
        logging.getLogger(LOGGER_NAME).removeHandler(self.log_handler)

    # -- view -----------------------------------------------------------------------
    def log_min_level(self) -> int:
        return logging.getLevelNamesMapping()[self.ui.comboBox_logLevel.currentText()]

    def _append_log_record(self, level: int, text: str) -> None:
        self._log_records.append((level, text))
        if level >= self.log_min_level():
            self._write_log_line(level, text)
        if level >= logging.ERROR:
            self.statusBar().showMessage("Error — see the log panel", 10000)

    def _write_log_line(self, level: int, text: str) -> None:
        view = self.ui.plainTextEdit_log
        cursor = view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if not view.document().isEmpty():
            cursor.insertBlock()
        fmt = QTextCharFormat()
        color = level_color(level)
        if color:
            fmt.setForeground(QColor(color))
        cursor.insertText(text, fmt)
        view.setTextCursor(cursor)
        view.ensureCursorVisible()  # keeps the newest line, and so the newest error, in view

    def refresh_log_theme(self) -> None:
        """Repaint every visible line with the current theme's level colours."""
        self._refilter_log()

    def _refilter_log(self, *_args) -> None:
        self.ui.plainTextEdit_log.clear()
        minimum = self.log_min_level()
        for level, text in self._log_records:
            if level >= minimum:
                self._write_log_line(level, text)

    def log_visible_text(self) -> str:
        return self.ui.plainTextEdit_log.toPlainText()

    def copy_log(self) -> None:
        QGuiApplication.clipboard().setText(self.log_visible_text())

    def clear_log(self) -> None:
        self._log_records.clear()
        self.ui.plainTextEdit_log.clear()

    # -- debug bundle ---------------------------------------------------------------
    def export_bundle(self, dest_dir: Path) -> Path:
        # DebugContext is written by the flash worker; it is only read when no flash runs.
        if self.flash_active():
            raise RuntimeError("Cannot export a debug bundle while a flash is running")
        path = create_debug_bundle(self.ctx, dest_dir, self.log_file)
        log.info("Debug bundle saved: %s", path)
        return path

    def _on_export_bundle_clicked(self) -> None:
        if self.flash_active():
            return
        desktop = Path.home() / "Desktop"
        start = desktop if desktop.is_dir() else Path.home()
        directory = QFileDialog.getExistingDirectory(self, "Save debug bundle to", str(start))
        if not directory:
            return
        try:
            path = self.export_bundle(Path(directory))
        except OSError as exc:
            log.error("Cannot write debug bundle: %s", exc)
            QMessageBox.critical(self, "WFlash", f"Cannot write the debug bundle:\n{redact(str(exc))}")
            return
        QMessageBox.information(self, "Debug bundle", f"Saved:\n{path}\n\nSend this file for debugging.")
