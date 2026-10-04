from wflash.core.firmware_source import FirmwareSource, files_note, short_timestamp


def test_to_dict_has_every_field():
    source = FirmwareSource("package", "group/pkgs", "Package · fw 1.4.0", "group/pkgs · 2026-10-04 09:20", "Downloaded · 1 file")
    assert source.to_dict() == {
        "kind": "package",
        "project": "group/pkgs",
        "title": "Package · fw 1.4.0",
        "detail": "group/pkgs · 2026-10-04 09:20",
        "cache_note": "Downloaded · 1 file",
    }


def test_files_note_singular_and_plural():
    assert files_note(True, 3) == "Cached · 3 files"
    assert files_note(False, 1) == "Downloaded · 1 file"
    assert files_note(False, 0) == "Downloaded · 0 files"


def test_short_timestamp():
    assert short_timestamp("2026-10-04T09:20:11.123Z") == "2026-10-04 09:20"
    assert short_timestamp("yesterday") == "yesterday"
    assert short_timestamp(None) == ""
