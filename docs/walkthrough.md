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

## Phase 1.3: Logging và che token

Phase này xây dựng tầng logging đầu tiên cho app, với tập trung vào việc **che giấu token GitLab và bất kỳ giá trị nhạy cảm nào** trước khi ghi vào log. Mục đích là tạo nền tảng đáng tin cậy cho việc log chi tiết mọi bước của workflow (download artifact, set path, flash) mà không lo lắng về việc vô tình lộ credential của user trong log file hay debug bundle. Logging setup tạo per-session DEBUG log file với naming dựa trên timestamp, tự động dọn dẹp các file log cũ, và hỗ trợ chế độ verbose để log mọi lời gọi `isystem.connect` khi debug. 

Bản đầu tiên che header `PRIVATE-TOKEN`; sau đó (fix round 1, R8) mở rộng che: glpat- token (20+ ký tự), `Bearer <token>`, và `private_token=<value>` trong URL/query string, tất cả không cần đăng ký, để bảo vệ ngay cả khi code quên gọi `register_secret()`.

### Thay đổi

- **`wflash/core/logging_setup.py`** (mới): module logging với `RedactingFormatter` để che token, interface công khai gồm: `LOGGER_NAME`, `CALLS_LOGGER`, `LOG_FORMAT`, `DATE_FORMAT`, hàm `get_logger()`, `register_secret()` / `clear_secrets()` / `redact()` cho quản lý token, `default_log_dir()` trả về đường dẫn platform-specific (macOS: `~/Library/Logs/WFlash`, Windows: `%LOCALAPPDATA%/WFlash/logs`, Linux: `~/.local/state/wflash/logs`), `setup_logging()` khởi tạo file handler với tên `wflash_YYYYMMDD_HHMMSS.log` và tự động dọn dẹp chỉ giữ 20 file mới nhất, `set_verbose()` để bật DEBUG cho `wflash.calls` logger. (Fix R8: hardening với regex cho glpat-, Bearer token, private_token query param).
- **`tests/test_logging_setup.py`** (mới): 13 test cases — 8 gốc (test regex redaction cho header `PRIVATE-TOKEN`, redact registered secret anywhere, ignore short/empty secret, redact exception trace, verify file handler write + redaction, verify keep-only-latest pruning, toggle verbose mode, verify platform-specific log dir) + 5 hardening (test glpat- bare token, Bearer token case-insensitive, private_token in query string, file sink with unregistered glpat).

### Đã kiểm tra

- `~/.venvs/wflash/bin/pytest tests/test_logging_setup.py -v` (RED): `ImportError: cannot import name 'logging_setup' from 'wflash.core'` (từ dòng 8 của test file).
- `~/.venvs/wflash/bin/pytest tests/test_logging_setup.py -v` (GREEN): 13 passed ✓.
- `~/.venvs/wflash/bin/pytest -q`: 23 passed ✓ (10 từ task 1.2 + 13 từ task 1.3).

## Phase 1.4: Profile

Phase này xây dựng schema cho profile — một YAML file khai báo project GitLab, các entry program/application từ workspace winIDEA, pattern để match file trong artifact, và các thông số timeout/reset. Mục đích là có bộ quy tắc khép kín để kiểm chứng user input (profile file) **trước** khi sử dụng — không để lỏng lẻo hoặc đoán. Pydantic làm công việc validation: duplicate entry bị từ chối, key lạ bị từ chối, miss required field bị từ chối. Example profile cho SAF85xx ghi rõ tên entry mà workspace phải có sẵn (từ spike 02_dump_options) và pattern để match file.

### Thay đổi

- **`profiles/saf85xx_example.yaml`** (mới): ví dụ profile cho SAF85xx, khai báo 1 program entry "App" match `**/*App*.s3` và 2 application entries "CM7_0", "CM7_1" match theo pattern, timeout download 600s, reset sau flash.
- **`wflash/core/profile.py`** (mới): Pydantic models cho `GitLabSpec`, `ProgramSpec`, `ApplicationSpec`, `PostFlash`, `Timeouts`, `Profile` với validator `_unique_targets()` để bảo đảm không trùng tên entry; hàm `load_profile(path)` để load YAML với error handling (OSError, UnicodeError → `ProfileError`, YAMLError → `ProfileError`, non-dict → `ProfileError`, validation error → `ProfileError`); hàm `list_profiles(directory)` để liệt kê `.yaml`/`.yml` file theo tên.
- **`tests/test_profile.py`** (mới): 11 test cases — load example, apply default, missing program rejected, unknown key rejected, duplicate entry rejected, invalid YAML rejected, non-mapping rejected, file not found rejected, non-UTF8 file rejected, list sorted, missing dir. (Fix R1: added test_non_utf8_file_rejected).

### Đã kiểm tra

- `~/.venvs/wflash/bin/pytest tests/test_profile.py::test_non_utf8_file_rejected -v` (RED): `UnicodeDecodeError` escapes from load_profile.
- `~/.venvs/wflash/bin/pytest tests/test_profile.py::test_non_utf8_file_rejected -v` (GREEN): 1 passed ✓.
- `~/.venvs/wflash/bin/pytest tests/test_profile.py -v`: 11 passed ✓.

## Phase 1.5: File matcher

Phase này xây dựng matching engine để map file từ artifact tới entry/application trong profile. Mục đích là tách rõ phần pattern matching logic (không phụ thuộc profile schema) từ phần áp dụng logic vào từng profile instance. Quy tắc matching: `*` khớp across path separator (posix style), `**/` đầu pattern cũng khớp file gốc, không phân biệt hoa thường. Nếu một pattern match nhiều file → để user chọn (mapping row không "ok"). Nếu một pattern match đúng 1 file → auto-select (mapping row "ok"). Nếu 0 file → mapping row không "ok", pending user chọn.

### Thay đổi

- **`wflash/core/file_matcher.py`** (mới): `MappingRow` dataclass (kind, target, pattern, candidates, selected) với `.ok` property (selected is not None) và `.to_dict()` method; `match_pattern(rel_posix, pattern)` để match case-insensitive; `build_mapping(profile, root)` để tính toàn bộ mapping; `candidates_for_kind(root, kind)` để liệt kê file theo kiểu (program: .s3/.srec/.s19/.mot, application: .elf); `PROGRAM_SUFFIXES` và `SYMBOL_SUFFIXES` constant.
- **`tests/test_file_matcher.py`** (mới): 6 test cases — match pattern rules, single candidate auto-select, multiple candidate not select, zero candidate, candidates by kind, to_dict serialization.

### Đã kiểm tra

- `~/.venvs/wflash/bin/pytest tests/test_file_matcher.py -v` (RED): `ModuleNotFoundError: No module named 'wflash.core.file_matcher'` ✓ (expected).
- `~/.venvs/wflash/bin/pytest tests/test_file_matcher.py -v` (GREEN): 6 passed ✓.
- `~/.venvs/wflash/bin/pytest -q`: 39 passed ✓ (33 trước + 6 task 1.5).

## Phase 1.6: Artifact cache

Phase này xây dựng artifact cache để lưu trữ extracted artifact files trên disk, organized by project_id/job_id. Mục đích là tránh phải download lại cùng artifact job nhiều lần trong session, đặc biệt tiếp theo nếu user "Refresh" GitLab browser hay thay profile. Cache có max_jobs limit (default 10) và prune oldest-by-mtime khi exceed. Extraction phải an toàn: reject path như `../../evil.txt` (zip slip). File `.complete` marker để mark cache entry thành công (dùng mtime để track "last used").

### Thay đổi

- **`wflash/core/artifact_cache.py`** (mới): `ArtifactCache` class với root path và max_jobs; `job_dir(project_id, job_id)` trả Path; `get(project_id, job_id)` trả `files/` dir nếu cached (touch marker để update mtime), None nếu miss; `store_zip(project_id, job_id, zip_path)` extract tới `.tmp` với error handling (OSError → `ArtifactError`, BadZipFile → `ArtifactError`, unsafe path → `ArtifactError` với hint riêng), cleanup `.tmp` trên exception, write `.complete` marker, atomically move tới final, prune, return `files/` dir; `entries()` liệt kê cached entries (exclude `.tmp`); `prune()` keep only max_jobs most recent by mtime, remove stale `.tmp` dirs, remove incomplete job dirs (no marker); `clear()` xóa toàn bộ cache.
- **`tests/test_artifact_cache.py`** (mới): 8 test cases — miss then store then hit, bad zip leaves no entry, zip slip rejected, prune keeps most recent, clear, missing zip_path raises and no tmp left, restore same job replaces content, leftover tmp and incomplete dirs cleaned. (Fix R2-R3: added missing_zip, restore, and cleanup tests).

### Đã kiểm tra

- `~/.venvs/wflash/bin/pytest tests/test_artifact_cache.py::test_missing_zip_raises_and_no_tmp_left tests/test_artifact_cache.py::test_restore_same_job_replaces_content tests/test_artifact_cache.py::test_leftover_tmp_and_incomplete_dirs_cleaned -v` (RED): FileNotFoundError not caught, .tmp dirs not cleaned.
- `~/.venvs/wflash/bin/pytest tests/test_artifact_cache.py::test_missing_zip_raises_and_no_tmp_left tests/test_artifact_cache.py::test_restore_same_job_replaces_content tests/test_artifact_cache.py::test_leftover_tmp_and_incomplete_dirs_cleaned -v` (GREEN): 3 passed ✓.
- `~/.venvs/wflash/bin/pytest tests/test_artifact_cache.py -v`: 8 passed ✓.

