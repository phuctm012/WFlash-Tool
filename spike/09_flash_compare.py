"""Spike 09: đọc lại external flash và so với các file đang tick. CHỈ ĐỌC, không ghi flash.

Log của lần program (spike 08) có hai pha ERASING: một trước RAD_SUZ05_FFI.s3, một trước file CAL .sre.
Log không cho biết pha thứ hai xóa bao nhiêu. Script này so nội dung flash với từng file để biết
dữ liệu của file đầu còn nguyên không, đặc biệt các đoạn nằm chung sector 64 KB với file CAL.

Mặc định chỉ so 256 byte đầu và cuối mỗi đoạn; thêm --full để so toàn bộ.
"""
import time
from pathlib import Path

from _common import Report, base_args, connect, try_call

DEVICES = "/iOPEN/UMIConfig.Devices.Devices"
SAMPLE = 256
READ_SIZE = 0x1000
PROGRESS_S = 5
ADDRESS_BYTES = {"1": 2, "2": 3, "3": 4}


def parse_srec(path):
    """Return contiguous (address, bytes) segments of an S-record file, sorted by address."""
    pieces = []
    for line in Path(path).read_text(encoding="ascii", errors="replace").splitlines():
        line = line.strip()
        if len(line) < 4 or line[0] != "S" or line[1] not in ADDRESS_BYTES:
            continue
        width = ADDRESS_BYTES[line[1]]
        raw = bytes.fromhex(line[2:])
        pieces.append((int.from_bytes(raw[1:1 + width], "big"), raw[1 + width:-1]))
    segments = []
    for address, data in sorted(pieces, key=lambda p: p[0]):
        if segments and segments[-1][0] + len(segments[-1][1]) == address:
            segments[-1][1].extend(data)
        else:
            segments.append((address, bytearray(data)))
    return segments


def find_byte_vector(ic):
    for name in dir(ic):
        low = name.lower()
        if "vector" in low and ("byte" in low or "uint8" in low):
            return name, getattr(ic, name)
    return None, None


def compare(report, umi, index, make_vector, address, expected, label):
    """Read the device over [address, address+len(expected)) and report the differences."""
    wrong = erased = 0
    first = None
    t0 = last = time.monotonic()
    report.line(f"{label}: reading 0x{len(expected):X} bytes from 0x{address:06X}")
    for start in range(0, len(expected), READ_SIZE):
        chunk = bytes(expected[start:start + READ_SIZE])
        # read() fills the vector in place and raises "Vector size is too small!" unless it is presized.
        data = make_vector(len(chunk))
        umi.read(index, address + start, len(chunk), data)
        actual = bytes(b if isinstance(b, int) else ord(b) for b in data)
        now = time.monotonic()
        if now - last >= PROGRESS_S:
            last = now
            done = start + len(chunk)
            report.line(f"    ... {done} / {len(expected)} bytes, {now - t0:.0f}s, {done / (now - t0):.0f} B/s")
        if len(actual) != len(chunk):
            report.line(f"{label}: read returned {len(actual)} bytes, asked {len(chunk)}")
            return
        for offset, (got, want) in enumerate(zip(actual, chunk)):
            if got != want:
                wrong += 1
                erased += got == 0xFF
                if first is None:
                    first = (address + start + offset, got, want)
    verdict = "MATCH" if wrong == 0 else "DIFFERENT"
    report.line(f"{label} 0x{address:06X} +0x{len(expected):X}: {verdict} wrong={wrong} wrong_and_0xFF={erased} ({time.monotonic() - t0:.1f}s)")
    if first is not None:
        report.line(f"    first difference at 0x{first[0]:06X}: flash=0x{first[1]:02X} file=0x{first[2]:02X}")


def main() -> None:
    parser = base_args(__doc__)
    parser.add_argument("--device-index", type=int, default=0, help="Chỉ số thiết bị (mặc định 0)")
    parser.add_argument("--full", action="store_true", help="So toàn bộ mỗi đoạn (chậm hơn)")
    args = parser.parse_args()
    report = Report("09_flash_compare")
    try:
        ic, cmgr = connect(report, args.instance)
        ide = ic.CIDEController(cmgr)
        umi = ic.CUMIController(cmgr)
        index = args.device_index
        dev = f"{DEVICES}[{index}]"
        workspace_dir = ide.getPath(ic.CIDEController.WORKSPACE_DIR)
        report.line(f"workspace dir: {workspace_dir}")
        report.line(f"CUMIController.read doc: {(ic.CUMIController.read.__doc__ or '').strip()}")
        report.line(f"vector-like names: {[n for n in dir(ic) if 'vector' in n.lower()]}")

        vector_name, make_vector = find_byte_vector(ic)
        report.line(f"byte vector: {vector_name}")
        if make_vector is None:
            report.line("no byte vector type -> stop")
            return

        for i in range(ide.getDynamicOptionSize(f"{dev}.DownloadFiles")):
            row = f"{dev}.DownloadFiles[{i}]"
            enabled = ide.getOptionStr(f"{row}.Enabled")
            stored = ide.getOptionStr(f"{row}.Path")
            offset = int(ide.getOptionStr(f"{row}.Offset"), 16)
            report.section(f"row {i}: enabled={enabled} offset=0x{offset:X} {stored}")
            if enabled != "true":
                report.line("not enabled -> skipped")
                continue
            path = Path(workspace_dir) / stored
            try:
                segments = parse_srec(path)
            except Exception:
                report.exc(f"parse {path}")
                continue
            report.line(f"{path}: {len(segments)} segments")
            for address, data in segments:
                target = address + offset
                label = f"seg@0x{address:06X}"
                try:
                    if args.full or len(data) <= 2 * SAMPLE:
                        compare(report, umi, index, make_vector, target, data, label)
                    else:
                        compare(report, umi, index, make_vector, target, data[:SAMPLE], label + " head")
                        tail = target + len(data) - SAMPLE
                        compare(report, umi, index, make_vector, tail, data[-SAMPLE:], label + " tail")
                except Exception:
                    report.exc(label)
                    try_call(report, "umi.getLastError", umi.getLastError)
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
