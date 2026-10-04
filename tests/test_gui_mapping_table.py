import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent

from tests.gui_stubs import EXAMPLE_PROFILE, SOURCE, HostWindow, make_artifact_tree
from wflash.core.profile import load_profile
from wflash.gui.mapping_table import (
    HINT_COMPLETE,
    HINT_INCOMPLETE,
    HINT_NO_FIRMWARE,
    NO_FIRMWARE_TITLE,
    MappingTableMixin,
    missing_style,
)
from wflash.gui.theme import THEMES, set_theme_name

pytestmark = pytest.mark.gui


class MappingHost(MappingTableMixin, HostWindow):
    def __init__(self, tmp):
        super().__init__(tmp)
        self.profile = load_profile(EXAMPLE_PROFILE)
        self._init_mapping_table()


@pytest.fixture
def host(qtbot, tmp_path):
    window = MappingHost(tmp_path)
    qtbot.addWidget(window)
    yield window
    set_theme_name("light")


def test_gui_starts_with_the_empty_source_card_and_hint(host):
    assert host.ui.label_sourceTitle.text() == NO_FIRMWARE_TITLE
    assert host.ui.label_sourceDetail.text() == "" and host.ui.label_sourceCache.text() == ""
    assert host.ui.label_mappingHint.text() == HINT_NO_FIRMWARE


def test_gui_unique_matches_are_selected_and_the_card_filled(host, tmp_path):
    root = make_artifact_tree(tmp_path / "art")
    host.on_firmware_ready(root, SOURCE)
    table = host.ui.tableWidget_mapping
    assert table.rowCount() == 3
    assert host.mapping_complete()
    assert [table.item(0, c).text() for c in range(4)] == ["1", "Program", "App", "**/*App*.s3"]
    assert [table.item(2, c).text() for c in range(3)] == ["3", "Symbols", "CM7_1"]
    assert host.mapping_combo(0).currentText() == "out/App.s3"
    assert host.mapping_combo(0).styleSheet() == ""
    assert host.ui.label_sourceTitle.text() == SOURCE.title
    assert host.ui.label_sourceDetail.text() == SOURCE.detail
    assert host.ui.label_sourceCache.text() == SOURCE.cache_note
    assert host.ui.frame_sourceCard.toolTip() == str(root)
    assert host.ui.label_mappingHint.text() == HINT_COMPLETE
    assert host.ctx.source == SOURCE.to_dict()
    assert host.flash_control_updates >= 1


def test_gui_ambiguous_and_missing_rows_need_a_manual_choice(host, tmp_path):
    root = make_artifact_tree(
        tmp_path / "art", {"a/App.s3": b"1", "b/App.s3": b"2", "x_cm7_0.elf": b"3", "other.elf": b"4"}
    )
    host.on_firmware_ready(root, SOURCE)
    assert not host.mapping_complete()
    assert host.ui.label_mappingHint.text() == HINT_INCOMPLETE
    program, cm7_1 = host.mapping_combo(0), host.mapping_combo(2)
    assert program.count() == 3  # "-- select file --" + the two candidates
    assert program.styleSheet() == missing_style() and program.property("missing") is True
    assert cm7_1.count() == 3  # "-- select file --" + every .elf in the artifact
    updates = host.flash_control_updates
    program.setCurrentIndex(program.findText("b/App.s3"))
    assert host.flash_control_updates == updates + 1
    assert not host.mapping_complete()
    cm7_1.setCurrentIndex(cm7_1.findText("other.elf"))
    assert host.mapping_complete()
    assert host.ui.label_mappingHint.text() == HINT_COMPLETE
    assert host.mapping_rows()[0].selected == root / "b" / "App.s3"
    assert host.mapping_rows()[2].selected == root / "other.elf"
    assert program.styleSheet() == "" and program.property("missing") is False
    program.setCurrentIndex(0)
    assert not host.mapping_complete()
    assert program.styleSheet() == missing_style()


def test_gui_red_rows_follow_the_theme(host, tmp_path):
    host.on_firmware_ready(make_artifact_tree(tmp_path / "art", {"x_cm7_0.elf": b"3"}), SOURCE)
    program = host.mapping_combo(0)
    assert THEMES["light"]["missing_bg"] in program.styleSheet()
    set_theme_name("dark")
    host.refresh_mapping_theme()
    assert THEMES["dark"]["missing_bg"] in program.styleSheet()
    number = host.ui.tableWidget_mapping.item(0, 0)
    assert number.background().color().name() == THEMES["dark"]["soft"]


def test_gui_clear_mapping(host, tmp_path):
    host.on_firmware_ready(make_artifact_tree(tmp_path / "art"), SOURCE)
    host.clear_mapping()
    assert host.ui.tableWidget_mapping.rowCount() == 0
    assert not host.mapping_complete()
    assert host.artifact_root is None and host.firmware_source is None
    assert host.ui.label_sourceTitle.text() == NO_FIRMWARE_TITLE
    assert host.ui.label_mappingHint.text() == HINT_NO_FIRMWARE
    assert host.ctx.source == {}


def test_gui_no_profile_or_closing_ignores_firmware(host, tmp_path):
    host.profile = None
    host.on_firmware_ready(make_artifact_tree(tmp_path / "art"), SOURCE)
    assert host.ui.tableWidget_mapping.rowCount() == 0
    host.profile = load_profile(EXAMPLE_PROFILE)
    host._closing = True
    host.on_firmware_ready(make_artifact_tree(tmp_path / "art2"), SOURCE)
    assert host.ui.tableWidget_mapping.rowCount() == 0
    assert host.ui.label_sourceTitle.text() == NO_FIRMWARE_TITLE


def test_gui_wheel_over_a_row_combo_does_not_change_the_choice(host, tmp_path, qtbot):
    root = make_artifact_tree(tmp_path / "art", {"a/App.s3": b"1", "b/App.s3": b"2", "x_cm7_0.elf": b"3"})
    host.on_firmware_ready(root, SOURCE)
    combo = host.mapping_combo(0)
    before = combo.currentIndex()
    event = QWheelEvent(
        QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, -120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False,
    )
    assert host.eventFilter(combo, event) is True
    assert combo.currentIndex() == before
    assert host.eventFilter(combo, QEvent(QEvent.Type.Enter)) is False
