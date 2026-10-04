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

- **`wflash/core/artifact_cache.py`** (mới + Fix R2): `store_zip()` error hints: BadZipFile → hint "Download again; corrupt", OSError extract → hint "Check disk space/path", unsafe path → hint "Artifact unsafe; check CI", rename OSError → hint "Close locked files..."; BaseException handling: catch only `Exception` subclasses, bare raise for non-Exception to allow KeyboardInterrupt/SystemExit; `prune()` uses `glob("*/*.tmp")` non-recursive so won't delete `.tmp` inside artifact `files/`.
- **`tests/test_artifact_cache.py`** (mới + Fix R2): 9 test cases including `test_zip_slip_rejected` (with hint check) and `test_artifact_with_tmp_folder_survives_prune`.

### Đã kiểm tra

- `~/.venvs/wflash/bin/pytest tests/test_artifact_cache.py::test_zip_slip_rejected tests/test_artifact_cache.py::test_artifact_with_tmp_folder_survives_prune -v` (RED): unsafe hint not set; recursive glob deletes .tmp inside artifact.
- `~/.venvs/wflash/bin/pytest tests/test_artifact_cache.py::test_zip_slip_rejected tests/test_artifact_cache.py::test_artifact_with_tmp_folder_survives_prune -v` (GREEN): 2 passed ✓.
- `~/.venvs/wflash/bin/pytest tests/test_artifact_cache.py -v`: 9 passed ✓.
- `~/.venvs/wflash/bin/pytest -q`: 49 passed ✓ (full suite).


## Phase 1.7: GitLab client

Phase này thêm client GitLab REST v4 tối giản để tool duyệt ref, pipeline, job rồi tải artifact mà không cần kéo thêm thư viện GitLab nặng. Token PAT được đăng ký với `register_secret` ngay khi tạo client nên không bao giờ lọt vào log ở dạng chưa che. Các lỗi hay gặp (401/403/404/SSL) được map sang hint cụ thể để người dùng biết cần làm gì tiếp (đổi token, xin quyền, chọn CA bundle...). Download ghi vào file `.part` rồi đổi tên, và xóa file dở khi hủy hoặc lỗi.

### Thay đổi

- **`wflash/core/gitlab_client.py`** (mới): `Ref`, `Pipeline`, `Job` (frozen dataclass) và `GitLabClient` với `get_project_id`, `list_refs`, `list_pipelines`, `list_jobs` (chỉ job có artifact archive, lọc theo glob), `download_artifacts` (stream, progress callback, hỗ trợ `CancelToken`).
- **`tests/test_gitlab_client.py`** (mới): 12 test dùng `responses` — encode path project, header token, ref/pipeline/job, download + cancel, hint 401/404, lỗi kết nối, lỗi SSL, che token.

### Đã kiểm tra

- `~/.venvs/wflash/bin/pytest tests/test_gitlab_client.py -q` (RED): `ModuleNotFoundError: No module named 'wflash.core.gitlab_client'` ✓ (expected).
- `~/.venvs/wflash/bin/pytest tests/test_gitlab_client.py -q -W error` (GREEN): 12 passed ✓.
- `~/.venvs/wflash/bin/pytest -q --ignore=tests/test_settings.py`: 61 passed ✓ (49 trước + 12 task 1.7; test_settings của task 1.8 chưa có module nên loại ra).

### Fix Round 1 (R12)

- **`wflash/core/gitlab_client.py`**: phản hồi 2xx không phải JSON/thiếu key (proxy, trang login) giờ thành `GitLabError("Unexpected response ...")` kèm hint; lỗi I/O khi tải (mkdir/open/write/replace) thành `ArtifactError`, luôn đóng response và xóa `.part`; phân trang theo header `X-Next-Page` cho branches/tags/jobs; `list_pipelines` kẹp `limit` vào 1..100.
- **`tests/test_gitlab_client.py`**: thêm 6 test (HTML 200, JSON thiếu `id`, lỗi ghi file, lỗi mkdir, phân trang, kẹp limit).
- `~/.venvs/wflash/bin/pytest tests/test_gitlab_client.py tests/test_settings.py -q` (RED): 9 failed, 19 passed (6 test gitlab mới + 3 test settings mới fail).
- `~/.venvs/wflash/bin/pytest tests/test_gitlab_client.py tests/test_settings.py -v -W error` (GREEN): 28 passed ✓.
- `~/.venvs/wflash/bin/pytest -q`: 77 passed ✓.

## Phase 1.8: Settings và token

Phase này thêm lớp cấu hình người dùng: settings lưu JSON trong thư mục config của OS, còn GitLab PAT được lưu trong keyring của hệ điều hành thay vì file văn bản. Mục đích là không để token nằm trên đĩa dạng plain text, đồng thời file settings hỏng hoặc thiếu không làm app crash (rơi về mặc định) và lỗi keyring khi đọc chỉ trả `None` kèm cảnh báo.

### Thay đổi

- **`wflash/core/settings.py`** (mới): `config_dir`, `default_cache_dir`, `bundled_profiles_dir`, `settings_path` theo từng nền tảng; dataclass `AppSettings` với `load`/`save` (bỏ qua key lạ, file hỏng hoặc không phải object); `get_token`/`set_token` qua keyring với service `WFlash-GitLab`.
- **`tests/test_settings.py`** (mới): 7 test — round trip, file thiếu, file hỏng, key lạ, resolved dirs (profile ví dụ có trong thư mục bundled), token qua keyring (mock), lỗi keyring trả `None`.

### Đã kiểm tra

- `~/.venvs/wflash/bin/pytest tests/test_settings.py -q` (RED): `ImportError: cannot import name 'settings' from 'wflash.core'` ✓ (expected).
- `~/.venvs/wflash/bin/pytest tests/test_settings.py -q -W error` (GREEN): 7 passed ✓.
- `~/.venvs/wflash/bin/pytest -q`: 68 passed ✓ (61 trước + 7 task 1.8).

### Fix Round 1 (R12)

- **`wflash/core/settings.py`**: `AppSettings.load` chỉ nhận giá trị đúng kiểu của default (bool phải là bool thật, int không phải bool), sai kiểu thì cảnh báo và dùng default; `set_token` bọc `KeyringError` thành `GitLabError` kèm hint.
- **`tests/test_settings.py`**: thêm 3 test (kiểu sai, bool không được nhận là int, lỗi keyring khi set_token); bỏ import `Path` thừa.
- RED/GREEN và full suite: xem mục Fix Round 1 của Phase 1.7 (chạy chung 2 file test): 28 passed, toàn bộ 77 passed ✓.

## Phase 1.9: Adapter interface và fake adapter

Phase này vạch ranh giới giữa workflow flash và winIDEA: toàn bộ code phía trên chỉ nói chuyện với giao diện `WinIDEAAdapter`, chỉ adapter thật (Plan 2) mới được import `isystem.connect`. Fake adapter được viết trước để GUI, workflow flash và stress test chạy được mọi nhánh lỗi/rollback ngay trên macOS, nơi không có winIDEA, nên khả năng chèn lỗi (failure injection) là phần quan trọng nhất.

### Thay đổi

- **`wflash/core/winidea_adapter.py`** (mới): `ProgressCallback`, `InstanceInfo` (có `label()`), `FileEntry`, Protocol `WinIDEAAdapter` và `create_adapter` (`"fake"` trả fake từ biến môi trường, `"real"` báo `WinIDEAError` cho tới Plan 2, loại khác `ValueError`).
- **`wflash/core/fake_adapter.py`** (mới): `FakeWinIDEAAdapter` giữ trạng thái trong bộ nhớ; chèn lỗi qua `fail_on` hoặc `WFLASH_FAKE_FAIL`: `connect`, `set_path`, `read_programs`, `read_applications`, `reset`, `download` (lỗi giữa chừng), `list_instances` (trả `[]`), `connection_lost` (connect thành công, các lệnh sau báo "Connection to winIDEA lost", `disconnect` vẫn chạy). Hỗ trợ cancel và timeout khi download.
- **`tests/test_fake_adapter.py`** (mới): 14 test gồm kết nối, đường dẫn, download/reset, các kiểu lỗi chèn, cancel, timeout, `from_env`, `create_adapter`.

### Đã kiểm tra

- `~/.venvs/wflash/bin/pytest tests/test_fake_adapter.py -v` (RED): `ModuleNotFoundError: No module named 'wflash.core.fake_adapter'` ✓ (expected).
- `~/.venvs/wflash/bin/pytest tests/test_fake_adapter.py -v -W error` (GREEN): 14 passed ✓.
- `~/.venvs/wflash/bin/pytest -q`: 91 passed ✓.

## Phase 1.10: Debug bundle

Phase này cho phép người dùng xuất một file zip duy nhất chứa mọi thứ cần để debug từ xa (log, môi trường, profile, mapping, snapshot workspace, lỗi). Lý do: tool chạy trên máy Windows có winIDEA mà dev không truy cập được, nên khi lỗi xảy ra cần một gói thông tin đầy đủ; mọi nội dung đều đi qua `redact` để token GitLab không bao giờ rời máy.

### Thay đổi

- **`wflash/core/debug_bundle.py`** (mới): `DebugContext` (mapping, adapter_info, snapshot `programs`/`applications` theo nhãn, danh sách lỗi kèm traceback), `collect_env_info` (phiên bản wflash, Python, nền tảng, PySide6, isystem.connect) và `create_debug_bundle` ghi zip `wflash_debug_<timestamp>.zip` gồm `log.txt`, `environment.json`, `profile.yaml`, `mapping.json`, `workspace_snapshots.json`, `errors.txt` (file log/profile thiếu thì bỏ qua).
- **`tests/test_debug_bundle.py`** (mới): 4 test — thông tin môi trường, snapshot và lỗi, nội dung bundle kèm che secret, bundle không có log/profile.

### Đã kiểm tra

- `~/.venvs/wflash/bin/pytest tests/test_debug_bundle.py -q` (RED): `ModuleNotFoundError: No module named 'wflash.core.debug_bundle'` ✓ (expected).
- `~/.venvs/wflash/bin/pytest tests/test_debug_bundle.py -q -W error` (GREEN): `4 passed in 0.09s` ✓.
- `~/.venvs/wflash/bin/pytest -q`: `95 passed in 0.50s` ✓.

## Phase 1.11: Flash workflow và rollback

Đây là phần cốt lõi của tool: chuỗi connect, kiểm tra entry, đổi đường dẫn, download, reset. Lý do thiết kế theo Approach A (chỉ đổi path, không bao giờ tạo entry mới): workspace winIDEA của người dùng phải luôn quay về được trạng thái cũ, nên mọi lỗi hoặc hủy trong lúc set path/download đều rollback path cũ, và adapter luôn được disconnect.

### Thay đổi

- **`wflash/core/flash_workflow.py`** (mới): `Step`, `FlashRequest`, `FlashWorkflow.run`. Từ chối mapping thiếu file trước khi connect; kiểm tra entry tồn tại trong workspace (`MappingError` kèm danh sách entry thật); snapshot `before`, `after_set`, `after_rollback`; lỗi ngoài `WFlashError` được bọc thành `FlashError("<Type>: <msg>")`; lỗi rollback được ghi vào `ctx.errors` mà không che lỗi gốc.
- **`tests/test_flash_workflow.py`** (mới): 12 test — 9 test theo brief cộng 3 test bổ sung (R14): lỗi khi set path thứ hai (path đầu được khôi phục), download timeout (rollback và bước ROLLBACK), mất kết nối giữa download (rollback thất bại ghi 1 lỗi, vẫn disconnect). Không phát hiện lỗi nào trong code workflow của brief.

### Đã kiểm tra

- `~/.venvs/wflash/bin/pytest tests/test_flash_workflow.py -q` (RED): `ModuleNotFoundError` khi collect `tests/test_flash_workflow.py` ✓ (expected).
- `~/.venvs/wflash/bin/pytest tests/test_flash_workflow.py -q -W error` (GREEN): `12 passed in 0.30s` ✓.
- `~/.venvs/wflash/bin/pytest -q`: `107 passed in 0.66s` ✓.

### Fix Round 1 (R15)

Review tìm ra 3 lỗi rollback quan trọng trong `FlashWorkflow`: rollback dừng ở lần restore lỗi đầu tiên (các entry sau vẫn trỏ file mới), callback `on_step(ROLLBACK)` ném lỗi thì bỏ qua rollback và che lỗi gốc, và rollback thất bại không hiện trong lỗi trả về.

- **`wflash/core/flash_workflow.py`**: chỉ restore các entry đã ghi thành công (`written`), mỗi entry một try riêng và ghi lỗi vào `ctx.errors`; thông báo `Step.ROLLBACK` nằm trong guard; khi có restore lỗi, lỗi cuối được gắn `rollback_failed = True` và hint bắt đầu bằng "ROLLBACK FAILED"; lỗi đọc snapshot `after_rollback` được log riêng; lỗi không phải `WFlashError` được ghi cả traceback vào `ctx.errors` khi bọc thành `FlashError`.
- **`wflash/core/errors.py`**: `WFlashError.rollback_failed = False`.
- **`tests/test_flash_workflow.py`**: 6 test mới (restore tiếp tục sau lỗi, entry chưa ghi không bị đụng, callback ROLLBACK ném lỗi, cờ rollback_failed, ctx.errors có traceback, lỗi snapshot), test mất kết nối dùng thông báo download riêng, `test_rollback_failure_recorded` nay khẳng định `ctx.errors == []` vì chưa có gì được ghi thì không cần restore.

Đã kiểm tra:
- `~/.venvs/wflash/bin/pytest tests/test_flash_workflow.py -q` (RED, code cũ): `8 failed, 10 passed` ✓ (expected).
- `~/.venvs/wflash/bin/pytest tests/test_flash_workflow.py -v -W error` (GREEN): `18 passed in 0.42s` ✓.
- `~/.venvs/wflash/bin/pytest -q`: `113 passed in 0.67s` ✓.

### Fix Round 2 (R16)

Re-review phát hiện một lỗ hổng còn lại: entry chỉ được ghi vào danh sách `written` sau khi `_set_path` trả về. Với adapter COM/SDK thật, một lệnh set ném lỗi (mất kết nối hoặc timeout sau khi đã gửi request) có thể đã được áp dụng, khiến entry đó kẹt ở path mới mà không ai biết.

- **`wflash/core/flash_workflow.py`**: entry được thêm vào `written` ngay TRƯỚC khi gọi `_set_path`, nên entry có lệnh set ném lỗi cũng được restore (ghi lại giá trị cũ vô hại); các entry sau đó vẫn không nhận lệnh set nào.
- **`tests/test_flash_workflow.py`**: thêm `test_set_that_raises_after_applying_is_restored`; `test_unwritten_entry_not_touched_on_rollback` nay mong đợi `["CM7_0", "CM7_0"]`; `test_rollback_failure_recorded` nay mong đợi 1 lỗi ghi nhận và `rollback_failed is True`.

Đã kiểm tra:
- `~/.venvs/wflash/bin/pytest tests/test_flash_workflow.py -q` (RED, code cũ): `3 failed, 16 passed` ✓ (expected).
- `~/.venvs/wflash/bin/pytest tests/test_flash_workflow.py -v -W error` (GREEN): `19 passed in 0.42s` ✓.
- `~/.venvs/wflash/bin/pytest -q`: `114 passed in 0.77s` ✓.

## Phase 1.12: Lớp worker cho GUI (QThreadPool)

Bắt đầu phần GUI bằng lớp chạy việc nặng ngoài GUI thread, vì mọi lỗi crash/deadlock của dự án SFlash đều nằm ở đây. `core/` vẫn chỉ thấy callback thường + `CancelToken`; `WorkerSignals` biến chúng thành Qt signal. `WorkerRegistry` giữ worker (và object signal của nó) tới khi signal `finished` đã được xử lý, từ chối slot là lambda/hàm thường (quy tắc 8), chỉ cho `start()` trên GUI thread (quy tắc 6) và chờ có giới hạn thời gian trong khi vẫn bơm event (quy tắc 3).

### Thay đổi

- **`pyproject.toml`**: đăng ký marker `gui` để `pytest -k "not gui"` chỉ chạy core.
- **`wflash/gui/workers.py`** (mới): `WorkerSignals`, `WorkerContext` (progress ném `CancelledError` sau khi hủy — quy tắc 7), `Worker` (`autoDelete=False`, có ghi lý do), `WorkerRegistry` (`start`, `cancel`, `cancel_all`, `wait_idle`, `abandon_running`).
- **`tests/test_gui_workers.py`** (mới): 12 test vòng đời worker, tên đều chứa `thread`.

### Đã kiểm tra

- `~/.venvs/wflash/bin/pytest tests/test_gui_workers.py -v` (RED, chưa có `workers.py`): `ImportError: cannot import name 'workers' from 'wflash.gui'` khi collect, `1 error in 0.10s` ✓ (expected).
- `~/.venvs/wflash/bin/pytest tests/test_gui_workers.py -v` (GREEN): `12 passed in 0.50s` ✓.
- `~/.venvs/wflash/bin/pytest -k thread -v`: `12 passed, 114 deselected in 0.78s` ✓.
- `~/.venvs/wflash/bin/pytest -k "not gui" -q`: `114 passed, 12 deselected in 0.68s`, không có `PytestUnknownMarkWarning` ✓.
- `~/.venvs/wflash/bin/pytest -q` (chạy 5 lần liên tiếp): `126 passed` mỗi lần (~1.1s) ✓.

### Fix Round 1 (R20)

Review chứng minh PySide6 6.11 giữ tham chiếu Python tới mọi runnable đã `QThreadPool.start()` trong suốt đời pool (200 worker chạy tuần tự + `wait_idle` + `gc.collect()` vẫn còn 200 `Worker` và 200 `WorkerSignals`). Vì vậy cơ chế retire/purge của registry thực ra không giải phóng gì, và các test về vòng đời pass bất kể registry.

Quyết định: giữ việc pool giữ runnable làm bảo đảm vòng đời thật sự, KHÔNG thêm đường giải phóng (giải phóng sẽ khiến QObject đã connect bị hủy trên pool thread, vi phạm quy tắc 6). Bộ nhớ tăng một `Worker` nhỏ mỗi thao tác, chấp nhận.

- **`wflash/gui/workers.py`**: ghi chú cạnh `setAutoDelete(False)` và trong docstring `WorkerRegistry`: pool là bảo đảm chính, tham chiếu/`_retired` của registry chỉ là lớp phụ cộng theo dõi idle.
- **`tests/test_gui_workers.py`**: thêm `test_thread_pool_retains_finished_runnables` (20 worker tuần tự, xóa mọi tham chiếu, `gc.collect()`, khẳng định cả 20 vẫn sống; nếu nâng cấp PySide đổi hành vi, test báo cần xem lại race).

Đã kiểm tra:
- RED (tạm đảo khẳng định thành `alive == 0`): `AssertionError ... assert 20 == 0`, `1 failed` ✓ (chứng minh pool giữ đủ 20; đã hoàn nguyên).
- `~/.venvs/wflash/bin/pytest -k thread -v`: `13 passed, 114 deselected in 0.82s` ✓.
- `~/.venvs/wflash/bin/pytest -q`: `127 passed in 1.09s` ✓.

## Phase 1.13: Layout Designer cho cửa sổ chính và Settings

Theo quy tắc Designer-first trong CLAUDE.md, toàn bộ layout tĩnh nằm trong file `.ui` và code Python sinh bằng `pyside6-uic`, không dựng widget bằng tay. Mọi widget/layout đặt tên `<loại>_<ý nghĩa>` để code mixin đọc được; một test tự động kiểm tra tên, kiểm tra file sinh ra khớp với XML và mọi `self.ui.<tên>` đều tồn tại.

### Thay đổi

- **`wflash/gui/main_window.ui`** (mới): thanh profile, nhóm GitLab (ref → pipeline → job → tải artifact), bảng mapping 4 cột, nhóm Flash (instance, reset/run, Cancel/Flash, bước + tiến trình, dòng đỏ ROLLBACK FAILED ẩn sẵn), log panel, status bar.
- **`wflash/gui/settings_dialog.ui`** (mới): GitLab URL, token (ẩn ký tự), CA bundle, thư mục cache + Clear cache, số job giữ lại, thư mục profile, verbose.
- **`wflash/gui/ui_main_window.py`, `wflash/gui/ui_settings_dialog.py`** (sinh bằng `pyside6-uic`, không sửa tay).
- **`tests/test_gui_ui_files.py`** (mới): 6 test.

### Đã kiểm tra

- `~/.venvs/wflash/bin/pytest tests/test_gui_ui_files.py -v` (RED, chưa có `.ui`/`ui_*.py`): `6 failed in 0.40s` (`ModuleNotFoundError: No module named 'wflash.gui.ui_main_window'`) ✓ (expected).
- `pyside6-uic` sinh 2 module; `QT_QPA_PLATFORM=offscreen ~/.venvs/wflash/bin/python -c "import wflash.gui.ui_main_window, wflash.gui.ui_settings_dialog; print('ok')"`: `ok`; `grep -n "setVisible(False)" wflash/gui/ui_main_window.py` có `self.label_rollbackWarning.setVisible(False)` ✓.
- `~/.venvs/wflash/bin/pytest tests/test_gui_ui_files.py -v` (GREEN): `6 passed in 0.48s` ✓.
- `~/.venvs/wflash/bin/pytest -q`: `133 passed in 1.66s`; `~/.venvs/wflash/bin/pytest -k thread -q`: `13 passed, 120 deselected` ✓.

## Phase 1.14: Test double dùng chung cho GUI

GUI test và stress test cần một GitLab giả đủ thật để kiểm tra đúng code xử lý lỗi. Thay vì mock cả `GitLabClient`, `FakeGitLabSession` chỉ thay phần mạng (`requests.Session`), nên phân trang, phân loại lỗi 401/403/404/mất kết nối và tải zip theo chunk vẫn chạy bằng code thật. `HostWindow` cho phép test từng mixin riêng mà không cần cả `MainWindow`.

### Thay đổi

- **`tests/gui_stubs.py`** (mới): `FakeGitLabSession`, `SessionClientFactory`, `HostWindow`, `make_artifact_tree`, `write_profiles`, token giả có dạng PAT thật.
- **`tests/test_gui_stubs.py`** (mới): 5 test chứng minh session giả đi qua `GitLabClient` thật.

### Đã kiểm tra

- `~/.venvs/wflash/bin/pytest tests/test_gui_stubs.py -q` (RED, chưa có `gui_stubs.py`): `ModuleNotFoundError: No module named 'tests.gui_stubs'`, `1 error in 0.07s` ✓ (expected).
- `~/.venvs/wflash/bin/pytest tests/test_gui_stubs.py -v` (GREEN): `5 passed in 0.35s` ✓.
- `~/.venvs/wflash/bin/pytest -q`: `138 passed in 1.57s`; `~/.venvs/wflash/bin/pytest -k thread -q`: `13 passed, 125 deselected` ✓.

## Phase 1.15: Log panel

Log panel là nơi người dùng thấy chuyện gì đang xảy ra và là nguồn của debug bundle, nên nó phải nhận log từ mọi thread mà không đụng widget ngoài GUI thread: handler chỉ phát một signal queued, slot là method của cửa sổ (không phải lambda). Token đi qua `RedactingFormatter` trước khi tới panel; export bundle bị chặn khi đang flash vì `DebugContext` lúc đó do worker ghi.

### Thay đổi

- **`wflash/gui/log_panel.py`** (mới): `LogEmitter`, `QtLogHandler`, `LogPanelMixin` (màu theo level, lọc level, Copy, Clear, export debug bundle).
- **`tests/test_gui_log_panel.py`** (mới): 7 test (lọc, traceback, che token, copy/clear, log từ thread khác, export + chặn khi flash, gỡ handler khi đóng).

### Đã kiểm tra

- `~/.venvs/wflash/bin/pytest tests/test_gui_log_panel.py -v` (RED, chưa có `log_panel.py`): `ModuleNotFoundError: No module named 'wflash.gui.log_panel'`, `1 error in 0.30s` ✓ (expected).
- `~/.venvs/wflash/bin/pytest tests/test_gui_log_panel.py -v` (GREEN): `7 passed in 0.45s` ✓.
- `~/.venvs/wflash/bin/pytest -q`: `145 passed in 1.64s`; `~/.venvs/wflash/bin/pytest -k thread -q`: `14 passed, 131 deselected` ✓.

## Phase 1.16: Hộp thoại Settings

Settings là nơi duy nhất nhập GitLab URL, token, CA bundle (cho chứng chỉ nội bộ — spec §8) và nút xóa cache (spec §2). Layout nằm trong `settings_dialog.ui`; Python chỉ nạp giá trị, kiểm tra hợp lệ và trả về bản sao `AppSettings`. Token chỉ đi ra qua `result_token()`, việc lưu vào keyring do cửa sổ chính làm.

### Thay đổi

- **`wflash/gui/settings_dialog.py`** (mới): `SettingsDialog` (validate URL/CA bundle, browse, Clear cache có xác nhận).
- **`tests/test_gui_settings_dialog.py`** (mới): 5 test.

### Đã kiểm tra

- `~/.venvs/wflash/bin/pytest tests/test_gui_settings_dialog.py -q` (RED, chưa có `settings_dialog.py`): `ERROR tests/test_gui_settings_dialog.py`, `1 error in 0.18s` (`ModuleNotFoundError: No module named 'wflash.gui.settings_dialog'`) ✓ (expected).
- `~/.venvs/wflash/bin/pytest tests/test_gui_settings_dialog.py tests/test_gui_ui_files.py -v` (GREEN): `11 passed in 0.51s` ✓.
- `~/.venvs/wflash/bin/pytest -q`: `150 passed in 1.73s`; `~/.venvs/wflash/bin/pytest -k thread -q`: `14 passed, 136 deselected` ✓.

## Phase 1.17: Bảng mapping

Chọn nhầm file là lỗi tệ nhất tool này có thể gây ra (flash sai binary), nên bảng mapping không bao giờ tự chọn khi pattern khớp 0 hoặc nhiều file: dòng đó tô đỏ, người dùng phải chọn, và nút Flash tắt cho tới khi mọi dòng có file (spec §5). Các dòng là nội dung động nên được dựng trong Python; bảng, cột và header nằm trong `.ui`.

### Thay đổi

- **`wflash/gui/mapping_table.py`** (mới): `MappingTableMixin` (dựng dòng + combo chọn file, tô đỏ dòng chưa chọn, `mapping_complete()`).
- **`tests/test_gui_mapping_table.py`** (mới): 4 test.

### Đã kiểm tra

- `~/.venvs/wflash/bin/pytest tests/test_gui_mapping_table.py -q` (RED, chưa có `mapping_table.py`): `ERROR tests/test_gui_mapping_table.py`, `1 error in 0.28s` (`ModuleNotFoundError: No module named 'wflash.gui.mapping_table'`) ✓ (expected).
- `~/.venvs/wflash/bin/pytest tests/test_gui_mapping_table.py tests/test_gui_ui_files.py -q` (GREEN): `10 passed in 0.59s` ✓.
- `~/.venvs/wflash/bin/pytest -q`: `154 passed in 1.72s`; `~/.venvs/wflash/bin/pytest -k thread -q`: `14 passed, 140 deselected` ✓.

## Phase 1.16 / 1.17 - sửa vòng 1 (an toàn dữ liệu)

Review chỉ ra `ArtifactCache.clear()` là `rmtree(root, ignore_errors=True)`: nếu người dùng gõ nhầm thư mục cache thành `~/Desktop` thì cả thư mục bị xóa, và lỗi quyền bị nuốt nhưng vẫn báo "cleared". Sửa: `clear()` (thay đổi nhỏ ở `wflash/core/artifact_cache.py`) chỉ xóa đúng layout cache (`<root>/<số>/<số>` và `<số>.tmp`), rồi `rmdir` thư mục project nếu rỗng; không bao giờ xóa root hay file lạ; lỗi xóa được gom lại và ném `ArtifactError("Could not clear N cached artifact(s)")` sau khi đã xóa phần còn lại. Dialog Settings hiện lỗi + hint và không đặt `cache_cleared`. Mỗi combo trong bảng mapping nuốt sự kiện cuộn chuột để cuộn bảng không đổi file được chọn.

### Đã kiểm tra

- RED (test viết trước, code cũ): `~/.venvs/wflash/bin/pytest tests/test_artifact_cache.py tests/test_gui_settings_dialog.py tests/test_gui_mapping_table.py -q`: `5 failed, 17 passed, 1 error` (clear xóa cả root, không raise, không có eventFilter).
- GREEN: cùng lệnh với `-v`: `22 passed in 0.61s` ✓.
- `~/.venvs/wflash/bin/pytest -q`: `158 passed in 1.70s`; `~/.venvs/wflash/bin/pytest -k thread -q`: `14 passed, 144 deselected` ✓.

## Phase 1.18: Duyệt GitLab và tải artifact

GUI không bao giờ gọi GitLab trực tiếp: mỗi bước ref → pipeline → job → download là một worker `gitlab-*`. Kết quả mang "generation" để kết quả cũ (sau khi refresh hoặc đổi profile) bị bỏ thay vì hiện sai. Hủy tải đặt cờ guard trước khi hủy token, nên một kết quả đã nằm trong hàng đợi cũng không nạp artifact sau khi người dùng bấm Cancel (quy tắc 4). Lỗi 401/403/404/SSL/mất kết nối hiện đúng gợi ý của `GitLabClient`.

### Thay đổi

- **`wflash/gui/gitlab_browser.py`** (mới): `default_client_factory`, `GitlabBrowserMixin` (refresh, chọn ref/pipeline/job, tải có cache, cancel, xử lý lỗi).
- **`tests/test_gui_gitlab_browser.py`** (mới): 11 test (duyệt + tải, cache, double-click, cancel, completion đã queue trước cancel, 401/403/404, mất kết nối, đổi profile giữa chừng, factory) và sau vòng sửa 1 là 13 test (thêm: cập nhật nút Flash khi worker liệt kê bắt đầu/kết thúc, bỏ lỗi của worker cũ).

### Đã kiểm tra

- `~/.venvs/wflash/bin/pytest tests/test_gui_gitlab_browser.py -q` (RED, chưa có `gitlab_browser.py`): collection error `ImportError: cannot import name 'gitlab_browser' from 'wflash.gui'` ✓ (expected).
- `~/.venvs/wflash/bin/pytest tests/test_gui_gitlab_browser.py tests/test_gui_ui_files.py -q` (GREEN): `17 passed in 1.91s` ✓.
- Chạy `tests/test_gui_gitlab_browser.py` 3 lần: `11 passed` mỗi lần (1.60s, 1.63s, 1.59s) ✓.
- `~/.venvs/wflash/bin/pytest -q`: `169 passed in 2.99s`; `~/.venvs/wflash/bin/pytest -k thread -q`: `14 passed, 155 deselected` ✓.

### Sửa vòng 1 (R22)

`_start_gitlab` giờ gọi `_update_gitlab_controls()` và `_update_flash_controls()` ngay sau khi worker bắt đầu, nên Flash tắt trong lúc worker liệt kê chạy (trước đây chỉ download làm vậy). Khi kết quả tải bị bỏ (cờ cancel hoặc đổi profile), thanh tiến trình được đặt lại về 0..100, "Cancelled" thay vì kẹt ở "Extracting". Lỗi của worker liệt kê thuộc generation cũ chỉ ghi log WARNING, không hiện dialog và không vào `ctx`.

- RED (test viết trước): `~/.venvs/wflash/bin/pytest tests/test_gui_gitlab_browser.py -q`: `3 failed, 10 passed`.
- GREEN: 3 lần chạy cùng file: `13 passed` mỗi lần (2.54s, 2.30s, 2.29s).
- `~/.venvs/wflash/bin/pytest -q`: `171 passed in 3.70s`; `~/.venvs/wflash/bin/pytest -k thread -q`: `14 passed, 157 deselected`.

## Phase 1.19: Flash từ GUI

Mixin Flash chỉ khởi chạy `FlashWorkflow` trong một worker và hiển thị kết quả; rollback vẫn là trách nhiệm của core (Approach A). Danh sách instance winIDEA luôn lấy từ `list_instances()` (lỗi → danh sách rỗng), combo lưu dict và đọc bằng `currentData()`. Khi rollback thất bại (R15), GUI hiện dòng đỏ ROLLBACK FAILED và hộp thoại riêng — kể cả khi lỗi đến từ Cancel — vì người dùng tuyệt đối không được bỏ lỡ việc workspace có thể vẫn trỏ tới file mới.

### Thay đổi

- **`wflash/gui/flash_mixin.py`** (mới): `safe_list_instances`, `instance_data`, `FlashMixin` (Flash/Cancel, bước + tiến trình, khóa các điều khiển khi đang flash, hiển thị rollback thất bại).
- **`tests/test_gui_flash.py`** (mới): 11 test (combo là dict, không có instance, happy path, run sau reset, lỗi download + rollback, thiếu entry, rollback thất bại, cancel giữa download, double Flash, mapping chưa đủ).

### Đã kiểm tra

- RED (chưa có `flash_mixin.py`): `~/.venvs/wflash/bin/pytest tests/test_gui_flash.py -q`: `ERROR tests/test_gui_flash.py`, `1 error in 0.25s` (collection, ModuleNotFoundError) ✓ (expected).
- GREEN: `~/.venvs/wflash/bin/pytest tests/test_gui_flash.py tests/test_gui_ui_files.py -q`: `17 passed in 1.77s` ✓.
- Chạy `tests/test_gui_flash.py` 3 lần: `11 passed` mỗi lần (1.55s, 1.60s, 1.50s) ✓.
- `~/.venvs/wflash/bin/pytest -q`: `182 passed in 4.70s`; `~/.venvs/wflash/bin/pytest -k thread -q`: `16 passed, 166 deselected` ✓.

## Phase 1.20: Ghép cửa sổ chính

`MainWindow` được ghép bằng đa kế thừa từ bốn mixin, cùng một `self.ui`, đúng kiến trúc SFlash mà CLAUDE.md chốt. Bản thân `main_window.py` chỉ giữ trạng thái dùng chung (settings, adapter, `DebugContext`, `WorkerRegistry`, cờ `_closing`), thanh profile, Settings và đường tắt máy. Token nhập ở Settings được đăng ký để che trong log trước khi lưu vào keyring; lỗi keyring hiện ra cho người dùng thay vì bị nuốt.

### Thay đổi

- **`wflash/gui/main_window.py`** (mới): `MainWindow`, `show_error`, profile (nạp/lưu `last_profile`, lỗi YAML hiện hộp thoại), `open_settings`, `closeEvent` tối thiểu (gỡ log handler).
- **`tests/test_gui_main_window.py`** (mới): 9 test (ghép đủ 4 mixin, profile khi khởi động, chuỗi GitLab → mapping → flash, mapping mơ hồ chặn Flash, lỗi + bundle có rollback, tiêu đề rollback thất bại, profile hỏng, Settings lưu + che token, lỗi keyring).
- **`wflash/gui/flash_mixin.py`** (R23): `start_flash` từ chối và Flash bị tắt khi worker liệt kê instance đang chạy (adapter winIDEA thật có thể không thread-safe; `refresh_instances` cập nhật điều khiển ngay khi bắt đầu và khi worker kết thúc); `cancel_flash` bỏ qua nếu đã yêu cầu hủy (không ghi đè `label_step`).
- **`tests/test_gui_flash.py`** (R23): thêm 3 test (hủy khi đang download mà restore thất bại -> cảnh báo rollback + log CRITICAL + `rollback_failed`; Flash bị từ chối khi worker instance chạy; hủy lần hai không ghi đè `label_step`).

### Đã kiểm tra

- RED R23: `~/.venvs/wflash/bin/pytest tests/test_gui_flash.py -q`: `2 failed, 12 passed` (test instance-worker và second-cancel; test rollback-khi-hủy đã xanh sẵn nhờ core).
- GREEN R23: cùng lệnh: `14 passed in 1.68s`.
- RED main window (chưa có `main_window.py`): `pytest tests/test_gui_main_window.py -q`: `ERROR tests/test_gui_main_window.py`, `1 error in 0.25s` (collection) ✓.
- GREEN: `pytest tests/test_gui_main_window.py tests/test_gui_ui_files.py -q`: `15 passed in 1.35s` ✓.
- Chạy `tests/test_gui_main_window.py tests/test_gui_flash.py` 3 lần: `23 passed` mỗi lần (2.41s, 2.40s, 2.39s) ✓.
- `~/.venvs/wflash/bin/pytest -q`: `194 passed in 5.49s`; `~/.venvs/wflash/bin/pytest -k thread -q`: `19 passed, 175 deselected` ✓.
- `QT_QPA_PLATFORM=offscreen ~/.venvs/wflash/bin/python -c "from wflash.gui.main_window import MainWindow; print('import ok')"`: `import ok` ✓.

## Phase 1.21: Đóng cửa sổ khi đang flash

`closeEvent` là nơi deadlock hay xảy ra nhất (SFlash từng treo vì chờ thread trong `closeEvent`). Thứ tự bây giờ: hỏi xác nhận nếu đang flash, dựng cờ `_closing` trước, hủy mọi worker, rồi chờ có giới hạn (15 s) trong khi vẫn bơm event — để rollback và disconnect của workflow chạy xong *trước* khi cửa sổ biến mất. Quá giờ thì worker được giữ lại trong `_ABANDONED` (không bao giờ xóa object signal khi worker còn chạy) và log CRITICAL. Lỗi flash bắt được trong lúc đóng luôn được ghi vào `ctx` + log sau khi chờ; riêng rollback thất bại còn log CRITICAL và hiện hộp thoại "WFlash — rollback failed".

### Thay đổi

- **`wflash/gui/main_window.py`**: `CLOSE_TIMEOUT_S`, `closeEvent` đầy đủ (kể cả ghi `ctx.add_error` + log cho lỗi flash lưu trong `_flash_error_during_close`).
- **`tests/test_gui_close_window.py`** (mới): 7 test `test_gui_thread_*` (đóng giữa download, từ chối đóng, đóng giữa lúc fetch GitLab, báo rollback thất bại, chờ có giới hạn khi worker bỏ qua cancel, log CRITICAL + ctx cho rollback thất bại, lỗi thường lúc đóng được ghi không hiện dialog), kiểm tra không có cảnh báo threading của Qt.

### Đã kiểm tra

- RED: `~/.venvs/wflash/bin/pytest tests/test_gui_close_window.py -q`: `7 failed in 22.56s`.
- GREEN: cùng lệnh, chạy 5 lần: `7 passed` mỗi lần (3.37s, 3.30s, 3.28s, 3.26s, 3.31s).
- `~/.venvs/wflash/bin/pytest -k thread -q`: `26 passed, 175 deselected in 4.48s`; `~/.venvs/wflash/bin/pytest -q`: `201 passed in 8.77s`.

### Hardening (R24)

Chờ trong `closeEvent` bơm event nên cửa sổ vẫn tương tác được; bốn lỗ hổng được vá: (1) khóa `centralWidget()` + thông báo status bar trước khi chờ, để Settings/file dialog không mở lồng trong vòng chờ và phá giới hạn 15 s; (2) cờ `_close_in_progress` — `closeEvent` gọi lại lúc đang chờ thì `ignore()` ngay; (3) `CancelledError` không rollback-thất-bại (người dùng đóng, rollback ổn) log WARNING "Flash cancelled by closing; previous paths restored" thay vì ERROR; (4) quá giờ mà worker flash bị bỏ lại thì ngoài log CRITICAL còn hiện `QMessageBox.warning` "WFlash — flash still running" nhắc kiểm tra danh sách file download/symbol trong winIDEA. Thêm 2 test mới (khóa UI + đóng lồng, WARNING không ERROR) và mở rộng test worker bỏ qua cancel; test đóng lồng gọi thẳng `closeEvent` vì `QWidget.close()` của Qt tự chặn re-entry nên không quan sát được cờ.

- RED: 3 test fail trước khi sửa (`pytest tests/test_gui_close_window.py -k "wait_is_bounded or warning_not_error or disables_ui"`: `3 failed`); tắt riêng guard `_close_in_progress` thì test đóng lồng `1 failed`.
- GREEN: `tests/test_gui_close_window.py` 5 lần: `9 passed` mỗi lần (~3.8s); `pytest -k thread -q`: `28 passed, 175 deselected`; `pytest -q`: `203 passed in 9.02s`.

## Phase 1.22: Entry point và excepthook

`python -m wflash` giờ chạy được app thật: đọc settings, mở log file DEBUG, cài `sys.excepthook`/`threading.excepthook` để không lỗi nào im lặng (spec §8), tạo adapter (`--adapter fake` trên macOS), mở cửa sổ. `--smoke` đóng *cửa sổ* sau 1,5 s chứ không `app.quit()`, để đường tắt máy thật (`closeEvent`) cũng được chạy.

### Thay đổi

- **`wflash/main.py`** (mới): `parse_args`, `install_excepthooks` (hộp thoại chỉ trên GUI thread), `main`.
- **`wflash/__main__.py`** (mới).
- **`tests/test_gui_main.py`** (mới): 3 test.

### Đã kiểm tra

- RED: `~/.venvs/wflash/bin/pytest tests/test_gui_main.py -q`: collection error `ModuleNotFoundError: No module named 'wflash.main'`; GREEN: `3 passed in 0.13s`.
- Smoke: `QT_QPA_PLATFORM=offscreen ~/.venvs/wflash/bin/python -m wflash --adapter fake --smoke; echo "exit=$?"`: `exit=0`. Log mới nhất có `WFlash 0.1.0 starting (adapter=fake, ...)`, `Found 1 winIDEA instance(s)`, `WFlash exiting (code 0)`.
- `pytest -q`: `206 passed in 9.02s`; `pytest -k thread -q`: `29 passed, 177 deselected`; `pytest -k "not gui" -q`: `116 passed, 90 deselected`.

## Phase 1.23: Stress test headless

Unit test cô lập không bắt được lớp lỗi nguy hiểm nhất (worker còn chạy khi cửa sổ đóng, signal tới object đã xóa, deadlock khi đóng), vì nó chỉ xuất hiện khi nhiều thao tác nối tiếp trong một process. `tools/stress_test.py` chạy `MainWindow` thật với fake adapter và GitLab giả qua năm nhóm (flash, rollback, gitlab, races, secrets), fail khi checkpoint sai *và* khi Qt in cảnh báo threading hoặc có exception không bắt — những thứ không ném lỗi Python nên thường trôi qua stderr.

### Thay đổi

- **`tools/stress_test.py`** (mới): 5 section, `--list`, `--section`, `--iterations`, `--keep`; in `STRESS_RESULT=PASS/FAIL`.

### Đã kiểm tra

- `~/.venvs/wflash/bin/python tools/stress_test.py --list`: 5 dòng `flash`, `rollback`, `gitlab`, `races`, `secrets`.
- Chạy đủ: `CHECKPOINTS=225 FAILED=0 QT_THREADING_WARNINGS=0 OTHER_QT_WARNINGS=56 TIME=15.2s`, `STRESS_RESULT=PASS`, exit=0 (cảnh báo khác chỉ là font và `propagateSizeHints()` của nền offscreen).
- `--section flash --section races`: `STRESS_RESULT=PASS`.
- Làm hỏng `wait_idle(CLOSE_TIMEOUT_S)` thành `wait_idle(0.0)` rồi chạy `--section races`: `FAIL: no worker was abandoned: ['flash-2', 'gitlab-refs-2']`, `CHECKPOINTS=48 FAILED=1`, `STRESS_RESULT=FAIL`, exit=1. Sau `git checkout -- wflash/gui/main_window.py` thì `git diff --stat` rỗng.
- `pytest -q`: `206 passed in 9.07s`; `pytest -k thread -q`: `29 passed, 177 deselected in 4.93s`.

### Vòng sửa 1 (R25): stress test không được pass rỗng

- Double-click giờ thử trên job *chưa cache* với session chậm: chờ download chạy thật (worker chạy, progress > 0), gọi `download_selected_artifact()` hai lần, kiểm tra đúng 1 worker và đúng 1 request artifact.
- Mọi `pump_until`/`wait_flash_idle` mà checkpoint sau phụ thuộc đều được bọc `check`, lặp lại bị bỏ qua nếu chờ thất bại; hủy/đóng giữa download đều có checkpoint riêng chứng minh download đang chạy trước đó.
- Thêm pattern Qt threading ("different thread", "another thread", "outside the GUI thread"); in mọi cảnh báo Qt khác; message handler giữ đến sau khi teardown.
- Cancel kiểm tra khôi phục đúng chính xác program *và* symbol path của lần flash đầu (cả section races).
- Kết quả: chạy đủ `CHECKPOINTS=255 FAILED=0 QT_THREADING_WARNINGS=0`, `STRESS_RESULT=PASS`; `--section flash --section races`: `CHECKPOINTS=93`, PASS; phá `wait_idle(0.0)` → `FAIL: no worker was abandoned: ['flash-2', 'gitlab-refs-2']`, `STRESS_RESULT=FAIL`, rồi `git checkout` khôi phục (diff sạch); `pytest -q`: `206 passed`; `-k thread`: `29 passed, 177 deselected`.

## Phase 1.24: Đóng gói PyInstaller và README

Người dùng cuối dùng bản `.exe` onedir (spec §11). Spec PyInstaller chỉ gói `isystem.connect` nếu máy build có (cài từ thư mục winIDEA, R1) — không có thì `.exe` vẫn chạy với `--adapter fake`. Script build trên Windows chạy toàn bộ test, `-k thread` và stress test trước khi build, đúng quy trình trước khi push trong CLAUDE.md.

### Thay đổi

- **`wflash.spec`** (mới), **`scripts/build_windows.bat`** (mới).
- **`README.md`**: viết lại (chạy từ source, cấu hình, quy trình, ROLLBACK FAILED, log/bundle, phát triển với Designer, test, build).

### Đã kiểm tra

- Build thử trên macOS: `~/.venvs/wflash/bin/pyinstaller --noconfirm wflash.spec` dừng ở `SystemError: lipo command (['lipo', '-thin', 'arm64', '.../build/wflash/WFlash', ...]) failed with error code 69! output: You have not agreed to the Xcode license agreements. Please run 'sudo xcodebuild -license' ...`. Đây là do máy (Xcode licence chưa chấp nhận), không phải spec; không chạy sudo; build Windows (Task 25) là căn cứ. Đã `rm -rf build dist`.
- `pytest -q`: `206 passed in 9.05s`; `pytest -k thread -q`: `29 passed, 177 deselected in 5.07s`; `tools/stress_test.py`: `STRESS_RESULT=PASS`; `QT_QPA_PLATFORM=offscreen ~/.venvs/wflash/bin/python -m wflash --adapter fake --smoke`: `exit=0`.

### Vòng sửa 1 (R26): README

- Thêm lưu ý: adapter winIDEA thật chưa có (Plan 2), chạy không tham số sẽ báo lỗi; dùng `--adapter fake`, và shortcut `--adapter fake` cho `WFlash.exe`.
- Bỏ đường dẫn miniforge riêng của máy: dùng `python3 -m venv ~/.venvs/wflash` (Python 3.11+), venv vẫn nằm ngoài OneDrive.
