"""Spike 02: tìm nơi workspace lưu đường dẫn .s3/.elf.

(a) Parse file workspace (.xjrf, XML) và in mọi element chứa đường dẫn file.
(b) Thử đọc một số option URL ứng viên qua CIDEController.getOptionStr,
    gồm cả URL suy ra từ đường dẫn XML ở bước (a).
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from _common import Report, base_args, connect, try_call

FILE_RE = re.compile(r"\.(elf|s3|srec|s19|mot|hex)\b", re.IGNORECASE)

CANDIDATE_URLS = [
    "/IDE/Debug.DownloadFiles.File[0].Path",
    "/IDE/Debug.DownloadFiles.File[0].Options.Path",
    "/IDE/System.Debug.Applications[0].Name",
    "/IDE/System.Debug.Applications[0].SymbolFiles.File[0].Path",
    "/IDE/System.Debug.Applications[1].SymbolFiles.File[0].Path",
    "/IDE/System.Debug.SoCs[0].Name",
    "/IDE/System.Debug.SoCs[0].DLFs_Program.File[0].Path",
    "/IDE/System.Debug.SoCs[0].Cores[0].Name",
]


def walk(elem, path, out):
    counts = {}
    for child in elem:
        counts[child.tag] = counts.get(child.tag, 0) + 1
    seen = {}
    for child in elem:
        idx = seen.get(child.tag, 0)
        seen[child.tag] = idx + 1
        seg = f"{child.tag}[{idx}]" if counts[child.tag] > 1 else child.tag
        child_path = f"{path}.{seg}" if path else seg
        texts = [child.text or ""] + list(child.attrib.values())
        if any(FILE_RE.search(t) for t in texts):
            out.append((child_path, child.text, dict(child.attrib)))
        walk(child, child_path, out)


def main() -> None:
    parser = base_args(__doc__)
    parser.add_argument("--workspace", help="Đường dẫn file .xjrf (mặc định: lấy từ winIDEA)")
    parser.add_argument("--url", action="append", default=[], help="Option URL bổ sung để thử")
    args = parser.parse_args()
    report = Report("02_dump_options")
    try:
        ic, cmgr = connect(report, args.instance)
        ide = ic.CIDEController(cmgr)
        ws = args.workspace
        if not ws:
            const = getattr(ic.CIDEController, "WORKSPACE_FILE_NAME", None)
            ws = try_call(report, "ide.getPath(WORKSPACE_FILE_NAME)", lambda: ide.getPath(const)) if const else None

        derived = []
        report.section(f"workspace XML: {ws}")
        if ws and Path(ws).is_file():
            root = ET.parse(ws).getroot()
            report.line(f"root tag: {root.tag}")
            report.line("top-level children: " + ", ".join(c.tag for c in root))
            hits = []
            walk(root, "", hits)
            for p, text, attrib in hits:
                report.line(f"{p} = {text!r} {attrib}")
                derived.append("/IDE/" + p)
                derived.append("/IDE/" + p.split(".", 1)[-1])
        else:
            report.line("workspace file not found; pass --workspace")

        report.section("probe option URLs")
        for url in CANDIDATE_URLS + args.url + derived:
            try_call(report, f"getOptionStr {url}", lambda u=url: ide.getOptionStr(u))
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
