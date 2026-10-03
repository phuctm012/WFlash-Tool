# WFlash — Walkthrough

Nhật ký phát triển theo từng phase. Mỗi thay đổi đáng kể về code/feature đều có một mục `## Phase X.Y` ở đây, viết **ngay khi làm**, không để dồn tới cuối session.

Format của mỗi phase: một đoạn mở đầu nói **vì sao** làm (lý do, bối cảnh, bug nó sửa), rồi `### Thay đổi` liệt kê theo **tên file in đậm**, rồi `### Đã kiểm tra` ghi đúng những gì đã thực sự chạy và kết quả. Lý do là phần quan trọng nhất — code thì git còn giữ, còn lý do thì không.

---

## Phase 0.1: Dựng bộ quy tắc kỹ thuật cho repo

Spec (`docs/superpowers/specs/2026-10-04-wflash-tool-design.md`) đã chốt *làm gì*, plan (`docs/superpowers/plans/2026-10-04-wflash-tool.md`, Plan 1, Task 1-6) đã chốt *làm theo thứ tự nào*. Phase này dựng phần còn thiếu: *làm như thế nào* — bộ quy tắc kỹ thuật đã được kiểm chứng ở project SFlash (`.../01_STUDY/06_PYSIDE6`, flash ECU qua CAN/UDS, đã ship v3.1) chuyển sang đây, vì hai project dùng cùng PySide6 và cùng mô hình worker thread.

Phần đáng giá nhất không phải kiến trúc mà là **các failure mode của worker thread**: ở SFlash tất cả đều từng là crash thật đã ship — `QThread: Destroyed while thread is still running`, deadlock trong `closeEvent`, thread nền bị leak gây `Signal source has been deleted` sau đó vài phút, signal hoàn thành được giao *sau khi* user đã cancel (và tự khởi động tiếp công việc mới), và lock-order inversion GIL ↔ Qt mutex gây deadlock/SIGSEGV ngẫu nhiên ~1/6 lần chạy. WFlash chạy worker cho tải artifact và cho flash nên cùng lớp rủi ro, nhưng **plan dùng `Worker` (QRunnable) trên `QThreadPool`, không phải `moveToThread`** — nên mục threading trong `CLAUDE.md` được viết lại theo đúng mô hình đó (QObject mang signal phải sống lâu hơn runnable; `setAutoDelete` và quyền sở hữu phía Python; không `waitForDone()` trên GUI thread; guard flag trước khi cancel; không lambda cho signal từ pool thread), và giữ hai quy tắc của `moveToThread` ở cuối như ghi chú nếu sau này đổi mô hình.

Hai điểm được ghi riêng cho WFlash vì spec/plan chưa nói tới:

- **Cancel và timeout phải nằm trong lời gọi chặn thật.** `download()` chạy tới 600 s, nên token chỉ kiểm tra giữa các step không có tác dụng gì trong đúng step duy nhất mất thời gian. Phải kiểm tra trong từng progress callback, và fail theo đường lỗi bình thường để rollback vẫn chạy, log và debug bundle vẫn được ghi.
- **Rollback phải là bảo đảm cấu trúc** (`try/finally`), không phải một dòng ở cuối happy path. Fail khi đang set path thứ 2 trong 3 vẫn phải khôi phục path thứ 1. Timeout mà để workspace đã sửa và session còn attach là bug, không phải timeout.

Trong lúc viết, đọc plan phát hiện ba chỗ nếu copy nguyên SFlash sẽ sai, đã sửa theo plan: venv đặt **ngoài** OneDrive (`~/.venvs/wflash`, tránh OneDrive sync hàng nghìn file site-packages), entry point là `python -m wflash` chứ không phải `main.py` ở gốc, và dependency là `requests` chứ không phải `python-gitlab`. Cũng ghi lại rằng `python3` của hệ thống là stub licence của Xcode và báo lỗi — phải dùng `/Users/tranminhphuc/miniforge3/bin/python3.13`.

**Quyết định kiến trúc GUI:** spec §4 và File Structure của plan đều liệt kê `gui/*.py` viết tay, không có `.ui`. User chọn làm theo kiến trúc UI của SFlash, nên chốt **Designer-first + mixin**: `main_window.ui` là nguồn sự thật, `ui_main_window.py` sinh bằng `pyside6-uic` và không sửa tay, `MainWindow` ghép từ các mixin dùng chung một `self.ui`. Đổi lúc này gần như không tốn gì vì các task GUI (Task 7+) chưa được viết. File Structure của plan đã cập nhật; **spec §4 vẫn còn danh sách cũ, cần sửa khi chạm vào file đó lần tới**.

Ngoài ra plan ghi "Spec đã được cập nhật" cho hai điểm `requests` và `FileEntry`, nhưng bản spec đang commit thì chưa — đã ghi chú trong `CLAUDE.md` để lần sau không tin sai.

### Thay đổi

- **`CLAUDE.md`** (mới): mô tả project, Rule zero (không viết lời gọi `isystem.connect` chưa xác minh — kèm hai cái bẫy version-match và bitness), Commands theo venv ngoài OneDrive, Conventions chốt từ plan (logger + `RedactingFormatter`, `WFlashError` có `hint`, GUI tiếng Anh/tài liệu tiếng Việt, commit trailer), 6 rule bắt buộc, và phần Architecture: layering + quy tắc import, adapter boundary (fake trước real sau), Approach A (chỉ sửa path / không tạo entry / luôn rollback), GUI Designer-first, threading model 8 mục cho `QThreadPool`, bảo mật PAT, mapping không được đoán, instance luôn enumerate, error taxonomy.
- **`docs/superpowers/plans/2026-10-04-wflash-tool.md`**: File Structure mục `wflash/gui/` đổi sang cấu trúc Designer-first + mixin, kèm một đoạn ghi rõ quyết định này thay cho §4 của spec và áp dụng cho Task 7+.
- **`.claude/settings.json`** (mới): `QT_QPA_PLATFORM=offscreen` cho các lần chạy GUI ad-hoc (test đã tự set trong `tests/conftest.py`).
- **`.claude/skills/test/SKILL.md`** (mới): `pytest -q`, chạy riêng `-k thread`, kiểm tra app còn start được, tất cả gọi qua `~/.venvs/wflash/bin`.
- **`.claude/skills/stress-test/SKILL.md`** (mới): protocol bắt buộc trước khi push cả session; ghi rõ `tools/stress_test.py` **chưa tồn tại** và liệt kê 5 section cần có (flash / rollback / gitlab / races / secrets), cách đọc kết quả (checkpoint + Qt threading warning), 5 cái bẫy khi viết script, và cách lấy native stack bằng `sample` khi `faulthandler` không đủ.
- **`.claude/skills/regenerate-ui/SKILL.md`** (mới): `pyside6-uic` + kiểm tra mọi `self.ui.<name>` còn tồn tại trong `.ui`.
- **`.claude/skills/steward/SKILL.md`** (mới): checklist trước khi push (5 lỗi hay gặp của họ project này), convention, danh sách "never".
- **`.claude/agents/thread-checker.md`** (mới): audit 7 failure mode threading.
- **`.claude/agents/winidea-analyst.md`** (mới): audit 9 điểm — API có bằng chứng trong notes, Approach A, rollback toàn phần, mapping không đoán, cancel/timeout tới được chỗ chặn, lazy import + layering, PAT không lọt sink nào, error taxonomy, fake adapter sinh được lỗi thật.
- **`.claude/agents/ui-reviewer.md`** (mới): audit đồng bộ `.ui` ↔ mixin, kèm một mục không thuần hình thức: nút Flash phải tắt khi mapping chưa đủ.
- **`docs/walkthrough.md`** (mới): file này.
- **`docs/winidea_api_notes.md`** (mới): khung rỗng để Phase 0 spike điền vào; là nguồn sự thật cho mọi lời gọi API thật.

### Đã kiểm tra

- Đọc hết `CLAUDE.md` + 4 skill + 4 agent của SFlash để lấy đúng nội dung đã kiểm chứng, không viết lại từ ký ức.
- Đọc hết spec **và** plan (Global Constraints, File Structure, Task 1-6, phần cuối) trước khi viết, nên `CLAUDE.md` mô tả đúng project này (SAF85xx, winIDEA 9.21.x attach, Approach A, GitLab PAT + keyring, fake adapter, debug bundle, `QThreadPool`) chứ không phải bản copy của SFlash.
- Đối chiếu từng đường dẫn `CLAUDE.md` nhắc tới với file thật trong repo: spec, plan, walkthrough, api notes — đều tồn tại.
- Chưa có code nên **chưa chạy được `pytest`**; mọi lệnh trong skill viết theo stack và venv mà plan Global Constraints đã chốt, chưa được chạy thật lần nào.
- `docs/winidea_api_notes.md` còn rỗng → theo đúng Rule zero, hiện tại **không** lời gọi API thật nào được coi là đã xác minh.
## Phase 1.1: Spike scripts winIDEA

Phase này viết 6 script Python độc lập cho Windows để ghi lại hành vi của `isystem.connect` trên winIDEA 9.21 + workspace SAF85xx thực. Mục đích là thu thập dữ liệu ban đầu cho việc xây dựng adapter thật trong Plan 2: cách liệt kê instance, kết nối, tìm option path chứa đường dẫn file `.s3`/`.elf`, cách thay đổi option và khôi phục, cách chạy download và kiểm tra trạng thái CPU sau flash, cách reset và halt. Mỗi script ghi kết quả vào file `.txt` có timestamp để dễ so sánh và lưu trữ.

### Thay đổi

- **`.gitignore`** (mới): thêm `.superpowers/`, `__pycache__/`, `*.pyc`, `.venv/`, `build/`, `dist/`, `*.egg-info/`, `.pytest_cache/`, `spike/results/`
- **`spike/README.md`** (mới): hướng dẫn chạy spike trên Windows; thay vì `pip install -r requirements.txt`, chỉ rõ cách cài `isystem.connect` từ thư mục SDK của winIDEA 9.21, và kiểm tra version + bitness
- **`spike/_common.py`** (mới): `Report` class để tee output vào file + stdout, `base_args()`, `try_call()` để bọc API gọi, `connect()` để kết nối đến winIDEA instance
- **`spike/01_connect.py`** (mới): liệt kê instance, in version, liệt kê API surface
- **`spike/02_dump_options.py`** (mới): parse workspace `.xjrf` (XML) tìm file path, probe candidate option URL
- **`spike/03_set_paths.py`** (mới): đổi option value rồi khôi phục
- **`spike/04_download.py`** (mới): chạy download, đo thời gian, kiểm tra CPU status
- **`spike/05_reset.py`** (mới): reset target, kiểm tra status, probe multi-core API

### Đã kiểm tra

- Syntax check all 6 scripts với `/Users/tranminhphuc/miniforge3/bin/python3.13 -m py_compile`: pass, không lỗi.
- **Chưa chạy** script trên Windows với winIDEA 9.21 thực; hiện tại **không** lời gọi `isystem.connect` nào được coi là đã xác minh (theo Rule zero của CLAUDE.md).

## Phase 1.2: Khung project, lớp lỗi và CancelToken

Phase này dựng khung project Python đầu tiên với error hierarchy và `CancelToken` để hỗ trợ hủy bỏ thao tác một cách thread-safe. Mục đích là tạo nền tảng cho các layer cao hơn (gitlab module, flash workflow, GUI) để sử dụng lỗi có thuộc tính `hint` (được hiển thị trên GUI với lời khuyên cho người dùng) và token cancel để dừng các thao tác dài (download artifact, flash) từ GUI thread. Đồng thời thiết lập venv ngoài OneDrive theo Global Constraints để tránh OneDrive sync hàng nghìn file.

### Thay đổi

- **`pyproject.toml`** (mới): build system, project metadata (name=wflash, version=0.1.0), dependencies (PySide6, requests, pydantic, PyYAML, keyring) và dev extras (pytest, pytest-qt, responses, pyinstaller). Theo ruling R1, không có `winidea` extra — `isystem.connect` sẽ được cài từ thư mục SDK của winIDEA 9.21 trên Windows.
- **`wflash/__init__.py`** (mới): package root, khai báo `__version__ = "0.1.0"`.
- **`wflash/core/__init__.py`** (mới): empty, marker cho package `core`.
- **`wflash/gui/__init__.py`** (mới): empty, marker cho package `gui`.
- **`wflash/core/errors.py`** (mới): exception hierarchy với base `WFlashError` có thuộc tính `hint` (user-facing advice, không phải restate lỗi); subclasses `ProfileError`, `GitLabError`, `ArtifactError`, `MappingError`, `WinIDEAError`, `FlashError`, `CancelledError`, mỗi lớp có `default_hint` riêng.
- **`wflash/core/cancel.py`** (mới): `CancelToken` dùng `threading.Event` để cho phép hủy bỏ thao tác từ thread khác; các method: `cancel()`, `cancelled` (property), `raise_if_cancelled()`, `wait(timeout)`.
- **`tests/__init__.py`** (mới): empty, marker cho package test.
- **`tests/conftest.py`** (mới): đặt `QT_QPA_PLATFORM=offscreen` để GUI test chạy headless không cần display.
- **`tests/test_errors_cancel.py`** (mới): 10 test cases — verify error có `hint` default, custom hint override, subclass hierarchy (7 loại error), và lifecycle của `CancelToken` (not cancelled → wait return False → cancel → cancelled → wait return True → raise CancelledError).

### Đã kiểm tra

- `/Users/tranminhphuc/miniforge3/bin/python3.13 -m venv ~/.venvs/wflash`: venv tạo thành công ở ngoài OneDrive.
- `~/.venvs/wflash/bin/pip install -e ".[dev]"`: cài toàn bộ dependencies thành công (kết thúc bằng `Successfully installed ... wflash-0.1.0`).
- `~/.venvs/wflash/bin/pytest tests/test_errors_cancel.py -v` (RED): `ModuleNotFoundError: No module named 'wflash.core.cancel'` ✓ (expected, chưa implement).
- Implement `wflash/core/errors.py` và `wflash/core/cancel.py`.
- `~/.venvs/wflash/bin/pytest tests/test_errors_cancel.py -v` (GREEN): 10 passed ✓.

