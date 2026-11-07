"""Mapping table mixin: which firmware file goes to which winIDEA entry, plus the source card.

A profile may declare several sources (one artifact each). Each then gets a row with its own
Load button, built here because the rows depend on the profile; a row of the table only ever
sees the files of its own source, and Flash waits for every source.

A row whose pattern matched zero or several files is red and has no file selected; the
user must choose one (spec §5). Nothing here ever picks a file on the user's behalf.

Host contract: `self.ui`, `self.profile` (Profile | None), `self.ctx` (DebugContext),
`self._closing`, `self._update_flash_controls()`. The rows are dynamic content, so they
are built here; the table, its columns, the source card and the hint live in main_window.ui.
"""
from __future__ import annotations

from functools import partial
from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QFontDatabase
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidgetItem

from wflash.core.file_matcher import (
    MappingRow,
    build_mapping,
    build_mapping_for_source,
    candidates_for_kind,
    pending_rows,
)
from wflash.core.firmware_source import FirmwareSource
from wflash.core.logging_setup import get_logger
from wflash.gui.theme import current_theme

log = get_logger("ui.mapping")

NUMBER_COLUMN, TYPE_COLUMN, TARGET_COLUMN, PATTERN_COLUMN, FILE_COLUMN = range(5)
NONE_TEXT = "-- select file --"
NO_FIRMWARE_TITLE = "No firmware loaded — use Load from GitLab…"
HINT_NO_FIRMWARE = "Load firmware to fill the mapping."
HINT_INCOMPLETE = "Red rows need a file before Flash is enabled."
HINT_COMPLETE = "All rows mapped — Flash enabled."
SOURCE_NOT_LOADED = "Not loaded"
SHORT_COMMIT = 8


def missing_style() -> str:
    """Stylesheet of a row combo that still needs a file, in the current theme's colours."""
    t = current_theme()
    return (
        f"QComboBox {{ background-color: {t['missing_bg']}; border: 1px solid {t['missing_border']}; "
        f"color: {t['text']}; }}"
    )


class MappingTableMixin:
    def _init_mapping_table(self) -> None:
        self._mapping_rows: list[MappingRow] = []
        self.artifact_root: Path | None = None
        self.firmware_source: FirmwareSource | None = None
        self._loading_source: str | None = None  # which source the open Load dialog is filling
        self._source_rows: dict[str, list[MappingRow]] = {}
        self._source_loaded: dict[str, FirmwareSource] = {}
        self._source_widgets: dict[str, tuple[QPushButton, QLabel]] = {}
        header = self.ui.tableWidget_mapping.horizontalHeader()
        for column in (NUMBER_COLUMN, TYPE_COLUMN, TARGET_COLUMN, PATTERN_COLUMN):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(FILE_COLUMN, QHeaderView.ResizeMode.Stretch)
        self._show_firmware_source(None, None)
        self._update_mapping_hint()

    def on_firmware_ready(self, path: Path, source: FirmwareSource) -> None:
        """Build the mapping for freshly downloaded (or cached) firmware from Load from GitLab."""
        if self.profile is None or self._closing:
            return
        if self.profile.sources:
            self._on_source_ready(path, source)
            return
        rows = build_mapping(self.profile, path)
        self.firmware_source = source
        self.ctx.source = source.to_dict()  # no flash runs while firmware is being loaded
        self._show_firmware_source(source, path)
        self.set_mapping_rows(rows, path)
        log.info("Firmware loaded: %s (%s) from %s", source.title, source.cache_note, path)
        self._log_rows(rows, path)

    def _log_rows(self, rows: list[MappingRow], path: Path) -> None:
        for row in rows:
            if row.ok:
                log.info("%s '%s' -> %s", row.kind, row.target, row.selected.relative_to(path).as_posix())
            else:
                log.warning(
                    "%s '%s': %d file(s) match '%s'; choose a file manually",
                    row.kind, row.target, len(row.candidates), row.pattern,
                )

    # -- several sources ----------------------------------------------------------------
    def rebuild_source_slots(self) -> None:
        """One row per source of the current profile; nothing is loaded in a fresh row."""
        layout = self.ui.verticalLayout_sourceSlots
        while layout.count():
            row = layout.takeAt(0).layout()
            while row is not None and row.count():
                widget = row.takeAt(0).widget()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()
        self._source_widgets = {}
        self._source_rows = {}
        self._source_loaded = {}
        sources = self.profile.sources if self.profile is not None else {}
        for widget in (
            self.ui.pushButton_loadFromGitlab,
            self.ui.label_sourceTitle,
            self.ui.label_sourceDetail,
            self.ui.label_sourceCache,
        ):
            widget.setVisible(not sources)
        for source_id, spec in sources.items():
            head = QHBoxLayout()
            head.addWidget(QLabel(spec.label))
            button = QPushButton("Load from GitLab…")
            # GUI-thread signal from a GUI-thread widget: a partial is safe here (threading rule 8).
            button.clicked.connect(partial(self._on_source_load_clicked, source_id))
            head.addWidget(button)
            layout.addLayout(head)
            summary_row = QHBoxLayout()
            summary = QLabel(SOURCE_NOT_LOADED)
            summary.setWordWrap(True)
            summary_row.addWidget(summary)
            layout.addLayout(summary_row)
            self._source_widgets[source_id] = (button, summary)
        self.ui.label_commitWarning.setVisible(False)

    def source_load_button(self, source_id: str) -> QPushButton:
        return self._source_widgets[source_id][0]

    def source_load_buttons(self) -> list[QPushButton]:
        return [button for button, _summary in self._source_widgets.values()]

    def source_summary(self, source_id: str) -> QLabel:
        return self._source_widgets[source_id][1]

    def _on_source_load_clicked(self, source_id: str, *_args) -> None:
        self.open_gitlab_dialog_for(source_id)

    def _on_source_ready(self, path: Path, source: FirmwareSource) -> None:
        source_id = self._loading_source
        if source_id not in self._source_widgets:
            log.error("Firmware arrived for no known source: %s", source.title)
            return
        rows = build_mapping_for_source(self.profile, source_id, path)
        self._source_rows[source_id] = rows
        self._source_loaded[source_id] = source
        self.ctx.source = {key: loaded.to_dict() for key, loaded in self._source_loaded.items()}
        commit = f" · commit {source.commit[:SHORT_COMMIT]}" if source.commit else ""
        summary = self.source_summary(source_id)
        summary.setText(f"{source.title}{commit} · {source.cache_note}")
        summary.setToolTip(str(path))
        log.info("Source '%s' loaded: %s (%s) from %s", source_id, source.title, source.cache_note, path)
        self._log_rows(rows, path)
        loaded = {(row.kind, row.target): row for group in self._source_rows.values() for row in group}
        merged = [loaded.get((row.kind, row.target), row) for row in pending_rows(self.profile)]
        self.set_mapping_rows(merged, None)
        self._update_commit_warning()

    def _update_commit_warning(self) -> None:
        commits = {key: src.commit for key, src in self._source_loaded.items() if src.commit}
        different = len(set(commits.values())) > 1
        self.ui.label_commitWarning.setVisible(different)
        if not different:
            self.ui.label_commitWarning.clear()
            return
        names = ", ".join(
            f"{self.profile.sources[key].label}: {commit[:SHORT_COMMIT]}" for key, commit in commits.items()
        )
        text = f"These files come from different commits ({names}). Symbols may not match the flashed firmware."
        self.ui.label_commitWarning.setText(text)
        log.warning("%s", text)

    def _show_firmware_source(self, source: FirmwareSource | None, path: Path | None) -> None:
        if source is None:
            self.ui.label_sourceTitle.setText(NO_FIRMWARE_TITLE)
            self.ui.label_sourceDetail.setText("")
            self.ui.label_sourceCache.setText("")
            self.ui.frame_sourceCard.setToolTip("")
            return
        self.ui.label_sourceTitle.setText(source.title)
        self.ui.label_sourceDetail.setText(source.detail)
        self.ui.label_sourceCache.setText(source.cache_note)
        self.ui.frame_sourceCard.setToolTip(str(path) if path else "")

    def set_mapping_rows(self, rows: list[MappingRow], root: Path | None) -> None:
        table = self.ui.tableWidget_mapping
        fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self._mapping_rows = rows
        self.artifact_root = root
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            number = QTableWidgetItem(str(index + 1))
            number.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(index, NUMBER_COLUMN, number)
            kind_text = "Program" if row.kind == "program" else "Symbols"
            table.setItem(index, TYPE_COLUMN, QTableWidgetItem(kind_text))
            table.setItem(index, TARGET_COLUMN, QTableWidgetItem(row.target))
            pattern = QTableWidgetItem(row.pattern)
            pattern.setFont(fixed)
            table.setItem(index, PATTERN_COLUMN, pattern)
            combo = QComboBox()
            combo.installEventFilter(self)  # swallow wheel events, see eventFilter
            combo.addItem(NONE_TEXT, None)
            base = row.root or root
            options = row.candidates or (candidates_for_kind(base, row.kind) if base is not None else [])
            for option in options:
                combo.addItem(option.relative_to(base).as_posix(), str(option))
            if row.selected is not None:
                combo.setCurrentIndex(options.index(row.selected) + 1)
            # GUI-thread signal from a GUI-thread widget: a partial is safe here. The
            # lambda/partial ban (threading rule 8) is about signals emitted from pool threads.
            combo.currentIndexChanged.connect(partial(self._on_mapping_choice, index))
            table.setCellWidget(index, FILE_COLUMN, combo)
            self._paint_mapping_row(index)
        self._update_mapping_hint()
        self._update_flash_controls()

    def eventFilter(self, watched, event) -> bool:
        # Scrolling the table must never silently change which file gets flashed.
        if event.type() == QEvent.Type.Wheel and isinstance(watched, QComboBox):
            return True
        return super().eventFilter(watched, event)

    def clear_mapping(self) -> None:
        self._mapping_rows = []
        self.artifact_root = None
        self.firmware_source = None
        self.ctx.source = {}
        self.rebuild_source_slots()
        self.ui.tableWidget_mapping.setRowCount(0)
        self._show_firmware_source(None, None)
        self._update_mapping_hint()
        self._update_flash_controls()

    def mapping_combo(self, index: int) -> QComboBox:
        return self.ui.tableWidget_mapping.cellWidget(index, FILE_COLUMN)

    def _on_mapping_choice(self, index: int, _combo_index: int) -> None:
        data = self.mapping_combo(index).currentData()
        self._mapping_rows[index].selected = Path(data) if data else None
        self._paint_mapping_row(index)
        self._update_mapping_hint()
        self._update_flash_controls()

    def _paint_mapping_row(self, index: int) -> None:
        ok = self._mapping_rows[index].ok
        combo = self.mapping_combo(index)
        combo.setProperty("missing", not ok)
        combo.setStyleSheet("" if ok else missing_style())
        number = self.ui.tableWidget_mapping.item(index, NUMBER_COLUMN)
        if number is not None:
            number.setBackground(QColor(current_theme()["soft"]))

    def refresh_mapping_theme(self) -> None:
        """Repaint the dynamic row colours after the theme changed."""
        for index in range(len(self._mapping_rows)):
            self._paint_mapping_row(index)

    def _update_mapping_hint(self) -> None:
        if not self._mapping_rows:
            text = HINT_NO_FIRMWARE
        elif self.mapping_complete():
            text = HINT_COMPLETE
        else:
            text = HINT_INCOMPLETE
        self.ui.label_mappingHint.setText(text)

    def mapping_rows(self) -> list[MappingRow]:
        return list(self._mapping_rows)

    def mapping_complete(self) -> bool:
        return bool(self._mapping_rows) and all(row.ok for row in self._mapping_rows)
