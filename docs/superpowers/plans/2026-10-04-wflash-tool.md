# WFlash Tool (Plan 1: Spike + Core + GUI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây dựng WFlash: tool PySide6 duyệt GitLab artifact, map file `.s3`/`.elf` theo profile, và điều phối flash qua một `WinIDEAAdapter` (fake adapter trong plan này), kèm log panel và debug bundle; đồng thời cung cấp script spike để xác minh API `isystem.connect` trên Windows.

**Architecture:** Package `wflash/core` (không phụ thuộc Qt) chứa GitLab client, cache, profile, file matcher, adapter protocol + fake, workflow, logging và debug bundle. Package `wflash/gui` chứa các widget PySide6, mọi thao tác chậm chạy qua `Worker` trên `QThreadPool`. `RealWinIDEAAdapter` thuộc **Plan 2**, viết sau khi có kết quả spike (Task 1).

**Tech Stack:** Python ≥3.11, PySide6, requests, pydantic v2, PyYAML, keyring, pytest, pytest-qt, responses, PyInstaller.

**Spec:** `docs/superpowers/specs/2026-10-04-wflash-tool-design.md`

## Global Constraints

- Python `>=3.11`. Trên macOS dev dùng `/Users/tranminhphuc/miniforge3/bin/python3.13`.
- Virtualenv đặt **ngoài** thư mục OneDrive: `~/.venvs/wflash` (tránh OneDrive sync hàng nghìn file). Mọi lệnh `pytest`/`python` trong plan chạy trong venv này, từ thư mục gốc repo.
- winIDEA mục tiêu: 9.21.x. Chỉ adapter thật (Plan 2) và script trong `spike/` được import `isystem.connect`.
- `wflash/core/**` **không** import PySide6.
- Text hiển thị trên GUI bằng tiếng Anh; tài liệu (README, spike/README) bằng tiếng Việt.
- Logger: `logging.getLogger("wflash.<module>")` qua `get_logger("<module>")`. Không bao giờ ghi token GitLab chưa che; mọi handler dùng `RedactingFormatter`.
- Mọi lỗi nghiệp vụ kế thừa `WFlashError` và có thuộc tính `hint`.
- Test GUI chạy với `QT_QPA_PLATFORM=offscreen` (đặt trong `tests/conftest.py`).
- Mỗi commit kết thúc bằng trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (các lệnh commit bên dưới dùng `-m` thứ hai cho trailer).
- Không commit thay đổi mode của `README.md` có sẵn trừ khi task yêu cầu sửa README.

## File Structure

```
pyproject.toml                       # metadata, deps, pytest config
.gitignore
wflash/__init__.py                   # __version__
wflash/__main__.py                   # python -m wflash
wflash/main.py                       # CLI args, logging, excepthooks, khởi động GUI
wflash/core/__init__.py
wflash/core/errors.py                # WFlashError + lỗi theo tầng
wflash/core/cancel.py                # CancelToken
wflash/core/logging_setup.py         # file log, redaction, verbose
wflash/core/profile.py               # Profile (pydantic), load_profile, list_profiles
wflash/core/file_matcher.py          # MappingRow, build_mapping
wflash/core/artifact_cache.py        # ArtifactCache
wflash/core/gitlab_client.py         # GitLabClient (requests)
wflash/core/settings.py              # AppSettings (JSON) + token qua keyring
wflash/core/winidea_adapter.py       # Protocol, dataclass, create_adapter
wflash/core/fake_adapter.py          # FakeWinIDEAAdapter
wflash/core/debug_bundle.py          # DebugContext, create_debug_bundle
wflash/core/flash_workflow.py        # FlashWorkflow, Step, FlashRequest
wflash/gui/__init__.py
wflash/gui/main_window.ui            # Designer — nguồn sự thật của layout
wflash/gui/ui_main_window.py         # sinh bởi pyside6-uic, KHÔNG sửa tay
wflash/gui/main_window.py            # MainWindow ghép từ các mixin, chung một self.ui
wflash/gui/gitlab_browser.py         # GitlabBrowserMixin (ref → pipeline → job → download)
wflash/gui/mapping_table.py          # MappingTableMixin
wflash/gui/flash_mixin.py            # FlashMixin (Flash/Cancel, trạng thái từng step)
wflash/gui/log_panel.py              # LogPanelMixin + QtLogHandler
wflash/gui/settings_dialog.py        # SettingsDialog (+ .ui riêng)
wflash/gui/workers.py                # Worker, WorkerContext (QThreadPool)
profiles/saf85xx_example.yaml
spike/README.md, spike/_common.py, spike/01_connect.py … spike/05_reset.py
wflash.spec                          # PyInstaller
scripts/build_windows.bat
tests/conftest.py + tests/test_*.py
```

GUI theo kiến trúc **Designer-first + mixin** (giống project SFlash): `main_window.ui` là nguồn sự thật, `ui_main_window.py` sinh bằng `pyside6-uic` và không sửa tay, `MainWindow` ghép từ các mixin dùng chung một `self.ui`. Quyết định này thay cho §4 của spec và cho danh sách `gui/*.py` viết tay ở các bản plan trước; chi tiết trong `CLAUDE.md`, mục "GUI: Designer-first". Các task GUI (Task 7+) phải viết theo cấu trúc trên.

Spec ghi `python-gitlab`; plan dùng `requests` trực tiếp (ít dependency, dễ mock bằng `responses`). Spec ghi `ProgramEntry`/`AppEntry`; plan gộp thành `FileEntry(name, path)`. Spec đã được cập nhật theo hai điểm này.

---

### Task 1: Spike scripts cho winIDEA (Phase 0)

Mục tiêu: script độc lập để user chạy trên Windows, ghi kết quả vào `spike/results/*.txt`. API `isystem.connect` dùng ở đây là phỏng đoán có kiểm soát: mọi lời gọi chưa chắc chắn đều bọc try/except và ghi lỗi vào report thay vì dừng script. Không có unit test (chạy được chỉ trên Windows có winIDEA); kiểm tra bằng `py_compile`.

**Files:**
- Create: `spike/README.md`, `spike/requirements.txt`, `spike/_common.py`, `spike/01_connect.py`, `spike/02_dump_options.py`, `spike/03_set_paths.py`, `spike/04_download.py`, `spike/05_reset.py`
- Modify: `.gitignore` (tạo mới nếu chưa có)

**Interfaces:**
- Consumes: không.
- Produces: file kết quả `spike/results/<script>_<timestamp>.txt` dùng để viết Plan 2.

- [ ] **Step 1: Tạo `.gitignore`**

```gitignore
__pycache__/
*.pyc
.venv/
build/
dist/
*.egg-info/
.pytest_cache/
spike/results/
```

- [ ] **Step 2: Tạo `spike/requirements.txt`**

```text
# Cài đúng bản khớp winIDEA 9.21 (xem pip index versions isystem.connect)
isystem.connect>=9.21,<9.22
```

- [ ] **Step 3: Tạo `spike/_common.py`**

```python
"""Shared helpers for spike scripts: tee output to a result file and connect to winIDEA."""
from __future__ import annotations

import argparse
import datetime
import importlib.metadata
import pathlib
import platform
import sys
import traceback

OUT_DIR = pathlib.Path(__file__).parent / "results"


class Report:
    def __init__(self, name: str) -> None:
        OUT_DIR.mkdir(exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = OUT_DIR / f"{name}_{stamp}.txt"
        self._fh = self.path.open("w", encoding="utf-8")
        self.line(f"# {name}  {stamp}")
        self.line(f"python={sys.version}")
        self.line(f"platform={platform.platform()}")

    def line(self, text: str = "") -> None:
        print(text)
        self._fh.write(text + "\n")
        self._fh.flush()

    def section(self, title: str) -> None:
        self.line()
        self.line(f"== {title} ==")

    def exc(self, context: str) -> None:
        self.line(f"!! {context}:\n{traceback.format_exc()}")

    def close(self) -> None:
        self.line()
        self.line(f"Saved: {self.path}")
        self._fh.close()


def base_args(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--instance", help="winIDEA instance id (xem output của 01_connect.py)")
    return parser


def try_call(report: Report, label: str, fn):
    """Call fn(), log result or exception, return result or None."""
    try:
        value = fn()
    except Exception:
        report.exc(label)
        return None
    report.line(f"{label} -> {value!r}")
    return value


def connect(report: Report, instance_id: str | None):
    """Return (ic module, ConnectionMgr). Raises if connect fails."""
    import isystem.connect as ic

    report.section("isystem.connect")
    try:
        report.line(f"package version: {importlib.metadata.version('isystem.connect')}")
    except importlib.metadata.PackageNotFoundError:
        report.line("package version: unknown")
    report.line(f"module file: {getattr(ic, '__file__', '?')}")

    cmgr = ic.ConnectionMgr()

    report.section("instances")
    instances = []
    try:
        vec = ic.VectorWinIDEAInstanceInfo()
        cmgr.enumerateWinIDEAInstances("", ic.CConnectionConfig(), vec)
        for inst in vec:
            info = {
                "id": try_call(report, "  getInstanceId", inst.getInstanceId),
                "workspace": try_call(report, "  getWorkspace", inst.getWorkspace),
                "port": try_call(report, "  getTcpPort", inst.getTcpPort),
            }
            instances.append(info)
            report.line(f"instance: {info}")
    except Exception:
        report.exc("enumerateWinIDEAInstances")

    if instance_id is None and len(instances) == 1:
        instance_id = instances[0]["id"]

    report.section("connect")
    if instance_id:
        report.line(f"connecting to instance {instance_id!r}")
        try:
            cfg = ic.CConnectionConfig()
            cfg.instanceId(instance_id)
            cmgr.connect(cfg)
        except Exception:
            report.exc("connect(cfg.instanceId)")
            report.line("fallback: cmgr.connect()")
            cmgr.connect()
    else:
        report.line("no/many instances -> cmgr.connect() (most recent winIDEA)")
        cmgr.connect()
    report.line(f"isAttached: {try_call(report, 'cmgr.isAttached', cmgr.isAttached)}")
    return ic, cmgr
```

- [ ] **Step 4: Tạo `spike/01_connect.py`**

```python
"""Spike 01: liệt kê instance winIDEA, connect, in version và workspace."""
from _common import Report, base_args, connect, try_call


def main() -> None:
    args = base_args(__doc__).parse_args()
    report = Report("01_connect")
    try:
        ic, cmgr = connect(report, args.instance)
        ide = ic.CIDEController(cmgr)
        report.section("winIDEA info")
        try_call(report, "ide.getWinIDEAVersion", lambda: str(ide.getWinIDEAVersion().toString()))
        try_call(report, "cmgr.getWinIDEAVersion", lambda: str(cmgr.getWinIDEAVersion()))
        for name in ("WORKSPACE_DIR", "WORKSPACE_FILE_NAME", "WINIDEA_EXE_DIR"):
            const = getattr(ic.CIDEController, name, None)
            if const is None:
                report.line(f"CIDEController.{name}: not available")
                continue
            try_call(report, f"ide.getPath({name})", lambda c=const: ide.getPath(c))
        report.section("API surface")
        for cls in ("CIDEController", "CLoaderController", "CDebugFacade", "CExecutionController"):
            obj = getattr(ic, cls, None)
            members = sorted(m for m in dir(obj) if not m.startswith("_")) if obj else []
            report.line(f"{cls}: {', '.join(members)}")
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Tạo `spike/02_dump_options.py`**

```python
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
```

- [ ] **Step 6: Tạo `spike/03_set_paths.py`**

```python
"""Spike 03: đổi giá trị một option URL, đọc lại, rồi khôi phục giá trị cũ."""
from _common import Report, base_args, connect, try_call


def main() -> None:
    parser = base_args(__doc__)
    parser.add_argument("--url", required=True, action="append", help="Option URL (từ kết quả 02)")
    parser.add_argument("--new-path", required=True, action="append", help="Giá trị mới, cùng thứ tự với --url")
    parser.add_argument("--keep", action="store_true", help="Không khôi phục giá trị cũ")
    args = parser.parse_args()
    report = Report("03_set_paths")
    try:
        ic, cmgr = connect(report, args.instance)
        ide = ic.CIDEController(cmgr)
        for url, new in zip(args.url, args.new_path):
            report.section(url)
            old = try_call(report, "read old", lambda: ide.getOptionStr(url))
            try_call(report, "setOption(new)", lambda: ide.setOption(url, new))
            try_call(report, "read back", lambda: ide.getOptionStr(url))
            if not args.keep and old is not None:
                try_call(report, "restore old", lambda: ide.setOption(url, old))
                try_call(report, "read after restore", lambda: ide.getOptionStr(url))
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Tạo `spike/04_download.py`**

```python
"""Spike 04: chạy download với cấu hình hiện tại của workspace, đo thời gian."""
import threading
import time

from _common import Report, base_args, connect, try_call


def main() -> None:
    parser = base_args(__doc__)
    parser.add_argument("--facade", action="store_true", help="Dùng CDebugFacade.download() thay vì CLoaderController")
    args = parser.parse_args()
    report = Report("04_download")
    try:
        ic, cmgr = connect(report, args.instance)
        done = threading.Event()
        t0 = time.monotonic()

        def ticker():
            while not done.wait(5):
                report.line(f"... still downloading, {time.monotonic() - t0:.0f}s")

        threading.Thread(target=ticker, daemon=True).start()
        report.section("download")
        try:
            if args.facade:
                ic.CDebugFacade(cmgr).download()
            else:
                ic.CLoaderController(cmgr).download()
            report.line("download() returned normally")
        except Exception:
            report.exc("download")
        finally:
            done.set()
        report.line(f"elapsed: {time.monotonic() - t0:.1f}s")

        report.section("CPU status after download")
        debug = ic.CDebugFacade(cmgr)
        status = try_call(report, "getCPUStatus", debug.getCPUStatus)
        if status is not None:
            for m in ("isStopped", "isRunning", "isReset", "toString"):
                if hasattr(status, m):
                    try_call(report, f"status.{m}", getattr(status, m))
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 8: Tạo `spike/05_reset.py`**

```python
"""Spike 05: reset target, kiểm tra trạng thái halted; tùy chọn chạy (--run)."""
from _common import Report, base_args, connect, try_call


def dump_status(report, debug, label):
    status = try_call(report, f"{label} getCPUStatus", debug.getCPUStatus)
    if status is None:
        return
    for m in ("isStopped", "isRunning", "isReset", "toString"):
        if hasattr(status, m):
            try_call(report, f"{label} status.{m}", getattr(status, m))


def main() -> None:
    parser = base_args(__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    report = Report("05_reset")
    try:
        ic, cmgr = connect(report, args.instance)
        debug = ic.CDebugFacade(cmgr)
        dump_status(report, debug, "before")
        try_call(report, "debug.reset", debug.reset)
        dump_status(report, debug, "after reset")
        if args.run:
            try_call(report, "debug.run", debug.run)
            dump_status(report, debug, "after run")
        report.section("multi-core probe")
        for name in ("getCoreIds", "getCores"):
            if hasattr(cmgr, name):
                try_call(report, f"cmgr.{name}", getattr(cmgr, name))
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 9: Tạo `spike/README.md`**

```markdown
# Spike winIDEA (chạy trên Windows)

Mục đích: xác minh API `isystem.connect` trên winIDEA 9.21 + workspace SAF85xx trước khi viết adapter thật.

## Chuẩn bị

1. Cài Python 3.11+ (64-bit) trên Windows.
2. `py -m venv %USERPROFILE%\.venvs\wflash-spike`
3. `%USERPROFILE%\.venvs\wflash-spike\Scripts\activate`
4. `pip install -r spike\requirements.txt`
   (nếu bản pip không khớp, dùng bản Python SDK đi kèm thư mục cài winIDEA)
5. Mở winIDEA với workspace SAF85xx, kiểm tra flash tay hoạt động.

## Chạy theo thứ tự (trong thư mục `spike`)

| Lệnh | Tác dụng | Có thay đổi target/workspace? |
|---|---|---|
| `python 01_connect.py` | liệt kê instance, version, API | Không |
| `python 02_dump_options.py` | tìm option chứa đường dẫn .s3/.elf | Không |
| `python 03_set_paths.py --url <URL> --new-path C:\tmp\test.elf` | đổi path rồi tự khôi phục | Đổi tạm, tự khôi phục |
| `python 04_download.py` | flash bằng cấu hình hiện tại, đo thời gian | **Có: flash ECU** |
| `python 05_reset.py` | reset + halt | **Có: reset ECU** |

- Nhiều instance winIDEA: thêm `--instance <id>` (id lấy từ output 01).
- URL cho bước 03 lấy từ các dòng `getOptionStr ... -> '...elf'` thành công trong output 02.

## Gửi kết quả

Nén thư mục `spike\results\` và gửi lại.
```

- [ ] **Step 10: Kiểm tra cú pháp**

Run: `~/.venvs/wflash/bin/python -m py_compile spike/_common.py spike/0*.py` (nếu venv chưa có, dùng `/Users/tranminhphuc/miniforge3/bin/python3.13 -m py_compile ...`)
Expected: không có output, exit code 0.

- [ ] **Step 11: Commit**

```bash
git add .gitignore spike/
git commit -m "feat(spike): add winIDEA isystem.connect spike scripts" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Scaffold project, errors, CancelToken

**Files:**
- Create: `pyproject.toml`, `wflash/__init__.py`, `wflash/core/__init__.py`, `wflash/gui/__init__.py`, `wflash/core/errors.py`, `wflash/core/cancel.py`, `tests/__init__.py`, `tests/conftest.py`, `tests/test_errors_cancel.py`

**Interfaces:**
- Produces:
  - `wflash.__version__: str`
  - `WFlashError(message: str, hint: str = "")` với `.hint`; subclasses `ProfileError, GitLabError, ArtifactError, MappingError, WinIDEAError, FlashError, CancelledError`
  - `CancelToken`: `cancel()`, `cancelled: bool`, `raise_if_cancelled()`, `wait(timeout: float) -> bool`

- [ ] **Step 1: Tạo venv và `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "wflash"
version = "0.1.0"
description = "Flash SAF85xx ECU via winIDEA from GitLab artifacts"
requires-python = ">=3.11"
dependencies = [
    "PySide6>=6.6",
    "requests>=2.31",
    "pydantic>=2.5",
    "PyYAML>=6.0",
    "keyring>=24",
]

[project.optional-dependencies]
winidea = ["isystem.connect>=9.21,<9.22; sys_platform == 'win32'"]
dev = ["pytest>=8", "pytest-qt>=4.4", "responses>=0.25", "pyinstaller>=6.3"]

[project.scripts]
wflash = "wflash.main:main"

[tool.setuptools.packages.find]
include = ["wflash*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
qt_api = "pyside6"
```

Run:
```bash
/Users/tranminhphuc/miniforge3/bin/python3.13 -m venv ~/.venvs/wflash
~/.venvs/wflash/bin/pip install -e ".[dev]"
```
Expected: cài thành công (dòng cuối `Successfully installed ... wflash-0.1.0`).

- [ ] **Step 2: Tạo package files**

`wflash/__init__.py`:
```python
"""WFlash: flash ECU via winIDEA from GitLab artifacts."""
__version__ = "0.1.0"
```

`wflash/core/__init__.py`, `wflash/gui/__init__.py`, `tests/__init__.py`: file rỗng.

`tests/conftest.py`:
```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

- [ ] **Step 3: Viết test fail `tests/test_errors_cancel.py`**

```python
import pytest

from wflash.core.cancel import CancelToken
from wflash.core.errors import (
    ArtifactError,
    CancelledError,
    FlashError,
    GitLabError,
    MappingError,
    ProfileError,
    WFlashError,
    WinIDEAError,
)


def test_error_uses_default_hint():
    err = GitLabError("boom")
    assert str(err) == "boom"
    assert err.hint == GitLabError.default_hint
    assert err.hint


def test_error_custom_hint_overrides_default():
    assert MappingError("x", hint="do this").hint == "do this"


@pytest.mark.parametrize(
    "cls",
    [ProfileError, GitLabError, ArtifactError, MappingError, WinIDEAError, FlashError, CancelledError],
)
def test_all_errors_subclass_base(cls):
    assert issubclass(cls, WFlashError)


def test_cancel_token_lifecycle():
    token = CancelToken()
    assert not token.cancelled
    token.raise_if_cancelled()
    assert token.wait(0.01) is False
    token.cancel()
    assert token.cancelled
    assert token.wait(0.01) is True
    with pytest.raises(CancelledError):
        token.raise_if_cancelled()
```

- [ ] **Step 4: Chạy test, xác nhận fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_errors_cancel.py -v`
Expected: FAIL / ERROR `ModuleNotFoundError: No module named 'wflash.core.cancel'`

- [ ] **Step 5: Implement `wflash/core/errors.py`**

```python
"""Exception hierarchy. Every error carries a short user-facing `hint`."""
from __future__ import annotations


class WFlashError(Exception):
    default_hint = ""

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.hint = hint or self.default_hint


class ProfileError(WFlashError):
    default_hint = "Check the profile YAML file."


class GitLabError(WFlashError):
    default_hint = "Check the GitLab URL, token and network connection in Settings."


class ArtifactError(WFlashError):
    default_hint = "Clear the cache and download the artifact again."


class MappingError(WFlashError):
    default_hint = "Check the file mapping table and the entry names in the profile."


class WinIDEAError(WFlashError):
    default_hint = "Make sure winIDEA is running with the correct workspace."


class FlashError(WFlashError):
    default_hint = "See the log for details and try a manual download in winIDEA."


class CancelledError(WFlashError):
    default_hint = ""
```

- [ ] **Step 6: Implement `wflash/core/cancel.py`**

```python
"""Cooperative cancellation shared between GUI and worker threads."""
from __future__ import annotations

import threading

from wflash.core.errors import CancelledError


class CancelToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise CancelledError("Operation cancelled by user")

    def wait(self, timeout: float) -> bool:
        """Sleep up to `timeout` seconds; return True as soon as cancelled."""
        return self._event.wait(timeout)
```

- [ ] **Step 7: Chạy test, xác nhận pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_errors_cancel.py -v`
Expected: 10 passed

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml wflash tests
git commit -m "feat(core): scaffold package with error hierarchy and CancelToken" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Logging với redaction

**Files:**
- Create: `wflash/core/logging_setup.py`
- Test: `tests/test_logging_setup.py`

**Interfaces:**
- Consumes: không.
- Produces:
  - `LOGGER_NAME = "wflash"`, `CALLS_LOGGER = "wflash.calls"`
  - `get_logger(name: str) -> logging.Logger` (trả về `wflash.<name>`)
  - `register_secret(value: str | None) -> None`, `clear_secrets() -> None`, `redact(text: str) -> str`
  - `RedactingFormatter(logging.Formatter)`, `LOG_FORMAT: str`, `DATE_FORMAT: str`
  - `default_log_dir() -> Path`
  - `setup_logging(log_dir: Path | None = None, keep: int = 20, verbose: bool = False) -> Path`
  - `set_verbose(enabled: bool) -> None` (logger `wflash.calls` DEBUG khi bật, INFO khi tắt)
  - `close_file_handler() -> None`

- [ ] **Step 1: Viết test fail `tests/test_logging_setup.py`**

```python
import logging
import os
import sys
import time

import pytest

from wflash.core import logging_setup as ls


@pytest.fixture(autouse=True)
def _cleanup():
    ls.clear_secrets()
    yield
    ls.close_file_handler()
    ls.clear_secrets()


def test_redact_private_token_header():
    text = "headers={'PRIVATE-TOKEN': 'glpat-abc123XYZ', 'Accept': 'json'}"
    out = ls.redact(text)
    assert "glpat-abc123XYZ" not in out
    assert "PRIVATE-TOKEN': '***" in out


def test_redact_registered_secret_anywhere():
    ls.register_secret("supersecretvalue")
    assert ls.redact("url?token=supersecretvalue&x=1") == "url?token=***&x=1"


def test_register_secret_ignores_short_or_empty():
    ls.register_secret("")
    ls.register_secret(None)
    ls.register_secret("ab")
    assert ls.redact("ab cd") == "ab cd"


def test_formatter_redacts_exception_text():
    ls.register_secret("tok-999999")
    fmt = ls.RedactingFormatter(ls.LOG_FORMAT, ls.DATE_FORMAT)
    try:
        raise RuntimeError("failed with tok-999999")
    except RuntimeError:
        record = logging.LogRecord("wflash.t", logging.ERROR, __file__, 1, "oops", None, sys.exc_info())
    out = fmt.format(record)
    assert "tok-999999" not in out
    assert "RuntimeError" in out


def test_setup_logging_writes_debug_to_file(tmp_path):
    path = ls.setup_logging(tmp_path)
    ls.register_secret("hidden-token-1")
    ls.get_logger("test").debug("debug line with hidden-token-1")
    ls.close_file_handler()
    content = path.read_text(encoding="utf-8")
    assert path.parent == tmp_path
    assert path.name.startswith("wflash_") and path.suffix == ".log"
    assert "debug line with ***" in content
    assert "hidden-token-1" not in content


def test_setup_logging_keeps_latest_files(tmp_path):
    for i in range(5):
        old = tmp_path / f"wflash_2020010{i}_000000.log"
        old.write_text("x")
        os.utime(old, (time.time() - 1000 + i, time.time() - 1000 + i))
    ls.setup_logging(tmp_path, keep=3)
    remaining = sorted(p.name for p in tmp_path.glob("wflash_*.log"))
    assert len(remaining) == 3
    assert "wflash_20200104_000000.log" in remaining
    assert "wflash_20200100_000000.log" not in remaining


def test_set_verbose_toggles_calls_logger():
    ls.set_verbose(True)
    assert logging.getLogger(ls.CALLS_LOGGER).isEnabledFor(logging.DEBUG)
    ls.set_verbose(False)
    assert not logging.getLogger(ls.CALLS_LOGGER).isEnabledFor(logging.DEBUG)


def test_default_log_dir_ends_with_wflash_component():
    assert "wflash" in str(ls.default_log_dir()).lower()
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_logging_setup.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'wflash.core.logging_setup'`

- [ ] **Step 3: Implement `wflash/core/logging_setup.py`**

```python
"""Logging setup: per-session DEBUG log file, secret redaction, verbose call logging."""
from __future__ import annotations

import datetime
import logging
import os
import re
import sys
from pathlib import Path

LOGGER_NAME = "wflash"
CALLS_LOGGER = "wflash.calls"
LOG_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-7s [%(threadName)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_SECRETS: set[str] = set()
_HEADER_RE = re.compile(r"(PRIVATE-TOKEN['\"]?\s*[:=]\s*['\"]?)([^'\"\s,}]+)", re.IGNORECASE)
_file_handler: logging.Handler | None = None


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def register_secret(value: str | None) -> None:
    if value and len(value) >= 4:
        _SECRETS.add(value)


def clear_secrets() -> None:
    _SECRETS.clear()


def redact(text: str) -> str:
    text = _HEADER_RE.sub(r"\1***", text)
    for secret in _SECRETS:
        text = text.replace(secret, "***")
    return text


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def default_log_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "WFlash" / "logs"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "WFlash"
    return Path.home() / ".local" / "state" / "wflash" / "logs"


def _prune(log_dir: Path, keep: int) -> None:
    files = sorted(log_dir.glob("wflash_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def close_file_handler() -> None:
    global _file_handler
    if _file_handler is not None:
        logging.getLogger(LOGGER_NAME).removeHandler(_file_handler)
        _file_handler.close()
        _file_handler = None


def set_verbose(enabled: bool) -> None:
    logging.getLogger(CALLS_LOGGER).setLevel(logging.DEBUG if enabled else logging.INFO)


def setup_logging(log_dir: Path | None = None, keep: int = 20, verbose: bool = False) -> Path:
    """Attach a fresh DEBUG file handler to the `wflash` logger and return the log path."""
    global _file_handler
    log_dir = log_dir or default_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    _prune(log_dir, keep - 1)

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = log_dir / f"wflash_{stamp}.log"
    counter = 1
    while path.exists():
        path = log_dir / f"wflash_{stamp}_{counter}.log"
        counter += 1

    close_file_handler()
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(RedactingFormatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(handler)
    _file_handler = handler
    set_verbose(verbose)
    return path
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_logging_setup.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add wflash/core/logging_setup.py tests/test_logging_setup.py
git commit -m "feat(core): add session log file with secret redaction" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Profile

**Files:**
- Create: `wflash/core/profile.py`, `profiles/saf85xx_example.yaml`
- Test: `tests/test_profile.py`

**Interfaces:**
- Consumes: `ProfileError` (Task 2).
- Produces:
  - `GitLabSpec(project: str, job_filter: str = "*")`
  - `ProgramSpec(winidea_entry: str, pattern: str)`, `ApplicationSpec(winidea_app: str, pattern: str)`
  - `PostFlash(reset: bool = True, run: bool = False)`, `Timeouts(download_s: int = 600)`
  - `Profile(name, gitlab, programs: list[ProgramSpec], applications: list[ApplicationSpec], post_flash, timeouts)`
  - `load_profile(path: Path) -> Profile` (raise `ProfileError`), `list_profiles(directory: Path) -> list[Path]`
  - `EXAMPLE_PROFILE` không cần; test dùng đường dẫn `profiles/saf85xx_example.yaml`.

- [ ] **Step 1: Tạo `profiles/saf85xx_example.yaml`**

```yaml
# Ví dụ profile SAF85xx. Tên entry/Application phải trùng với workspace winIDEA
# (lấy từ kết quả spike 02_dump_options).
name: SAF85xx_Radar
gitlab:
  project: group/saf85xx-sw     # path hoặc id project
  job_filter: "build_*"         # glob tên job hiển thị
programs:                       # entry download có sẵn trong workspace (trỏ tới Winbond ext flash)
  - winidea_entry: "App"
    pattern: "**/*App*.s3"
applications:                   # file symbol cho từng Application/core
  - winidea_app: "CM7_0"
    pattern: "**/*cm7_0*.elf"
  - winidea_app: "CM7_1"
    pattern: "**/*cm7_1*.elf"
post_flash:
  reset: true
  run: false
timeouts:
  download_s: 600
```

- [ ] **Step 2: Viết test fail `tests/test_profile.py`**

```python
from pathlib import Path

import pytest

from wflash.core.errors import ProfileError
from wflash.core.profile import list_profiles, load_profile

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "profiles" / "saf85xx_example.yaml"

MINIMAL = """
name: P
gitlab: {project: g/p}
programs:
  - {winidea_entry: App, pattern: "*.s3"}
"""


def write(tmp_path, text, name="p.yaml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_example_profile_loads():
    profile = load_profile(EXAMPLE)
    assert profile.name == "SAF85xx_Radar"
    assert profile.gitlab.project == "group/saf85xx-sw"
    assert [p.winidea_entry for p in profile.programs] == ["App"]
    assert [a.winidea_app for a in profile.applications] == ["CM7_0", "CM7_1"]
    assert profile.post_flash.reset is True and profile.post_flash.run is False
    assert profile.timeouts.download_s == 600


def test_defaults_applied(tmp_path):
    profile = load_profile(write(tmp_path, MINIMAL))
    assert profile.gitlab.job_filter == "*"
    assert profile.applications == []
    assert profile.post_flash.reset is True
    assert profile.timeouts.download_s == 600


def test_missing_programs_rejected(tmp_path):
    with pytest.raises(ProfileError, match="programs"):
        load_profile(write(tmp_path, "name: P\ngitlab: {project: g/p}\n"))


def test_unknown_key_rejected(tmp_path):
    with pytest.raises(ProfileError, match="typo_key"):
        load_profile(write(tmp_path, MINIMAL + "typo_key: 1\n"))


def test_duplicate_targets_rejected(tmp_path):
    text = MINIMAL + '  - {winidea_entry: App, pattern: "*.s3"}\n'
    with pytest.raises(ProfileError, match="Duplicate"):
        load_profile(write(tmp_path, text))


def test_invalid_yaml_rejected(tmp_path):
    with pytest.raises(ProfileError, match="Invalid YAML"):
        load_profile(write(tmp_path, "name: [unclosed"))


def test_non_mapping_rejected(tmp_path):
    with pytest.raises(ProfileError, match="mapping"):
        load_profile(write(tmp_path, "- a\n- b\n"))


def test_missing_file_rejected(tmp_path):
    with pytest.raises(ProfileError, match="Cannot read"):
        load_profile(tmp_path / "nope.yaml")


def test_list_profiles_sorted(tmp_path):
    write(tmp_path, MINIMAL, "b.yaml")
    write(tmp_path, MINIMAL, "a.yml")
    (tmp_path / "notes.txt").write_text("x")
    assert [p.name for p in list_profiles(tmp_path)] == ["a.yml", "b.yaml"]


def test_list_profiles_missing_dir(tmp_path):
    assert list_profiles(tmp_path / "missing") == []
```

- [ ] **Step 3: Chạy test, xác nhận fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_profile.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'wflash.core.profile'`

- [ ] **Step 4: Implement `wflash/core/profile.py`**

```python
"""Project profile: which GitLab project to browse and how artifact files map to winIDEA entries."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from wflash.core.errors import ProfileError


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GitLabSpec(_Strict):
    project: str = Field(min_length=1)
    job_filter: str = "*"


class ProgramSpec(_Strict):
    winidea_entry: str = Field(min_length=1)
    pattern: str = Field(min_length=1)


class ApplicationSpec(_Strict):
    winidea_app: str = Field(min_length=1)
    pattern: str = Field(min_length=1)


class PostFlash(_Strict):
    reset: bool = True
    run: bool = False


class Timeouts(_Strict):
    download_s: int = Field(default=600, gt=0)


class Profile(_Strict):
    name: str = Field(min_length=1)
    gitlab: GitLabSpec
    programs: list[ProgramSpec] = Field(min_length=1)
    applications: list[ApplicationSpec] = Field(default_factory=list)
    post_flash: PostFlash = Field(default_factory=PostFlash)
    timeouts: Timeouts = Field(default_factory=Timeouts)

    @model_validator(mode="after")
    def _unique_targets(self) -> "Profile":
        for label, names in (
            ("program entry", [p.winidea_entry for p in self.programs]),
            ("application", [a.winidea_app for a in self.applications]),
        ):
            dupes = sorted({n for n in names if names.count(n) > 1})
            if dupes:
                raise ValueError(f"Duplicate {label}: {', '.join(dupes)}")
        return self


def load_profile(path: Path) -> Profile:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProfileError(f"Cannot read profile {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ProfileError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileError(f"Profile {path} must be a mapping at the top level")
    try:
        return Profile.model_validate(data)
    except ValidationError as exc:
        raise ProfileError(f"Invalid profile {path}:\n{exc}") from exc


def list_profiles(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted([*directory.glob("*.yaml"), *directory.glob("*.yml")], key=lambda p: p.name)
```

- [ ] **Step 5: Chạy test, xác nhận pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_profile.py -v`
Expected: 10 passed

- [ ] **Step 6: Commit**

```bash
git add wflash/core/profile.py profiles/ tests/test_profile.py
git commit -m "feat(core): add profile schema and example SAF85xx profile" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: File matcher

**Files:**
- Create: `wflash/core/file_matcher.py`
- Test: `tests/test_file_matcher.py`

**Interfaces:**
- Consumes: `Profile` (Task 4).
- Produces:
  - `MappingRow(kind: Literal["program","application"], target: str, pattern: str, candidates: list[Path], selected: Path | None = None)` với `.ok: bool`, `.to_dict() -> dict`
  - `PROGRAM_SUFFIXES = (".s3", ".srec", ".s19", ".mot")`, `SYMBOL_SUFFIXES = (".elf",)`
  - `match_pattern(rel_posix: str, pattern: str) -> bool` (không phân biệt hoa thường; `*` khớp qua cả thư mục; `**/` đầu pattern cũng khớp file ở gốc)
  - `build_mapping(profile: Profile, root: Path) -> list[MappingRow]` (program trước, application sau, theo thứ tự profile)
  - `candidates_for_kind(root: Path, kind: str) -> list[Path]`

- [ ] **Step 1: Viết test fail `tests/test_file_matcher.py`**

```python
from pathlib import Path

from wflash.core.file_matcher import build_mapping, candidates_for_kind, match_pattern
from wflash.core.profile import load_profile

EXAMPLE = Path(__file__).resolve().parents[1] / "profiles" / "saf85xx_example.yaml"


def make_tree(root: Path, files: list[str]) -> None:
    for rel in files:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")


def test_match_pattern_rules():
    assert match_pattern("out/bin/App.s3", "**/*App*.s3")
    assert match_pattern("App.s3", "**/*App*.s3")
    assert match_pattern("OUT/APP.S3", "**/*app*.s3")
    assert match_pattern("out/App.s3", "*.s3")
    assert not match_pattern("out/App.elf", "**/*App*.s3")


def test_single_candidate_is_selected(tmp_path):
    make_tree(tmp_path, ["out/SAF_App.s3", "out/saf_cm7_0.elf", "out/saf_cm7_1.elf", "out/readme.txt"])
    rows = build_mapping(load_profile(EXAMPLE), tmp_path)
    assert [(r.kind, r.target) for r in rows] == [
        ("program", "App"),
        ("application", "CM7_0"),
        ("application", "CM7_1"),
    ]
    assert all(r.ok for r in rows)
    assert rows[0].selected == tmp_path / "out" / "SAF_App.s3"


def test_multiple_candidates_not_selected(tmp_path):
    make_tree(tmp_path, ["a/App.s3", "b/App.s3", "x_cm7_0.elf", "x_cm7_1.elf"])
    rows = build_mapping(load_profile(EXAMPLE), tmp_path)
    program = rows[0]
    assert program.selected is None and not program.ok
    assert program.candidates == [tmp_path / "a" / "App.s3", tmp_path / "b" / "App.s3"]


def test_zero_candidates(tmp_path):
    make_tree(tmp_path, ["App.s3", "x_cm7_0.elf"])
    rows = build_mapping(load_profile(EXAMPLE), tmp_path)
    cm7_1 = rows[2]
    assert cm7_1.candidates == [] and cm7_1.selected is None


def test_candidates_for_kind(tmp_path):
    make_tree(tmp_path, ["a.s3", "b.SREC", "c.elf", "d.map"])
    assert [p.name for p in candidates_for_kind(tmp_path, "program")] == ["a.s3", "b.SREC"]
    assert [p.name for p in candidates_for_kind(tmp_path, "application")] == ["c.elf"]


def test_to_dict(tmp_path):
    make_tree(tmp_path, ["App.s3", "x_cm7_0.elf", "x_cm7_1.elf"])
    data = build_mapping(load_profile(EXAMPLE), tmp_path)[0].to_dict()
    assert data == {
        "kind": "program",
        "target": "App",
        "pattern": "**/*App*.s3",
        "candidates": [str(tmp_path / "App.s3")],
        "selected": str(tmp_path / "App.s3"),
    }
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_file_matcher.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'wflash.core.file_matcher'`

- [ ] **Step 3: Implement `wflash/core/file_matcher.py`**

```python
"""Match files from an extracted artifact to the winIDEA entries declared in a profile."""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from wflash.core.profile import Profile

Kind = Literal["program", "application"]
PROGRAM_SUFFIXES = (".s3", ".srec", ".s19", ".mot")
SYMBOL_SUFFIXES = (".elf",)


@dataclass
class MappingRow:
    kind: Kind
    target: str
    pattern: str
    candidates: list[Path] = field(default_factory=list)
    selected: Path | None = None

    @property
    def ok(self) -> bool:
        return self.selected is not None

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "target": self.target,
            "pattern": self.pattern,
            "candidates": [str(p) for p in self.candidates],
            "selected": str(self.selected) if self.selected else None,
        }


def match_pattern(rel_posix: str, pattern: str) -> bool:
    rel = rel_posix.lower()
    pat = pattern.lower()
    if fnmatch.fnmatchcase(rel, pat):
        return True
    return pat.startswith("**/") and fnmatch.fnmatchcase(rel, pat[3:])


def _files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


def _row(kind: Kind, target: str, pattern: str, root: Path, files: list[Path]) -> MappingRow:
    candidates = [p for p in files if match_pattern(p.relative_to(root).as_posix(), pattern)]
    selected = candidates[0] if len(candidates) == 1 else None
    return MappingRow(kind, target, pattern, candidates, selected)


def build_mapping(profile: Profile, root: Path) -> list[MappingRow]:
    files = _files(root)
    rows = [_row("program", s.winidea_entry, s.pattern, root, files) for s in profile.programs]
    rows += [_row("application", s.winidea_app, s.pattern, root, files) for s in profile.applications]
    return rows


def candidates_for_kind(root: Path, kind: str) -> list[Path]:
    suffixes = PROGRAM_SUFFIXES if kind == "program" else SYMBOL_SUFFIXES
    return [p for p in _files(root) if p.suffix.lower() in suffixes]
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_file_matcher.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add wflash/core/file_matcher.py tests/test_file_matcher.py
git commit -m "feat(core): map artifact files to winIDEA entries by profile patterns" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Artifact cache

**Files:**
- Create: `wflash/core/artifact_cache.py`
- Test: `tests/test_artifact_cache.py`

**Interfaces:**
- Consumes: `ArtifactError` (Task 2), `get_logger` (Task 3).
- Produces: `ArtifactCache(root: Path, max_jobs: int = 10)` với
  - `job_dir(project_id: int, job_id: int) -> Path` → `root/<project_id>/<job_id>`
  - `get(project_id, job_id) -> Path | None` → thư mục `files/` đã giải nén (chạm mtime marker để đánh dấu vừa dùng)
  - `store_zip(project_id, job_id, zip_path: Path) -> Path` → giải nén an toàn, ghi marker `.complete`, prune, trả về thư mục `files/`
  - `entries() -> list[Path]`, `prune() -> None`, `clear() -> None`

- [ ] **Step 1: Viết test fail `tests/test_artifact_cache.py`**

```python
import os
import time
import zipfile

import pytest

from wflash.core.artifact_cache import ArtifactCache
from wflash.core.errors import ArtifactError


def make_zip(path, members):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def test_miss_then_store_then_hit(tmp_path):
    cache = ArtifactCache(tmp_path / "cache")
    assert cache.get(1, 10) is None
    z = make_zip(tmp_path / "a.zip", {"out/App.s3": "S0", "out/x.elf": "ELF"})
    files = cache.store_zip(1, 10, z)
    assert (files / "out" / "App.s3").read_text() == "S0"
    assert files == tmp_path / "cache" / "1" / "10" / "files"
    assert cache.get(1, 10) == files


def test_bad_zip_raises_and_leaves_no_entry(tmp_path):
    cache = ArtifactCache(tmp_path / "cache")
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    with pytest.raises(ArtifactError):
        cache.store_zip(1, 10, bad)
    assert cache.get(1, 10) is None
    assert cache.entries() == []


def test_zip_slip_rejected(tmp_path):
    cache = ArtifactCache(tmp_path / "cache")
    z = make_zip(tmp_path / "evil.zip", {"../../evil.txt": "x"})
    with pytest.raises(ArtifactError, match="Unsafe"):
        cache.store_zip(1, 10, z)
    assert not (tmp_path / "evil.txt").exists()


def test_prune_keeps_most_recent(tmp_path):
    cache = ArtifactCache(tmp_path / "cache", max_jobs=2)
    z = make_zip(tmp_path / "a.zip", {"f.s3": "x"})
    for job in (1, 2):
        cache.store_zip(5, job, z)
        marker = cache.job_dir(5, job) / ".complete"
        os.utime(marker, (time.time() - 100 + job, time.time() - 100 + job))
    cache.store_zip(5, 3, z)
    assert cache.get(5, 1) is None
    assert cache.get(5, 2) is not None
    assert cache.get(5, 3) is not None


def test_clear(tmp_path):
    cache = ArtifactCache(tmp_path / "cache")
    cache.store_zip(1, 1, make_zip(tmp_path / "a.zip", {"f": "x"}))
    cache.clear()
    assert cache.entries() == []
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_artifact_cache.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'wflash.core.artifact_cache'`

- [ ] **Step 3: Implement `wflash/core/artifact_cache.py`**

```python
"""On-disk cache of extracted GitLab job artifacts: <root>/<project_id>/<job_id>/files."""
from __future__ import annotations

import datetime
import os
import shutil
import zipfile
from pathlib import Path

from wflash.core.errors import ArtifactError
from wflash.core.logging_setup import get_logger

MARKER = ".complete"
log = get_logger("cache")


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    dest_resolved = dest.resolve()
    for info in zf.infolist():
        target = (dest / info.filename).resolve()
        if not target.is_relative_to(dest_resolved):
            raise ArtifactError(f"Unsafe path in artifact zip: {info.filename}")
    zf.extractall(dest)


class ArtifactCache:
    def __init__(self, root: Path, max_jobs: int = 10) -> None:
        self.root = root
        self.max_jobs = max_jobs

    def job_dir(self, project_id: int, job_id: int) -> Path:
        return self.root / str(project_id) / str(job_id)

    def get(self, project_id: int, job_id: int) -> Path | None:
        job = self.job_dir(project_id, job_id)
        marker = job / MARKER
        if not marker.is_file():
            return None
        os.utime(marker)
        return job / "files"

    def store_zip(self, project_id: int, job_id: int, zip_path: Path) -> Path:
        final = self.job_dir(project_id, job_id)
        tmp = final.with_name(final.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        files_dir = tmp / "files"
        files_dir.mkdir(parents=True)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                _safe_extract(zf, files_dir)
        except zipfile.BadZipFile as exc:
            shutil.rmtree(tmp, ignore_errors=True)
            raise ArtifactError(f"Artifact is not a valid zip file: {exc}") from exc
        except ArtifactError:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        (tmp / MARKER).write_text(datetime.datetime.now().isoformat(), encoding="utf-8")
        shutil.rmtree(final, ignore_errors=True)
        tmp.rename(final)
        log.info("Cached artifact for project %s job %s at %s", project_id, job_id, final)
        self.prune()
        return final / "files"

    def entries(self) -> list[Path]:
        if not self.root.is_dir():
            return []
        return [m.parent for m in self.root.glob(f"*/*/{MARKER}")]

    def prune(self) -> None:
        jobs = sorted(self.entries(), key=lambda d: (d / MARKER).stat().st_mtime, reverse=True)
        for old in jobs[self.max_jobs:]:
            log.info("Pruning cached artifact %s", old)
            shutil.rmtree(old, ignore_errors=True)

    def clear(self) -> None:
        log.info("Clearing artifact cache %s", self.root)
        shutil.rmtree(self.root, ignore_errors=True)
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_artifact_cache.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add wflash/core/artifact_cache.py tests/test_artifact_cache.py
git commit -m "feat(core): add artifact cache keyed by job id with safe extraction" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: GitLab client

**Files:**
- Create: `wflash/core/gitlab_client.py`
- Test: `tests/test_gitlab_client.py`

**Interfaces:**
- Consumes: `CancelToken` (Task 2), `GitLabError` (Task 2), `get_logger`, `register_secret` (Task 3).
- Produces:
  - `Ref(name: str, kind: Literal["branch","tag"])`, `Pipeline(id: int, ref: str, status: str, sha: str, created_at: str)`, `Job(id: int, name: str, stage: str, status: str, finished_at: str)` (frozen dataclasses)
  - `GitLabClient(base_url: str, token: str, ca_bundle: str | None = None, session: requests.Session | None = None, timeout: float = 30.0)`
    - `get_project_id(project: str) -> int`
    - `list_refs(project_id: int) -> list[Ref]` (branch trước, tag sau)
    - `list_pipelines(project_id: int, ref: str, limit: int = 20) -> list[Pipeline]` (mới nhất trước)
    - `list_jobs(project_id: int, pipeline_id: int, name_glob: str = "*") -> list[Job]` (chỉ job có artifact archive, sort theo tên)
    - `download_artifacts(project_id: int, job_id: int, dest: Path, progress_cb: Callable[[int, int], None] | None = None, cancel: CancelToken | None = None) -> Path` (trả về `dest/artifacts_<job_id>.zip`)

- [ ] **Step 1: Viết test fail `tests/test_gitlab_client.py`**

```python
import pytest
import requests
import responses
from responses import matchers

from wflash.core.cancel import CancelToken
from wflash.core.errors import CancelledError, GitLabError
from wflash.core.gitlab_client import GitLabClient, Job, Pipeline, Ref
from wflash.core.logging_setup import clear_secrets, redact

BASE = "https://gitlab.example.com"
API = BASE + "/api/v4"
TOKEN = "glpat-secret-token"


@pytest.fixture
def client():
    yield GitLabClient(BASE + "/", TOKEN)
    clear_secrets()


@responses.activate
def test_project_id_lookup_encodes_path_and_sends_token(client):
    responses.get(f"{API}/projects/group%2Fsaf85xx-sw", json={"id": 42})
    assert client.get_project_id("group/saf85xx-sw") == 42
    assert responses.calls[0].request.headers["PRIVATE-TOKEN"] == TOKEN


def test_numeric_project_id_needs_no_request(client):
    assert client.get_project_id("42") == 42


@responses.activate
def test_list_refs(client):
    responses.get(f"{API}/projects/42/repository/branches", json=[{"name": "main"}, {"name": "dev"}])
    responses.get(f"{API}/projects/42/repository/tags", json=[{"name": "v1.0"}])
    assert client.list_refs(42) == [Ref("main", "branch"), Ref("dev", "branch"), Ref("v1.0", "tag")]


@responses.activate
def test_list_pipelines_passes_ref_and_order(client):
    responses.get(
        f"{API}/projects/42/pipelines",
        match=[matchers.query_param_matcher({"ref": "main", "per_page": "20", "order_by": "id", "sort": "desc"})],
        json=[{"id": 100, "ref": "main", "status": "success", "sha": "abcdef123456", "created_at": "2026-10-01T10:00:00Z"}],
    )
    assert client.list_pipelines(42, "main") == [
        Pipeline(100, "main", "success", "abcdef123456", "2026-10-01T10:00:00Z")
    ]


@responses.activate
def test_list_jobs_filters_by_glob_and_artifacts(client):
    archive = [{"file_type": "archive"}, {"file_type": "trace"}]
    responses.get(
        f"{API}/projects/42/pipelines/100/jobs",
        json=[
            {"id": 3, "name": "build_app", "stage": "build", "status": "success", "artifacts": archive},
            {"id": 4, "name": "build_docs", "stage": "build", "status": "success", "artifacts": [{"file_type": "trace"}]},
            {"id": 5, "name": "test_unit", "stage": "test", "status": "success", "artifacts": archive},
            {"id": 6, "name": "build_boot", "stage": "build", "status": "success", "artifacts_file": {"filename": "a.zip"}},
        ],
    )
    jobs = client.list_jobs(42, 100, "build_*")
    assert [j.name for j in jobs] == ["build_app", "build_boot"]
    assert jobs[0] == Job(3, "build_app", "build", "success", "")


@responses.activate
def test_download_artifacts_streams_to_file(client, tmp_path):
    body = b"PK" + b"x" * 5000
    responses.get(f"{API}/projects/42/jobs/7/artifacts", body=body, auto_calculate_content_length=True)
    seen = []
    path = client.download_artifacts(42, 7, tmp_path, progress_cb=lambda d, t: seen.append((d, t)))
    assert path == tmp_path / "artifacts_7.zip"
    assert path.read_bytes() == body
    assert seen[-1] == (len(body), len(body))


@responses.activate
def test_download_cancel_removes_partial_file(client, tmp_path):
    responses.get(f"{API}/projects/42/jobs/7/artifacts", body=b"x" * 10)
    token = CancelToken()
    token.cancel()
    with pytest.raises(CancelledError):
        client.download_artifacts(42, 7, tmp_path, cancel=token)
    assert list(tmp_path.iterdir()) == []


@responses.activate
def test_http_401_has_token_hint(client):
    responses.get(f"{API}/projects/42/repository/branches", status=401, json={"message": "401 Unauthorized"})
    with pytest.raises(GitLabError) as info:
        client.list_refs(42)
    assert "401" in str(info.value)
    assert "token" in info.value.hint.lower()


@responses.activate
def test_http_404_has_expired_hint(client, tmp_path):
    responses.get(f"{API}/projects/42/jobs/7/artifacts", status=404, json={"message": "404 Not Found"})
    with pytest.raises(GitLabError) as info:
        client.download_artifacts(42, 7, tmp_path / "unused")
    assert "expired" in info.value.hint


@responses.activate
def test_connection_error(client):
    responses.get(f"{API}/projects/42/repository/branches", body=requests.exceptions.ConnectionError("refused"))
    with pytest.raises(GitLabError, match="Cannot reach"):
        client.list_refs(42)


@responses.activate
def test_ssl_error_suggests_ca_bundle(client):
    responses.get(f"{API}/projects/42/repository/branches", body=requests.exceptions.SSLError("bad cert"))
    with pytest.raises(GitLabError) as info:
        client.list_refs(42)
    assert "CA bundle" in info.value.hint


def test_token_is_registered_for_redaction(client):
    assert redact(f"header {TOKEN}") == "header ***"
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_gitlab_client.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'wflash.core.gitlab_client'`

- [ ] **Step 3: Implement `wflash/core/gitlab_client.py`**

```python
"""Minimal GitLab REST v4 client: browse refs → pipelines → jobs and download job artifacts."""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal
from urllib.parse import quote

import requests

from wflash.core.cancel import CancelToken
from wflash.core.errors import GitLabError
from wflash.core.logging_setup import get_logger, register_secret

log = get_logger("gitlab")
CHUNK = 1024 * 1024
DownloadProgress = Callable[[int, int], None]  # (bytes_done, bytes_total or 0 if unknown)

_HINTS = {
    401: "Token is invalid or expired. Create a Personal Access Token with scope read_api and update it in Settings.",
    403: "Your token has no access to this project. Ask for project access or check the token scope.",
    404: "Not found. Check the project path in the profile; the artifact may also have expired.",
}


@dataclass(frozen=True)
class Ref:
    name: str
    kind: Literal["branch", "tag"]


@dataclass(frozen=True)
class Pipeline:
    id: int
    ref: str
    status: str
    sha: str
    created_at: str


@dataclass(frozen=True)
class Job:
    id: int
    name: str
    stage: str
    status: str
    finished_at: str


def _has_archive(job: dict) -> bool:
    if any(a.get("file_type") == "archive" for a in job.get("artifacts") or []):
        return True
    return bool(job.get("artifacts_file"))


class GitLabClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        ca_bundle: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base = base_url.rstrip("/") + "/api/v4"
        self.session = session or requests.Session()
        self.session.headers["PRIVATE-TOKEN"] = token
        self.verify: bool | str = ca_bundle or True
        self.timeout = timeout
        register_secret(token)

    def _get(self, path: str, params: dict | None = None, stream: bool = False) -> requests.Response:
        url = self.base + path
        log.debug("GET %s params=%s", url, params)
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout, verify=self.verify, stream=stream)
        except requests.exceptions.SSLError as exc:
            raise GitLabError(
                f"SSL error connecting to GitLab: {exc}",
                hint="If GitLab uses an internal certificate, set the CA bundle file in Settings.",
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise GitLabError(f"Cannot reach GitLab: {exc}") from exc
        if resp.status_code >= 400:
            raise GitLabError(
                f"GitLab returned HTTP {resp.status_code} for {path}: {resp.text[:200]}",
                hint=_HINTS.get(resp.status_code, ""),
            )
        return resp

    def get_project_id(self, project: str) -> int:
        if project.isdigit():
            return int(project)
        return int(self._get(f"/projects/{quote(project, safe='')}").json()["id"])

    def list_refs(self, project_id: int) -> list[Ref]:
        branches = self._get(f"/projects/{project_id}/repository/branches", {"per_page": 100}).json()
        tags = self._get(f"/projects/{project_id}/repository/tags", {"per_page": 100}).json()
        return [Ref(b["name"], "branch") for b in branches] + [Ref(t["name"], "tag") for t in tags]

    def list_pipelines(self, project_id: int, ref: str, limit: int = 20) -> list[Pipeline]:
        params = {"ref": ref, "per_page": limit, "order_by": "id", "sort": "desc"}
        data = self._get(f"/projects/{project_id}/pipelines", params).json()
        return [
            Pipeline(p["id"], p.get("ref", ""), p.get("status", ""), p.get("sha", ""), p.get("created_at") or "")
            for p in data
        ]

    def list_jobs(self, project_id: int, pipeline_id: int, name_glob: str = "*") -> list[Job]:
        data = self._get(f"/projects/{project_id}/pipelines/{pipeline_id}/jobs", {"per_page": 100}).json()
        jobs = [
            Job(j["id"], j["name"], j.get("stage", ""), j.get("status", ""), j.get("finished_at") or "")
            for j in data
            if _has_archive(j) and fnmatch.fnmatchcase(j["name"], name_glob)
        ]
        return sorted(jobs, key=lambda j: j.name)

    def download_artifacts(
        self,
        project_id: int,
        job_id: int,
        dest: Path,
        progress_cb: DownloadProgress | None = None,
        cancel: CancelToken | None = None,
    ) -> Path:
        resp = self._get(f"/projects/{project_id}/jobs/{job_id}/artifacts", stream=True)
        dest.mkdir(parents=True, exist_ok=True)
        final = dest / f"artifacts_{job_id}.zip"
        part = final.with_suffix(".zip.part")
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        log.info("Downloading artifacts of job #%s (%s bytes)", job_id, total or "unknown")
        try:
            with resp, part.open("wb") as fh:
                for chunk in resp.iter_content(CHUNK):
                    if cancel is not None:
                        cancel.raise_if_cancelled()
                    fh.write(chunk)
                    done += len(chunk)
                    if progress_cb is not None:
                        progress_cb(done, total)
        except requests.exceptions.RequestException as exc:
            part.unlink(missing_ok=True)
            raise GitLabError(f"Artifact download interrupted: {exc}") from exc
        except BaseException:
            part.unlink(missing_ok=True)
            raise
        part.replace(final)
        log.info("Downloaded %.1f MB to %s", done / 1e6, final)
        return final
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_gitlab_client.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add wflash/core/gitlab_client.py tests/test_gitlab_client.py
git commit -m "feat(core): add GitLab client for pipelines, jobs and artifacts" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Settings + token qua keyring

**Files:**
- Create: `wflash/core/settings.py`
- Test: `tests/test_settings.py`

**Interfaces:**
- Consumes: `get_logger` (Task 3).
- Produces:
  - `KEYRING_SERVICE = "WFlash-GitLab"`
  - `config_dir() -> Path`, `default_cache_dir() -> Path`, `bundled_profiles_dir() -> Path`, `settings_path() -> Path`
  - `AppSettings(gitlab_url="", ca_bundle="", cache_dir="", max_cached_jobs=10, profiles_dir="", last_profile="", verbose=False)` với `resolved_cache_dir() -> Path`, `resolved_profiles_dir() -> Path`, `AppSettings.load(path: Path | None = None) -> AppSettings`, `save(path: Path | None = None) -> None`
  - `get_token(gitlab_url: str) -> str | None`, `set_token(gitlab_url: str, token: str) -> None`

- [ ] **Step 1: Viết test fail `tests/test_settings.py`**

```python
import json
from pathlib import Path

import keyring

from wflash.core import settings as st
from wflash.core.settings import AppSettings


def test_round_trip(tmp_path):
    path = tmp_path / "s.json"
    AppSettings(gitlab_url="https://gl", max_cached_jobs=3, verbose=True).save(path)
    loaded = AppSettings.load(path)
    assert loaded.gitlab_url == "https://gl"
    assert loaded.max_cached_jobs == 3
    assert loaded.verbose is True


def test_missing_file_gives_defaults(tmp_path):
    assert AppSettings.load(tmp_path / "missing.json") == AppSettings()


def test_corrupt_file_gives_defaults(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{not json", encoding="utf-8")
    assert AppSettings.load(path) == AppSettings()


def test_unknown_keys_ignored(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"gitlab_url": "https://gl", "old_option": 1}), encoding="utf-8")
    assert AppSettings.load(path).gitlab_url == "https://gl"


def test_resolved_dirs(tmp_path):
    assert AppSettings(cache_dir=str(tmp_path)).resolved_cache_dir() == tmp_path
    assert AppSettings().resolved_cache_dir() == st.default_cache_dir()
    bundled = AppSettings().resolved_profiles_dir()
    assert bundled == st.bundled_profiles_dir()
    assert (bundled / "saf85xx_example.yaml").is_file()


def test_token_roundtrip_via_keyring(monkeypatch):
    store = {}
    monkeypatch.setattr(keyring, "set_password", lambda s, u, p: store.__setitem__((s, u), p))
    monkeypatch.setattr(keyring, "get_password", lambda s, u: store.get((s, u)))
    st.set_token("https://gl", "glpat-1")
    assert st.get_token("https://gl") == "glpat-1"
    assert store == {(st.KEYRING_SERVICE, "https://gl"): "glpat-1"}
    assert st.get_token("") is None


def test_get_token_keyring_error_returns_none(monkeypatch):
    def boom(service, user):
        raise keyring.errors.KeyringError("locked")

    monkeypatch.setattr(keyring, "get_password", boom)
    assert st.get_token("https://gl") is None
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_settings.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'wflash.core.settings'`

- [ ] **Step 3: Implement `wflash/core/settings.py`**

```python
"""User settings stored as JSON in the user config dir; GitLab token stored in the OS keyring."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import keyring
import keyring.errors

from wflash.core.logging_setup import get_logger

KEYRING_SERVICE = "WFlash-GitLab"
log = get_logger("settings")


def config_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "WFlash"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "WFlash"
    return Path.home() / ".config" / "wflash"


def default_cache_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "WFlash" / "cache"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "WFlash"
    return Path.home() / ".cache" / "wflash"


def bundled_profiles_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "profiles"
    return Path(__file__).resolve().parents[2] / "profiles"


def settings_path() -> Path:
    return config_dir() / "settings.json"


@dataclass
class AppSettings:
    gitlab_url: str = ""
    ca_bundle: str = ""
    cache_dir: str = ""
    max_cached_jobs: int = 10
    profiles_dir: str = ""
    last_profile: str = ""
    verbose: bool = False

    def resolved_cache_dir(self) -> Path:
        return Path(self.cache_dir) if self.cache_dir else default_cache_dir()

    def resolved_profiles_dir(self) -> Path:
        return Path(self.profiles_dir) if self.profiles_dir else bundled_profiles_dir()

    @classmethod
    def load(cls, path: Path | None = None) -> "AppSettings":
        path = path or settings_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError) as exc:
            log.warning("Ignoring unreadable settings file %s: %s", path, exc)
            return cls()
        if not isinstance(data, dict):
            log.warning("Ignoring settings file %s: not a JSON object", path)
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: Path | None = None) -> None:
        path = path or settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


def get_token(gitlab_url: str) -> str | None:
    if not gitlab_url:
        return None
    try:
        return keyring.get_password(KEYRING_SERVICE, gitlab_url)
    except keyring.errors.KeyringError as exc:
        log.warning("Cannot read GitLab token from keyring: %s", exc)
        return None


def set_token(gitlab_url: str, token: str) -> None:
    keyring.set_password(KEYRING_SERVICE, gitlab_url, token)
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_settings.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add wflash/core/settings.py tests/test_settings.py
git commit -m "feat(core): add JSON settings and keyring token storage" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: WinIDEAAdapter protocol + FakeWinIDEAAdapter

**Files:**
- Create: `wflash/core/winidea_adapter.py`, `wflash/core/fake_adapter.py`
- Test: `tests/test_fake_adapter.py`

**Interfaces:**
- Consumes: `CancelToken`, `WinIDEAError`, `FlashError` (Task 2), `get_logger`, `CALLS_LOGGER` (Task 3).
- Produces:
  - `ProgressCallback = Callable[[int | None, str], None]` (percent hoặc None nếu không xác định, message)
  - `InstanceInfo(instance_id: str, workspace: str, tcp_port: int | None = None)` với `label() -> str`
  - `FileEntry(name: str, path: str)`
  - `WinIDEAAdapter` (Protocol): `list_instances() -> list[InstanceInfo]`, `connect(instance_id: str) -> None`, `disconnect() -> None`, `get_info() -> dict[str, str]`, `read_programs() -> list[FileEntry]`, `read_applications() -> list[FileEntry]`, `set_program_path(name: str, path: str) -> None`, `set_symbol_path(name: str, path: str) -> None`, `download(progress: ProgressCallback, cancel: CancelToken, timeout_s: int) -> None`, `reset(run: bool) -> None`
  - `create_adapter(kind: str) -> WinIDEAAdapter` (`"fake"` → `FakeWinIDEAAdapter.from_env()`, `"real"` → `WinIDEAError` cho tới khi Plan 2 thay thế)
  - `FakeWinIDEAAdapter(programs: dict | None = None, applications: dict | None = None, download_seconds: float = 3.0, fail_on: Iterable[str] = ())`, thuộc tính công khai `programs`, `applications`, `fail_on`, `connected_to`, `target_state`, `calls`; `from_env()` đọc `WFLASH_FAKE_FAIL` (vd `download,reset`) và `WFLASH_FAKE_DOWNLOAD_S`. Instance id duy nhất: `"fake-1"`. Mặc định programs `{"App": ...}`, applications `{"CM7_0": ..., "CM7_1": ...}` (khớp profile ví dụ).

- [ ] **Step 1: Viết test fail `tests/test_fake_adapter.py`**

```python
import pytest

from wflash.core.cancel import CancelToken
from wflash.core.errors import CancelledError, FlashError, WinIDEAError
from wflash.core.fake_adapter import FakeWinIDEAAdapter
from wflash.core.winidea_adapter import FileEntry, InstanceInfo, create_adapter


def connected(**kwargs):
    adapter = FakeWinIDEAAdapter(download_seconds=0.02, **kwargs)
    adapter.connect("fake-1")
    return adapter


def test_instance_label_uses_workspace_file_name():
    info = InstanceInfo("id-7", r"C:\ws\SAF85xx.xjrf", 5313)
    assert info.label() == "SAF85xx.xjrf (id-7)"


def test_requires_connection():
    with pytest.raises(WinIDEAError, match="Not connected"):
        FakeWinIDEAAdapter().read_programs()


def test_connect_unknown_instance():
    with pytest.raises(WinIDEAError, match="No winIDEA instance"):
        FakeWinIDEAAdapter().connect("other")


def test_list_and_read_defaults():
    adapter = FakeWinIDEAAdapter()
    assert [i.instance_id for i in adapter.list_instances()] == ["fake-1"]
    adapter.connect("fake-1")
    assert [e.name for e in adapter.read_programs()] == ["App"]
    assert [e.name for e in adapter.read_applications()] == ["CM7_0", "CM7_1"]
    assert adapter.get_info()["adapter"] == "fake"


def test_set_paths_download_reset():
    adapter = connected()
    adapter.set_program_path("App", "/new/App.s3")
    adapter.set_symbol_path("CM7_0", "/new/a.elf")
    assert FileEntry("App", "/new/App.s3") in adapter.read_programs()
    progress = []
    adapter.download(lambda p, m: progress.append(p), CancelToken(), timeout_s=60)
    assert progress[-1] == 100
    adapter.reset(run=False)
    assert adapter.target_state == "halted"
    adapter.reset(run=True)
    assert adapter.target_state == "running"


def test_set_unknown_entry():
    with pytest.raises(WinIDEAError, match="Unknown program entry"):
        connected().set_program_path("Nope", "/x")


def test_injected_download_failure_mid_way():
    adapter = connected(fail_on={"download"})
    progress = []
    with pytest.raises(FlashError, match="injected"):
        adapter.download(lambda p, m: progress.append(p), CancelToken(), timeout_s=60)
    assert progress and progress[-1] < 100


def test_injected_reset_failure():
    with pytest.raises(WinIDEAError, match="injected in 'reset'"):
        connected(fail_on={"reset"}).reset(run=False)


def test_cancel_during_download():
    adapter = connected()
    token = CancelToken()
    with pytest.raises(CancelledError):
        adapter.download(lambda p, m: token.cancel(), token, timeout_s=60)


def test_timeout():
    with pytest.raises(FlashError, match="timed out"):
        connected().download(lambda p, m: None, CancelToken(), timeout_s=0)


def test_from_env(monkeypatch):
    monkeypatch.setenv("WFLASH_FAKE_FAIL", "download, reset")
    monkeypatch.setenv("WFLASH_FAKE_DOWNLOAD_S", "0.5")
    adapter = FakeWinIDEAAdapter.from_env()
    assert adapter.fail_on == {"download", "reset"}
    assert adapter.download_seconds == 0.5


def test_create_adapter():
    assert isinstance(create_adapter("fake"), FakeWinIDEAAdapter)
    with pytest.raises(WinIDEAError):
        create_adapter("real")
    with pytest.raises(ValueError):
        create_adapter("other")
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_fake_adapter.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'wflash.core.fake_adapter'`

- [ ] **Step 3: Implement `wflash/core/winidea_adapter.py`**

```python
"""Interface between the flash workflow and winIDEA. Only adapters talk to isystem.connect."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Callable, Protocol

from wflash.core.cancel import CancelToken
from wflash.core.errors import WinIDEAError

ProgressCallback = Callable[[int | None, str], None]


@dataclass(frozen=True)
class InstanceInfo:
    instance_id: str
    workspace: str
    tcp_port: int | None = None

    def label(self) -> str:
        name = PureWindowsPath(self.workspace).name or self.workspace
        return f"{name} ({self.instance_id})"


@dataclass(frozen=True)
class FileEntry:
    """A download (program) or symbol (application) file entry in the winIDEA workspace."""

    name: str
    path: str


class WinIDEAAdapter(Protocol):
    def list_instances(self) -> list[InstanceInfo]: ...

    def connect(self, instance_id: str) -> None: ...

    def disconnect(self) -> None: ...

    def get_info(self) -> dict[str, str]:
        """winIDEA version, workspace path and adapter name, for logs and the debug bundle."""
        ...

    def read_programs(self) -> list[FileEntry]: ...

    def read_applications(self) -> list[FileEntry]: ...

    def set_program_path(self, name: str, path: str) -> None:
        """Replace only the file path of an existing download entry; keep its other options."""
        ...

    def set_symbol_path(self, name: str, path: str) -> None:
        """Replace only the symbol file path of an existing application."""
        ...

    def download(self, progress: ProgressCallback, cancel: CancelToken, timeout_s: int) -> None: ...

    def reset(self, run: bool) -> None: ...


def create_adapter(kind: str) -> WinIDEAAdapter:
    if kind == "fake":
        from wflash.core.fake_adapter import FakeWinIDEAAdapter

        return FakeWinIDEAAdapter.from_env()
    if kind == "real":
        raise WinIDEAError(
            "The real winIDEA adapter is not available in this build yet.",
            hint="Run the spike scripts (spike/README.md) and send the results. Meanwhile start WFlash with --adapter fake.",
        )
    raise ValueError(f"Unknown adapter kind: {kind}")
```

- [ ] **Step 4: Implement `wflash/core/fake_adapter.py`**

```python
"""In-memory winIDEA stand-in for development on macOS and for tests.

Failures can be injected per operation: connect, set_path, download, reset
(constructor `fail_on`, or env WFLASH_FAKE_FAIL="download,reset").
"""
from __future__ import annotations

import logging
import os
import time
from typing import Iterable

from wflash.core.cancel import CancelToken
from wflash.core.errors import FlashError, WinIDEAError
from wflash.core.logging_setup import CALLS_LOGGER
from wflash.core.winidea_adapter import FileEntry, InstanceInfo, ProgressCallback

calls_log = logging.getLogger(CALLS_LOGGER)
INSTANCE_ID = "fake-1"
WORKSPACE = r"C:\fake\SAF85xx\SAF85xx.xjrf"


class FakeWinIDEAAdapter:
    def __init__(
        self,
        programs: dict[str, str] | None = None,
        applications: dict[str, str] | None = None,
        download_seconds: float = 3.0,
        fail_on: Iterable[str] = (),
    ) -> None:
        self.programs = dict(programs if programs is not None else {"App": r"C:\fake\old\App.s3"})
        self.applications = dict(
            applications
            if applications is not None
            else {"CM7_0": r"C:\fake\old\cm7_0.elf", "CM7_1": r"C:\fake\old\cm7_1.elf"}
        )
        self.download_seconds = download_seconds
        self.fail_on = set(fail_on)
        self.connected_to: str | None = None
        self.target_state = "unknown"
        self.calls: list[str] = []

    @classmethod
    def from_env(cls) -> "FakeWinIDEAAdapter":
        fail = [f.strip() for f in os.environ.get("WFLASH_FAKE_FAIL", "").split(",") if f.strip()]
        seconds = float(os.environ.get("WFLASH_FAKE_DOWNLOAD_S", "3"))
        return cls(download_seconds=seconds, fail_on=fail)

    def _call(self, op: str, detail: str = "") -> None:
        self.calls.append(op)
        calls_log.debug("fake.%s %s", op, detail)
        if op in self.fail_on and op != "download":
            raise WinIDEAError(f"Fake failure injected in '{op}'")

    def _require_connected(self) -> None:
        if self.connected_to is None:
            raise WinIDEAError("Not connected to winIDEA")

    def list_instances(self) -> list[InstanceInfo]:
        self._call("list_instances")
        return [InstanceInfo(INSTANCE_ID, WORKSPACE, 5313)]

    def connect(self, instance_id: str) -> None:
        self._call("connect", instance_id)
        if instance_id != INSTANCE_ID:
            raise WinIDEAError(f"No winIDEA instance with id {instance_id!r}")
        self.connected_to = instance_id

    def disconnect(self) -> None:
        self._call("disconnect")
        self.connected_to = None

    def get_info(self) -> dict[str, str]:
        self._require_connected()
        return {"winidea_version": "9.21.0 (fake)", "workspace": WORKSPACE, "adapter": "fake"}

    def read_programs(self) -> list[FileEntry]:
        self._require_connected()
        self._call("read_programs")
        return [FileEntry(k, v) for k, v in self.programs.items()]

    def read_applications(self) -> list[FileEntry]:
        self._require_connected()
        self._call("read_applications")
        return [FileEntry(k, v) for k, v in self.applications.items()]

    def set_program_path(self, name: str, path: str) -> None:
        self._require_connected()
        self._call("set_path", f"program {name}={path}")
        if name not in self.programs:
            raise WinIDEAError(f"Unknown program entry {name!r}")
        self.programs[name] = path

    def set_symbol_path(self, name: str, path: str) -> None:
        self._require_connected()
        self._call("set_path", f"application {name}={path}")
        if name not in self.applications:
            raise WinIDEAError(f"Unknown application {name!r}")
        self.applications[name] = path

    def download(self, progress: ProgressCallback, cancel: CancelToken, timeout_s: int) -> None:
        self._require_connected()
        self._call("download")
        steps = 20
        start = time.monotonic()
        for i in range(1, steps + 1):
            if cancel.wait(self.download_seconds / steps):
                cancel.raise_if_cancelled()
            if time.monotonic() - start > timeout_s:
                raise FlashError(f"Download timed out after {timeout_s}s")
            if "download" in self.fail_on and i == steps // 2:
                raise FlashError("Fake failure injected in 'download'")
            progress(i * 100 // steps, "Programming external flash (fake)")
        self.target_state = "downloaded"

    def reset(self, run: bool) -> None:
        self._require_connected()
        self._call("reset", f"run={run}")
        self.target_state = "running" if run else "halted"
```

- [ ] **Step 5: Chạy test, xác nhận pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_fake_adapter.py -v`
Expected: 12 passed

- [ ] **Step 6: Commit**

```bash
git add wflash/core/winidea_adapter.py wflash/core/fake_adapter.py tests/test_fake_adapter.py
git commit -m "feat(core): add winIDEA adapter protocol and fake adapter" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Debug bundle

**Files:**
- Create: `wflash/core/debug_bundle.py`
- Test: `tests/test_debug_bundle.py`

**Interfaces:**
- Consumes: `FileEntry` (Task 9), `redact` (Task 3), `wflash.__version__`.
- Produces:
  - `DebugContext(profile_path: Path | None = None, mapping: list[dict] = [], adapter_info: dict[str, str] = {}, snapshots: dict[str, dict] = {}, errors: list[str] = [])` với `snapshot(label: str, programs: list[FileEntry], applications: list[FileEntry]) -> None`, `add_error(exc: BaseException) -> None`
  - `collect_env_info() -> dict[str, str]`
  - `create_debug_bundle(ctx: DebugContext, dest_dir: Path, log_file: Path | None) -> Path` → zip chứa `log.txt` (nếu có), `environment.json`, `profile.yaml` (nếu có), `mapping.json`, `workspace_snapshots.json`, `errors.txt`

- [ ] **Step 1: Viết test fail `tests/test_debug_bundle.py`**

```python
import json
import zipfile

from wflash.core.debug_bundle import DebugContext, collect_env_info, create_debug_bundle
from wflash.core.logging_setup import clear_secrets, register_secret
from wflash.core.winidea_adapter import FileEntry


def test_env_info_has_versions():
    info = collect_env_info()
    for key in ("wflash", "python", "platform", "PySide6", "isystem.connect"):
        assert key in info


def test_snapshot_and_error_recorded():
    ctx = DebugContext()
    ctx.snapshot("before", [FileEntry("App", "a.s3")], [FileEntry("CM7_0", "a.elf")])
    assert ctx.snapshots["before"] == {
        "programs": [{"name": "App", "path": "a.s3"}],
        "applications": [{"name": "CM7_0", "path": "a.elf"}],
    }
    try:
        raise ValueError("bad thing")
    except ValueError as exc:
        ctx.add_error(exc)
    assert "Traceback" in ctx.errors[0] and "bad thing" in ctx.errors[0]


def test_bundle_contents_and_redaction(tmp_path):
    register_secret("glpat-SECRET-1")
    log_file = tmp_path / "w.log"
    log_file.write_text("line with glpat-SECRET-1\n", encoding="utf-8")
    profile = tmp_path / "p.yaml"
    profile.write_text("name: P\n", encoding="utf-8")
    ctx = DebugContext(profile_path=profile, mapping=[{"target": "App"}], adapter_info={"adapter": "fake"})
    ctx.snapshot("before", [FileEntry("App", "a.s3")], [])
    path = create_debug_bundle(ctx, tmp_path / "out", log_file)
    clear_secrets()
    assert path.parent == tmp_path / "out" and path.name.startswith("wflash_debug_")
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        assert names == {
            "log.txt", "environment.json", "profile.yaml", "mapping.json", "workspace_snapshots.json", "errors.txt",
        }
        assert "glpat-SECRET-1" not in zf.read("log.txt").decode()
        env = json.loads(zf.read("environment.json"))
        assert env["winidea.adapter"] == "fake"
        assert json.loads(zf.read("workspace_snapshots.json"))["before"]["programs"][0]["name"] == "App"
        assert zf.read("errors.txt").decode() == "(no errors recorded)"


def test_bundle_without_log_or_profile(tmp_path):
    path = create_debug_bundle(DebugContext(), tmp_path, None)
    with zipfile.ZipFile(path) as zf:
        assert "log.txt" not in zf.namelist()
        assert "profile.yaml" not in zf.namelist()
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_debug_bundle.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'wflash.core.debug_bundle'`

- [ ] **Step 3: Implement `wflash/core/debug_bundle.py`**

```python
"""Collect everything needed to debug a session remotely into one redacted zip file."""
from __future__ import annotations

import datetime
import importlib.metadata
import json
import platform
import sys
import traceback
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from wflash import __version__
from wflash.core.logging_setup import redact
from wflash.core.winidea_adapter import FileEntry


@dataclass
class DebugContext:
    profile_path: Path | None = None
    mapping: list[dict] = field(default_factory=list)
    adapter_info: dict[str, str] = field(default_factory=dict)
    snapshots: dict[str, dict] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def snapshot(self, label: str, programs: list[FileEntry], applications: list[FileEntry]) -> None:
        self.snapshots[label] = {
            "programs": [asdict(e) for e in programs],
            "applications": [asdict(e) for e in applications],
        }

    def add_error(self, exc: BaseException) -> None:
        self.errors.append("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


def _dist_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def collect_env_info() -> dict[str, str]:
    return {
        "wflash": __version__,
        "python": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "executable": sys.executable,
        "frozen": str(bool(getattr(sys, "frozen", False))),
        "PySide6": _dist_version("PySide6"),
        "isystem.connect": _dist_version("isystem.connect"),
    }


def create_debug_bundle(ctx: DebugContext, dest_dir: Path, log_file: Path | None) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = dest_dir / f"wflash_debug_{stamp}.zip"
    env = {**collect_env_info(), **{f"winidea.{k}": v for k, v in ctx.adapter_info.items()}}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        if log_file is not None and log_file.is_file():
            zf.writestr("log.txt", redact(log_file.read_text(encoding="utf-8", errors="replace")))
        zf.writestr("environment.json", redact(json.dumps(env, indent=2)))
        if ctx.profile_path is not None and ctx.profile_path.is_file():
            zf.writestr("profile.yaml", redact(ctx.profile_path.read_text(encoding="utf-8", errors="replace")))
        zf.writestr("mapping.json", redact(json.dumps(ctx.mapping, indent=2)))
        zf.writestr("workspace_snapshots.json", redact(json.dumps(ctx.snapshots, indent=2)))
        zf.writestr("errors.txt", redact("\n\n".join(ctx.errors) or "(no errors recorded)"))
    return path
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_debug_bundle.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add wflash/core/debug_bundle.py tests/test_debug_bundle.py
git commit -m "feat(core): add redacted debug bundle export" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Flash workflow

**Files:**
- Create: `wflash/core/flash_workflow.py`
- Test: `tests/test_flash_workflow.py`

**Interfaces:**
- Consumes: `WinIDEAAdapter`, `ProgressCallback` (Task 9), `MappingRow` (Task 5), `DebugContext` (Task 10), `CancelToken`, `MappingError`, `FlashError`, `WFlashError` (Task 2).
- Produces:
  - `Step(str, Enum)`: `CONNECT, VALIDATE, SET_PATHS, DOWNLOAD, RESET, ROLLBACK, DONE`; `.value` là text hiển thị (vd `"Done"`)
  - `FlashRequest(instance_id: str, mapping: list[MappingRow], reset: bool = True, run: bool = False, timeout_s: int = 600)`
  - `FlashWorkflow(adapter, ctx: DebugContext, on_step: Callable[[Step], None] | None = None, on_progress: ProgressCallback | None = None)` với `run(req: FlashRequest, cancel: CancelToken) -> None`
  - Hành vi: lỗi không thuộc `WFlashError` được bọc thành `FlashError("<Type>: <msg>")`; lỗi/hủy trong lúc set path hoặc download → rollback path cũ; luôn disconnect; snapshot `before`, `after_set`, `after_rollback` vào `ctx`.

- [ ] **Step 1: Viết test fail `tests/test_flash_workflow.py`**

```python
from pathlib import Path

import pytest

from wflash.core.cancel import CancelToken
from wflash.core.debug_bundle import DebugContext
from wflash.core.errors import CancelledError, FlashError, MappingError, WinIDEAError
from wflash.core.fake_adapter import FakeWinIDEAAdapter
from wflash.core.file_matcher import build_mapping
from wflash.core.flash_workflow import FlashRequest, FlashWorkflow, Step
from wflash.core.profile import load_profile

EXAMPLE = Path(__file__).resolve().parents[1] / "profiles" / "saf85xx_example.yaml"
OLD_APP = r"C:\fake\old\App.s3"


@pytest.fixture
def rows(tmp_path):
    for name in ("App.s3", "x_cm7_0.elf", "x_cm7_1.elf"):
        (tmp_path / name).write_bytes(b"x")
    return build_mapping(load_profile(EXAMPLE), tmp_path)


def run(adapter, rows, cancel=None, **req_kwargs):
    ctx = DebugContext()
    steps, progress = [], []
    wf = FlashWorkflow(adapter, ctx, on_step=steps.append, on_progress=lambda p, m: progress.append(p))
    error = None
    try:
        wf.run(FlashRequest("fake-1", rows, **req_kwargs), cancel or CancelToken())
    except Exception as exc:  # returned for assertions
        error = exc
    return ctx, steps, progress, error


def test_happy_path(rows, tmp_path):
    adapter = FakeWinIDEAAdapter(download_seconds=0.02)
    ctx, steps, progress, error = run(adapter, rows)
    assert error is None
    assert adapter.programs["App"] == str((tmp_path / "App.s3").resolve())
    assert adapter.applications["CM7_1"] == str((tmp_path / "x_cm7_1.elf").resolve())
    assert adapter.target_state == "halted"
    assert steps == [Step.CONNECT, Step.VALIDATE, Step.SET_PATHS, Step.DOWNLOAD, Step.RESET, Step.DONE]
    assert progress[-1] == 100
    assert adapter.connected_to is None
    assert set(ctx.snapshots) == {"before", "after_set"}
    assert ctx.adapter_info["adapter"] == "fake"
    assert ctx.mapping[0]["target"] == "App"


def test_run_after_reset(rows):
    adapter = FakeWinIDEAAdapter(download_seconds=0.02)
    assert run(adapter, rows, run=True)[3] is None
    assert adapter.target_state == "running"


def test_no_reset(rows):
    adapter = FakeWinIDEAAdapter(download_seconds=0.02)
    _, steps, _, error = run(adapter, rows, reset=False)
    assert error is None
    assert "reset" not in adapter.calls
    assert Step.RESET not in steps


def test_unmapped_row_rejected_before_connect(rows):
    rows[0].selected = None
    adapter = FakeWinIDEAAdapter()
    error = run(adapter, rows)[3]
    assert isinstance(error, MappingError) and "App" in str(error)
    assert "connect" not in adapter.calls


def test_missing_workspace_entry(rows):
    adapter = FakeWinIDEAAdapter(programs={"Other": "o.s3"}, download_seconds=0.02)
    error = run(adapter, rows)[3]
    assert isinstance(error, MappingError)
    assert "program 'App'" in str(error)
    assert "Other" in error.hint
    assert adapter.programs == {"Other": "o.s3"}
    assert adapter.connected_to is None


def test_download_failure_rolls_back(rows):
    adapter = FakeWinIDEAAdapter(download_seconds=0.02, fail_on={"download"})
    ctx, steps, _, error = run(adapter, rows)
    assert isinstance(error, FlashError)
    assert adapter.programs["App"] == OLD_APP
    assert Step.ROLLBACK in steps and Step.DONE not in steps
    assert "after_rollback" in ctx.snapshots


def test_cancel_during_download_rolls_back(rows):
    adapter = FakeWinIDEAAdapter(download_seconds=0.5)
    token = CancelToken()
    ctx = DebugContext()
    wf = FlashWorkflow(adapter, ctx, on_progress=lambda p, m: token.cancel())
    with pytest.raises(CancelledError):
        wf.run(FlashRequest("fake-1", rows), token)
    assert adapter.programs["App"] == OLD_APP


def test_unexpected_exception_wrapped(rows):
    class Broken(FakeWinIDEAAdapter):
        def download(self, progress, cancel, timeout_s):
            raise RuntimeError("COM error")

    adapter = Broken()
    error = run(adapter, rows)[3]
    assert isinstance(error, FlashError)
    assert "RuntimeError: COM error" in str(error)
    assert adapter.programs["App"] == OLD_APP


def test_rollback_failure_recorded(rows):
    adapter = FakeWinIDEAAdapter(fail_on={"set_path"})
    ctx, _, _, error = run(adapter, rows)
    assert isinstance(error, WinIDEAError)
    assert len(ctx.errors) == 1 and "set_path" in ctx.errors[0]
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_flash_workflow.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'wflash.core.flash_workflow'`

- [ ] **Step 3: Implement `wflash/core/flash_workflow.py`**

```python
"""Flash sequence: connect → validate entries → set paths → download → reset, with rollback."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from wflash.core.cancel import CancelToken
from wflash.core.debug_bundle import DebugContext
from wflash.core.errors import FlashError, MappingError, WFlashError
from wflash.core.file_matcher import MappingRow
from wflash.core.logging_setup import get_logger
from wflash.core.winidea_adapter import ProgressCallback, WinIDEAAdapter

log = get_logger("flash")


class Step(str, Enum):
    CONNECT = "Connecting to winIDEA"
    VALIDATE = "Checking workspace entries"
    SET_PATHS = "Updating file paths"
    DOWNLOAD = "Downloading to external flash"
    RESET = "Resetting target"
    ROLLBACK = "Restoring previous paths"
    DONE = "Done"


@dataclass
class FlashRequest:
    instance_id: str
    mapping: list[MappingRow]
    reset: bool = True
    run: bool = False
    timeout_s: int = 600


class FlashWorkflow:
    def __init__(
        self,
        adapter: WinIDEAAdapter,
        ctx: DebugContext,
        on_step: Callable[[Step], None] | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        self.adapter = adapter
        self.ctx = ctx
        self._on_step = on_step or (lambda step: None)
        self._on_progress = on_progress or (lambda percent, message: None)

    def run(self, req: FlashRequest, cancel: CancelToken) -> None:
        missing = [row.target for row in req.mapping if not row.ok]
        if missing:
            raise MappingError(
                f"No file selected for: {', '.join(missing)}",
                hint="Choose a file for every red row in the mapping table.",
            )
        self.ctx.mapping = [row.to_dict() for row in req.mapping]
        try:
            self._step(Step.CONNECT)
            self.adapter.connect(req.instance_id)
            try:
                self.ctx.adapter_info = dict(self.adapter.get_info())
                log.info("winIDEA: %s", self.ctx.adapter_info)
                self._run_connected(req, cancel)
            finally:
                self._disconnect()
        except WFlashError:
            raise
        except Exception as exc:
            raise FlashError(f"{type(exc).__name__}: {exc}") from exc
        self._step(Step.DONE)

    def _run_connected(self, req: FlashRequest, cancel: CancelToken) -> None:
        self._step(Step.VALIDATE)
        current = self._read_current("before")
        self._check_targets(req.mapping, current)
        backup = [(row.kind, row.target, current[row.kind][row.target]) for row in req.mapping]
        cancel.raise_if_cancelled()
        try:
            self._step(Step.SET_PATHS)
            for row in req.mapping:
                self._set_path(row.kind, row.target, str(row.selected.resolve()))
            self._read_current("after_set")
            cancel.raise_if_cancelled()
            self._step(Step.DOWNLOAD)
            self.adapter.download(self._on_progress, cancel, req.timeout_s)
        except BaseException:
            self._rollback(backup)
            raise
        if req.reset:
            self._step(Step.RESET)
            self.adapter.reset(run=req.run)

    def _read_current(self, label: str) -> dict[str, dict[str, str]]:
        programs = self.adapter.read_programs()
        applications = self.adapter.read_applications()
        self.ctx.snapshot(label, programs, applications)
        return {
            "program": {e.name: e.path for e in programs},
            "application": {e.name: e.path for e in applications},
        }

    def _check_targets(self, mapping: list[MappingRow], current: dict[str, dict[str, str]]) -> None:
        missing = [f"{row.kind} '{row.target}'" for row in mapping if row.target not in current[row.kind]]
        if missing:
            raise MappingError(
                "Entries not found in the winIDEA workspace: " + ", ".join(missing),
                hint=(
                    f"Workspace programs: {sorted(current['program'])}; "
                    f"applications: {sorted(current['application'])}. Update the profile to use these names."
                ),
            )

    def _set_path(self, kind: str, target: str, path: str) -> None:
        log.info("Set %s '%s' -> %s", kind, target, path)
        if kind == "program":
            self.adapter.set_program_path(target, path)
        else:
            self.adapter.set_symbol_path(target, path)

    def _rollback(self, backup: list[tuple[str, str, str]]) -> None:
        self._step(Step.ROLLBACK)
        try:
            for kind, target, old in backup:
                self._set_path(kind, target, old)
            self._read_current("after_rollback")
        except Exception as exc:
            log.error("Rollback failed; the workspace may still point to the new files: %s", exc)
            self.ctx.add_error(exc)

    def _disconnect(self) -> None:
        try:
            self.adapter.disconnect()
        except Exception:
            log.warning("Disconnect from winIDEA failed", exc_info=True)

    def _step(self, step: Step) -> None:
        log.info("== %s ==", step.value)
        self._on_step(step)
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_flash_workflow.py -v`
Expected: 9 passed

- [ ] **Step 5: Chạy toàn bộ test core**

Run: `~/.venvs/wflash/bin/pytest -v`
Expected: tất cả pass (83 tests)

- [ ] **Step 6: Commit**

```bash
git add wflash/core/flash_workflow.py tests/test_flash_workflow.py
git commit -m "feat(core): add flash workflow with rollback and step reporting" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: GUI log panel

**Files:**
- Create: `wflash/gui/log_panel.py`
- Test: `tests/test_log_panel.py`

**Interfaces:**
- Consumes: `RedactingFormatter` (Task 3).
- Produces:
  - `QtLogHandler(logging.Handler)` với `.emitter.record: Signal(int, str)`; thread-safe (signal queued về GUI thread)
  - `LogPanel(QWidget)`: thuộc tính `handler: QtLogHandler`, `level_combo`, `copy_btn`, `clear_btn`, `export_btn`, `view`; signals `exportRequested()`, `errorLogged(str)`; methods `append_record(level: int, text: str)`, `min_level() -> int`, `visible_text() -> str`, `copy_all()`, `clear()`. Mặc định lọc INFO.

- [ ] **Step 1: Viết test fail `tests/test_log_panel.py`**

```python
import logging
import threading

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from wflash.core.logging_setup import clear_secrets, register_secret
from wflash.gui.log_panel import LogPanel


@pytest.fixture
def panel(qtbot):
    p = LogPanel()
    qtbot.addWidget(p)
    logger = logging.getLogger("wflash.test_panel")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(p.handler)
    yield p, logger
    logger.removeHandler(p.handler)
    clear_secrets()


def test_info_filter_hides_debug_until_changed(panel):
    p, log = panel
    log.debug("dbg-line")
    log.info("info-line")
    assert "info-line" in p.visible_text()
    assert "dbg-line" not in p.visible_text()
    p.level_combo.setCurrentIndex(0)
    assert "dbg-line" in p.visible_text()


def test_error_emits_signal_and_keeps_traceback(panel, qtbot):
    p, log = panel
    with qtbot.waitSignal(p.errorLogged, timeout=1000) as blocker:
        try:
            raise ValueError("broken value")
        except ValueError:
            log.exception("operation failed")
    assert "operation failed" in blocker.args[0]
    assert "Traceback" in p.visible_text() and "ValueError: broken value" in p.visible_text()


def test_secret_redacted(panel):
    p, log = panel
    register_secret("glpat-panel-1")
    log.info("token glpat-panel-1")
    assert "glpat-panel-1" not in p.visible_text()
    assert "token ***" in p.visible_text()


def test_copy_and_clear(panel):
    p, log = panel
    log.info("copy me")
    p.copy_all()
    assert "copy me" in QGuiApplication.clipboard().text()
    p.clear()
    assert p.visible_text() == ""


def test_export_button_emits(panel, qtbot):
    p, _ = panel
    with qtbot.waitSignal(p.exportRequested, timeout=1000):
        qtbot.mouseClick(p.export_btn, Qt.LeftButton)


def test_logging_from_worker_thread(panel, qtbot):
    p, log = panel
    t = threading.Thread(target=lambda: log.info("from-thread"))
    t.start()
    t.join()
    qtbot.waitUntil(lambda: "from-thread" in p.visible_text(), timeout=1000)
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_log_panel.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'wflash.gui.log_panel'`

- [ ] **Step 3: Implement `wflash/gui/log_panel.py`**

```python
"""Log panel fed by a logging.Handler. Records may come from any thread."""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QFontDatabase, QGuiApplication, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from wflash.core.logging_setup import RedactingFormatter

LEVELS = [("DEBUG", logging.DEBUG), ("INFO", logging.INFO), ("WARNING", logging.WARNING), ("ERROR", logging.ERROR)]
COLORS = {
    logging.DEBUG: "#8a8a8a",
    logging.WARNING: "#c77700",
    logging.ERROR: "#d32f2f",
    logging.CRITICAL: "#d32f2f",
}
PANEL_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
MAX_RECORDS = 20000


class _Emitter(QObject):
    record = Signal(int, str)


class QtLogHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.emitter = _Emitter()
        self.setFormatter(RedactingFormatter(PANEL_FORMAT, "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            text = self.format(record)
        except Exception:
            self.handleError(record)
            return
        self.emitter.record.emit(record.levelno, text)


class LogPanel(QWidget):
    exportRequested = Signal()
    errorLogged = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._records: list[tuple[int, str]] = []

        self.level_combo = QComboBox()
        for name, level in LEVELS:
            self.level_combo.addItem(name, level)
        self.level_combo.setCurrentIndex(1)
        self.copy_btn = QPushButton("Copy")
        self.clear_btn = QPushButton("Clear")
        self.export_btn = QPushButton("Export debug bundle…")
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(MAX_RECORDS)
        self.view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.view.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Log level:"))
        bar.addWidget(self.level_combo)
        bar.addStretch(1)
        bar.addWidget(self.copy_btn)
        bar.addWidget(self.clear_btn)
        bar.addWidget(self.export_btn)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(bar)
        layout.addWidget(self.view)

        self.handler = QtLogHandler()
        self.handler.emitter.record.connect(self.append_record)
        self.level_combo.currentIndexChanged.connect(self._refilter)
        self.copy_btn.clicked.connect(self.copy_all)
        self.clear_btn.clicked.connect(self.clear)
        self.export_btn.clicked.connect(self.exportRequested)

    def min_level(self) -> int:
        return int(self.level_combo.currentData())

    def append_record(self, level: int, text: str) -> None:
        self._records.append((level, text))
        if len(self._records) > MAX_RECORDS:
            del self._records[: len(self._records) - MAX_RECORDS]
        if level >= self.min_level():
            self._write(level, text)
        if level >= logging.ERROR:
            self.errorLogged.emit(text)

    def _write(self, level: int, text: str) -> None:
        cursor = self.view.textCursor()
        cursor.movePosition(QTextCursor.End)
        if not self.view.document().isEmpty():
            cursor.insertBlock()
        fmt = QTextCharFormat()
        color = COLORS.get(level)
        if color:
            fmt.setForeground(QColor(color))
        cursor.insertText(text, fmt)
        self.view.setTextCursor(cursor)
        self.view.ensureCursorVisible()

    def _refilter(self, *_args) -> None:
        self.view.clear()
        minimum = self.min_level()
        for level, text in self._records:
            if level >= minimum:
                self._write(level, text)

    def visible_text(self) -> str:
        return self.view.toPlainText()

    def copy_all(self) -> None:
        QGuiApplication.clipboard().setText(self.visible_text())

    def clear(self) -> None:
        self._records.clear()
        self.view.clear()
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_log_panel.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add wflash/gui/log_panel.py tests/test_log_panel.py
git commit -m "feat(gui): add log panel with level filter, copy and export" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: GUI workers

**Files:**
- Create: `wflash/gui/workers.py`
- Test: `tests/test_workers.py`

**Interfaces:**
- Consumes: `CancelToken`, `CancelledError`, `WFlashError` (Task 2), `get_logger` (Task 3).
- Produces:
  - `WorkerSignals(QObject)`: `progress(object, str)`, `step(str)`, `succeeded(object)`, `failed(object)`, `finished()`
  - `WorkerContext(cancel: CancelToken, progress: Callable[[int | None, str], None], step: Callable[[str], None])`
  - `Worker(fn: Callable[[WorkerContext], Any], name: str)` (QRunnable, `autoDelete=False`) với `.signals`, `.cancel: CancelToken`. Lỗi `WFlashError` → log ERROR (traceback ở DEBUG); lỗi khác → log kèm traceback; cancel → WARNING. Luôn phát `finished` cuối cùng.

- [ ] **Step 1: Viết test fail `tests/test_workers.py`**

```python
from PySide6.QtCore import QThreadPool

from wflash.core.errors import CancelledError
from wflash.gui.workers import Worker


def start(worker):
    QThreadPool.globalInstance().start(worker)


def test_success_returns_result(qtbot):
    worker = Worker(lambda ctx: 42, "t-success")
    with qtbot.waitSignal(worker.signals.succeeded, timeout=2000) as blocker:
        start(worker)
    assert blocker.args == [42]


def test_failure_emits_exception(qtbot):
    def fn(ctx):
        raise ValueError("nope")

    worker = Worker(fn, "t-fail")
    with qtbot.waitSignal(worker.signals.failed, timeout=2000) as blocker:
        start(worker)
    assert isinstance(blocker.args[0], ValueError)


def test_progress_and_step_forwarded(qtbot):
    def fn(ctx):
        ctx.step("S1")
        ctx.progress(50, "half")

    worker = Worker(fn, "t-progress")
    steps, progress = [], []
    worker.signals.step.connect(steps.append)
    worker.signals.progress.connect(lambda p, m: progress.append((p, m)))
    with qtbot.waitSignal(worker.signals.finished, timeout=2000):
        start(worker)
    qtbot.waitUntil(lambda: steps == ["S1"] and progress == [(50, "half")], timeout=1000)


def test_cancel(qtbot):
    def fn(ctx):
        while not ctx.cancel.wait(0.01):
            pass
        ctx.cancel.raise_if_cancelled()

    worker = Worker(fn, "t-cancel")
    with qtbot.waitSignal(worker.signals.failed, timeout=2000) as blocker:
        start(worker)
        worker.cancel.cancel()
    assert isinstance(blocker.args[0], CancelledError)
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_workers.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'wflash.gui.workers'`

- [ ] **Step 3: Implement `wflash/gui/workers.py`**

```python
"""Run blocking work on QThreadPool and report back to the GUI thread through Qt signals."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal

from wflash.core.cancel import CancelToken
from wflash.core.errors import CancelledError, WFlashError
from wflash.core.logging_setup import get_logger

log = get_logger("worker")


class WorkerSignals(QObject):
    progress = Signal(object, str)
    step = Signal(str)
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()


@dataclass
class WorkerContext:
    cancel: CancelToken
    progress: Callable[[int | None, str], None]
    step: Callable[[str], None]


class Worker(QRunnable):
    def __init__(self, fn: Callable[[WorkerContext], Any], name: str) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.fn = fn
        self.name = name
        self.signals = WorkerSignals()
        self.cancel = CancelToken()

    def run(self) -> None:
        threading.current_thread().name = f"worker-{self.name}"
        ctx = WorkerContext(
            cancel=self.cancel,
            progress=lambda percent, message: self.signals.progress.emit(percent, message),
            step=self.signals.step.emit,
        )
        log.debug("%s started", self.name)
        try:
            result = self.fn(ctx)
        except CancelledError as exc:
            log.warning("%s cancelled", self.name)
            self.signals.failed.emit(exc)
        except WFlashError as exc:
            log.error("%s failed: %s%s", self.name, exc, f" (hint: {exc.hint})" if exc.hint else "")
            log.debug("%s traceback", self.name, exc_info=True)
            self.signals.failed.emit(exc)
        except Exception as exc:
            log.exception("%s crashed: %s", self.name, exc)
            self.signals.failed.emit(exc)
        else:
            log.debug("%s finished", self.name)
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_workers.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add wflash/gui/workers.py tests/test_workers.py
git commit -m "feat(gui): add QThreadPool worker with cancel, progress and error signals" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Settings dialog

**Files:**
- Create: `wflash/gui/settings_dialog.py`
- Test: `tests/test_settings_dialog.py`

**Interfaces:**
- Consumes: `AppSettings`, `default_cache_dir`, `bundled_profiles_dir` (Task 8).
- Produces: `SettingsDialog(settings: AppSettings, token: str, parent=None)` với widget `url_edit`, `token_edit`, `ca_edit`, `cache_edit`, `max_jobs_spin`, `profiles_edit`, `verbose_check`, `error_label`, `buttons: QDialogButtonBox`; `result_settings() -> AppSettings` (bản sao mới, giữ `last_profile`), `result_token() -> str`. Validate khi OK: URL phải bắt đầu `http://`/`https://` (nếu không rỗng); CA bundle phải là file tồn tại (nếu không rỗng).

- [ ] **Step 1: Viết test fail `tests/test_settings_dialog.py`**

```python
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from wflash.core.settings import AppSettings
from wflash.gui.settings_dialog import SettingsDialog


def make(qtbot, **kwargs):
    dialog = SettingsDialog(AppSettings(last_profile="keep.yaml", **kwargs), "old-token")
    qtbot.addWidget(dialog)
    return dialog


def test_accept_returns_new_settings(qtbot, tmp_path):
    dialog = make(qtbot)
    ca = tmp_path / "ca.pem"
    ca.write_text("cert")
    dialog.url_edit.setText("https://gitlab.example.com/ ")
    dialog.token_edit.setText(" glpat-new ")
    dialog.ca_edit.setText(str(ca))
    dialog.max_jobs_spin.setValue(5)
    dialog.verbose_check.setChecked(True)
    dialog.buttons.button(QDialogButtonBox.Ok).click()
    assert dialog.result() == QDialog.Accepted
    result = dialog.result_settings()
    assert result.gitlab_url == "https://gitlab.example.com"
    assert result.ca_bundle == str(ca)
    assert result.max_cached_jobs == 5
    assert result.verbose is True
    assert result.last_profile == "keep.yaml"
    assert dialog.result_token() == "glpat-new"


def test_invalid_url_blocks_accept(qtbot):
    dialog = make(qtbot)
    dialog.url_edit.setText("gitlab.example.com")
    dialog.buttons.button(QDialogButtonBox.Ok).click()
    assert dialog.result() != QDialog.Accepted
    assert "http" in dialog.error_label.text()


def test_missing_ca_file_blocks_accept(qtbot, tmp_path):
    dialog = make(qtbot)
    dialog.url_edit.setText("https://gl")
    dialog.ca_edit.setText(str(tmp_path / "missing.pem"))
    dialog.buttons.button(QDialogButtonBox.Ok).click()
    assert dialog.result() != QDialog.Accepted
    assert "CA bundle" in dialog.error_label.text()
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_settings_dialog.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'wflash.gui.settings_dialog'`

- [ ] **Step 3: Implement `wflash/gui/settings_dialog.py`**

```python
"""Settings dialog: GitLab URL/token, CA bundle, cache, profiles folder, verbose logging."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wflash.core.settings import AppSettings, bundled_profiles_dir, default_cache_dir


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, token: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        self._settings = settings

        self.url_edit = QLineEdit(settings.gitlab_url)
        self.url_edit.setPlaceholderText("https://gitlab.company.com")
        self.token_edit = QLineEdit(token)
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.token_edit.setPlaceholderText("Personal Access Token (scope read_api)")
        self.ca_edit = QLineEdit(settings.ca_bundle)
        self.ca_edit.setPlaceholderText("Optional: .pem file for an internal certificate")
        self.cache_edit = QLineEdit(settings.cache_dir)
        self.cache_edit.setPlaceholderText(str(default_cache_dir()))
        self.max_jobs_spin = QSpinBox()
        self.max_jobs_spin.setRange(1, 100)
        self.max_jobs_spin.setValue(settings.max_cached_jobs)
        self.profiles_edit = QLineEdit(settings.profiles_dir)
        self.profiles_edit.setPlaceholderText(str(bundled_profiles_dir()))
        self.verbose_check = QCheckBox("Verbose winIDEA call logging")
        self.verbose_check.setChecked(settings.verbose)
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #d32f2f;")
        self.error_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow("GitLab URL:", self.url_edit)
        form.addRow("Access token:", self.token_edit)
        form.addRow("CA bundle:", self._with_browse(self.ca_edit, directory=False))
        form.addRow("Cache folder:", self._with_browse(self.cache_edit, directory=True))
        form.addRow("Cached jobs to keep:", self.max_jobs_spin)
        form.addRow("Profiles folder:", self._with_browse(self.profiles_edit, directory=True))
        form.addRow("", self.verbose_check)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(self.buttons)

    def _with_browse(self, edit: QLineEdit, directory: bool) -> QWidget:
        button = QPushButton("Browse…")
        button.clicked.connect(lambda: self._browse(edit, directory))
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit, 1)
        row.addWidget(button)
        return container

    def _browse(self, edit: QLineEdit, directory: bool) -> None:
        if directory:
            path = QFileDialog.getExistingDirectory(self, "Select folder", edit.text())
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select CA bundle", edit.text(), "Certificates (*.pem *.crt *.cer);;All files (*)"
            )
        if path:
            edit.setText(path)

    def _on_accept(self) -> None:
        url = self.url_edit.text().strip()
        if url and not url.startswith(("http://", "https://")):
            self.error_label.setText("GitLab URL must start with http:// or https://")
            return
        ca = self.ca_edit.text().strip()
        if ca and not Path(ca).is_file():
            self.error_label.setText(f"CA bundle file not found: {ca}")
            return
        self.error_label.clear()
        self.accept()

    def result_settings(self) -> AppSettings:
        return replace(
            self._settings,
            gitlab_url=self.url_edit.text().strip().rstrip("/"),
            ca_bundle=self.ca_edit.text().strip(),
            cache_dir=self.cache_edit.text().strip(),
            max_cached_jobs=self.max_jobs_spin.value(),
            profiles_dir=self.profiles_edit.text().strip(),
            verbose=self.verbose_check.isChecked(),
        )

    def result_token(self) -> str:
        return self.token_edit.text().strip()
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_settings_dialog.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add wflash/gui/settings_dialog.py tests/test_settings_dialog.py
git commit -m "feat(gui): add settings dialog with validation" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: GitLab panel

**Files:**
- Create: `wflash/gui/gitlab_panel.py`, `tests/stubs.py`
- Test: `tests/test_gitlab_panel.py`

**Interfaces:**
- Consumes: `GitLabClient`, `Ref`, `Pipeline`, `Job` (Task 7), `ArtifactCache` (Task 6), `Profile` (Task 4), `Worker`, `WorkerContext` (Task 13).
- Produces:
  - `GitLabPanel(client_provider: Callable[[], GitLabClient], cache_provider: Callable[[], ArtifactCache], pool: QThreadPool | None = None, parent=None)`
  - Signals: `artifactReady(object path: Path, str label)`, `errorOccurred(object exc)`
  - Methods: `set_profile(profile: Profile)`, `refresh()`, `download_selected()`, `cancel_download()`
  - Widgets: `ref_combo`, `refresh_btn`, `pipeline_list`, `job_list`, `download_btn`, `cancel_btn`, `progress`
  - `client_provider` được gọi trong worker thread (có thể raise `GitLabError` nếu thiếu cấu hình).
  - `tests/stubs.py::StubClient` dùng chung cho Task 15 và Task 17.

- [ ] **Step 1: Tạo `tests/stubs.py`**

```python
"""Test doubles shared by GUI tests."""
import zipfile

from wflash.core.gitlab_client import Job, Pipeline, Ref


class StubClient:
    def __init__(self):
        self.downloads = 0

    def get_project_id(self, project):
        return 42

    def list_refs(self, project_id):
        return [Ref("main", "branch"), Ref("v1.0", "tag")]

    def list_pipelines(self, project_id, ref, limit=20):
        return [Pipeline(100, ref, "success", "abcdef1234567", "2026-10-01T10:00:00Z")]

    def list_jobs(self, project_id, pipeline_id, name_glob="*"):
        return [Job(7, "build_app", "build", "success", "")]

    def download_artifacts(self, project_id, job_id, dest, progress_cb=None, cancel=None):
        self.downloads += 1
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / f"artifacts_{job_id}.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("out/App.s3", "S0")
            zf.writestr("out/x_cm7_0.elf", "E0")
            zf.writestr("out/x_cm7_1.elf", "E1")
        if progress_cb:
            progress_cb(10, 10)
        return path
```

- [ ] **Step 2: Viết test fail `tests/test_gitlab_panel.py`**

```python
from pathlib import Path

import pytest

from tests.stubs import StubClient
from wflash.core.artifact_cache import ArtifactCache
from wflash.core.errors import GitLabError
from wflash.core.profile import load_profile
from wflash.gui.gitlab_panel import GitLabPanel

EXAMPLE = Path(__file__).resolve().parents[1] / "profiles" / "saf85xx_example.yaml"


@pytest.fixture
def setup(qtbot, tmp_path):
    client = StubClient()
    cache = ArtifactCache(tmp_path / "cache")
    panel = GitLabPanel(lambda: client, lambda: cache)
    qtbot.addWidget(panel)
    panel.set_profile(load_profile(EXAMPLE))
    return panel, client


def browse_to_job(panel, qtbot):
    panel.refresh()
    qtbot.waitUntil(lambda: panel.pipeline_list.count() == 1, timeout=3000)
    panel.pipeline_list.setCurrentRow(0)
    qtbot.waitUntil(lambda: panel.job_list.count() == 1, timeout=3000)
    panel.job_list.setCurrentRow(0)
    qtbot.waitUntil(panel.download_btn.isEnabled, timeout=3000)


def test_browse_and_download(setup, qtbot):
    panel, client = setup
    browse_to_job(panel, qtbot)
    assert panel.ref_combo.count() == 2
    assert "build_app" in panel.job_list.item(0).text()
    with qtbot.waitSignal(panel.artifactReady, timeout=3000) as blocker:
        panel.download_btn.click()
    path, label = blocker.args
    assert (path / "out" / "App.s3").read_text() == "S0"
    assert "#7" in label and "build_app" in label


def test_second_download_uses_cache(setup, qtbot):
    panel, client = setup
    browse_to_job(panel, qtbot)
    for _ in range(2):
        with qtbot.waitSignal(panel.artifactReady, timeout=3000):
            panel.download_btn.click()
        qtbot.waitUntil(panel.download_btn.isEnabled, timeout=3000)
    assert client.downloads == 1


def test_provider_error_is_emitted(qtbot, tmp_path):
    def provider():
        raise GitLabError("GitLab URL or token is not configured")

    panel = GitLabPanel(provider, lambda: ArtifactCache(tmp_path))
    qtbot.addWidget(panel)
    panel.set_profile(load_profile(EXAMPLE))
    with qtbot.waitSignal(panel.errorOccurred, timeout=3000) as blocker:
        panel.refresh()
    assert isinstance(blocker.args[0], GitLabError)
```

- [ ] **Step 3: Chạy test, xác nhận fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_gitlab_panel.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'wflash.gui.gitlab_panel'`

- [ ] **Step 4: Implement `wflash/gui/gitlab_panel.py`**

```python
"""GitLab browser: ref → pipeline → job, then download (or reuse cached) artifacts."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QThreadPool, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wflash.core.artifact_cache import ArtifactCache
from wflash.core.gitlab_client import GitLabClient, Job, Pipeline, Ref
from wflash.core.logging_setup import get_logger
from wflash.core.profile import Profile
from wflash.gui.workers import Worker, WorkerContext

log = get_logger("ui.gitlab")
ROLE = Qt.UserRole


class GitLabPanel(QWidget):
    artifactReady = Signal(object, str)
    errorOccurred = Signal(object)

    def __init__(
        self,
        client_provider: Callable[[], GitLabClient],
        cache_provider: Callable[[], ArtifactCache],
        pool: QThreadPool | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client_provider = client_provider
        self._cache_provider = cache_provider
        self._pool = pool or QThreadPool.globalInstance()
        self._profile: Profile | None = None
        self._project_id: int | None = None
        self._workers: set[Worker] = set()
        self._download_worker: Worker | None = None

        self.project_label = QLabel("No profile")
        self.ref_combo = QComboBox()
        self.refresh_btn = QPushButton("Refresh")
        self.pipeline_list = QListWidget()
        self.job_list = QListWidget()
        self.download_btn = QPushButton("Download artifact")
        self.cancel_btn = QPushButton("Cancel")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        ref_row = QHBoxLayout()
        ref_row.addWidget(QLabel("Branch/tag:"))
        ref_row.addWidget(self.ref_combo, 1)
        ref_row.addWidget(self.refresh_btn)
        dl_row = QHBoxLayout()
        dl_row.addWidget(self.progress, 1)
        dl_row.addWidget(self.cancel_btn)
        dl_row.addWidget(self.download_btn)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.project_label)
        layout.addLayout(ref_row)
        layout.addWidget(QLabel("Pipelines:"))
        layout.addWidget(self.pipeline_list, 2)
        layout.addWidget(QLabel("Jobs with artifacts:"))
        layout.addWidget(self.job_list, 1)
        layout.addLayout(dl_row)

        self.refresh_btn.clicked.connect(self.refresh)
        self.ref_combo.currentIndexChanged.connect(self._on_ref_changed)
        self.pipeline_list.currentItemChanged.connect(self._on_pipeline_changed)
        self.job_list.currentItemChanged.connect(self._update_buttons)
        self.download_btn.clicked.connect(self.download_selected)
        self.cancel_btn.clicked.connect(self.cancel_download)
        self._update_buttons()

    # -- plumbing -----------------------------------------------------------------
    def _start(self, name: str, fn: Callable[[WorkerContext], object], on_success, on_progress=None) -> Worker:
        worker = Worker(fn, name)
        self._workers.add(worker)
        worker.signals.succeeded.connect(on_success)
        worker.signals.failed.connect(self.errorOccurred.emit)
        if on_progress is not None:
            worker.signals.progress.connect(on_progress)
        worker.signals.finished.connect(lambda w=worker: self._on_worker_finished(w))
        self._pool.start(worker)
        return worker

    def _on_worker_finished(self, worker: Worker) -> None:
        self._workers.discard(worker)
        if worker is self._download_worker:
            self._download_worker = None
        self._update_buttons()

    def _update_buttons(self, *_args) -> None:
        downloading = self._download_worker is not None
        self.refresh_btn.setEnabled(self._profile is not None)
        self.download_btn.setEnabled(self.job_list.currentItem() is not None and not downloading)
        self.cancel_btn.setEnabled(downloading)

    # -- browsing -----------------------------------------------------------------
    def set_profile(self, profile: Profile) -> None:
        self._profile = profile
        self._project_id = None
        self.project_label.setText(f"Project: {profile.gitlab.project}  (jobs: {profile.gitlab.job_filter})")
        self.ref_combo.blockSignals(True)
        self.ref_combo.clear()
        self.ref_combo.blockSignals(False)
        self.pipeline_list.clear()
        self.job_list.clear()
        self._update_buttons()

    def refresh(self) -> None:
        if self._profile is None:
            return
        project = self._profile.gitlab.project

        def job(ctx: WorkerContext):
            client = self._client_provider()
            project_id = client.get_project_id(project)
            return project_id, client.list_refs(project_id)

        self._start("gitlab-refs", job, self._on_refs)

    def _on_refs(self, result: tuple[int, list[Ref]]) -> None:
        self._project_id, refs = result
        self.ref_combo.blockSignals(True)
        self.ref_combo.clear()
        for ref in refs:
            self.ref_combo.addItem(ref.name + (" (tag)" if ref.kind == "tag" else ""), ref.name)
        self.ref_combo.blockSignals(False)
        log.info("Loaded %d branches/tags", len(refs))
        self._on_ref_changed()

    def _on_ref_changed(self, *_args) -> None:
        ref = self.ref_combo.currentData()
        self.pipeline_list.clear()
        self.job_list.clear()
        if ref is None or self._project_id is None:
            return
        project_id = self._project_id

        def job(ctx: WorkerContext):
            client = self._client_provider()
            return ref, client.list_pipelines(project_id, ref)

        self._start("gitlab-pipelines", job, self._on_pipelines)

    def _on_pipelines(self, result: tuple[str, list[Pipeline]]) -> None:
        ref, pipelines = result
        if ref != self.ref_combo.currentData():
            return
        self.pipeline_list.clear()
        for p in pipelines:
            created = p.created_at[:16].replace("T", " ")
            item = QListWidgetItem(f"#{p.id}   {p.status:<9} {created}   {p.sha[:8]}")
            item.setData(ROLE, p.id)
            self.pipeline_list.addItem(item)

    def _on_pipeline_changed(self, current: QListWidgetItem | None, _previous=None) -> None:
        self.job_list.clear()
        if current is None or self._project_id is None or self._profile is None:
            self._update_buttons()
            return
        project_id = self._project_id
        pipeline_id = current.data(ROLE)
        job_filter = self._profile.gitlab.job_filter

        def job(ctx: WorkerContext):
            client = self._client_provider()
            return pipeline_id, client.list_jobs(project_id, pipeline_id, job_filter)

        self._start("gitlab-jobs", job, self._on_jobs)

    def _on_jobs(self, result: tuple[int, list[Job]]) -> None:
        pipeline_id, jobs = result
        current = self.pipeline_list.currentItem()
        if current is None or current.data(ROLE) != pipeline_id:
            return
        self.job_list.clear()
        for j in jobs:
            item = QListWidgetItem(f"{j.name}   [{j.stage}]   {j.status}")
            item.setData(ROLE, (j.id, j.name))
            self.job_list.addItem(item)
        if not jobs:
            log.warning("Pipeline #%s has no jobs with artifacts matching the profile filter", pipeline_id)
        self._update_buttons()

    # -- download -----------------------------------------------------------------
    def download_selected(self) -> None:
        item = self.job_list.currentItem()
        if item is None or self._project_id is None or self._profile is None:
            return
        job_id, job_name = item.data(ROLE)
        project_id = self._project_id
        label = f"{self._profile.gitlab.project}  job #{job_id} ({job_name})"

        def job(ctx: WorkerContext) -> Path:
            cache = self._cache_provider()
            cached = cache.get(project_id, job_id)
            if cached is not None:
                log.info("Using cached artifact for job #%s: %s", job_id, cached)
                return cached
            client = self._client_provider()
            with tempfile.TemporaryDirectory(prefix="wflash_dl_") as tmp:
                zip_path = client.download_artifacts(
                    project_id,
                    job_id,
                    Path(tmp),
                    progress_cb=lambda done, total: ctx.progress(
                        int(done * 100 / total) if total else None, f"{done / 1e6:.1f} MB"
                    ),
                    cancel=ctx.cancel,
                )
                ctx.progress(None, "Extracting")
                return cache.store_zip(project_id, job_id, zip_path)

        def done(path: Path) -> None:
            self.progress.setRange(0, 100)
            self.progress.setValue(100)
            self.progress.setFormat("Ready")
            self.artifactReady.emit(path, label)

        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._download_worker = self._start("gitlab-download", job, done, on_progress=self._on_progress)
        self._update_buttons()

    def cancel_download(self) -> None:
        if self._download_worker is not None:
            log.warning("Artifact download cancel requested")
            self._download_worker.cancel.cancel()

    def _on_progress(self, percent: int | None, message: str) -> None:
        if percent is None:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(percent)
        self.progress.setFormat(message)
```

- [ ] **Step 5: Chạy test, xác nhận pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_gitlab_panel.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add wflash/gui/gitlab_panel.py tests/stubs.py tests/test_gitlab_panel.py
git commit -m "feat(gui): add GitLab pipeline/job browser with cached artifact download" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 16: Mapping table

**Files:**
- Create: `wflash/gui/mapping_table.py`
- Test: `tests/test_mapping_table.py`

**Interfaces:**
- Consumes: `MappingRow`, `candidates_for_kind` (Task 5).
- Produces: `MappingTable(QTableWidget)` với signal `mappingChanged()`; methods `set_rows(rows: list[MappingRow], root: Path)`, `clear_rows()`, `rows() -> list[MappingRow]`, `all_ok() -> bool`. Cột 3 là `QComboBox` (mục 0 = `"-- select file --"`, data `None`; các mục sau data là `Path`). Nếu row không có candidate, combo liệt kê mọi file cùng loại (`candidates_for_kind`). Combo chưa chọn có stylesheet chứa `#ffcdd2`.

- [ ] **Step 1: Viết test fail `tests/test_mapping_table.py`**

```python
from pathlib import Path

from wflash.core.file_matcher import build_mapping
from wflash.core.profile import load_profile
from wflash.gui.mapping_table import MappingTable

EXAMPLE = Path(__file__).resolve().parents[1] / "profiles" / "saf85xx_example.yaml"


def make_files(root, names):
    for rel in names:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")


def make_table(qtbot, root):
    table = MappingTable()
    qtbot.addWidget(table)
    table.set_rows(build_mapping(load_profile(EXAMPLE), root), root)
    return table


def test_all_selected_when_unique(qtbot, tmp_path):
    make_files(tmp_path, ["App.s3", "x_cm7_0.elf", "x_cm7_1.elf"])
    table = make_table(qtbot, tmp_path)
    assert table.rowCount() == 3
    assert table.all_ok()
    assert table.cellWidget(0, 3).currentText() == "App.s3"
    assert "#ffcdd2" not in table.cellWidget(0, 3).styleSheet()


def test_manual_selection_resolves_ambiguity_and_missing(qtbot, tmp_path):
    make_files(tmp_path, ["a/App.s3", "b/App.s3", "x_cm7_0.elf", "other.elf"])
    table = make_table(qtbot, tmp_path)
    assert not table.all_ok()
    program = table.cellWidget(0, 3)
    cm7_1 = table.cellWidget(2, 3)
    assert program.count() == 3
    assert "#ffcdd2" in program.styleSheet()
    assert cm7_1.count() == 3  # "-- select --" + every .elf in the artifact
    with qtbot.waitSignal(table.mappingChanged, timeout=1000):
        program.setCurrentIndex(program.findText("b/App.s3"))
    cm7_1.setCurrentIndex(cm7_1.findText("other.elf"))
    assert table.all_ok()
    assert table.rows()[0].selected == tmp_path / "b" / "App.s3"
    assert table.rows()[2].selected == tmp_path / "other.elf"


def test_clear_rows(qtbot, tmp_path):
    make_files(tmp_path, ["App.s3", "x_cm7_0.elf", "x_cm7_1.elf"])
    table = make_table(qtbot, tmp_path)
    table.clear_rows()
    assert table.rowCount() == 0
    assert not table.all_ok()
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_mapping_table.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'wflash.gui.mapping_table'`

- [ ] **Step 3: Implement `wflash/gui/mapping_table.py`**

```python
"""Table showing which artifact file goes to which winIDEA entry; unresolved rows are red."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QHeaderView, QTableWidget, QTableWidgetItem, QWidget

from wflash.core.file_matcher import MappingRow, candidates_for_kind

COLUMNS = ["Type", "winIDEA target", "Pattern", "File"]
NONE_TEXT = "-- select file --"
MISSING_STYLE = "QComboBox { background-color: #ffcdd2; color: black; }"


class MappingTable(QTableWidget):
    mappingChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, len(COLUMNS), parent)
        self.setHorizontalHeaderLabels(COLUMNS)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self._rows: list[MappingRow] = []

    def set_rows(self, rows: list[MappingRow], root: Path) -> None:
        self._rows = rows
        self.setRowCount(len(rows))
        for i, row in enumerate(rows):
            kind_text = "Program (.s3)" if row.kind == "program" else "Symbols (.elf)"
            for col, text in enumerate((kind_text, row.target, row.pattern)):
                self.setItem(i, col, QTableWidgetItem(text))
            combo = QComboBox()
            combo.addItem(NONE_TEXT, None)
            options = row.candidates or candidates_for_kind(root, row.kind)
            for path in options:
                combo.addItem(path.relative_to(root).as_posix(), path)
            if row.selected is not None:
                combo.setCurrentIndex(options.index(row.selected) + 1)
            combo.currentIndexChanged.connect(lambda _index, r=i, c=combo: self._on_choice(r, c))
            self.setCellWidget(i, 3, combo)
            self._paint(i)
        self.resizeColumnsToContents()
        self.mappingChanged.emit()

    def clear_rows(self) -> None:
        self._rows = []
        self.setRowCount(0)
        self.mappingChanged.emit()

    def _on_choice(self, index: int, combo: QComboBox) -> None:
        self._rows[index].selected = combo.currentData()
        self._paint(index)
        self.mappingChanged.emit()

    def _paint(self, index: int) -> None:
        combo = self.cellWidget(index, 3)
        combo.setStyleSheet("" if self._rows[index].ok else MISSING_STYLE)

    def rows(self) -> list[MappingRow]:
        return list(self._rows)

    def all_ok(self) -> bool:
        return bool(self._rows) and all(row.ok for row in self._rows)
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_mapping_table.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add wflash/gui/mapping_table.py tests/test_mapping_table.py
git commit -m "feat(gui): add mapping table with manual file selection" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 17: Main window

**Files:**
- Create: `wflash/gui/main_window.py`
- Test: `tests/test_main_window.py`

**Interfaces:**
- Consumes: mọi thứ từ Task 4–16: `AppSettings`, `get_token`, `set_token` (8), `GitLabClient` (7), `ArtifactCache` (6), `build_mapping` (5), `load_profile`, `list_profiles` (4), `FlashWorkflow`, `FlashRequest` (11), `DebugContext`, `create_debug_bundle` (10), `WinIDEAAdapter` (9), `LogPanel` (12), `Worker` (13), `SettingsDialog` (14), `GitLabPanel` (15), `MappingTable` (16), `LOGGER_NAME`, `register_secret`, `set_verbose` (3).
- Produces:
  - `default_client_factory(settings: AppSettings) -> GitLabClient` (raise `GitLabError` nếu thiếu URL/token)
  - `MainWindow(settings: AppSettings, adapter: WinIDEAAdapter, client_factory=default_client_factory, log_file: Path | None = None, settings_path: Path | None = None, pool: QThreadPool | None = None)`
  - Public: `profile`, `ctx: DebugContext`, `artifact_root`, widgets `profile_combo`, `settings_btn`, `gitlab_panel`, `mapping_table`, `instance_combo`, `refresh_instances_btn`, `reset_check`, `run_check`, `flash_btn`, `cancel_btn`, `step_label`, `progress`, `log_panel`; methods `reload_profiles()`, `on_artifact_ready(path: Path, label: str)`, `refresh_instances()`, `start_flash()`, `cancel_flash()`, `export_bundle(dest_dir: Path) -> Path`, `show_error(exc: BaseException)`, `open_settings()`
  - `step_label` hiển thị `Step.value` trong lúc flash, `"Failed"` khi lỗi, `"Cancelled"` khi hủy.

- [ ] **Step 1: Viết test fail `tests/test_main_window.py`**

```python
import json
import shutil
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from tests.stubs import StubClient
from wflash.core.fake_adapter import FakeWinIDEAAdapter
from wflash.core.settings import AppSettings
from wflash.gui.main_window import MainWindow

EXAMPLE = Path(__file__).resolve().parents[1] / "profiles" / "saf85xx_example.yaml"
OLD_APP = r"C:\fake\old\App.s3"


@pytest.fixture
def env(qtbot, tmp_path, monkeypatch):
    errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: errors.append(args[2]))
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    shutil.copy(EXAMPLE, profiles / "saf.yaml")
    settings = AppSettings(profiles_dir=str(profiles), cache_dir=str(tmp_path / "cache"))
    adapter = FakeWinIDEAAdapter(download_seconds=0.2)
    window = MainWindow(
        settings, adapter, client_factory=lambda s: StubClient(), settings_path=tmp_path / "settings.json"
    )
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: window.instance_combo.count() == 1, timeout=3000)
    artifact = tmp_path / "artifact"
    for rel in ("out/App.s3", "out/x_cm7_0.elf", "out/x_cm7_1.elf"):
        path = artifact / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    return SimpleNamespace(window=window, adapter=adapter, artifact=artifact, errors=errors, tmp=tmp_path)


def test_profile_loaded_on_start(env):
    assert env.window.profile.name == "SAF85xx_Radar"
    assert json.loads((env.tmp / "settings.json").read_text())["last_profile"] == "saf.yaml"
    assert not env.window.flash_btn.isEnabled()


def test_flash_happy_path(env, qtbot):
    w = env.window
    w.on_artifact_ready(env.artifact, "job #7")
    assert w.flash_btn.isEnabled()
    qtbot.mouseClick(w.flash_btn, Qt.LeftButton)
    assert not w.settings_btn.isEnabled()
    qtbot.waitUntil(lambda: w.step_label.text() == "Done", timeout=5000)
    qtbot.waitUntil(w.flash_btn.isEnabled, timeout=2000)
    assert env.adapter.programs["App"] == str((env.artifact / "out" / "App.s3").resolve())
    assert env.adapter.target_state == "halted"
    assert env.errors == []


def test_ambiguous_mapping_blocks_flash(env):
    (env.artifact / "out" / "y_cm7_0.elf").write_bytes(b"x")
    env.window.on_artifact_ready(env.artifact, "job #7")
    assert not env.window.flash_btn.isEnabled()


def test_flash_failure_shows_error_rolls_back_and_exports(env, qtbot):
    env.adapter.fail_on = {"download"}
    w = env.window
    w.on_artifact_ready(env.artifact, "job #7")
    qtbot.mouseClick(w.flash_btn, Qt.LeftButton)
    qtbot.waitUntil(lambda: bool(env.errors), timeout=5000)
    assert "injected" in env.errors[0]
    assert "Export debug bundle" in env.errors[0]
    assert w.step_label.text() == "Failed"
    assert env.adapter.programs["App"] == OLD_APP
    qtbot.waitUntil(w.flash_btn.isEnabled, timeout=2000)
    bundle = w.export_bundle(env.tmp / "bundle")
    with zipfile.ZipFile(bundle) as zf:
        assert "injected" in zf.read("errors.txt").decode()
        assert "after_rollback" in zf.read("workspace_snapshots.json").decode()


def test_cancel_flash(env, qtbot):
    env.adapter.download_seconds = 5
    w = env.window
    w.on_artifact_ready(env.artifact, "job #7")
    qtbot.mouseClick(w.flash_btn, Qt.LeftButton)
    qtbot.waitUntil(lambda: w.step_label.text() == "Downloading to external flash", timeout=3000)
    qtbot.mouseClick(w.cancel_btn, Qt.LeftButton)
    qtbot.waitUntil(lambda: w.step_label.text() == "Cancelled", timeout=3000)
    qtbot.waitUntil(w.flash_btn.isEnabled, timeout=2000)
    assert env.adapter.programs["App"] == OLD_APP
    assert env.errors == []
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_main_window.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'wflash.gui.main_window'`

- [ ] **Step 3: Implement `wflash/gui/main_window.py`**

```python
"""Main window: profile → GitLab artifact → file mapping → flash via winIDEA, with log panel."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from wflash.core.artifact_cache import ArtifactCache
from wflash.core.debug_bundle import DebugContext, create_debug_bundle
from wflash.core.errors import CancelledError, GitLabError, ProfileError, WinIDEAError
from wflash.core.file_matcher import build_mapping
from wflash.core.flash_workflow import FlashRequest, FlashWorkflow
from wflash.core.gitlab_client import GitLabClient
from wflash.core.logging_setup import LOGGER_NAME, get_logger, register_secret, set_verbose
from wflash.core.profile import Profile, list_profiles, load_profile
from wflash.core.settings import AppSettings, get_token, set_token
from wflash.core.winidea_adapter import InstanceInfo, WinIDEAAdapter
from wflash.gui.gitlab_panel import GitLabPanel
from wflash.gui.log_panel import LogPanel
from wflash.gui.mapping_table import MappingTable
from wflash.gui.settings_dialog import SettingsDialog
from wflash.gui.workers import Worker, WorkerContext

log = get_logger("ui")
ClientFactory = Callable[[AppSettings], GitLabClient]


def default_client_factory(settings: AppSettings) -> GitLabClient:
    token = get_token(settings.gitlab_url)
    if not settings.gitlab_url or not token:
        raise GitLabError(
            "GitLab URL or token is not configured",
            hint="Open Settings… and enter the GitLab URL and a Personal Access Token (scope read_api).",
        )
    return GitLabClient(settings.gitlab_url, token, ca_bundle=settings.ca_bundle or None)


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: AppSettings,
        adapter: WinIDEAAdapter,
        client_factory: ClientFactory = default_client_factory,
        log_file: Path | None = None,
        settings_path: Path | None = None,
        pool: QThreadPool | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("WFlash — winIDEA ECU flasher")
        self.settings = settings
        self.adapter = adapter
        self.log_file = log_file
        self._client_factory = client_factory
        self._settings_path = settings_path
        self._pool = pool or QThreadPool.globalInstance()
        self.ctx = DebugContext()
        self.profile: Profile | None = None
        self.artifact_root: Path | None = None
        self._workers: set[Worker] = set()
        self._flash_worker: Worker | None = None

        self.log_panel = LogPanel()
        logging.getLogger(LOGGER_NAME).addHandler(self.log_panel.handler)

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(220)
        self.reload_profiles_btn = QPushButton("Reload")
        self.settings_btn = QPushButton("Settings…")
        self.gitlab_panel = GitLabPanel(self._make_client, self._make_cache, self._pool)
        self.artifact_label = QLabel("No artifact loaded")
        self.artifact_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.mapping_table = MappingTable()
        self.instance_combo = QComboBox()
        self.refresh_instances_btn = QPushButton("Refresh")
        self.reset_check = QCheckBox("Reset after flash")
        self.reset_check.setChecked(True)
        self.run_check = QCheckBox("Run after reset")
        self.flash_btn = QPushButton("Flash")
        self.cancel_btn = QPushButton("Cancel")
        self.step_label = QLabel("Idle")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        self._build_layout()
        self._connect_signals()
        self.reload_profiles()
        self.refresh_instances()
        self._update_buttons()

    # -- layout -------------------------------------------------------------------
    def _build_layout(self) -> None:
        top = QHBoxLayout()
        top.addWidget(QLabel("Profile:"))
        top.addWidget(self.profile_combo)
        top.addWidget(self.reload_profiles_btn)
        top.addStretch(1)
        top.addWidget(self.settings_btn)

        gitlab_box = QGroupBox("1. GitLab artifact")
        gitlab_layout = QVBoxLayout(gitlab_box)
        gitlab_layout.addWidget(self.gitlab_panel)

        mapping_box = QGroupBox("2. Files → winIDEA")
        mapping_layout = QVBoxLayout(mapping_box)
        mapping_layout.addWidget(self.artifact_label)
        mapping_layout.addWidget(self.mapping_table)

        flash_box = QGroupBox("3. Flash")
        flash_layout = QVBoxLayout(flash_box)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("winIDEA instance:"))
        row1.addWidget(self.instance_combo, 1)
        row1.addWidget(self.refresh_instances_btn)
        row2 = QHBoxLayout()
        row2.addWidget(self.reset_check)
        row2.addWidget(self.run_check)
        row2.addStretch(1)
        row2.addWidget(self.cancel_btn)
        row2.addWidget(self.flash_btn)
        row3 = QHBoxLayout()
        row3.addWidget(self.step_label)
        row3.addWidget(self.progress, 1)
        flash_layout.addLayout(row1)
        flash_layout.addLayout(row2)
        flash_layout.addLayout(row3)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(mapping_box, 1)
        right_layout.addWidget(flash_box)

        upper = QSplitter(Qt.Horizontal)
        upper.addWidget(gitlab_box)
        upper.addWidget(right)
        upper.setStretchFactor(1, 2)
        vertical = QSplitter(Qt.Vertical)
        vertical.addWidget(upper)
        vertical.addWidget(self.log_panel)
        vertical.setStretchFactor(0, 3)
        vertical.setStretchFactor(1, 2)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.addLayout(top)
        central_layout.addWidget(vertical, 1)
        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        self.reload_profiles_btn.clicked.connect(self.reload_profiles)
        self.settings_btn.clicked.connect(self.open_settings)
        self.gitlab_panel.artifactReady.connect(self.on_artifact_ready)
        self.gitlab_panel.errorOccurred.connect(self._on_worker_failed)
        self.mapping_table.mappingChanged.connect(self._update_buttons)
        self.refresh_instances_btn.clicked.connect(self.refresh_instances)
        self.flash_btn.clicked.connect(self.start_flash)
        self.cancel_btn.clicked.connect(self.cancel_flash)
        self.log_panel.exportRequested.connect(self._on_export_clicked)
        self.log_panel.errorLogged.connect(lambda _text: self.statusBar().showMessage("Error — see log panel", 10000))

    # -- helpers ------------------------------------------------------------------
    def _make_client(self) -> GitLabClient:
        return self._client_factory(self.settings)

    def _make_cache(self) -> ArtifactCache:
        return ArtifactCache(self.settings.resolved_cache_dir(), self.settings.max_cached_jobs)

    def _save_settings(self) -> None:
        try:
            self.settings.save(self._settings_path)
        except OSError as exc:
            log.warning("Cannot save settings: %s", exc)

    def _start(self, name: str, fn: Callable[[WorkerContext], object], on_success, on_progress=None, on_step=None) -> Worker:
        worker = Worker(fn, name)
        self._workers.add(worker)
        worker.signals.succeeded.connect(on_success)
        worker.signals.failed.connect(self._on_worker_failed)
        if on_progress is not None:
            worker.signals.progress.connect(on_progress)
        if on_step is not None:
            worker.signals.step.connect(on_step)
        worker.signals.finished.connect(lambda w=worker: self._on_worker_finished(w))
        self._pool.start(worker)
        return worker

    def _on_worker_finished(self, worker: Worker) -> None:
        self._workers.discard(worker)
        if worker is self._flash_worker:
            self._flash_worker = None
        self._update_buttons()

    def _update_buttons(self, *_args) -> None:
        flashing = self._flash_worker is not None
        self.flash_btn.setEnabled(
            not flashing
            and self.profile is not None
            and self.mapping_table.all_ok()
            and self.instance_combo.count() > 0
        )
        self.cancel_btn.setEnabled(flashing)
        for widget in (
            self.profile_combo,
            self.reload_profiles_btn,
            self.settings_btn,
            self.gitlab_panel,
            self.mapping_table,
            self.instance_combo,
            self.refresh_instances_btn,
        ):
            widget.setEnabled(not flashing)

    def show_error(self, exc: BaseException) -> None:
        hint = getattr(exc, "hint", "")
        text = str(exc)
        if hint:
            text += f"\n\nHint: {hint}"
        text += "\n\nUse 'Export debug bundle…' in the log panel to collect logs for support."
        QMessageBox.critical(self, "WFlash error", text)

    def _on_worker_failed(self, exc: BaseException) -> None:
        self.ctx.add_error(exc)
        if isinstance(exc, CancelledError):
            if self._flash_worker is not None:
                self.step_label.setText("Cancelled")
            return
        if self._flash_worker is not None:
            self.step_label.setText("Failed")
        self.show_error(exc)

    # -- profiles -----------------------------------------------------------------
    def reload_profiles(self) -> None:
        directory = self.settings.resolved_profiles_dir()
        paths = list_profiles(directory)
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for path in paths:
            self.profile_combo.addItem(path.stem, path)
        if paths:
            index = next((i for i, p in enumerate(paths) if p.name == self.settings.last_profile), 0)
            self.profile_combo.setCurrentIndex(index)
        self.profile_combo.blockSignals(False)
        if not paths:
            log.warning("No profiles found in %s", directory)
        self._on_profile_selected()

    def _on_profile_selected(self, *_args) -> None:
        path = self.profile_combo.currentData()
        self.profile = None
        self.artifact_root = None
        self.artifact_label.setText("No artifact loaded")
        self.mapping_table.clear_rows()
        if path is None:
            self._update_buttons()
            return
        try:
            profile = load_profile(path)
        except ProfileError as exc:
            log.error("%s", exc)
            self.ctx.add_error(exc)
            self.show_error(exc)
            self._update_buttons()
            return
        self.profile = profile
        self.ctx.profile_path = path
        self.reset_check.setChecked(profile.post_flash.reset)
        self.run_check.setChecked(profile.post_flash.run)
        self.gitlab_panel.set_profile(profile)
        self.settings.last_profile = path.name
        self._save_settings()
        log.info("Profile loaded: %s (%s)", profile.name, path)
        self._update_buttons()

    # -- artifact -----------------------------------------------------------------
    def on_artifact_ready(self, path: Path, label: str) -> None:
        if self.profile is None:
            return
        self.artifact_root = path
        rows = build_mapping(self.profile, path)
        self.mapping_table.set_rows(rows, path)
        self.artifact_label.setText(f"{label}\n{path}")
        for row in rows:
            if row.ok:
                log.info("%s '%s' -> %s", row.kind, row.target, row.selected.relative_to(path).as_posix())
            else:
                log.warning(
                    "%s '%s': %d file(s) match '%s'; choose a file manually",
                    row.kind, row.target, len(row.candidates), row.pattern,
                )
        self._update_buttons()

    # -- winIDEA ------------------------------------------------------------------
    def refresh_instances(self) -> None:
        self._start("winidea-instances", lambda ctx: self.adapter.list_instances(), self._on_instances)

    def _on_instances(self, instances: list[InstanceInfo]) -> None:
        self.instance_combo.clear()
        for inst in instances:
            self.instance_combo.addItem(inst.label(), inst.instance_id)
        if instances:
            log.info("Found %d winIDEA instance(s)", len(instances))
        else:
            log.warning("No running winIDEA instance found. Open winIDEA with the SAF85xx workspace and click Refresh.")
        self._update_buttons()

    def start_flash(self) -> None:
        if self._flash_worker is not None or self.profile is None or not self.mapping_table.all_ok():
            return
        instance_id = self.instance_combo.currentData()
        if instance_id is None:
            self.show_error(WinIDEAError("No winIDEA instance selected"))
            return
        request = FlashRequest(
            instance_id=instance_id,
            mapping=self.mapping_table.rows(),
            reset=self.reset_check.isChecked(),
            run=self.run_check.isChecked(),
            timeout_s=self.profile.timeouts.download_s,
        )
        adapter, ctx = self.adapter, self.ctx

        def job(wctx: WorkerContext) -> None:
            workflow = FlashWorkflow(adapter, ctx, on_step=lambda s: wctx.step(s.value), on_progress=wctx.progress)
            workflow.run(request, wctx.cancel)

        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        self._flash_worker = self._start(
            "flash", job, self._on_flash_done, on_progress=self._on_progress, on_step=self.step_label.setText
        )
        self._update_buttons()

    def cancel_flash(self) -> None:
        if self._flash_worker is not None:
            log.warning("Flash cancel requested")
            self._flash_worker.cancel.cancel()

    def _on_progress(self, percent: int | None, message: str) -> None:
        if percent is None:
            self.progress.setRange(0, 0)
            self.progress.setFormat(message)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(percent)
            self.progress.setFormat(f"%p%  {message}")

    def _on_flash_done(self, _result: object) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        log.info("Flash completed successfully")
        self.statusBar().showMessage("Flash completed", 10000)

    # -- debug bundle & settings --------------------------------------------------
    def export_bundle(self, dest_dir: Path) -> Path:
        path = create_debug_bundle(self.ctx, dest_dir, self.log_file)
        log.info("Debug bundle saved: %s", path)
        return path

    def _on_export_clicked(self) -> None:
        desktop = Path.home() / "Desktop"
        start = desktop if desktop.is_dir() else Path.home()
        directory = QFileDialog.getExistingDirectory(self, "Save debug bundle to", str(start))
        if not directory:
            return
        try:
            path = self.export_bundle(Path(directory))
        except OSError as exc:
            log.error("Cannot write debug bundle: %s", exc)
            QMessageBox.critical(self, "WFlash", f"Cannot write debug bundle:\n{exc}")
            return
        QMessageBox.information(self, "Debug bundle", f"Saved:\n{path}\n\nSend this file for debugging.")

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, get_token(self.settings.gitlab_url) or "", self)
        if dialog.exec() != QDialog.Accepted:
            return
        self.settings = dialog.result_settings()
        token = dialog.result_token()
        if token and self.settings.gitlab_url:
            register_secret(token)
            try:
                set_token(self.settings.gitlab_url, token)
            except Exception as exc:
                log.error("Cannot store token in the keyring: %s", exc)
        set_verbose(self.settings.verbose)
        self._save_settings()
        log.info("Settings saved")
        self.reload_profiles()

    def closeEvent(self, event) -> None:
        if self._flash_worker is not None:
            answer = QMessageBox.question(self, "WFlash", "A flash is in progress. Cancel it and quit?")
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self._flash_worker.cancel.cancel()
        logging.getLogger(LOGGER_NAME).removeHandler(self.log_panel.handler)
        super().closeEvent(event)
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_main_window.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add wflash/gui/main_window.py tests/test_main_window.py
git commit -m "feat(gui): add main window wiring GitLab, mapping, flash and log panel" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 18: Entry point (`main.py`), excepthooks, smoke run

**Files:**
- Create: `wflash/main.py`, `wflash/__main__.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `setup_logging`, `get_logger` (3), `AppSettings` (8), `create_adapter` (9), `MainWindow` (17), `WFlashError` (2).
- Produces:
  - `parse_args(argv: list[str] | None = None) -> argparse.Namespace` với `adapter` (`real` mặc định trên `win32`, ngược lại `fake`), `verbose: bool`, `smoke: bool`
  - `install_excepthooks() -> None` (thay `sys.excepthook` và `threading.excepthook`; log CRITICAL kèm traceback; hiện dialog nếu có QApplication)
  - `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Viết test fail `tests/test_main.py`**

```python
import logging
import sys
import threading

from PySide6.QtWidgets import QMessageBox

from wflash.main import install_excepthooks, parse_args


def test_default_adapter_depends_on_platform(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert parse_args([]).adapter == "real"
    monkeypatch.setattr(sys, "platform", "darwin")
    assert parse_args([]).adapter == "fake"


def test_flags():
    args = parse_args(["--adapter", "fake", "--verbose", "--smoke"])
    assert (args.adapter, args.verbose, args.smoke) == ("fake", True, True)


def test_excepthooks_log_and_show_dialog(qapp, monkeypatch, caplog):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: shown.append(a))
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    caplog.set_level(logging.DEBUG, logger="wflash")
    install_excepthooks()

    try:
        raise RuntimeError("kaboom")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    assert "kaboom" in caplog.text
    assert shown

    thread = threading.Thread(target=lambda: 1 / 0, name="bad-thread")
    thread.start()
    thread.join()
    assert "ZeroDivisionError" in caplog.text
    assert "bad-thread" in caplog.text
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `~/.venvs/wflash/bin/pytest tests/test_main.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'wflash.main'`

- [ ] **Step 3: Implement `wflash/main.py`**

```python
"""WFlash entry point: parse args, set up logging and crash hooks, start the GUI."""
from __future__ import annotations

import argparse
import sys
import threading

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from wflash import __version__
from wflash.core.errors import WFlashError
from wflash.core.logging_setup import get_logger, setup_logging
from wflash.core.settings import AppSettings
from wflash.core.winidea_adapter import create_adapter


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="wflash", description="Flash ECU via winIDEA from GitLab artifacts")
    parser.add_argument(
        "--adapter",
        choices=["real", "fake"],
        default="real" if sys.platform == "win32" else "fake",
        help="winIDEA adapter (default: real on Windows, fake elsewhere)",
    )
    parser.add_argument("--verbose", action="store_true", help="Log every winIDEA call")
    parser.add_argument("--smoke", action="store_true", help="Start, then quit after 1.5 s (launch check)")
    return parser.parse_args(argv)


def install_excepthooks() -> None:
    log = get_logger("crash")

    def excepthook(exc_type, exc, tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log.critical("Unhandled exception", exc_info=(exc_type, exc, tb))
        if QApplication.instance() is not None:
            QMessageBox.critical(
                None,
                "WFlash crashed",
                f"{exc_type.__name__}: {exc}\n\nDetails are in the log. Use 'Export debug bundle…' to send them.",
            )

    def thread_excepthook(args: threading.ExceptHookArgs) -> None:
        name = args.thread.name if args.thread is not None else "?"
        log.critical(
            "Unhandled exception in thread %s", name, exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
        )

    sys.excepthook = excepthook
    threading.excepthook = thread_excepthook


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = AppSettings.load()
    log_file = setup_logging(verbose=args.verbose or settings.verbose)
    log = get_logger("main")
    log.info("WFlash %s starting (adapter=%s, log=%s)", __version__, args.adapter, log_file)
    install_excepthooks()
    app = QApplication.instance() or QApplication(sys.argv[:1])

    try:
        adapter = create_adapter(args.adapter)
    except WFlashError as exc:
        log.error("%s", exc)
        QMessageBox.critical(None, "WFlash", f"{exc}\n\n{exc.hint}")
        return 1

    from wflash.gui.main_window import MainWindow

    window = MainWindow(settings, adapter, log_file=log_file)
    window.resize(1280, 820)
    window.show()
    if args.smoke:
        QTimer.singleShot(1500, app.quit)
    return app.exec()
```

`wflash/__main__.py`:
```python
from wflash.main import main

raise SystemExit(main())
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `~/.venvs/wflash/bin/pytest tests/test_main.py -v`
Expected: 3 passed

- [ ] **Step 5: Smoke run app với fake adapter**

Run: `QT_QPA_PLATFORM=offscreen ~/.venvs/wflash/bin/python -m wflash --adapter fake --smoke; echo "exit=$?"`
Expected: `exit=0`; một file log mới trong `~/Library/Logs/WFlash/` có dòng `WFlash 0.1.0 starting (adapter=fake` và `Found 1 winIDEA instance(s)`.

Kiểm tra: `ls -t ~/Library/Logs/WFlash | head -1 | xargs -I{} grep -E "starting|Found 1" ~/Library/Logs/WFlash/{}`

- [ ] **Step 6: Chạy toàn bộ test**

Run: `~/.venvs/wflash/bin/pytest -v`
Expected: tất cả pass (83 core + 27 GUI/main = 110 tests)

- [ ] **Step 7: Commit**

```bash
git add wflash/main.py wflash/__main__.py tests/test_main.py
git commit -m "feat: add entry point with crash hooks and smoke mode" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 19: Đóng gói PyInstaller + README

**Files:**
- Create: `wflash.spec`, `scripts/build_windows.bat`
- Modify: `README.md` (thay toàn bộ nội dung)

**Interfaces:**
- Consumes: `wflash/__main__.py` (Task 18), thư mục `profiles/` (Task 4).
- Produces: `dist/WFlash/WFlash(.exe)` dạng onedir, profiles nằm trong `_internal/profiles` (khớp `bundled_profiles_dir()` ở Task 8 qua `sys._MEIPASS`).

- [ ] **Step 1: Tạo `wflash.spec`**

```python
# PyInstaller spec. Build: pyinstaller --noconfirm wflash.spec
from PyInstaller.utils.hooks import collect_all

datas = [("profiles", "profiles")]
binaries = []
hiddenimports = ["keyring.backends.Windows", "keyring.backends.macOS"]
try:
    import isystem.connect  # noqa: F401

    _d, _b, _h = collect_all("isystem")
    datas += _d
    binaries += _b
    hiddenimports += _h
except ImportError:
    print("WARNING: isystem.connect not installed; building without real winIDEA support")

a = Analysis(
    ["wflash/__main__.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="WFlash", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="WFlash")
```

- [ ] **Step 2: Tạo `scripts/build_windows.bat`**

```bat
@echo off
setlocal
cd /d "%~dp0\.."
set VENV=%USERPROFILE%\.venvs\wflash
if not exist "%VENV%" py -3 -m venv "%VENV%" || exit /b 1
call "%VENV%\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -e ".[dev,winidea]" || exit /b 1
set QT_QPA_PLATFORM=offscreen
pytest || exit /b 1
set QT_QPA_PLATFORM=
pyinstaller --noconfirm wflash.spec || exit /b 1
echo.
echo Built: dist\WFlash\WFlash.exe
```

- [ ] **Step 3: Build thử trên macOS để kiểm tra spec**

Run: `cd "<repo>" && ~/.venvs/wflash/bin/pyinstaller --noconfirm wflash.spec`
Expected: dòng `WARNING: isystem.connect not installed`, kết thúc `Build complete!`, có `dist/WFlash/WFlash` và `dist/WFlash/_internal/profiles/saf85xx_example.yaml`.

Run: `QT_QPA_PLATFORM=offscreen dist/WFlash/WFlash --adapter fake --smoke; echo "exit=$?"`
Expected: `exit=0`

Lưu ý: `build/` và `dist/` đã nằm trong `.gitignore` (Task 1). Nếu chạy trong thư mục OneDrive, sau khi kiểm tra xong xóa `build/ dist/` để OneDrive không sync: `rm -rf build dist`.

- [ ] **Step 4: Viết `README.md`**

```markdown
# WFlash Tool

Tool desktop (Python + PySide6) để flash ECU **NXP SAF85xx** qua **winIDEA 9.21** (`isystem.connect`):
chọn artifact từ GitLab CI, tự map file `.s3`/`.elf` vào workspace winIDEA, download vào external flash Winbond, reset + halt.

> Trạng thái: GUI, GitLab, cache, mapping, workflow và log đã chạy với **fake adapter**.
> Adapter winIDEA thật sẽ được viết sau khi có kết quả spike (`spike/README.md`).

## Chạy từ source

macOS (dev, fake adapter):

    /path/to/python3.11+ -m venv ~/.venvs/wflash
    ~/.venvs/wflash/bin/pip install -e ".[dev]"
    ~/.venvs/wflash/bin/python -m wflash --adapter fake

Windows:

    py -3 -m venv %USERPROFILE%\.venvs\wflash
    %USERPROFILE%\.venvs\wflash\Scripts\activate
    pip install -e ".[dev,winidea]"
    python -m wflash            (mặc định --adapter real)
    python -m wflash --adapter fake

Tham số: `--adapter real|fake`, `--verbose` (log mọi lời gọi winIDEA), `--smoke` (mở rồi tự thoát, để kiểm tra).

Fake adapter giả lập lỗi qua biến môi trường:
`WFLASH_FAKE_FAIL=download` (hoặc `connect`, `set_path`, `reset`, có thể nối bằng dấu phẩy), `WFLASH_FAKE_DOWNLOAD_S=10`.

## Cấu hình

1. **Settings…**: GitLab URL, Personal Access Token (scope `read_api`, lưu trong Windows Credential Manager), CA bundle nếu GitLab dùng chứng chỉ nội bộ.
2. **Profile** (`profiles/*.yaml`): project GitLab, filter tên job, tên entry download và tên Application trong winIDEA, pattern file. Xem `profiles/saf85xx_example.yaml`.

## Quy trình

1. Chọn profile → **Refresh** → chọn branch/tag → pipeline → job → **Download artifact** (có cache theo job).
2. Kiểm tra bảng mapping; dòng đỏ cần chọn file thủ công.
3. Chọn instance winIDEA đang mở → **Flash**. Lỗi khi set path/download sẽ tự khôi phục đường dẫn cũ trong workspace.

## Log và gửi lỗi

- Log panel ở dưới cửa sổ (lọc theo level, Copy, Clear).
- Log file: `%LOCALAPPDATA%\WFlash\logs\` (Windows), `~/Library/Logs/WFlash/` (macOS), giữ 20 file gần nhất.
- **Export debug bundle…**: tạo `wflash_debug_<thời gian>.zip` gồm log, môi trường, profile, mapping, trạng thái workspace trước/sau và traceback. Token đã được che. Gửi file zip này khi cần hỗ trợ.

## Build .exe (Windows)

    scripts\build_windows.bat

Kết quả: `dist\WFlash\WFlash.exe` (copy cả thư mục `dist\WFlash`).

## Test

    QT_QPA_PLATFORM=offscreen pytest
```

- [ ] **Step 5: Commit**

```bash
git add wflash.spec scripts/build_windows.bat README.md
git commit -m "build: add PyInstaller spec, Windows build script and README" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 20: Kiểm tra trên Windows (thủ công, do user thực hiện)

Không có code. Checklist gửi cho user sau khi Task 1–19 xong:

- [ ] **Step 1: Spike** — làm theo `spike/README.md`, gửi lại `spike/results/*.txt`.
- [ ] **Step 2: Build** — chạy `scripts\build_windows.bat`; xác nhận tất cả test pass và có `dist\WFlash\WFlash.exe`.
- [ ] **Step 3: GitLab thật** — chạy `WFlash.exe --adapter fake`, nhập GitLab URL + PAT, sửa `profiles\saf85xx_example.yaml` (project, job_filter, pattern) cho đúng, duyệt tới job và tải artifact; kiểm tra bảng mapping.
- [ ] **Step 4: Flash giả lập** — bấm Flash với fake adapter; thử thêm `set WFLASH_FAKE_FAIL=download` rồi chạy lại để thấy rollback + popup lỗi.
- [ ] **Step 5: Gửi debug bundle** — bấm **Export debug bundle…** sau bước 3–4, gửi file zip cùng kết quả spike.

---

## Plan 2 (viết sau khi có kết quả spike)

Phạm vi dự kiến, chỉ để định hướng, **không thực hiện trong plan này**:

- `wflash/core/real_adapter.py`: `RealWinIDEAAdapter` implement `WinIDEAAdapter` bằng `isystem.connect` với option URL thật lấy từ spike 02/03; log mọi lời gọi lên `wflash.calls`; chạy `download()` trong thread phụ để áp timeout và cho phép hủy (nếu API hỗ trợ).
- `create_adapter("real")` trả về `RealWinIDEAAdapter`.
- Cập nhật tên entry/Application thật trong `profiles/saf85xx_example.yaml`.
- Checklist kiểm tra thủ công trên Windows: connect, set path, download, reset, rollback.
