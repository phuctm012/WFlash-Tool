import csv

from tests.gui_stubs import TOKEN
from wflash.core import flash_history
from wflash.core.flash_history import HISTORY_COLUMNS, append_flash
from wflash.core.logging_setup import clear_secrets, register_secret


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.reader(fh))


def test_appends_one_line_per_flash_under_a_single_header(tmp_path):
    path = tmp_path / "h.csv"
    append_flash({"time": "2026-11-09 14:32:05", "profile": "SUZ05", "result": "Done", "tries": 1}, path)
    append_flash({"time": "2026-11-09 14:40:00", "profile": "SUZ05", "result": "Failed", "error": "x"}, path)
    rows = read(path)
    assert rows[0] == list(HISTORY_COLUMNS)
    assert [r[HISTORY_COLUMNS.index("result")] for r in rows[1:]] == ["Done", "Failed"]
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")  # Excel reads UTF-8 with a BOM


def test_keeps_only_the_newest_rows(tmp_path):
    path = tmp_path / "h.csv"
    for i in range(7):
        append_flash({"time": str(i)}, path, keep=5)
    assert [r[0] for r in read(path)[1:]] == ["2", "3", "4", "5", "6"]


def test_token_is_masked(tmp_path):
    register_secret(TOKEN)
    try:
        path = tmp_path / "h.csv"
        append_flash({"error": f"auth failed for {TOKEN}"}, path)
        assert TOKEN not in path.read_text(encoding="utf-8-sig")
    finally:
        clear_secrets()


def test_a_write_failure_only_logs(tmp_path, caplog):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    append_flash({"result": "Done"}, blocker / "h.csv")  # parent is a file: cannot write
    assert "Cannot write the flash history" in caplog.text


def test_history_path_is_under_the_local_app_data_on_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(flash_history.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert flash_history.history_path() == tmp_path / "WFlash" / "flash_history.csv"
