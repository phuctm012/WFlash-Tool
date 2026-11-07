"""Spike 06: dò cách đọc danh sách file của thiết bị external flash (Winbond, cấu hình UMI).

Kết quả spike 02: file .s3 nằm trong phần HServer của workspace
(HServerData.Data.UMI1.Devices.Devices[0].DownloadFiles[i].Path), không nằm trong /IDE/,
nên mọi URL /IDE/... đều lỗi. Script này chỉ ĐỌC, không đổi gì trên workspace hay target:

(a) in chữ ký các class liên quan tới UMI / storage device / loader,
(b) thử getOptionJSON / getOptionStr với nhiều tiền tố + đường dẫn ứng viên,
(c) dump cấu trúc JSON của Applications (symbol file) để thấy các field (Path, bật/tắt, ...),
(d) thử đọc danh sách download của CLoaderController.
"""
import itertools

from _common import Report, base_args, connect, try_call

CLASSES = [
    "CUMIController",
    "CStorageDeviceController",
    "CStorageDeviceFactory",
    "CBasicFlashStorageDevice",
    "CLoaderController",
    "CDownloadConfiguration",
    "COptionController",
    "COptionFilesCfg",
    "COptionAppCfg",
    "COptionAppsCfg",
    "COptionSessionCfg",
    "COptionSoCCfg",
]

PREFIXES = ["/iOPEN/", "/IOPEN/", "/HServer/", "/IDE/HServer.", "/IDE/"]
ROOTS = [
    "UMI1",
    "UMI1.Devices",
    "UMI1.Devices.Devices[0]",
    "UMI1.Devices.Devices[0].DownloadFiles",
    "UMI1.Devices.Devices[0].DownloadFiles[0].Path",
    "Data.UMI1.Devices.Devices[0].DownloadFiles[0].Path",
    "HServerData.Data.UMI1.Devices.Devices[0].DownloadFiles[0].Path",
    "UMIConfig.Devices.Devices[0].DownloadFiles[0].Path",
    "HW.BDM.UMIConfig.Devices.Devices[0].DownloadFiles[0].Path",
    "HServerData.HW.BDM.UMIConfig.Devices.Devices[0].DownloadFiles[0].Path",
]

IDE_JSON = [
    "/IDE/System.Debug.Applications",
    "/IDE/System.Debug.Applications[0]",
    "/IDE/System.Debug.Applications[0].SymbolFiles",
    "/IDE/System.Debug.Applications[0].SymbolFiles.File[0]",
    "/IDE/System.Debug.SoCs",
    "/IDE/System.Debug",
]

MAX_CHARS = 6000


def short(value):
    text = repr(value)
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS] + f"... <{len(text)} chars>"


def dump_class(report, ic, name):
    cls = getattr(ic, name, None)
    if cls is None:
        report.line(f"{name}: not available")
        return
    report.line(f"--- {name}")
    if cls.__doc__:
        report.line(f"  doc: {cls.__doc__.strip()[:800]}")
    init = getattr(cls, "__init__", None)
    if init is not None and init.__doc__:
        report.line(f"  __init__: {init.__doc__.strip()[:800]}")
    for member in sorted(m for m in dir(cls) if not m.startswith("_")):
        doc = (getattr(getattr(cls, member), "__doc__", "") or "").strip().replace("\n", " | ")
        report.line(f"  {member}: {doc[:400]}")


def main() -> None:
    args = base_args(__doc__).parse_args()
    report = Report("06_probe_umi")
    try:
        ic, cmgr = connect(report, args.instance)
        ide = ic.CIDEController(cmgr)

        report.section("class signatures")
        for name in CLASSES:
            try:
                dump_class(report, ic, name)
            except Exception:
                report.exc(f"dump {name}")

        report.section("option URLs: getOptionJSON / getOptionStr")
        for prefix, root in itertools.product(PREFIXES, ROOTS):
            url = prefix + root
            if root.endswith(".Path"):
                try_call(report, f"getOptionStr {url}", lambda u=url: ide.getOptionStr(u))
            else:
                try_call(report, f"getOptionJSON {url}", lambda u=url: short(ide.getOptionJSON(u)))

        report.section("IDE option tree (JSON)")
        for url in IDE_JSON:
            try_call(report, f"getOptionJSON {url}", lambda u=url: short(ide.getOptionJSON(u)))
        try_call(report, "optionExists /IDE/System.Debug.Applications[0].SymbolFiles.File[1].Path",
                 lambda: ide.optionExists("/IDE/System.Debug.Applications[0].SymbolFiles.File[1].Path"))
        try_call(report, "getDynamicOptionSize /IDE/System.Debug.Applications",
                 lambda: ide.getDynamicOptionSize("/IDE/System.Debug.Applications"))
        try_call(report, "getDynamicOptionSize /IDE/System.Debug.Applications[0].SymbolFiles.File",
                 lambda: ide.getDynamicOptionSize("/IDE/System.Debug.Applications[0].SymbolFiles.File"))

        report.section("CLoaderController download lists")
        loader = ic.CLoaderController(cmgr)
        for const in ("DLIST_PRIMARY", "DLIST_TARGET"):
            value = getattr(ic.CLoaderController, const, None)
            report.line(f"CLoaderController.{const} = {value!r}")
            if value is not None:
                try_call(report, f"getDownloadList({const})", lambda v=value: short(loader.getDownloadList(v)))
        try_call(report, "getDefaultDownloadFile", lambda: short(ide.getDefaultDownloadFile()))

        report.section("UMI controller")
        umi_cls = getattr(ic, "CUMIController", None)
        if umi_cls is not None:
            umi = try_call(report, "CUMIController(cmgr)", lambda: umi_cls(cmgr))
            if umi is not None:
                for name in sorted(m for m in dir(umi) if m.startswith(("get", "is", "enumerate"))):
                    try_call(report, f"umi.{name}()", lambda n=name: short(getattr(umi, n)()))
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
