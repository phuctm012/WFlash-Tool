from wflash.core.srec import is_srec_file, parse_srec, read_image, sample_ranges, visible_segments


def record(address: int, data: bytes) -> str:
    body = bytes([4 + len(data) + 1]) + address.to_bytes(4, "big") + data
    return "S3" + body.hex().upper() + f"{(~sum(body)) & 0xFF:02X}"


def test_parse_srec_merges_contiguous_records_and_skips_headers(tmp_path):
    path = tmp_path / "a.s3"
    path.write_text(
        "S00600004844521B\n"
        + record(0x110, b"\x22" * 16) + "\n"
        + record(0x100, b"\x11" * 16) + "\n"
        + record(0x7F2FC0, b"\x33" * 4) + "\n"
        + "S70500000000FA\n"
    )
    assert parse_srec(path) == [(0x100, b"\x11" * 16 + b"\x22" * 16), (0x7F2FC0, b"\x33" * 4)]


def test_parse_srec_reads_s1_and_s2_addresses(tmp_path):
    path = tmp_path / "a.sre"
    s1 = bytes([2 + 1 + 1]) + (0x1234).to_bytes(2, "big") + b"\xAA"
    s2 = bytes([3 + 1 + 1]) + (0x7F0000).to_bytes(3, "big") + b"\xBB"
    path.write_text(f"S1{s1.hex()}00\nS2{s2.hex()}00\n")
    assert parse_srec(path) == [(0x1234, b"\xAA"), (0x7F0000, b"\xBB")]


def test_sample_ranges_takes_head_and_tail_of_long_segments():
    data = bytes(range(256)) * 3
    assert sample_ranges([(0x1000, data)], sample=256) == [(0x1000, data[:256]), (0x1000 + 512, data[-256:])]


def test_sample_ranges_keeps_short_segments_whole():
    assert sample_ranges([(0x10, b"abc")], sample=256) == [(0x10, b"abc")]


def test_is_srec_file():
    assert is_srec_file("RAD_SUZ05_FFI.s3")
    assert is_srec_file("x_CAL.SRE")
    assert not is_srec_file("image.bin")


def test_visible_segments_removes_what_a_later_image_overwrites():
    ffi = [(0x0, b"A" * 100)]
    bm = [(0x10, b"B" * 10)]
    assert visible_segments([ffi, bm]) == [[(0x0, b"A" * 16), (0x1A, b"A" * 74)], [(0x10, b"B" * 10)]]


def test_visible_segments_can_remove_a_whole_segment():
    assert visible_segments([[(0x10, b"A" * 4)], [(0x0, b"B" * 100)]]) == [[], [(0x0, b"B" * 100)]]


def test_read_image_applies_the_offset_to_a_bin(tmp_path):
    path = tmp_path / "x.bin"
    path.write_bytes(b"abc")
    assert read_image(path, 0xF1000) == [(0xF1000, b"abc")]


def test_read_image_applies_the_offset_to_srecords(tmp_path):
    path = tmp_path / "x.s3"
    path.write_text(record(0x100, b"\x11") + "\n")
    assert read_image(path, 0x1000) == [(0x1100, b"\x11")]
