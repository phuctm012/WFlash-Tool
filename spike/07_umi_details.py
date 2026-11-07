"""Spike 07: chi tiết danh sách file của external flash (Winbond, UMI). CHỈ ĐỌC.

Kết quả spike 06: URL đọc được path là
    /iOPEN/UMIConfig.Devices.Devices[0].DownloadFiles[0].Path -> 'Radar_SUZ05_Gen7.s3'
Script này:
(a) đọc lần lượt DownloadFiles[i].Path cho tới khi hết (lỗi "out of range"),
(b) thử tên field ứng viên cho offset / bật-tắt của từng dòng và cho thiết bị,
(c) in tên thiết bị storage/UMI và hằng số program mode,
(d) in đầy đủ tài liệu các hàm sẽ dùng để program (CUMIController, CStorageDeviceFactory, CSessionCtrl).

Không gọi getOptionJSON trên cây lớn: ở spike 06, getOptionJSON('/IDE/System.Debug.Applications')
làm winIDEA ngừng trả lời. Chỉ khi thêm --json mới thử JSON của MỘT dòng DownloadFiles (nhỏ), và chạy cuối cùng.
"""
from _common import Report, base_args, connect, try_call

DEVICE = "/iOPEN/UMIConfig.Devices.Devices"
MAX_FILES = 32

FILE_FIELDS = [
    "Path", "Offset", "Address", "Enabled", "Enable", "Use", "Used", "Checked", "Active",
    "Download", "Load", "Type", "Format", "Options.Offset", "Options.Type", "Options.Enabled",
]
DEVICE_FIELDS = [
    "Name", "Device", "DeviceName", "Type", "Interface", "Parallel", "Enabled",
    "MassEraseBeforeDownload", "ProgramAtDownload", "AllowMassErase", "VerifyAfterProgram",
    "VerifyOnTheFly", "ReadOnly", "AllowDownloadOnly", "UseBufferCompression", "UseHashVerification",
    "Options.MassEraseBeforeDownload", "Options.ProgramAtDownload",
]


def full_doc(report, label, obj):
    doc = (getattr(obj, "__doc__", "") or "").strip()
    report.line(f"--- {label}")
    for line in doc.splitlines():
        report.line(f"    {line}")


def main() -> None:
    parser = base_args(__doc__)
    parser.add_argument("--device", type=int, default=0, help="Chỉ số thiết bị UMI (mặc định 0)")
    parser.add_argument("--json", action="store_true", help="Thử getOptionJSON trên DownloadFiles[0] (có rủi ro, chạy cuối)")
    args = parser.parse_args()
    report = Report("07_umi_details")
    try:
        ic, cmgr = connect(report, args.instance)
        ide = ic.CIDEController(cmgr)
        dev = f"{DEVICE}[{args.device}]"

        report.section(f"{dev}.DownloadFiles[i].Path")
        count = 0
        for i in range(MAX_FILES):
            url = f"{dev}.DownloadFiles[{i}].Path"
            if try_call(report, f"getOptionStr {url}", lambda u=url: ide.getOptionStr(u)) is None:
                break
            count += 1
        report.line(f"files found: {count}")

        report.section("file fields (row 0 and 1)")
        for i in range(min(count, 2)):
            for field in FILE_FIELDS:
                url = f"{dev}.DownloadFiles[{i}].{field}"
                try_call(report, f"getOptionStr {url}", lambda u=url: ide.getOptionStr(u))

        report.section("device fields")
        for field in DEVICE_FIELDS:
            url = f"{dev}.{field}"
            try_call(report, f"getOptionStr {url}", lambda u=url: ide.getOptionStr(u))
        try_call(report, f"getDynamicOptionSize {dev}.DownloadFiles",
                 lambda: ide.getDynamicOptionSize(f"{dev}.DownloadFiles"))

        report.section("storage / UMI devices")
        factory = getattr(ic, "CStorageDeviceFactory", None)
        if factory is not None:
            try_call(report, "CStorageDeviceFactory.DEVICES_OPT_URL", lambda: factory.DEVICES_OPT_URL)
            names = ic.StrVector() if hasattr(ic, "StrVector") else None
            if names is not None:
                try_call(report, "getDeviceNames(cmgr, vec)", lambda: factory.getDeviceNames(cmgr, names))
                report.line(f"device names: {list(names)}")
                umi = ic.CUMIController(cmgr)
                for name in names:
                    try_call(report, f"umi.getDeviceIndex({name!r})", lambda n=name: umi.getDeviceIndex(n))
            else:
                report.line("ic.StrVector not available")
        consts = sorted(n for n in dir(ic) if "wProg" in n or n.startswith("IConnectUMI"))
        report.line(f"program-mode names in module: {consts}")
        for holder in ("IConnectUMI", "CUMIController", "CStorageDeviceController"):
            obj = getattr(ic, holder, None)
            if obj is not None:
                report.line(f"{holder}: {[n for n in dir(obj) if 'Prog' in n or 'prog' in n]}")
        for name in consts:
            try_call(report, f"ic.{name}", lambda n=name: getattr(ic, n))

        report.section("API docs (full)")
        for cls_name, members in (
            ("CUMIController", ("__init__", "getDeviceIndex", "write", "verify", "erase", "getLastError")),
            ("CStorageDeviceFactory", ("getDeviceNames", "makeDevice")),
            ("CStorageDeviceController", ("write", "verify")),
            ("CLoaderController", ("download", "getDownloadList")),
        ):
            cls = getattr(ic, cls_name, None)
            for member in members:
                if cls is not None and hasattr(cls, member):
                    full_doc(report, f"{cls_name}.{member}", getattr(cls, member))
        session = getattr(ic, "CSessionCtrl", None)
        if session is not None:
            full_doc(report, "CSessionCtrl", session)
            for member in sorted(m for m in dir(session) if not m.startswith("_")):
                full_doc(report, f"CSessionCtrl.{member}", getattr(session, member))

        if args.json:
            report.section("JSON of one download file row (risky)")
            url = f"{dev}.DownloadFiles[0]"
            try_call(report, f"getOptionJSON {url}", lambda: ide.getOptionJSON(url))
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
