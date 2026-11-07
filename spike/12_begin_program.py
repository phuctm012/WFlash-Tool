"""Spike 12: flash qua CSessionCtrl.begin_program(). GHI VÀO FLASH.

Debug -> Download trong winIDEA nạp mọi file đang tick rồi xóa một lần và ghi (log 2026-11-07).
CLoaderController.download() đã deprecated, tài liệu khuyên dùng begin_program, và begin_program
dừng target ở reset vector. Script hỏi xác nhận, đo thời gian, in trạng thái sau khi xong.
Sau đó kiểm tra Output của winIDEA có đúng một pha ERASING không.
"""
import threading
import time

from _common import Report, base_args, connect, try_call

DEVICE = "/iOPEN/UMIConfig.Devices.Devices[0]"


def dump_status(report, ic, cmgr, session, label):
    try_call(report, f"{label} SoC status", lambda: session.get_status().SoCs()[0].status_string())
    status = try_call(report, f"{label} getCPUStatus", ic.CDebugFacade(cmgr).getCPUStatus)
    if status is not None:
        try_call(report, f"{label} toString", status.toString)


def main() -> None:
    parser = base_args(__doc__)
    parser.add_argument("--yes", action="store_true", help="Không hỏi xác nhận")
    args = parser.parse_args()
    report = Report("12_begin_program")
    try:
        ic, cmgr = connect(report, args.instance)
        ide = ic.CIDEController(cmgr)
        session = ic.CSessionCtrl(cmgr)

        report.section("configuration")
        try_call(report, "Device", lambda: ide.getOptionStr(f"{DEVICE}.Device"))
        try_call(report, "ProgramAtDownload", lambda: ide.getOptionStr(f"{DEVICE}.ProgramAtDownload"))
        for i in range(ide.getDynamicOptionSize(f"{DEVICE}.DownloadFiles")):
            row = f"{DEVICE}.DownloadFiles[{i}]"
            try_call(report, f"[{i}] Enabled", lambda r=row: ide.getOptionStr(f"{r}.Enabled"))
            try_call(report, f"[{i}] Offset", lambda r=row: ide.getOptionStr(f"{r}.Offset"))
            try_call(report, f"[{i}] Path", lambda r=row: ide.getOptionStr(f"{r}.Path"))
        dump_status(report, ic, cmgr, session, "before")

        if not args.yes:
            answer = input("Run begin_program now? This WRITES the Winbond flash. Type YES: ")
            if answer.strip() != "YES":
                report.line("cancelled by user")
                return

        report.section("begin_program")
        done = threading.Event()
        t0 = time.monotonic()

        def ticker():
            while not done.wait(5):
                report.line(f"... still programming, {time.monotonic() - t0:.0f}s")

        threading.Thread(target=ticker, daemon=True).start()
        try:
            report.line(f"begin_program -> {session.begin_program()!r}")
        except Exception:
            report.exc("begin_program")
        finally:
            done.set()
        report.line(f"elapsed: {time.monotonic() - t0:.1f}s")

        report.section("after")
        dump_status(report, ic, cmgr, session, "after")
        time.sleep(2)
        dump_status(report, ic, cmgr, session, "after +2s")
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
