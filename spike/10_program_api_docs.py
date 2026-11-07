"""Spike 10: tìm API tương đương nút Hardware -> Winbond -> Program. KHÔNG ghi flash, KHÔNG đụng target.

Chỉ in docstring và đọc cấu trúc menu của winIDEA. Không gọi invoke, serviceCall, write, flush, erase,
download, reset hay read. Lý do: umi.write(index, mode) có 2 pha erase với 2 file đang tick, còn nút
Program chỉ có 1; umi.read thì nạp monitor vào target.
"""
from _common import Report, base_args, connect, try_call

DOCS = {
    "CIDEController": ("getMenuStructure", "invoke", "invoke_T", "serviceCall", "mapToServiceCallString",
                       "parseServiceCallMap", "getCapabilities"),
    "CUMIController": ("write", "flush", "erase", "readState", "verify"),
    "CStorageDeviceController": ("write", "flush", "erase", "verify"),
    "IConnectUMI": (),
    "CDebugFacade": ("download",),
    "CSessionCtrl": ("begin_program", "program_verify"),
}
KEYWORDS = ("winbond", "w25q", "program", "mass erase", "verify", "blank")


def full_doc(report, label, obj):
    report.line(f"--- {label}")
    for line in (getattr(obj, "__doc__", "") or "").strip().splitlines():
        report.line(f"    {line}")


def dump_item(report, item, depth=0):
    """Print a menu item and its children, whatever shape the binding returns."""
    report.line("  " * depth + repr(item))
    if depth > 6:
        return
    for name in sorted(n for n in dir(item) if n.startswith(("get", "is")) and not n.startswith("__")):
        try:
            value = getattr(item, name)()
        except Exception:
            continue
        report.line("  " * (depth + 1) + f"{name} -> {value!r}")
        if not isinstance(value, (str, int, float, bool, type(None))):
            try:
                for child in value:
                    dump_item(report, child, depth + 2)
            except TypeError:
                pass


def main() -> None:
    args = base_args(__doc__).parse_args()
    report = Report("10_program_api_docs")
    try:
        ic, cmgr = connect(report, args.instance)
        report.section("API docs")
        for cls_name, members in DOCS.items():
            cls = getattr(ic, cls_name, None)
            if cls is None:
                report.line(f"{cls_name}: not available")
                continue
            if not members:
                public = sorted(n for n in dir(cls) if not n.startswith("_"))
                report.line(f"{cls_name} members: {public}")
                for name in public:
                    value = getattr(cls, name)
                    if isinstance(value, int):
                        report.line(f"  {name} = {value}")
            for member in members:
                if hasattr(cls, member):
                    full_doc(report, f"{cls_name}.{member}", getattr(cls, member))
                else:
                    report.line(f"--- {cls_name}.{member}: not available")

        report.section("menu structure (read only)")
        ide = ic.CIDEController(cmgr)
        menu = try_call(report, "ide.getMenuStructure()", ide.getMenuStructure)
        if menu is not None:
            text = repr(menu)
            report.line(f"keyword hits in repr: {[k for k in KEYWORDS if k in text.lower()]}")
            if not isinstance(menu, str):
                try:
                    for item in menu:
                        dump_item(report, item)
                except TypeError:
                    dump_item(report, menu)
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
