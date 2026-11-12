"""Spike 19: tìm đường dẫn option của danh sách file nạp Winbond trên workspace kiểu UMI1. CHỈ ĐỌC.

Bench 1 (winIDEA 9.21.324, workspace DD_05_02_01): WFlash báo `Cannot resolve path:
UMIConfig.Devices.Devices`. Trong file .xjrf của workspace này, danh sách file nằm ở
`HServerData.Data.UMI1.Devices.Devices[0].DownloadFiles`, còn workspace Bench 2 (R_04_01_01) ở
`HServerData.HW.BDM.UMIConfig...`, đọc qua `/iOPEN/UMIConfig...`.

Spike này chỉ gọi getOptionStr và getDynamicOptionSize trên các gốc ứng viên, rồi in tên các
symbol file. Không setOption, không getOptionJSON (đã làm rớt kết nối), không download, không reset.
Chạy khi winIDEA đang mở workspace đó:  python 19_umi1_paths.py   (thêm --instance <port> nếu cần)
"""
from _common import Report, base_args, connect

ROOTS = (
    "/iOPEN/UMIConfig.Devices.Devices",        # Bench 2 (R_04_01_01): the one WFlash uses today
    "/iOPEN/Data.UMI1.Devices.Devices",        # mirrors the XML of this workspace
    "/iOPEN/UMI1.Devices.Devices",
    "/iOPEN/Cfg.SoC[0].BBS.UMI1.Devices.Devices",  # what winIDEA rewrote Data.UMI1 to in round 2
    "/iOPEN/Data.UMI.Devices.Devices",         # CStorageDeviceFactory.DEVICES_OPT_URL
)
FIELDS = ("Path", "Enabled", "Offset")
DEVICE_FIELDS = ("Manufacturer", "Device", "Name", "EraseBeforeDownload")


def read(report, ide, url):
    try:
        value = ide.getOptionStr(url)
        report.line(f"  OK  {url} -> {value!r}")
        return value
    except Exception as exc:  # noqa: BLE001 - a probe reports everything
        report.line(f"  !!  {url} -> {str(exc).splitlines()[0][:160]}")
        return None


def size(report, ide, url):
    try:
        n = ide.getDynamicOptionSize(url)
        report.line(f"  OK  getDynamicOptionSize({url}) -> {n}")
        return n
    except Exception as exc:  # noqa: BLE001
        report.line(f"  !!  getDynamicOptionSize({url}) -> {str(exc).splitlines()[0][:160]}")
        return None


def main():
    args = base_args(__doc__).parse_args()
    report = Report("19_umi1_paths")
    try:
        ic, cmgr = connect(report, args.instance)
        ide = ic.CIDEController(cmgr)
        report.section("winIDEA")
        for getter in ("getWinIDEAVersion",):
            try:
                report.line(f"{getter} -> {getattr(ide, getter)()}")
            except Exception as exc:  # noqa: BLE001
                report.line(f"{getter} !! {exc}")
        for root in ROOTS:
            report.section(root)
            devices = size(report, ide, root)
            for field in DEVICE_FIELDS:
                read(report, ide, f"{root}[0].{field}")
            rows = size(report, ide, f"{root}[0].DownloadFiles")
            for i in range(rows if isinstance(rows, int) and 0 < rows <= 10 else 4):
                for field in FIELDS:
                    read(report, ide, f"{root}[0].DownloadFiles[{i}].{field}")
            if devices is None and rows is None:
                report.line("  (root not resolved)")
        report.section("symbol files (the path WFlash already uses)")
        apps = size(report, ide, "/IDE/System.Debug.Applications")
        for a in range(apps if isinstance(apps, int) and 0 < apps <= 10 else 3):
            read(report, ide, f"/IDE/System.Debug.Applications[{a}].Name")
            files = size(report, ide, f"/IDE/System.Debug.Applications[{a}].SymbolFiles.File")
            for f in range(files if isinstance(files, int) and 0 < files <= 10 else 2):
                read(report, ide, f"/IDE/System.Debug.Applications[{a}].SymbolFiles.File[{f}].Path")
        report.section("storage devices")
        try:
            names = ic.StrVector()
            ic.CStorageDeviceFactory.getDeviceNames(cmgr, names)
            report.line(f"CStorageDeviceFactory.getDeviceNames -> {list(names)}")
        except Exception as exc:  # noqa: BLE001
            report.line(f"CStorageDeviceFactory.getDeviceNames !! {exc}")
    except Exception:  # noqa: BLE001
        report.exc("fatal")
    report.line(f"Saved: {report.path}")


if __name__ == "__main__":
    main()
