"""Spike 18: bo USB relay (HID) của bench 1 và 4. CHỈ ĐỌC, không bật/tắt relay nào.

Bench 1 và 4 tắt/bật nguồn ECU bằng bo USB relay 8 kênh (tool `usb_relay_control.py` của người
dùng), JTAG vẫn qua Switch Debugger. Người dùng (2026-11-12): ECU 0 = Relay 1, ECU 1 = Relay 2,
relay ON = ECU có nguồn.

Spike này kiểm tra trên máy thật, trước khi WFlash gọi bo này:
1. gói `hidapi` có cài được và nạp được trong env của WFlash không, version bao nhiêu;
2. bo relay hiện ra với VID/PID, serial, product nào;
3. mở được thiết bị không, kể cả khi cửa sổ USB Relay Control đang mở sẵn;
4. đọc trạng thái: lệnh hỏi `00 F1` (tool của người dùng gửi lệnh này mỗi giây), rồi đọc feature
   report id 0 và 1, rồi đọc interrupt; in nguyên các byte nhận được, để biết cách nào chạy.

Không gửi `00 FF`, `00 FD`, `00 FE`, `00 FC` (bật/tắt relay). Lệnh duy nhất gửi đi là `00 F1`.
Chạy trong env `pyside6` (Python 3.12):  pip install hidapi  rồi  python 18_usb_relay.py
"""
from __future__ import annotations

import argparse
import time

from _common import Report

CANDIDATES = ((0x16C0, 0x05DF), (0x5131, 0x2007))  # from the user's usb_relay_control.py
STATUS_REQUEST = [0x00, 0xF1]


def hexs(data) -> str:
    return " ".join(f"{b:02X}" for b in (data or []))


def text(value) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", "ignore") if isinstance(value, bytes) else str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true", help="list every HID device, not only the known relay VID/PID")
    parser.add_argument("--tries", type=int, default=8, help="open attempts per device (default 8)")
    args = parser.parse_args()
    report = Report("18_usb_relay")

    report.section("hidapi")
    try:
        import hid  # type: ignore
    except Exception as exc:  # noqa: BLE001 - a probe reports everything
        report.line(f"import hid FAILED: {exc!r}  (pip install hidapi)")
        return
    report.line(f"hid module: {getattr(hid, '__file__', '?')}")
    report.line(f"hid version: {getattr(hid, '__version__', getattr(hid, 'version', '?'))}")
    report.line(f"hid members: {[n for n in dir(hid) if not n.startswith('_')]}")
    report.line(f"hid.device members: {[n for n in dir(hid.device) if not n.startswith('_')]}")

    report.section("devices")
    entries = hid.enumerate()
    report.line(f"{len(entries)} HID entries in all")
    relays = []
    for entry in entries:
        vid, pid = int(entry.get("vendor_id") or 0), int(entry.get("product_id") or 0)
        known = (vid, pid) in CANDIDATES
        if known or args.all:
            report.line(f"{'RELAY ' if known else '      '}vid=0x{vid:04X} pid=0x{pid:04X} serial={text(entry.get('serial_number'))!r} "
                        f"product={text(entry.get('product_string'))!r} manufacturer={text(entry.get('manufacturer_string'))!r} "
                        f"usage_page=0x{int(entry.get('usage_page') or 0):04X} usage=0x{int(entry.get('usage') or 0):04X} "
                        f"interface={entry.get('interface_number')} path={entry.get('path')!r}")
        if known and entry.get("path"):
            relays.append(entry)
    if not relays:
        report.line("No relay board with a known VID/PID. Run again with --all and send the result.")
        return

    for n, entry in enumerate(relays):
        report.section(f"relay board {n}: status (sends only 00 F1)")
        dev = None
        started = time.monotonic()
        for attempt in range(1, args.tries + 1):
            try:
                dev = hid.device()
                dev.open_path(entry["path"])
                report.line(f"opened on attempt {attempt} after {time.monotonic() - started:.2f} s")
                break
            except Exception as exc:  # noqa: BLE001
                report.line(f"open attempt {attempt} failed: {exc!r}")
                dev = None
                time.sleep(0.25)
        if dev is None:
            report.line("could not open it (busy? close USB Relay Manager and run again)")
            continue
        try:
            for getter in ("get_manufacturer_string", "get_product_string", "get_serial_number_string"):
                try:
                    report.line(f"{getter}() -> {getattr(dev, getter)()!r}")
                except Exception as exc:  # noqa: BLE001
                    report.line(f"{getter}() !! {exc!r}")
            try:
                sent = dev.send_feature_report(STATUS_REQUEST)
                report.line(f"send_feature_report(00 F1) -> {sent}")
            except Exception as exc:  # noqa: BLE001
                report.line(f"send_feature_report(00 F1) !! {exc!r}")
            for report_id in (0x00, 0x01):
                try:
                    data = dev.get_feature_report(report_id, 9)
                    report.line(f"get_feature_report({report_id}, 9) -> [{hexs(data)}]  last byte mask=0x{(data[-1] if data else 0):02X}")
                except Exception as exc:  # noqa: BLE001
                    report.line(f"get_feature_report({report_id}, 9) !! {exc!r}")
            try:
                data = dev.read(9, timeout_ms=500)
                report.line(f"read(9, 500 ms) -> [{hexs(data)}]")
            except Exception as exc:  # noqa: BLE001
                report.line(f"read(9, 500 ms) !! {exc!r}")
        finally:
            dev.close()
    report.line()
    report.line("Compare the mask with the USB Relay Control window: bit 0 = Relay 1 ... bit 7 = Relay 8.")
    report.line(f"Result saved to {report.path}")


if __name__ == "__main__":
    main()
