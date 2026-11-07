"""Spike 13: liệt kê mọi option của thiết bị external flash. CHỈ ĐỌC, không flash, không gọi read.

Đọc file workspace (.xjrf) để lấy tên các field của thiết bị trong UMIConfig, rồi đọc từng field bằng
getOptionStr. Mục tiêu: tìm option của "Mass erase before download". Không ghi option nào và không
dùng getOptionJSON. Chỉ dùng thư viện chuẩn, nên chạy được bằng Python đi kèm winIDEA.
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from _common import Report, base_args, connect, try_call

DEVICES = "/iOPEN/UMIConfig.Devices.Devices"
KEYWORDS = ("erase", "mass", "program", "verify", "hash", "compress", "download")
LIST_ITEM = re.compile(r"^__\.(\d+)$")


def find_device(root):
    """Return the first element under UMIConfig with a DownloadFiles child."""
    for config in root.iter("UMIConfig"):
        for element in config.iter():
            if element.find("DownloadFiles") is not None:
                return element
    return None


def leaves(element, prefix=""):
    """Yield (option path, text) for the leaves, skipping the file rows."""
    for child in element:
        if child.tag == "DownloadFiles":
            continue
        item = LIST_ITEM.match(child.tag)
        if item:
            path = f"{prefix.rstrip('.')}[{item.group(1)}]."
        else:
            path = f"{prefix}{child.tag}."
        if len(child):
            yield from leaves(child, path)
        else:
            yield path.rstrip("."), (child.text or "").strip()


def main() -> None:
    parser = base_args(__doc__)
    parser.add_argument("--workspace", help="Đường dẫn file .xjrf (mặc định: lấy từ winIDEA)")
    parser.add_argument("--device-index", type=int, default=0)
    args = parser.parse_args()
    report = Report("13_device_options")
    try:
        ic, cmgr = connect(report, args.instance)
        report.line(f"module version: {try_call(report, 'getModuleVersion', ic.getModuleVersion)}")
        ide = ic.CIDEController(cmgr)
        workspace = args.workspace or ide.getPath(ic.CIDEController.WORKSPACE_FILE_NAME)
        report.line(f"workspace: {workspace}")
        device = find_device(ET.parse(workspace).getroot())
        if device is None:
            report.line("device element not found in workspace XML -> stop")
            return
        report.line(f"device element: {device.tag}, attributes {device.attrib}")
        report.section("device fields (XML value, then getOptionStr)")
        dev = f"{DEVICES}[{args.device_index}]"
        interesting = []
        for path, text in leaves(device):
            report.line(f"{path} = {text!r}")
            value = try_call(report, f"    {dev}.{path}", lambda p=path: ide.getOptionStr(f"{dev}.{p}"))
            if any(word in path.lower() for word in KEYWORDS):
                interesting.append((path, text, value))
        report.section("fields matching keywords")
        for path, text, value in interesting:
            report.line(f"{path}: xml={text!r} option={value!r}")
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
