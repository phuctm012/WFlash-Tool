"""Spike 01: liệt kê instance winIDEA, connect, in version và workspace."""
from _common import Report, base_args, connect, try_call


def main() -> None:
    args = base_args(__doc__).parse_args()
    report = Report("01_connect")
    try:
        ic, cmgr = connect(report, args.instance)
        ide = ic.CIDEController(cmgr)
        report.section("winIDEA info")
        try_call(report, "ide.getWinIDEAVersion", lambda: str(ide.getWinIDEAVersion().toString()))
        try_call(report, "cmgr.getWinIDEAVersion", lambda: str(cmgr.getWinIDEAVersion()))
        for name in ("WORKSPACE_DIR", "WORKSPACE_FILE_NAME", "WINIDEA_EXE_DIR"):
            const = getattr(ic.CIDEController, name, None)
            if const is None:
                report.line(f"CIDEController.{name}: not available")
                continue
            try_call(report, f"ide.getPath({name})", lambda c=const: ide.getPath(c))
        report.section("API surface")
        for cls in ("CIDEController", "CLoaderController", "CDebugFacade", "CExecutionController"):
            obj = getattr(ic, cls, None)
            members = sorted(m for m in dir(obj) if not m.startswith("_")) if obj else []
            report.line(f"{cls}: {', '.join(members)}")
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
