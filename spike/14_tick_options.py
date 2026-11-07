"""Spike 14: tìm và thử ghi dấu tick của Download Files và Symbol Files. KHÔNG flash.

Không tham số: chỉ đọc. --toggle-row i / --toggle-symbol j --field F: đảo giá trị, đọc lại, rồi khôi phục.
"""
from _common import Report, base_args, connect, try_call

DOWNLOAD = "/iOPEN/UMIConfig.Devices.Devices[0].DownloadFiles"
SYMBOLS = "/IDE/System.Debug.Applications[0].SymbolFiles.File"
FIELDS = ["Path", "Load", "Enabled", "Enable", "Use", "Used", "Active", "Checked",
          "Options.Load", "Options.LoadSymbols", "Options.LoadCode"]


def flip(report, ide, url):
    old = try_call(report, f"read {url}", lambda: ide.getOptionStr(url))
    if old not in ("true", "false"):
        report.line(f"{url}: not a true/false option -> skipped")
        return
    new = "false" if old == "true" else "true"
    try_call(report, f"setOption {url} = {new}", lambda: ide.setOption(url, new))
    try_call(report, "read back", lambda: ide.getOptionStr(url))
    try_call(report, f"restore {old}", lambda: ide.setOption(url, old))
    try_call(report, "read after restore", lambda: ide.getOptionStr(url))


def main() -> None:
    parser = base_args(__doc__)
    parser.add_argument("--toggle-row", type=int)
    parser.add_argument("--toggle-symbol", type=int)
    parser.add_argument("--field", default="Load")
    args = parser.parse_args()
    report = Report("14_tick_options")
    try:
        ic, cmgr = connect(report, args.instance)
        ide = ic.CIDEController(cmgr)
        report.section("download rows")
        for i in range(ide.getDynamicOptionSize(DOWNLOAD)):
            for field in ("Path", "Enabled", "Offset"):
                try_call(report, f"[{i}] {field}", lambda f=field, n=i: ide.getOptionStr(f"{DOWNLOAD}[{n}].{f}"))
        report.section("symbol files of application 0")
        for j in range(10):
            if not ide.optionExists(f"{SYMBOLS}[{j}].Path"):
                break
            for field in FIELDS:
                try_call(report, f"[{j}] {field}", lambda f=field, n=j: ide.getOptionStr(f"{SYMBOLS}[{n}].{f}"))
        if args.toggle_row is not None:
            report.section("toggle download row")
            flip(report, ide, f"{DOWNLOAD}[{args.toggle_row}].Enabled")
        if args.toggle_symbol is not None:
            report.section("toggle symbol file")
            flip(report, ide, f"{SYMBOLS}[{args.toggle_symbol}].{args.field}")
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
