"""Spike 17: program Winbond bằng cache rồi flush một lần (thử làm giống Hardware → Winbond → Program).
GHI VÀO FLASH ở bước 2. Script hỏi xác nhận trước mỗi bước.

Vì sao: user thấy bấm tay Hardware → Winbond W25Q64JW SPI → Program ít gặp "Error loading monitor"
hơn Debug → Download / begin_program. API ứng với menu đó, umi.write(index, wProgDevice), đã xoá
trước MỖI dòng tick và làm chết ECU (2026-11-07, spike 08) nên bị cấm.

Tài liệu SDK (TASKING, test_storage_flush.py và IConnectUMI):
  wProgCache = "program the data into the intermediate cache"
  flush()    = "program the device from the intermediate cache"
Giả thuyết: write(index, wProgCache) nạp mọi dòng tick vào cache mà không đụng flash, rồi flush(index)
xoá một lần và ghi một lần. CHƯA AI CHẠY: đây là lần đầu.

Các bước:
  0. Chỉ đọc: thiết bị, các dòng Download Files, trạng thái từng core. Dừng nếu có core NOT ACCESSIBLE
     hoặc core mặc định không STOP.
  1. umi.write(index, wProgCache): theo tài liệu chỉ ghi vào cache. Hỏi YES trước.
     Sau đó bạn xem Output của winIDEA: nếu thấy ERASING hoặc PROGRAMMING thì giả thuyết sai, gõ NO.
  2. umi.flush(index): GHI FLASH. Hỏi YES lần nữa.
  3. Đọc 16 byte ở 0x0 (như WFlash), reset, đọc lại trạng thái core.
Sau đó chạy 09_flash_compare.py để so mẫu với file.

Khôi phục nếu ECU không chạy: Hardware → Winbond W25Q64JW SPI → Program, hoặc Debug → Download bằng tay.
Không gọi write(wProgDevice), erase, getOptionJSON, set*. Không đổi đường dẫn hay dấu tick nào.
"""
import threading
import time

from _common import Report, base_args, connect, try_call

DEVICES = "/iOPEN/UMIConfig.Devices.Devices"
PROBE_BYTES = 16


def core_states(report, ic, cmgr):
    """(name, text) per core, the calls of spike 16 / RealWinIDEAAdapter._core_states."""
    try:
        session = ic.CSessionCtrl(cmgr)
        names = [core.name() for core in session.get_topology().SoCs()[0].cores()]
        states = []
        for i, core in enumerate(session.get_status().SoCs()[0].cores()):
            states.append((names[i] if i < len(names) else f"core {i}", core.status_string()))
    except Exception:
        report.exc("core states")
        return None
    report.line("cores: " + ", ".join(f"{name} {text}" for name, text in states))
    return states


def cpu_stopped(report, ic, cmgr):
    status = try_call(report, "getCPUStatus", lambda: ic.CDebugFacade(cmgr).getCPUStatus())
    return None if status is None else try_call(report, "isStopped", status.isStopped)


def ask(prompt: str) -> bool:
    return input(f"{prompt} Type YES: ").strip() == "YES"


def timed(report, label, fn):
    """Run fn with a 5 s heartbeat; return (ok, seconds)."""
    done = threading.Event()
    t0 = time.monotonic()

    def ticker():
        while not done.wait(5):
            report.line(f"... {label} still running, {time.monotonic() - t0:.0f}s")

    threading.Thread(target=ticker, daemon=True).start()
    ok = True
    try:
        report.line(f"{label} -> {fn()!r}")
    except Exception:
        ok = False
        report.exc(label)
    finally:
        done.set()
    elapsed = time.monotonic() - t0
    report.line(f"{label} elapsed: {elapsed:.1f}s")
    return ok, elapsed


def main() -> None:
    parser = base_args(__doc__)
    parser.add_argument("--device-index", type=int, default=0, help="Chỉ số thiết bị UMI (mặc định 0)")
    parser.add_argument("--no-reset", action="store_true", help="Không reset sau flush, để chạy 09 ngay sau đó")
    parser.add_argument("--expect-device", default="W25Q64JW", help="Model thiết bị phải khớp (mặc định W25Q64JW)")
    args = parser.parse_args()
    report = Report("17_umi_cache_flush")
    try:
        ic, cmgr = connect(report, args.instance)
        ide = ic.CIDEController(cmgr)
        umi = ic.CUMIController(cmgr)
        index = args.device_index

        report.section("0. device and rows (read only)")
        dev = f"{DEVICES}[{index}]"
        model = try_call(report, f"{dev}.Device", lambda: ide.getOptionStr(f"{dev}.Device"))
        enabled = try_call(report, f"{dev}.Enabled", lambda: ide.getOptionStr(f"{dev}.Enabled"))
        if model != args.expect_device or enabled != "true":
            report.line(f"expected an enabled {args.expect_device!r} at index {index} -> stop, nothing written")
            return
        rows = ide.getDynamicOptionSize(f"{dev}.DownloadFiles")
        for i in range(rows):
            row = f"{dev}.DownloadFiles[{i}]"
            for field in ("Enabled", "Offset", "Path"):
                try_call(report, f"[{i}] {field}", lambda r=row, f=field: ide.getOptionStr(f"{r}.{f}"))
        prog_cache = ic.IConnectUMI.wProgCache
        report.line(f"IConnectUMI.wProgCache = {prog_cache!r}")
        if prog_cache == ic.IConnectUMI.wProgDevice:
            report.line("wProgCache equals wProgDevice -> stop, nothing written")
            return

        report.section("0. cores (read only)")
        states = core_states(report, ic, cmgr)
        if states is None:
            report.line("core states unreadable -> stop, nothing written")
            return
        bad = [name for name, text in states if text.upper() == "NOT ACCESSIBLE"]
        if bad:
            report.line(f"NOT ACCESSIBLE: {bad} -> stop, nothing written. Reset or power-cycle, then run again.")
            return
        if cpu_stopped(report, ic, cmgr) is not True:
            report.line("default core not stopped -> stop, nothing written. Stop the CPU in winIDEA, then run again.")
            return

        report.section("1. umi.write(index, wProgCache)")
        if not ask("Step 1: load the ticked files into winIDEA's program CACHE (the docs say the flash is not "
                   "touched)."):
            report.line("step 1 cancelled by user, nothing written")
            return
        ok, cache_s = timed(report, "umi.write(wProgCache)", lambda: umi.write(index, prog_cache))
        try_call(report, "umi.getLastError", umi.getLastError)
        if not ok:
            report.line("cache write failed -> stop before flush")
            return
        report.line("Look at winIDEA's Output view now. If step 1 added ERASING or PROGRAMMING lines, answer 'yes': the "
                    "script stops and you recover with Hardware > Winbond > Program. Answer 'no' only if it added none.")
        seen = input("Did step 1 add ERASING or PROGRAMMING lines to the Output? (yes = stop / no = go on): ").strip().lower()
        report.line(f"user: Output after step 1 showed erase/program: {seen!r}")
        if seen != "no":
            report.line("step 1 may have touched the flash -> stop before flush")
            return

        report.section("2. umi.flush(index)  WRITES THE FLASH")
        if not ask("Step 2: program the Winbond flash from the cache. This ERASES and WRITES the flash. "
                   "Recovery if it fails: Hardware > Winbond > Program by hand."):
            report.line("step 2 cancelled by user, flash not written by this script")
            return
        ok, flush_s = timed(report, "umi.flush", lambda: umi.flush(index))
        try_call(report, "umi.getLastError", umi.getLastError)

        report.section("3. check")
        try_call(report, f"umi.read 0x0 {PROBE_BYTES} bytes",
                 lambda: (umi.read(index, 0, PROBE_BYTES, data := ic.ByteVector(PROBE_BYTES)), bytes(data).hex())[1])
        core_states(report, ic, cmgr)
        if args.no_reset:
            # Round 15: after this reset A53 and BBE32EP were NOT ACCESSIBLE and 09 could not read the flash.
            report.line("--no-reset: no reset, run 09_flash_compare.py now")
        else:
            try_call(report, "debug.reset", ic.CDebugFacade(cmgr).reset)
            cpu_stopped(report, ic, cmgr)
            core_states(report, ic, cmgr)
        report.line(f"summary: cache {cache_s:.1f}s, flush {flush_s:.1f}s, flush ok={ok}")
        report.line("Next: copy winIDEA's whole Output view into a text file (count the ERASING lines), "
                    "then run 09_flash_compare.py.")
    except Exception:
        report.exc("spike 17")
    finally:
        report.close()


if __name__ == "__main__":
    main()
