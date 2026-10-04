import pytest

from tests.gui_stubs import EXAMPLE_PROFILE, HostWindow, make_artifact_tree
from wflash.core.profile import load_profile
from wflash.gui.mapping_table import MISSING_STYLE, MappingTableMixin

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
    return window


def test_gui_unique_matches_are_selected(host, tmp_path):
    root = make_artifact_tree(tmp_path / "art")
    host.on_artifact_ready(root, "job #7")
    table = host.ui.tableWidget_mapping
    assert table.rowCount() == 3
    assert host.mapping_complete()
    assert host.mapping_combo(0).currentText() == "out/App.s3"
    assert host.mapping_combo(0).styleSheet() == ""
    assert table.item(0, 1).text() == "App"
    assert "job #7" in host.ui.label_artifact.text()
    assert host.flash_control_updates >= 1


def test_gui_ambiguous_and_missing_rows_need_a_manual_choice(host, tmp_path):
    root = make_artifact_tree(
        tmp_path / "art", {"a/App.s3": b"1", "b/App.s3": b"2", "x_cm7_0.elf": b"3", "other.elf": b"4"}
    )
    host.on_artifact_ready(root, "job #7")
    assert not host.mapping_complete()
    program, cm7_1 = host.mapping_combo(0), host.mapping_combo(2)
    assert program.count() == 3  # "-- select file --" + the two candidates
    assert program.styleSheet() == MISSING_STYLE
    assert cm7_1.count() == 3  # "-- select file --" + every .elf in the artifact
    updates = host.flash_control_updates
    program.setCurrentIndex(program.findText("b/App.s3"))
    assert host.flash_control_updates == updates + 1
    assert not host.mapping_complete()
    cm7_1.setCurrentIndex(cm7_1.findText("other.elf"))
    assert host.mapping_complete()
    assert host.mapping_rows()[0].selected == root / "b" / "App.s3"
    assert host.mapping_rows()[2].selected == root / "other.elf"
    assert program.styleSheet() == ""
    program.setCurrentIndex(0)
    assert not host.mapping_complete()
    assert program.styleSheet() == MISSING_STYLE


def test_gui_clear_mapping(host, tmp_path):
    host.on_artifact_ready(make_artifact_tree(tmp_path / "art"), "job #7")
    host.clear_mapping()
    assert host.ui.tableWidget_mapping.rowCount() == 0
    assert not host.mapping_complete()
    assert host.artifact_root is None
    assert host.ui.label_artifact.text() == "No artifact loaded"


def test_gui_no_profile_ignores_artifact(host, tmp_path):
    host.profile = None
    host.on_artifact_ready(make_artifact_tree(tmp_path / "art"), "job #7")
    assert host.ui.tableWidget_mapping.rowCount() == 0
