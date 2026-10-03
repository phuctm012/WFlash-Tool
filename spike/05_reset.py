"""Spike 05: reset target, kiểm tra trạng thái halted; tùy chọn chạy (--run)."""
from _common import Report, base_args, connect, try_call


def dump_status(report, debug, label):
    status = try_call(report, f"{label} getCPUStatus", debug.getCPUStatus)
    if status is None:
        return
    for m in ("isStopped", "isRunning", "isReset", "toString"):
        if hasattr(status, m):
            try_call(report, f"{label} status.{m}", getattr(status, m))


def main() -> None:
    parser = base_args(__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    report = Report("05_reset")
    try:
        ic, cmgr = connect(report, args.instance)
        debug = ic.CDebugFacade(cmgr)
        dump_status(report, debug, "before")
        try_call(report, "debug.reset", debug.reset)
        dump_status(report, debug, "after reset")
        if args.run:
            try_call(report, "debug.run", debug.run)
            dump_status(report, debug, "after run")
        report.section("multi-core probe")
        for name in ("getCoreIds", "getCores"):
            if hasattr(cmgr, name):
                try_call(report, f"cmgr.{name}", getattr(cmgr, name))
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
