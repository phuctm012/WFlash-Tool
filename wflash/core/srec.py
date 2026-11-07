"""S-record files: contiguous segments and the samples compared after a flash. No winIDEA here."""
from __future__ import annotations

from pathlib import Path, PurePath

ADDRESS_BYTES = {"1": 2, "2": 3, "3": 4}
SREC_SUFFIXES = {".s3", ".s2", ".s1", ".sre", ".srec", ".s19", ".mot"}


def is_srec_file(name: str) -> bool:
    return PurePath(name).suffix.lower() in SREC_SUFFIXES


def parse_srec(path: Path) -> list[tuple[int, bytes]]:
    """Return (address, data) segments sorted by address, with adjacent records merged."""
    pieces: list[tuple[int, bytes]] = []
    for line in Path(path).read_text(encoding="ascii", errors="replace").splitlines():
        line = line.strip()
        if len(line) < 4 or line[0] != "S" or line[1] not in ADDRESS_BYTES:
            continue
        width = ADDRESS_BYTES[line[1]]
        raw = bytes.fromhex(line[2:])
        pieces.append((int.from_bytes(raw[1:1 + width], "big"), raw[1 + width:-1]))
    segments: list[tuple[int, bytearray]] = []
    for address, data in sorted(pieces, key=lambda p: p[0]):
        if segments and segments[-1][0] + len(segments[-1][1]) == address:
            segments[-1][1].extend(data)
        else:
            segments.append((address, bytearray(data)))
    return [(address, bytes(data)) for address, data in segments]


def sample_ranges(segments: list[tuple[int, bytes]], sample: int = 256) -> list[tuple[int, bytes]]:
    """The start and end of each segment; a short segment is taken whole."""
    ranges: list[tuple[int, bytes]] = []
    for address, data in segments:
        if len(data) <= 2 * sample:
            ranges.append((address, data))
        else:
            ranges.append((address, data[:sample]))
            ranges.append((address + len(data) - sample, data[-sample:]))
    return ranges
