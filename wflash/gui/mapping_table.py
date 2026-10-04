"""Mapping table mixin: which artifact file goes to which winIDEA entry.

A row whose pattern matched zero or several files is red and has no file selected; the
user must choose one (spec §5). Nothing here ever picks a file on the user's behalf.

Host contract: `self.ui`, `self.profile` (Profile | None), `self._update_flash_controls()`.
The rows are dynamic content, so they are built here; the table, its columns and its
header live in main_window.ui.
"""
from __future__ import annotations

from functools import partial
from pathlib import Path

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QComboBox, QHeaderView, QTableWidgetItem

from wflash.core.file_matcher import MappingRow, build_mapping, candidates_for_kind
from wflash.core.logging_setup import get_logger

log = get_logger("ui.mapping")

FILE_COLUMN = 3
NONE_TEXT = "-- select file --"
MISSING_STYLE = "QComboBox { background-color: #ffcdd2; color: black; }"


class MappingTableMixin:
    def _init_mapping_table(self) -> None:
        self._mapping_rows: list[MappingRow] = []
        self.artifact_root: Path | None = None
        header = self.ui.tableWidget_mapping.horizontalHeader()
        header.setSectionResizeMode(FILE_COLUMN, QHeaderView.ResizeMode.Stretch)

    def on_artifact_ready(self, path: Path, label: str) -> None:
        """Build the mapping for a freshly downloaded (or cached) artifact."""
        if self.profile is None:
            return
        rows = build_mapping(self.profile, path)
        self.set_mapping_rows(rows, path)
        self.ui.label_artifact.setText(f"{label}\n{path}")
        for row in rows:
            if row.ok:
                log.info("%s '%s' -> %s", row.kind, row.target, row.selected.relative_to(path).as_posix())
            else:
                log.warning(
                    "%s '%s': %d file(s) match '%s'; choose a file manually",
                    row.kind, row.target, len(row.candidates), row.pattern,
                )

    def set_mapping_rows(self, rows: list[MappingRow], root: Path) -> None:
        table = self.ui.tableWidget_mapping
        self._mapping_rows = rows
        self.artifact_root = root
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            kind_text = "Program (.s3)" if row.kind == "program" else "Symbols (.elf)"
            for column, text in enumerate((kind_text, row.target, row.pattern)):
                table.setItem(index, column, QTableWidgetItem(text))
            combo = QComboBox()
            combo.installEventFilter(self)  # swallow wheel events, see eventFilter
            combo.addItem(NONE_TEXT, None)
            options = row.candidates or candidates_for_kind(root, row.kind)
            for option in options:
                combo.addItem(option.relative_to(root).as_posix(), str(option))
            if row.selected is not None:
                combo.setCurrentIndex(options.index(row.selected) + 1)
            # GUI-thread signal from a GUI-thread widget: a partial is safe here. The
            # lambda/partial ban (threading rule 8) is about signals emitted from pool threads.
            combo.currentIndexChanged.connect(partial(self._on_mapping_choice, index))
            table.setCellWidget(index, FILE_COLUMN, combo)
            self._paint_mapping_row(index)
        table.resizeColumnsToContents()
        self._update_flash_controls()

    def eventFilter(self, watched, event) -> bool:
        # Scrolling the table must never silently change which file gets flashed.
        if event.type() == QEvent.Type.Wheel and isinstance(watched, QComboBox):
            return True
        return super().eventFilter(watched, event)

    def clear_mapping(self) -> None:
        self._mapping_rows = []
        self.artifact_root = None
        self.ui.tableWidget_mapping.setRowCount(0)
        self.ui.label_artifact.setText("No artifact loaded")
        self._update_flash_controls()

    def mapping_combo(self, index: int) -> QComboBox:
        return self.ui.tableWidget_mapping.cellWidget(index, FILE_COLUMN)

    def _on_mapping_choice(self, index: int, _combo_index: int) -> None:
        data = self.mapping_combo(index).currentData()
        self._mapping_rows[index].selected = Path(data) if data else None
        self._paint_mapping_row(index)
        self._update_flash_controls()

    def _paint_mapping_row(self, index: int) -> None:
        self.mapping_combo(index).setStyleSheet("" if self._mapping_rows[index].ok else MISSING_STYLE)

    def mapping_rows(self) -> list[MappingRow]:
        return list(self._mapping_rows)

    def mapping_complete(self) -> bool:
        return bool(self._mapping_rows) and all(row.ok for row in self._mapping_rows)
