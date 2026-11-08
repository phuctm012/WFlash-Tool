"""S-record files: contiguous segments and the samples compared after a flash. No winIDEA here."""
from __future__ import annotations

from pathlib import Path, PurePath

ADDRESS_BYTES = {"1": 2, "2": 3, "3": 4}
SREC_SUFFIXES = {".s3", ".s2", ".s1", ".sre", ".srec", ".s19", ".mot"}
BINARY_SUFFIXES = {".bin"}


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


def is_image_file(name: str) -> bool:
    return is_srec_file(name) or PurePath(name).suffix.lower() in BINARY_SUFFIXES


def read_image(path: Path, offset: int) -> list[tuple[int, bytes]]:
    if Path(path).suffix.lower() in BINARY_SUFFIXES:
        return [(offset, Path(path).read_bytes())]
    return [(address + offset, data) for address, data in parse_srec(path)]


def visible_segments(images: list[list[tuple[int, bytes]]]) -> list[list[tuple[int, bytes]]]:
    """Later images are written over earlier ones, so compare each only where it stays on the flash."""
    result = []
    for i, image in enumerate(images):
        later = [(a, a + len(d)) for other in images[i + 1:] for a, d in other]
        kept: list[tuple[int, bytes]] = []
        for address, data in image:
            pieces = [(address, address + len(data))]
            for start, end in later:
                next_pieces = []
                for low, high in pieces:
                    if end <= low or start >= high:
                        next_pieces.append((low, high))
                        continue
                    if low < start:
                        next_pieces.append((low, start))
                    if end < high:
                        next_pieces.append((end, high))
                pieces = next_pieces
            kept += [(low, data[low - address:high - address]) for low, high in pieces]
        result.append(kept)
    return result
