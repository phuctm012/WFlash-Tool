"""Spike 11: tìm ví dụ và tài liệu của isystem.connect trên máy. KHÔNG kết nối winIDEA, KHÔNG đụng ECU.

Docstring của isystem.connect nhắc tới test_write.py, test_flush.py, test_begin_program.py...
Script quét các thư mục, chép file ví dụ tìm được vào results/examples/ để gửi lại, và liệt kê tài liệu.
"""
import argparse
import shutil
import sys
from pathlib import Path

from _common import OUT_DIR, Report

DEFAULT_ROOTS = [r"C:\Data\_Devtools\Winidea408"]
NAMES = {
    "test_write.py", "test_flush.py", "test_erase.py", "test_verify.py", "test_read.py", "test_invoke.py",
    "test_begin_program.py", "test_begin_prepare.py", "test_get_device_index.py", "test_storage_write.py",
    "test_storage_flush.py", "test_storage_erase.py", "test_storage_verify.py", "test_storage_get_devices_names.py",
}
KEYWORDS = ("CUMIController", "CStorageDevice", "wProgCache", "begin_program", "getMenuStructure", "ide.invoke(")
DOC_SUFFIXES = {".chm", ".pdf", ".html", ".htm"}
DOC_WORDS = ("sdk", "isystem", "connect", "umi", "python", "api", "script", "flash")
SKIP_DIRS = {"__pycache__", ".git"}
MAX_BYTES = 2_000_000
MAX_COPIES = 300
MAX_DOCS = 200


def mentions(path):
    try:
        if path.stat().st_size > MAX_BYTES:
            return []
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [k for k in KEYWORDS if k in text]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", help="Thư mục cần quét (lặp lại được)")
    args = parser.parse_args()
    report = Report("11_find_examples")
    try:
        roots = [Path(r) for r in (args.root or DEFAULT_ROOTS)]
        # site-packages of the running interpreter, where isystem.connect is installed.
        roots.append(Path(sys.prefix) / "Lib" / "site-packages" / "isystem")
        target = OUT_DIR / "examples"
        target.mkdir(exist_ok=True)
        copies = docs = 0
        for root in roots:
            report.section(f"root: {root} exists={root.is_dir()}")
            for path in sorted(root.rglob("*") if root.is_dir() else []):
                if not path.is_file() or SKIP_DIRS & set(path.parts):
                    continue
                suffix = path.suffix.lower()
                if suffix == ".py":
                    hits = mentions(path)
                    if (path.name in NAMES or hits) and path.name != "connect.py" and copies < MAX_COPIES:
                        copies += 1
                        shutil.copy2(path, target / f"{copies:03d}_{path.name}")
                        report.line(f"copied {copies:03d}: {path}  {hits}")
                elif suffix in DOC_SUFFIXES and docs < MAX_DOCS:
                    if any(word in path.name.lower() for word in DOC_WORDS):
                        docs += 1
                        report.line(f"doc: {path} ({path.stat().st_size} bytes)")
        report.line(f"copied: {copies}, docs listed: {docs}")
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
