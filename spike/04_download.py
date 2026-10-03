"""Spike 04: chạy download với cấu hình hiện tại của workspace, đo thời gian."""
import threading
import time

from _common import Report, base_args, connect, try_call


def main() -> None:
    parser = base_args(__doc__)
    parser.add_argument("--facade", action="store_true", help="Dùng CDebugFacade.download() thay vì CLoaderController")
    args = parser.parse_args()
    report = Report("04_download")
    try:
        ic, cmgr = connect(report, args.instance)
        done = threading.Event()
        t0 = time.monotonic()

        def ticker():
            while not done.wait(5):
                report.line(f"... still downloading, {time.monotonic() - t0:.0f}s")

        threading.Thread(target=ticker, daemon=True).start()
        report.section("download")
        try:
            if args.facade:
                ic.CDebugFacade(cmgr).download()
            else:
                ic.CLoaderController(cmgr).download()
            report.line("download() returned normally")
        except Exception:
            report.exc("download")
        finally:
            done.set()
        report.line(f"elapsed: {time.monotonic() - t0:.1f}s")

        report.section("CPU status after download")
        debug = ic.CDebugFacade(cmgr)
        status = try_call(report, "getCPUStatus", debug.getCPUStatus)
        if status is not None:
            for m in ("isStopped", "isRunning", "isReset", "toString"):
                if hasattr(status, m):
                    try_call(report, f"status.{m}", getattr(status, m))
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
