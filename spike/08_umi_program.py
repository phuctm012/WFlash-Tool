"""Spike 08: program external flash (Winbond) bằng CUMIController.write(). GHI VÀO FLASH.

Giống bấm tay Hardware -> Winbond ... -> Program: ghi các file đang được tick trong
Download Files của thiết bị. Script hỏi xác nhận trước khi ghi, đo thời gian, rồi reset target.

Tên thiết bị lấy từ CStorageDeviceFactory.getDeviceNames (hoặc --device-name).
Program mode lấy từ module (tên chứa 'wProgDevice'); không tìm thấy thì dừng, không đoán.
"""
import threading
import time

from _common import Report, base_args, connect, try_call


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
    parser.add_argument("--yes", action="store_true", help="Không hỏi xác nhận")
    args = parser.parse_args()
    report = Report("08_umi_program")
    try:
        ic, cmgr = connect(report, args.instance)
        ide = ic.CIDEController(cmgr)

        report.section("files that will be programmed")
        for i in range(32):
            url = f"/iOPEN/UMIConfig.Devices.Devices[0].DownloadFiles[{i}].Path"
            if try_call(report, url, lambda u=url: ide.getOptionStr(u)) is None:
                break

        report.section("device")
        name = args.device_name
        if name is None:
            names = ic.StrVector()
            try_call(report, "getDeviceNames", lambda: ic.CStorageDeviceFactory.getDeviceNames(cmgr, names))
            report.line(f"device names: {list(names)}")
            if not len(names):
                report.line("no device found -> stop")
                return
            name = names[0]
        umi = ic.CUMIController(cmgr)
        index = try_call(report, f"umi.getDeviceIndex({name!r})", lambda: umi.getDeviceIndex(name))
        mode_name, mode = find_prog_device(ic)
        report.line(f"program mode: {mode_name} = {mode!r}")
        if index is None or mode is None:
            report.line("device index or program mode not found -> stop (gửi kết quả 07 để mình xem)")
            return

        if not args.yes:
            answer = input(f"Program device {name!r} now? This WRITES the Winbond flash. Type YES: ")
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
