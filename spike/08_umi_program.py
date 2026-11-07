"""Spike 08: program external flash (Winbond) bằng CUMIController.write(). GHI VÀO FLASH.

CẢNH BÁO: với 2 file đang tick, write() xóa trước MỖI file; user báo chip bị xóa hết và ECU không
chạy được (2026-11-07). Script từ chối chạy trừ khi có đúng 1 dòng đang tick.
Script hỏi xác nhận trước khi ghi, đo thời gian, rồi reset target.

Thiết bị: --device-name, hoặc tên từ CStorageDeviceFactory.getDeviceNames. Nếu không có tên
(thiết bị Winbond có Name rỗng), dùng --device-index (mặc định 0). Script chỉ ghi khi thiết bị
ở chỉ số đó đang bật và có model đúng --expect-device.
Program mode lấy từ module (tên chứa 'wProgDevice'); không tìm thấy thì dừng, không đoán.
"""
import threading
import time

from _common import Report, base_args, connect, try_call

DEVICES = "/iOPEN/UMIConfig.Devices.Devices"


def find_prog_device(ic):
    for name in sorted(dir(ic)):
        if name.endswith("wProgDevice"):
            return name, getattr(ic, name)
    holder = getattr(ic, "IConnectUMI", None)
    if holder is not None and hasattr(holder, "wProgDevice"):
        return "IConnectUMI.wProgDevice", holder.wProgDevice
    return None, None


def main() -> None:
    parser = base_args(__doc__)
    parser.add_argument("--device-name", help="Tên thiết bị UMI (mặc định: thiết bị đầu tiên tìm được)")
    parser.add_argument("--device-index", type=int, default=0, help="Chỉ số thiết bị khi không có tên (mặc định 0)")
    parser.add_argument("--expect-device", default="W25Q64JW", help="Model thiết bị phải khớp (mặc định W25Q64JW)")
    parser.add_argument("--yes", action="store_true", help="Không hỏi xác nhận")
    args = parser.parse_args()
    report = Report("08_umi_program")
    try:
        ic, cmgr = connect(report, args.instance)
        ide = ic.CIDEController(cmgr)
        umi = ic.CUMIController(cmgr)

        report.section("device")
        names = ic.StrVector()
        try_call(report, "getDeviceNames", lambda: ic.CStorageDeviceFactory.getDeviceNames(cmgr, names))
        report.line(f"device names: {list(names)}")
        try_call(report, "getDynamicOptionSize Devices", lambda: ide.getDynamicOptionSize(DEVICES))
        for probe in ("W25Q64JW", ""):
            try_call(report, f"umi.getDeviceIndex({probe!r})", lambda n=probe: umi.getDeviceIndex(n))

        name = args.device_name or (names[0] if len(names) else None)
        if name is not None:
            index = try_call(report, f"umi.getDeviceIndex({name!r})", lambda: umi.getDeviceIndex(name))
            if index is None or index < 0:
                report.line("device name not found -> stop")
                return
        else:
            # Spike 07: the Winbond entry has an empty Name, so getDeviceNames returns nothing.
            index = args.device_index
            report.line(f"no device name -> using device index {index}")

        dev = f"{DEVICES}[{index}]"
        model = try_call(report, f"{dev}.Device", lambda: ide.getOptionStr(f"{dev}.Device"))
        enabled = try_call(report, f"{dev}.Enabled", lambda: ide.getOptionStr(f"{dev}.Enabled"))
        if model != args.expect_device or enabled != "true":
            report.line(f"expected an enabled {args.expect_device!r} at index {index} -> stop")
            return

        mode_name, mode = find_prog_device(ic)
        report.line(f"program mode: {mode_name} = {mode!r}")
        if mode is None:
            report.line("program mode not found -> stop")
            return

        report.section("files configured on this device")
        enabled_rows = 0
        for i in range(ide.getDynamicOptionSize(f"{dev}.DownloadFiles")):
            row = f"{dev}.DownloadFiles[{i}]"
            enabled_rows += try_call(report, f"[{i}] Enabled", lambda r=row: ide.getOptionStr(f"{r}.Enabled")) == "true"
            try_call(report, f"[{i}] Offset", lambda r=row: ide.getOptionStr(f"{r}.Offset"))
            try_call(report, f"[{i}] Path", lambda r=row: ide.getOptionStr(f"{r}.Path"))

        # 2026-11-07: with two rows enabled, write() erased before each file. The user reports the
        # whole chip ended up erased and the ECU no longer ran. Never run it with more than one row.
        if enabled_rows != 1:
            report.line(f"{enabled_rows} rows enabled, this script needs exactly 1 -> stop, nothing written")
            return

        if not args.yes:
            answer = input(f"Program device {model} (index {index}) now? This WRITES the Winbond flash. Type YES: ")
            if answer.strip() != "YES":
                report.line("cancelled by user")
                return

        report.section("umi.write")
        done = threading.Event()
        t0 = time.monotonic()

        def ticker():
            while not done.wait(5):
                report.line(f"... still programming, {time.monotonic() - t0:.0f}s")

        threading.Thread(target=ticker, daemon=True).start()
        try:
            result = umi.write(index, mode)
            report.line(f"umi.write -> {result!r}")
        except Exception:
            report.exc("umi.write")
            try_call(report, "umi.getLastError", umi.getLastError)
        finally:
            done.set()
        report.line(f"elapsed: {time.monotonic() - t0:.1f}s")

        report.section("reset after program")
        debug = ic.CDebugFacade(cmgr)
        try_call(report, "debug.reset", debug.reset)
        status = try_call(report, "getCPUStatus", debug.getCPUStatus)
        if status is not None:
            try_call(report, "status.isStopped", status.isStopped)
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
