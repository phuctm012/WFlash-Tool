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

## Phase 1.25: Đợt sửa sau review tổng

Review tổng của branch đã duyệt merge, nhưng còn một số lỗi độ bền và an toàn rẻ để sửa: race khi che secret, token lọt lên hộp thoại lỗi, file đã chọn bị xoá khỏi cache trước khi flash, và vài đường lỗi nhỏ (log dir không ghi được, Content-Length hỏng, profile hỏng không vào debug bundle). Mỗi mục làm theo TDD: test đỏ trước, rồi sửa.

### Thay đổi
- **wflash/core/logging_setup.py**: `redact()` duyệt snapshot `sorted(tuple(_SECRETS), key=len, reverse=True)`; hết `RuntimeError: Set changed size during iteration` khi worker gọi `register_secret`, và secret dài chứa secret ngắn được che trọn.
- **wflash/gui/main_window.py**: `show_error` đưa message và hint qua `redact()`; `_on_profile_selected` gán `ctx.profile_path` trước `load_profile`.
- **wflash/main.py**: hộp thoại excepthook qua `redact()`; thêm `init_logging()` rơi về `%TEMP%/WFlash/logs` khi `OSError`, hiện cảnh báo nêu thư mục dự phòng, nếu cả hai lỗi thì chạy không có file log.
- **wflash/gui/log_panel.py**: hộp thoại lỗi export bundle qua `redact()`.
- **wflash/core/flash_workflow.py**: trước khi connect, nếu file `selected` không còn tồn tại thì ném `MappingError` kèm hint tải lại artifact, không gọi adapter.
- **wflash/core/debug_bundle.py**: phiên bản PySide6 lấy từ metadata, nếu không có thì import cục bộ `PySide6.__version__` trong try (chỉ để đọc chuỗi version, core không import Qt ở mức module).
- **wflash/core/gitlab_client.py**: `Content-Length` sai định dạng coi là không rõ (total 0).

### Đã kiểm tra
- RED (trước khi sửa): 9 test fail, gồm `RuntimeError('Set changed size during iteration')`, `ValueError: invalid literal for int() with base 10: 'abc'`, `AttributeError: module 'wflash.main' has no attribute 'init_logging'`, `assert None == PosixPath(.../bad.yaml)`, `'not installed' == '6.11.2'`.
- GREEN: `~/.venvs/wflash/bin/pytest -q` -> `218 passed`; `pytest -k thread -q` -> `29 passed, 189 deselected`.
- `python tools/stress_test.py` -> `STRESS_RESULT=PASS`.
- `QT_QPA_PLATFORM=offscreen python -m wflash --adapter fake --smoke` -> exit 0.

## Phase 1.26: File `main.py` ở thư mục gốc

User muốn chạy giao diện bằng cách gọi trực tiếp một file `main.py`, thay vì nhớ cú pháp `python -m wflash`. File mới chỉ là lớp mỏng gọi `wflash.main.main()` — không có logic riêng, nên tham số (`--adapter`, `--verbose`, `--smoke`), logging, excepthook và đường đóng app giống hệt `python -m wflash`. File tự thêm thư mục gốc repo vào `sys.path`, để chạy được cả khi package chưa `pip install -e` hoặc khi đứng ở thư mục khác. Không ảnh hưởng tới build `.exe` (spec PyInstaller vẫn dùng `wflash/__main__.py`).

### Thay đổi

- **`main.py`** (mới): entry point ở gốc repo, gọi `wflash.main.main()`.
- **`tests/test_gui_root_main.py`** (mới): chạy `python main.py --adapter fake --smoke` bằng subprocess từ gốc repo và từ một thư mục khác, yêu cầu exit 0.
- **`README.md`**: thêm cách chạy bằng `main.py` (macOS và Windows).

### Đã kiểm tra

- RED: `~/.venvs/wflash/bin/pytest tests/test_gui_root_main.py -q` -> 2 failed, `can't open file '.../WFlash-Tool/main.py': [Errno 2] No such file or directory`.
- GREEN: cùng lệnh -> `2 passed in 4.47s`.
- `~/.venvs/wflash/bin/pytest -q` -> `220 passed in 13.09s`; `pytest -k thread -q` -> `29 passed, 191 deselected in 4.94s`.
- `QT_QPA_PLATFORM=offscreen ~/.venvs/wflash/bin/python main.py --adapter fake --smoke` -> exit 0.

## Phase 1.27: Ước lượng ETA và tốc độ (ProgressEstimator)

Phần đầu cửa sổ mới hiện `phần trăm | ETA | Speed` giống SFlash, nhưng winIDEA chỉ báo phần trăm. `ProgressEstimator` (core, không Qt) tính ETA từ thời gian đã trôi và phần trăm, còn tốc độ là **ước lượng** từ kích thước file `.s3` trên đĩa. Thời gian luôn được truyền vào (`now`) nên test dùng đồng hồ giả, không phụ thuộc máy.

### Thay đổi

- **`wflash/core/progress.py`** (mới): `ProgressEstimator`, `format_mmss`, `IDLE_TEXT`, `CALCULATING_TEXT`; đủ các chuỗi của spec §2.1 (đang chạy, xong, lỗi, hủy).
- **`tests/test_progress.py`** (mới): 8 test.

### Đã kiểm tra

- RED / GREEN `tests/test_progress.py`, `pytest -q`: RED: `ModuleNotFoundError: No module named 'wflash.core.progress'`; GREEN: `8 passed in 0.02s`; `pytest -q`: `228 passed in 13.74s`.

## Phase 1.28: FirmwareSource — firmware đang dùng đến từ đâu

Thẻ nguồn firmware trong vùng Setting và debug bundle cần cùng một mô tả: CI artifact hay package, project nào, job/version nào, lấy từ cache hay vừa tải. `FirmwareSource` (core) chứa đúng các chuỗi đó; `DebugContext.source` giữ bản dict và bundle có thêm `source.json` (đã che token như mọi file khác), vì câu hỏi đầu tiên khi debug luôn là "đã flash bản nào".

### Thay đổi

- **`wflash/core/firmware_source.py`** (mới): `FirmwareSource`, `files_note`, `short_timestamp`.
- **`wflash/core/debug_bundle.py`**: field `DebugContext.source`, file `source.json` trong bundle.
- **`tests/test_firmware_source.py`** (mới, 3 test), **`tests/test_debug_bundle.py`** (thêm `source.json` vào danh sách file, thêm 2 test).

### Đã kiểm tra

- RED / GREEN, `pytest -q`: RED: `ModuleNotFoundError: No module named 'wflash.core.firmware_source'`; GREEN: `11 passed in 0.11s`; `pytest -q`: `233 passed in 13.67s`.

## Phase 1.29: AppSettings cho popup GitLab, TLS và theme

Popup Load from GitLab và Preferences cần nhớ thêm: có kiểm tra chứng chỉ TLS không, dark mode, project CI người dùng sửa (nhớ theo từng profile), tên job, project và tên package. Cơ chế kiểm kiểu khi load được giữ và mở rộng cho `dict`: chỉ nhận dict str→str, sai thì về mặc định kèm warning — một file settings hỏng không được làm app chết. Cache package nằm trong `<cache_dir>/packages`.

### Thay đổi

- **`wflash/core/settings.py`**: 6 field mới, `_same_type` kiểm cả dict, `PACKAGES_SUBDIR`, `resolved_package_cache_dir()`.
- **`tests/test_settings.py`**: thêm 9 test (mặc định, round-trip, dict không dùng chung, dict sai kiểu, bool sai kiểu, thư mục cache package).

### Đã kiểm tra

- RED / GREEN, `pytest -q`: RED: `9 failed, 10 passed` (`AttributeError` cho field mới); GREEN: `19 passed in 0.09s`; `pytest -q`: `242 passed in 13.91s`.

## Phase 1.30: Cache cho file package (store_file) và cache chỉ đụng thư mục của nó

Package Registry có thể trả về một file không phải zip; `store_file` đặt nguyên file vào cache với cùng cơ chế `.tmp` → rename → marker như artifact. Cache package nằm ở `<cache_dir>/packages`, nên `prune()` cũ (xóa mọi thư mục `*/*` không có marker) sẽ xóa luôn cache package mỗi lần lưu một artifact. Giờ `entries/prune/clear` chỉ nhìn thư mục tên toàn chữ số. `has()` cho nhãn "Cached" mà không làm thay đổi thứ tự LRU.

### Thay đổi

- **`wflash/core/artifact_cache.py`**: `store_file`, `has`, `_store` dùng chung, `_project_dirs` chỉ thư mục số.
- **`tests/test_artifact_cache.py`**: thêm 4 test (file đơn, lỗi copy, `has` không chạm marker, prune không đụng `packages/`).

### Đã kiểm tra

- RED / GREEN, `pytest -q`: RED: `4 failed, 11 passed` (thiếu `store_file`/`has`); GREEN: `15 passed in 0.06s`; `pytest -q`: `246 passed in 13.30s`.

## Phase 1.31: GitLabClient — Package Registry và tùy chọn tắt kiểm tra TLS

Tab Package Registry làm giống SFlash: package generic, mỗi version có file đính kèm, tải file đầu tiên. Client vẫn dùng `requests` với phân loại lỗi và phân trang `X-Next-Page` sẵn có; API lọc tên package theo tiền tố nên client chỉ giữ đúng tên. Phần stream xuống đĩa (`.part`, hủy, lỗi ổ đĩa) được dùng chung cho artifact và package. Tên file server trả về được làm sạch để không ghi ra ngoài thư mục tải. `verify=False` là lựa chọn rõ ràng của người dùng (popup ghi WARNING), nên cảnh báo urllib3 mỗi request được tắt. Các hint nhắc "Settings" giờ trỏ tới "Load from GitLab…".

### Thay đổi

- **`wflash/core/gitlab_client.py`**: `verify`, `PackageVersion`, `list_package_versions`, `download_package`, `_stream`, `_safe_file_name`, hint mới.
- **`wflash/core/errors.py`**: hint mặc định của `GitLabError`.
- **`tests/test_gitlab_client.py`**: thêm 12 test (TLS, lọc đúng tên, phân trang tới limit, không có version, file đầu tiên, quote URL, không ghi ra ngoài, không có file, hủy, lỗi ổ đĩa, mất kết nối).

### Đã kiểm tra

- RED / GREEN, `pytest -q`: RED: `ImportError: cannot import name 'PackageVersion'`; GREEN: `31 passed in 0.20s`; `pytest -q`: `258 passed in 13.05s`.

## Phase 1.32: firmware_fetch — logic tìm/tải firmware nằm ở core

Popup GitLab chỉ nên lo giao diện; phần "job mới nhất thành công khớp ref + job name", "liệt kê job của các pipeline gần nhất", "tải qua cache rồi mô tả nguồn" là logic thuần, đặt ở core để test không cần Qt hay mạng. Nhiều job khớp mà không có tên job là lỗi có hint, không bao giờ tự chọn (CLAUDE.md: chọn sai file là điều tệ nhất tool có thể làm). Package zip được giải nén, file khác được giữ nguyên.

### Thay đổi

- **`wflash/core/firmware_fetch.py`** (mới): `JobRow`, `browse_jobs`, `find_latest_job`, `fetch_ci_artifact`, `latest_package`, `fetch_package`, `count_files`.
- **`tests/test_firmware_fetch.py`** (mới): 11 test với client giả.

### Đã kiểm tra

- RED / GREEN, `pytest -q`, `pytest -k "not gui" -q`: RED: `ModuleNotFoundError: No module named 'wflash.core.firmware_fetch'`; GREEN: `11 passed in 0.26s`; `pytest -q`: `269 passed in 13.13s`; `grep PySide6 wflash/core/firmware_fetch.py`: không có.

## Phase 1.33: WorkerRegistry chờ/bỏ theo tiền tố key

Popup GitLab dùng chung `WorkerRegistry` của cửa sổ chính. Khi đóng popup, nó phải chờ (có giới hạn, vẫn bơm event — quy tắc 3) đúng các worker `gitlab-` của nó, không chờ worker liệt kê instance winIDEA, và khi hết giờ chỉ được "bỏ" (park trong `_ABANDONED`, quy tắc 1) worker của nó. Không truyền tiền tố thì hành vi y như cũ, nên `closeEvent` của cửa sổ chính không đổi.

### Thay đổi

- **`wflash/gui/workers.py`**: tham số `prefix` cho `wait_idle` và `abandon_running`.
- **`tests/test_gui_workers.py`**: thêm `test_thread_wait_idle_with_prefix_ignores_other_workers`, `test_thread_abandon_with_prefix_parks_only_matching_workers`.

### Đã kiểm tra

- RED / GREEN, `pytest -k thread -v`, `pytest -q`: RED: `2 failed, 13 passed` (`wait_idle`/`abandon_running` chưa nhận `prefix`); GREEN: `15 passed in 0.69s`; `pytest -k thread -q`: `31 passed, 240 deselected`; `pytest -q`: `271 passed in 13.33s`.

## Phase 1.34: Theme Teal sáng/tối

WFlash dùng bố cục quen thuộc của SFlash nhưng phải khác màu để không nhầm hai tool: Teal. Màu tĩnh nằm trong hai file `.qss` (chọn widget theo objectName và dynamic property như `state="flashing"`); màu do code tô lúc chạy (dòng log, dòng mapping đỏ, cột `#`) lấy từ cùng bảng token `theme.py`. Thiếu file theme thì app chạy với style mặc định của Qt và ghi WARNING, không crash. `main.py` áp theme đã lưu trước khi tạo cửa sổ để lần vẽ đầu đã đúng màu. Chữ trắng trên màu primary và cancel đạt ≥ 4.5:1 ở cả hai chế độ (có test).

### Thay đổi

- **`wflash/gui/theme.py`**, **`wflash/gui/style.py`**, **`wflash/resources/style.qss`**, **`wflash/resources/style_dark.qss`** (mới).
- **`wflash/gui/log_panel.py`**: màu log theo theme, `refresh_log_theme()`.
- **`wflash/main.py`**: áp theme lúc khởi động, log `Theme: …`.
- **`pyproject.toml`**: package-data cho `.qss`.
- **`tests/test_gui_theme.py`** (mới, 9 test), **`tests/test_gui_root_main.py`** (smoke ở dark mode với HOME tạm).

### Đã kiểm tra

- RED / GREEN, `pytest -q`: RED: `ImportError: cannot import name 'style' from 'wflash.gui'`; GREEN: `12 passed in 6.61s` (theme + root main, gồm smoke dark mode); `pytest -q`: `281 passed in 16.17s`.

## Phase 1.35: Hộp thoại Preferences

Settings cũ bị tách làm hai: phần kết nối GitLab (URL, token, TLS, CA) chuyển sang popup Load from GitLab, phần còn lại thành Preferences: thư mục cache + số bản giữ lại + Clear cache (giờ xóa cả cache package), thư mục profile, verbose và Dark mode. Layout trong `preferences_dialog.ui`; Python chỉ nạp giá trị, kiểm tra thư mục profile có tồn tại và trả về bản sao `AppSettings`. `SettingsDialog` cũ còn đến Task 12.

### Thay đổi

- **`wflash/gui/preferences_dialog.ui`** (mới) + **`ui_preferences_dialog.py`** (sinh bằng `pyside6-uic`).
- **`wflash/gui/preferences_dialog.py`** (mới): `PreferencesDialog`.
- **`tests/test_gui_preferences_dialog.py`** (mới, 6 test), **`tests/test_gui_ui_files.py`** (thêm file `.ui` mới).

### Đã kiểm tra

- RED / GREEN, `pytest -q`: RED: `ModuleNotFoundError: No module named 'wflash.gui.preferences_dialog'`; GREEN: `14 passed in 0.78s`; `pytest -q`: `289 passed in 16.43s`.

## Phase 1.36: File Designer cho popup Load from GitLab

Popup GitLab theo CLAUDE.md là Designer trước: khung GitLab Connection (URL, token, Verify TLS, CA bundle, ghi chú scope `read_api`), hai tab CI Artifact và Package Registry, thanh tải + trạng thái + Stop, ô GitLab log và nút Cancel. Mọi widget/layout có tên `<loại>_<ý nghĩa>`; chỉ các dòng của hai bảng (và nút Download từng dòng) sẽ dựng bằng Python ở task sau.

### Thay đổi

- **`wflash/gui/gitlab_dialog.ui`** (mới) + **`ui_gitlab_dialog.py`** (sinh bằng `pyside6-uic`).
- **`tests/test_gui_ui_files.py`**: kiểm tên, đồng bộ file sinh, số cột hai bảng, hai tab, Verify TLS bật sẵn.

### Đã kiểm tra

- RED / GREEN, `pytest -q`: RED: `4 failed, 6 passed` (thiếu `gitlab_dialog.ui` / `ui_gitlab_dialog`); GREEN: `10 passed in 0.68s`; `pytest -q`: `291 passed in 16.54s`.

## Phase 1.37: Popup Load from GitLab (CI Artifact + Package Registry)

Logic duyệt/tải GitLab rời khỏi cửa sổ chính sang một dialog modal giống SFlash. Dialog dùng `WorkerRegistry` của cửa sổ chính (key `gitlab-`), giữ đủ 8 quy tắc threading: slot luôn là bound method, `_generation` tăng *trước* mọi lần hủy (Stop, đóng dialog, đóng cửa sổ) nên kết quả đã xếp hàng bị bỏ, đóng dialog chờ có giới hạn và bơm event (chỉ worker `gitlab-`), quá giờ thì "bỏ" worker thay vì treo. Tải qua `firmware_fetch` (core) nên cache và mô tả nguồn giống nhau cho CI và package. Token chỉ vào keyring; log riêng của dialog đi qua `redact()` và logger `wflash.gitlab`. Tắt Verify TLS được phép nhưng ghi WARNING một lần mỗi phiên. Tải xong dialog phát `firmwareReady(path, source)` rồi tự đóng.

### Thay đổi

- **`wflash/gui/gitlab_dialog.py`** (mới): `GitlabDialog`, `default_client_factory` (chuyển từ `gitlab_browser.py`, thêm `verify`), `byte_progress`, `warn_tls_disabled_once`.
- **`tests/gui_stubs.py`**: endpoint Package Registry giả, `patch_keyring`, `SOURCE`, `HostWindow._save_settings/on_firmware_ready`.
- **`tests/test_gui_gitlab_dialog.py`** (mới): 25 test, trong đó 5 test `thread`.

### Đã kiểm tra

- RED / GREEN, `pytest -k thread -v`, `pytest -q`: RED: `ImportError: cannot import name 'gitlab_dialog' from 'wflash.gui'`; GREEN: `25 passed in 2.69s`; `pytest -k thread -q`: `36 passed, 280 deselected`; `pytest -q`: `316 passed in 18.55s`.

## Phase 1.38: Cửa sổ chính mới — một cửa sổ, nút Flash/Cancel, vùng Setting, tab Information

Cửa sổ chính chuyển sang bố cục SFlash (spec redesign §2): phần đầu có nút Flash 90×70 — khi đang flash chính nút đó thành Cancel màu đỏ (dynamic property `state="flashing"`, màu từ QSS), thanh tiến trình không chữ, nhãn `phần trăm | ETA | Speed` từ `ProgressEstimator`, nhãn `Step: …`. Bên trái là vùng Setting rộng 360 px (profile, Load from GitLab… với thẻ nguồn firmware, instance winIDEA, Reset/Run, Preferences…), bên phải bảng mapping có cột `#` và dòng gợi ý; dưới cùng chỉ một tab Information; thanh trạng thái ghi version và tác giả. `GitlabBrowserMixin` và `SettingsDialog` bị xóa trong cùng commit với các test thay thế. Cửa sổ giữ một `GitlabDialog` suốt đời; `closeEvent` hạ cờ của dialog trước khi hủy worker (quy tắc 4) rồi mới đóng nó.

### Thay đổi

- **`wflash/gui/main_window.ui`** (viết lại) + **`ui_main_window.py`** (sinh lại).
- **`wflash/gui/main_window.py`**: 3 mixin, popup GitLab, Preferences, `apply_dark_mode`, status bar, `closeEvent` có dialog.
- **`wflash/gui/mapping_table.py`**: `on_firmware_ready`, cột `#`, thẻ nguồn, gợi ý, màu dòng đỏ theo theme.
- **`wflash/gui/flash_mixin.py`**: một nút Flash/Cancel, ETA/Speed, `Step: …`, màu thanh theo trạng thái.
- **`wflash/__init__.py`**: `APP_AUTHOR`.
- Xóa **`wflash/gui/gitlab_browser.py`**, **`wflash/gui/settings_dialog.*`**, **`wflash/gui/ui_settings_dialog.py`**, **`tests/test_gui_gitlab_browser.py`**, **`tests/test_gui_settings_dialog.py`**.
- Test viết lại: **`test_gui_ui_files.py`**, **`test_gui_mapping_table.py`**, **`test_gui_flash.py`**, **`test_gui_main_window.py`**, **`test_gui_close_window.py`**; **`tests/gui_stubs.py`** bỏ `on_artifact_ready`.

### Đã kiểm tra

- RED / GREEN, `pytest -k thread -v`, `pytest -q`, smoke `--adapter fake --smoke`: RED: 3 lỗi collection (`HINT_COMPLETE`, `program_bytes`, `APP_AUTHOR` chưa có); GREEN: 5 file test GUI `56 passed in 7.97s`; `pytest -k thread -q`: `38 passed, 266 deselected`; `pytest -q`: `304 passed in 18.64s`; smoke `--adapter fake --smoke`: exit 0. `tools/stress_test.py` chưa chạy được cho tới Task 13 (vẫn gọi GitLab browser cũ).
- `tools/stress_test.py` chưa chạy được (còn gọi GitLab browser cũ) — sửa ở Phase 1.39, chưa push.

## Phase 1.39: Stress test đi qua popup GitLab, thêm package và theme

Stress test phải chạy đúng đường người dùng: GitLab giờ nằm trong popup. Section `gitlab` mở popup, nạp ref, liệt kê job, tải (và tải lại từ cache), thử 401/403/404/mất kết nối, double-click, Stop (popup vẫn mở), đóng popup giữa lúc tải và đóng cửa sổ giữa lúc fetch/tải ở nhiều độ trễ; thêm Package Registry (bản mới nhất là zip, bản cũ là file thường để lại dòng đỏ). Section mới `theme` đổi sáng/tối ba lần khi đang flash và một lần khi popup mở. `secrets` kiểm thêm token gõ trong popup chỉ vào keyring giả, không vào `settings.json`, và log của popup đã che token. Keyring thật không bao giờ bị chạm.

### Thay đổi

- **`tools/stress_test.py`**: helper đi qua `GitlabDialog`, section `gitlab` viết lại, section `theme` mới, `secrets` mở rộng, keyring giả.

### Đã kiểm tra

- Trước khi sửa: `STRESS_RESULT=FAIL` (`refresh_gitlab` không còn). Sau khi sửa, `--list`, chạy đủ, `pytest -k thread -v`, `pytest -q`: RED: stress test cũ `CHECKPOINTS=17 FAILED=4 … STRESS_RESULT=FAIL` (thiếu `refresh_gitlab` / `on_artifact_ready`); GREEN: `--list` in 6 section; `CHECKPOINTS=348 FAILED=0 QT_THREADING_WARNINGS=0 OTHER_QT_WARNINGS=48 TIME=24.6s`, `STRESS_RESULT=PASS`; `pytest -k thread -q`: `38 passed, 266 deselected`; `pytest -q`: `304 passed in 18.68s`.

## Phase 1.40: Đóng gói theme và cập nhật README

Bản `.exe` phải mang theo hai file theme; `style.py` tìm chúng theo vị trí package nên spec PyInstaller chép `wflash/resources` vào đúng chỗ tương ứng. README mô tả giao diện mới (một cửa sổ, popup Load from GitLab với CI Artifact và Package Registry, Preferences, theme), cách cấu hình TLS/CA, và các file Designer cần sinh lại.

### Thay đổi

- **`wflash.spec`**: thêm `("wflash/resources", "wflash/resources")` vào `datas`.
- **`README.md`**: cấu hình, giao diện, quy trình mới, log/bundle (`source.json`), phát triển (3 file `.ui`, theme).
- **`tests/test_packaging.py`** (mới): 2 test.

### Đã kiểm tra

- RED / GREEN, `pytest -q`, `pytest -k thread -v`, `pytest -k "not gui" -q`, `tools/stress_test.py`, smoke sáng và tối: RED: `1 failed, 1 passed` (spec chưa chép `wflash/resources`); GREEN: `2 passed`; `pytest -q`: `306 passed in 18.69s`; `-k thread`: `38 passed`; `-k "not gui"`: `173 passed`; stress: `CHECKPOINTS=348 FAILED=0 QT_THREADING_WARNINGS=0`, `STRESS_RESULT=PASS`; smoke light exit 0; smoke dark (HOME tạm) exit 0 và log `wflash.main: Theme: dark`.

## Phase 1.41: Sửa popup Load from GitLab bị ép dòng Project/Branch/Job

User chạy app trên macOS và thấy trong tab CI Artifact các ô Project, Branch/tag, Job name bị ép dẹt, nút "Load branches/tags" mất chữ. Nguyên nhân gốc: `gitlab_dialog.ui` đặt cứng `minimumSize` 760×600 và kích thước mặc định 880×720. Qt chỉ tự áp chiều cao tối thiểu của layout cho cửa sổ **không** có `minimumSize` đặt tay; với style native của macOS các ô cao hơn nên layout cần 820 px, nhưng popup vẫn mở 720 px và layout phải ép các dòng xuống 13 px (bảng job và ô log giữ chiều cao cố định). Ở chế độ offscreen (style Fusion) layout chỉ cần 711 px nên test GUI không thấy lỗi. Sửa ở nguồn: bỏ `minimumSize` trong `.ui` để layout tự quyết chiều cao tối thiểu (popup tự mở 820 px trên macOS), và thêm test chặn kiểu lỗi này cho cả ba cửa sổ.

### Thay đổi

- **`wflash/gui/gitlab_dialog.ui`**: bỏ thuộc tính `minimumSize` 760×600; **`wflash/gui/ui_gitlab_dialog.py`** sinh lại bằng `pyside6-uic`.
- **`tests/test_gui_window_min_size.py`** (mới): mỗi cửa sổ (popup GitLab, Preferences, cửa sổ chính) phải có `minimumSize` và chiều cao thực tế không nhỏ hơn `layout().minimumSize()`.

### Đã kiểm tra

- Tái hiện với style native macOS: trước khi sửa `lineEdit_ciProject`/`comboBox_ref`/`comboBox_jobName` cao 13 px, popup 880×720 trong khi layout cần 820; sau khi sửa các dòng cao 27–29 px, popup tự mở 880×820 (đã xem ảnh chụp).
- RED: `tests/test_gui_window_min_size.py` → `1 failed, 2 passed` (`assert 600 >= 680` ở gitlab_dialog); GREEN: `3 passed`.
- `pytest -q`: 309 passed; `pytest -k thread -q`: 38 passed; `tools/stress_test.py`: `STRESS_RESULT=PASS`.

## Phase 1.42: Hướng dẫn thử nghiệm trên Windows

Adapter winIDEA thật chỉ viết được sau khi có kết quả chạy trên máy Windows có winIDEA 9.21 và ECU SAF85xx. Gom mọi việc user cần làm ở đó vào một file duy nhất, theo thứ tự: chuẩn bị venv, cài `isystem.connect` từ thư mục winIDEA và kiểm tra version/bitness, ghi tay tên entry download/Application và thiết bị Winbond, chạy spike 01–05 (kèm thử dừng download giữa chừng để quyết định cách xử lý Cancel), test tự động + stress test, GitLab thật (CI Artifact và Package Registry), build `.exe`, rồi đóng gói kết quả theo checklist.

### Thay đổi

- **`docs/windows_test_guide.md`** (mới): hướng dẫn từng bước, ghi rõ bước nào flash/reset ECU, checklist file cần gửi.
- **`README.md`**: trỏ tới hướng dẫn.
- **`.gitignore`**: bỏ qua `test_results/` (thư mục kết quả user tạo trên Windows).

### Đã kiểm tra

- Đối chiếu tham số trong hướng dẫn với `spike/0*.py` (`--instance`, `--workspace`, `--url`, `--new-path`, `--facade`, `--run`), `scripts/build_windows.bat`, `tools/stress_test.py` và nhãn `Export debug bundle…` trong `main_window.ui`. Chỉ thay tài liệu, không đổi code nên không chạy lại test.

## Phase 1.43: Môi trường Windows bằng conda (Miniforge)

User muốn dùng conda Miniforge thay cho venv trên Windows. Hướng dẫn thử nghiệm chuyển Phần 0 sang Miniforge: cài Miniforge, chọn version Python theo tag `cpXY` của wheel `isystem.connect` trong thư mục winIDEA (wheel có thể chỉ build cho vài version Python, conda cho chọn đúng version dễ hơn venv), tạo env `wflash`, cài thư viện bằng `pip` (không trộn Qt từ conda với PySide6 từ pip). Script build trước đây luôn tự tạo venv riêng nên sẽ bỏ qua env conda và không thấy `isystem.connect` đã cài; giờ nó dùng Python của env conda đang active (`CONDA_PREFIX`), từ chối chạy trong `base`, và vẫn dùng venv cũ khi không có conda.

### Thay đổi

- **`docs/windows_test_guide.md`**: Phần 0 viết lại cho Miniforge (0.1 cài, 0.2 chọn version Python, 0.3 tạo env); thêm cách xử lý lỗi `not a supported wheel`.
- **`scripts/build_windows.bat`**: ưu tiên env conda đang active, chặn `base`, fallback venv; chuyển sang CRLF vì script giờ dùng nhãn `goto`.
- **`.gitattributes`** (mới): `*.bat` luôn CRLF.
- **`README.md`**: thêm cách cài bằng conda.

### Đã kiểm tra

- Đọc lại luồng `goto` của script (không dùng biến được gán trong cùng khối ngoặc, tránh lỗi mở rộng biến lúc parse của `cmd`); file đã là CRLF. Chưa chạy được trên Windows từ máy macOS: sẽ được kiểm tra ở Phần 6 của hướng dẫn.

## Phase 1.44: Kết quả spike vòng 1 trên Windows và chuẩn bị vòng 2

User chạy spike 01–05 trên Windows 11 với winIDEA 9.21.408 và workspace SAF85xx thật. Kết quả ghi vào `docs/winidea_api_notes.md`, file này không còn trống. Ba phát hiện làm thay đổi thiết kế:

- File `.s3` **không** nằm trong danh sách download của Debug mà trong danh sách Download Files của thiết bị external flash (Winbond W25Q64JW, cấu hình UMI, phần HServer của workspace). Mỗi dòng chỉ có path, offset và ô tick, **không có tên**. Vì vậy profile không thể khớp entry `.s3` theo tên như thiết kế ban đầu (`winidea_entry`).
- Đọc path symbol file chạy được qua `/IDE/System.Debug.Applications[i].SymbolFiles.File[j].Path`. Workspace có 3 Application `App_M7`, `App_BBE`, `App_A53`, và một Application có thể có nhiều symbol file.
- `isystem.connect` là 9.26.11, còn winIDEA là 9.21.408. Mọi thao tác vẫn chạy, nhưng lệch version. Instance có id rỗng.

Ngoài ra: `CLoaderController.download()` chạy 6–8 s, sau đó CPU ở trạng thái `isMustInit`. `CDebugFacade.reset()` cho `isStopped=1` (không phải `isHalted`), và `run()` cho `isRunning=1`. Bước 03 vòng 1 truyền đường dẫn file vào `--url` nên việc ghi path chưa được kiểm chứng. Thêm `spike/06_probe_umi.py` (chỉ đọc) để dò URL và class của danh sách file Winbond. Thêm mục "Vòng 2" vào hướng dẫn thử nghiệm. Plan 2 chưa viết, vì cách đọc/ghi danh sách `.s3` quyết định lại cách profile khớp entry.

### Thay đổi

- **`docs/winidea_api_notes.md`**: ghi môi trường, API, URL đã chạy và đã lỗi, trạng thái CPU, câu hỏi mở.
- **`spike/06_probe_umi.py`** (mới): dump chữ ký `CUMIController`/storage/loader/option class; thử `getOptionJSON`/`getOptionStr` với các tiền tố `/iOPEN/`, `/HServer/`… cho `UMI1.Devices.Devices[0].DownloadFiles`; dump JSON cây `Applications`; đọc danh sách download của `CLoaderController`.
- **`spike/README.md`**: thêm bước 06.
- **`docs/windows_test_guide.md`**: mục "Vòng 2" (V2.1–V2.6).

### Đã kiểm tra

- Đọc toàn bộ `results.7z` (00_env, 01, 02, 03, 3 lần 04, 2 lần 05, 4 ảnh chụp; `00_manual.txt` trống). `python -m py_compile spike/06_probe_umi.py` thành công. Script 06 chưa chạy được trên macOS (cần winIDEA).

## Phase 1.45: Kết quả spike vòng 2, chuẩn bị vòng 3 (ghi path và program Winbond)

Vòng 2 tìm được URL đọc danh sách file của Winbond: `/iOPEN/UMIConfig.Devices.Devices[0].DownloadFiles[i].Path`. Phần `HServerData.HW.BDM.UMIConfig` trong XML workspace tương ứng với gốc option `/iOPEN/UMIConfig`. Docstring của `CUMIController.write(deviceIndex, programMode)` cho biết nó "ghi các file đã cấu hình vào thiết bị", tức là bằng nút Program. `CLoaderController.download()` đã bị đánh dấu deprecated, và docstring nói nó nạp *Program Files* của SoC rồi reset target. Ngoài ra có hai phát hiện quan trọng cho adapter:

- `getOptionJSON` trên cả cây `Applications` làm winIDEA ngừng trả lời. Mọi lệnh sau đó đều lỗi `ICONNECT_E_ROUTING`, vì vậy adapter chỉ được đọc từng option đơn.
- Đọc chỉ số vượt danh sách cho lỗi riêng: "Array index (1) out of range (1)". `optionExists` trả `False`, nên dùng được để đếm số dòng.

Bước 03 vòng 2 dùng `File[1]` nhưng workspace mới chỉ có một symbol file, nên vẫn chưa ghi được path. Thêm spike 07 (chỉ đọc: đếm dòng, field offset/tick, tên thiết bị, hằng số `wProgDevice`, docstring đầy đủ, `CSessionCtrl`) và spike 08 (program Winbond bằng `CUMIController.write`, hỏi `YES` trước khi ghi, không đoán hằng số). Thêm mục "Vòng 3" vào hướng dẫn.

### Thay đổi

- **`docs/winidea_api_notes.md`**: mục "Round 2 findings": URL `/iOPEN/UMIConfig...`, lỗi out-of-range, hazard `getOptionJSON`, chữ ký UMI/storage/loader.
- **`spike/07_umi_details.py`**, **`spike/08_umi_program.py`** (mới).
- **`spike/README.md`**: thêm 07, 08 và cảnh báo về 06.
- **`docs/windows_test_guide.md`**: mục "Vòng 3" (V3.1–V3.5).

### Đã kiểm tra

- Đọc toàn bộ `06_probe_umi_20261010_140822.txt` và `03_set_paths_20261010_141112.txt`. `py_compile` cho 07 và 08 thành công. Hai script chưa chạy được trên macOS (cần winIDEA).

## Phase 1.46: Kết quả spike 07 và 08, sửa cách 08 chọn thiết bị

Spike 07 cho biết danh sách file của Winbond có 3 dòng, đếm được bằng `getDynamicOptionSize`, và mỗi dòng có các field `Path`, `Offset`, `Enabled`, `Type`. Thiết bị có `Device='W25Q64JW'`, `Enabled='true'`, `ProgramAtDownload='true'` nhưng `Name` rỗng. Vì vậy `getDeviceNames` trả về danh sách trống và spike 08 dừng trước `umi.write`, chưa ghi gì vào flash. Đây là lỗi của script: nó giả định thiết bị luôn có tên, trong khi `CUMIController.write` nhận chỉ số thiết bị. Sửa 08 để dùng `--device-index` (mặc định 0) khi không có tên, và từ chối ghi nếu thiết bị ở chỉ số đó không bật hoặc không đúng model `--expect-device`. Docstring còn cho thấy `write` có overload nhận trực tiếp đường dẫn file, có thể giúp program mà không phải đổi path trong workspace; hướng này chưa được thử.

### Thay đổi

- **`spike/08_umi_program.py`**: chọn thiết bị theo chỉ số khi không có tên, kiểm tra model và trạng thái bật, liệt kê `Enabled`/`Offset`/`Path` từng dòng trước khi hỏi `YES`.
- **`docs/winidea_api_notes.md`**: mục "Round 3 findings".
- **`docs/windows_test_guide.md`**: mục "Bổ sung vòng 3".

### Đã kiểm tra

- Đọc `07_umi_details_20261107_112142.txt` và `08_umi_program_20261107_112400.txt`.
- Chạy 08 với một module `isystem.connect` giả: đúng model thì gọi `write(0, wProgDevice)`; sai model thì dừng; không gõ `YES` thì không ghi. Chưa chạy với winIDEA thật.

## Phase 1.47: Program Winbond qua API đã chạy, câu hỏi về pha ERASING thứ hai

User chạy 03 và 08 trên ECU thật. Ghi path `.s3` và `.elf` đều chạy, đọc lại đúng và khôi phục đúng. `CUMIController.write(0, wProgDevice)` trả về sau 117,4 s, không lỗi. User thấy trong Output có một lần ERASING nữa sau khi flash xong `.s3`. Log cho thấy mỗi dòng đang tick có một lượt erase + program riêng, theo thứ tự dòng. Số sector khớp chính xác với sector 64 KB (79 cho `.s3`, 1 cho CAL). Vì vậy CAL nằm chung sector `0x7F0000` với 4 đoạn cuối của `.s3`. Log không cho biết pha erase thứ hai xóa bao nhiêu, nên chưa thể nói flash có đúng không. Thêm spike 09 đọc lại flash và so với file, thay vì đoán.

Hai ghi chú trước đây bị sửa lại theo dữ liệu mới. `getDeviceNames` lần này trả về `Winbond W25Q64JW SPI` nên `Name` rỗng không phải nguyên nhân của danh sách trống lần trước; nguyên nhân chưa rõ. User xác nhận winIDEA không treo khi chạy 06, nên sau `getOptionJSON` chỉ có kết nối bị mất. Phạm vi do user chốt: chỉ thay dòng 1 (`.s3`), giữ nguyên dòng 2 (CAL), và chỉ đổi ELF của `App_M7`.

### Thay đổi

- **`spike/09_flash_compare.py`** (mới): phân tích S-record của các dòng đang tick, đọc flash bằng `umi.read`, báo số byte khác và số byte khác mà flash là `0xFF` theo từng đoạn.
- **`docs/winidea_api_notes.md`**: mục "Round 3 program run"; sửa ghi chú về `getDeviceNames` và `getOptionJSON`.
- **`spike/README.md`**, **`docs/windows_test_guide.md`**: thêm 09 và mục "Vòng 4".

### Đã kiểm tra

- Tính số sector từ 20 chunk trong log: 64 KB cho 79 và 1, khớp log; 32 KB cho 148 và 1; 4 KB cho 1120 và 3.
- Chạy 09 với module `isystem.connect` giả và file `.s3` tự tạo: đoạn còn nguyên báo `MATCH`, đoạn bị xóa báo `DIFFERENT wrong=16 wrong_and_0xFF=16`. `umi.read` thật và kiểu vector thật chưa được kiểm chứng.

## Phase 1.48: Sự cố: spike 08 làm ECU không chạy được

User báo sau khi chạy `08_umi_program.py` với 2 file đang tick (`RAD_SUZ05_FFI.s3` và CAL `.sre`), chip bị xóa hết và ECU không chạy được. Log có 2 pha ERASING, khớp với giả thuyết `write()` xóa toàn chip trước mỗi file; việc này chưa được xác nhận bằng cách đọc lại flash. Script đã được viết với giả định `write()` giống nút Program và chỉ thử trên module giả, nên không phát hiện được rủi ro này trước khi ghi lên ECU thật. Thêm chốt chặn: 08 từ chối chạy nếu số dòng đang tick khác 1. Gỡ các bước bấm Program và chạy 08 khỏi Vòng 4. Plan 2 không được dùng `umi.write(index, mode)` với nhiều dòng.

### Thay đổi

- **`spike/08_umi_program.py`**: dừng trước khi ghi nếu số dòng tick khác 1.
- **`docs/windows_test_guide.md`**, **`spike/README.md`**, **`docs/winidea_api_notes.md`**: ghi sự cố, cảnh báo, thay Vòng 4.

### Đã kiểm tra

- Chạy 08 với module giả : 2 dòng tick và 0 dòng tick đều dừng trước khi ghi, 1 dòng tick mới gọi `write`. Chưa chạy với winIDEA thật. ECU chưa được khôi phục tại thời điểm ghi.

## Phase 1.49: Sửa spike 09: umi.read cần vector có sẵn kích thước

Lần chạy 09 đầu tiên trên máy thật báo `Vector size is too small!` ở mọi đoạn, nên chưa so được gì. Không có gì bị ghi. Script truyền vector rỗng, còn module giả trước đây chấp nhận vector rỗng nên không phát hiện được. Phần phân tích file thì đúng: 20 đoạn của `.s3` trùng địa chỉ với 20 chunk trong Output.

### Thay đổi

- **`spike/09_flash_compare.py`**: tạo vector đúng kích thước trước khi gọi `read`.
- **`docs/winidea_api_notes.md`**: ghi yêu cầu của `umi.read`.

### Đã kiểm tra

- Module giả sửa lại để báo lỗi giống máy thật khi vector quá nhỏ: bản cũ tái hiện đúng lỗi, bản mới so được và báo đúng `MATCH`/`DIFFERENT`. Chưa chạy lại trên winIDEA thật.

## Phase 1.50: ECU đã khôi phục; Program bằng tay khác umi.write

User khôi phục được ECU bằng *Hardware → Winbond → Program*, không đổi file, 2 dòng vẫn tick, và xác nhận chỉ có 1 lần erase. Như vậy `umi.write(index, mode)` không tương đương nút Program khi có nhiều dòng tick; đây là giả định sai đã dẫn tới sự cố. Cảnh báo tránh dùng menu Program trong hướng dẫn được gỡ. Spike 09 `--full` trông như bị treo ở đoạn đầu 1,4 MB vì không in gì khi đang đọc; chưa biết là treo thật hay đọc chậm, nên thêm tiến độ và tốc độ đọc.

### Thay đổi

- **`spike/09_flash_compare.py`**: in dòng bắt đầu đọc, tiến độ mỗi 5 s kèm tốc độ, và thời gian mỗi đoạn.
- **`docs/windows_test_guide.md`**: viết lại Vòng 4.
- **`docs/winidea_api_notes.md`**: mục "Manual Program differs from umi.write".

### Đã kiểm tra

- Chạy 09 với module giả, đọc chậm giả lập: in tiến độ, vẫn báo đúng `MATCH`/`DIFFERENT`. Chưa chạy lại trên winIDEA thật.

## Phase 1.51: Ảnh cấu hình Winbond giải thích sự cố

Ảnh hộp thoại Device của workspace `R_04_01_01` cho thấy "Mass erase before download" đang bật và "Verify after program" đang tắt. Giả thuyết hợp lý nhất, chưa chứng minh: `umi.write` áp dụng mass erase cho từng dòng đang tick, nên lần xóa trước file CAL đã xóa `.s3` vừa ghi, và winIDEA không báo gì vì không verify.

### Thay đổi

- **`docs/winidea_api_notes.md`**: ghi cấu hình thiết bị và giả thuyết.

### Đã kiểm tra

- Đối chiếu ảnh với log hai pha ERASING của lần chạy 08. Chỉ đổi tài liệu, không chạy lại test.

## Phase 1.52: umi.read nạp monitor vào target; spike 10 chỉ đọc tài liệu

Lần chạy 09 `--full` cuối cùng cũng kết thúc: không so được đoạn nào, đoạn đầu lỗi `UMI Monitor errCode=0x1`, các đoạn sau lỗi `Error loading monitor`. Vậy trước đây gọi 09 là "chỉ đọc" là chưa đủ: nó không ghi flash theo những gì biết được, nhưng có đụng target. Tạm dừng 09. Hướng tìm API tương đương nút Program chuyển sang đọc docstring và cấu trúc menu, không gọi lệnh nào tác động lên target.

### Thay đổi

- **`spike/10_program_api_docs.py`** (mới): in docstring các hàm liên quan (`invoke`, `serviceCall`, `flush`, `write`, `begin_program`...), hằng số `IConnectUMI`, cấu trúc menu.
- **`docs/windows_test_guide.md`**, **`spike/README.md`**, **`docs/winidea_api_notes.md`**: cảnh báo về 09, thay bằng 10.

### Đã kiểm tra

- Đọc `09_flash_compare_20261107_120935.txt`: 0 đoạn `MATCH`/`DIFFERENT`. Chạy 10 với module giả: in được docstring, hằng số và menu; không có lời gọi nào tới `invoke`, `write`, `flush`, `read`, `reset`. Chưa chạy trên winIDEA thật.

## Phase 1.53: Spike 10 chưa chỉ ra lệnh Program; thêm spike 11 tìm ví dụ

Spike 10 không tác động lên target. Nó ghi lại được hằng số `IConnectUMI` và cách dùng `invoke`, nhưng không có danh sách tên hàm dịch vụ, và `getMenuStructure` cần tham số chưa biết. Vì vậy chưa có bằng chứng cho lệnh nào tương đương nút Program, và chưa đề xuất lệnh ghi flash mới. Docstring nhắc tới các file ví dụ, nên thêm spike 11 tìm chúng trên máy.

### Thay đổi

- **`spike/11_find_examples.py`** (mới): quét thư mục winIDEA và package `isystem`, chép ví dụ vào `results/examples/`, liệt kê tài liệu. Không import `isystem.connect`.
- **`docs/winidea_api_notes.md`**, **`spike/README.md`**, **`docs/windows_test_guide.md`**: ghi kết quả 10, thêm 11.

### Đã kiểm tra

- Chạy 11 trên macOS với thư mục giả: chép `test_flush.py` (theo tên) và `mine.py` (theo từ khóa), bỏ qua `other.py`; liệt kê `sdk_python.pdf`, bỏ qua `readme.pdf`. Chưa chạy trên Windows.

## Phase 1.54: 09 lấy mẫu chạy được: Program tay giữ đủ hai file

Sau khi Program bằng tay, 09 bản lấy mẫu đọc được flash và mọi mẫu đều `MATCH`, kể cả các đoạn `.s3` nằm chung sector `0x7F0000` với CAL. Đây là mốc chuẩn cho một lần flash đúng, dù chỉ là lấy mẫu. Mỗi lần đọc mất khoảng 4,4 s bất kể kích thước, nên `--full` với khối 4 KB sẽ mất khoảng 80 phút; điều này hợp với việc nó trông như bị treo.

### Thay đổi

- **`docs/winidea_api_notes.md`**, **`docs/windows_test_guide.md`**: ghi kết quả và thời gian đọc.

### Đã kiểm tra

- Đọc `09_flash_compare_20261107_122743.txt`: toàn bộ mẫu `MATCH`, không có lỗi. Chỉ đổi tài liệu.

## Phase 1.55: Debug → Download chỉ xóa một lần; spike 12 thử begin_program

User bấm Debug → Download và gửi log: nạp cả hai file trước (`Device 'Program' feature`), rồi một pha ERASING và ghi 79 sector, ECU chạy bình thường. Đây là luồng tool cần tái tạo. Log không có lần chạy API nào nên chưa biết `download()` hay `begin_program()` có cùng trình tự không. Thêm spike 12 cho `begin_program`, vì tài liệu khuyên dùng nó thay `download()` đã deprecated và nói nó dừng target ở reset vector. Vòng 5 yêu cầu chạy 04 trước, rồi 12, mỗi lần lưu Output và kiểm tra lại.

### Thay đổi

- **`spike/12_begin_program.py`** (mới): hỏi `YES`, đo thời gian, in cấu hình và trạng thái trước/sau.
- **`docs/winidea_api_notes.md`**, **`spike/README.md`**, **`docs/windows_test_guide.md`**: ghi log và Vòng 5.

### Đã kiểm tra

- Chạy 12 với module giả: `--yes` gọi `begin_program`; không gõ `YES` thì không gọi. Chưa chạy với winIDEA thật.

## Phase 1.56: download() qua API chạy đúng như Debug → Download

Spike 04 trên ECU thật: 99 s, Output có một pha ERASING và 79 sector, giống hệt bấm tay; sau đó target đang dừng (`isStopped=1`); 09 cho 37/37 mẫu `MATCH`; user xác nhận ECU chạy sau khi bật lại nguồn. User cũng báo bước 12 (`begin_program`) không làm hỏng ECU, log sẽ gửi sau. Chưa thử flash một firmware khác qua API, nên `MATCH` chưa chứng minh nội dung mới được ghi; việc này cần kiểm tra khi có adapter thật.

### Thay đổi

- **`docs/winidea_api_notes.md`**: mục kết quả `download()`.

### Đã kiểm tra

- Đọc `v5_04_output.txt`, `04_download_20261107_124313.txt`, `09_flash_compare_20261107_124630.txt`. Chỉ đổi tài liệu.

## Phase 1.57: begin_program cũng đạt

Spike 12: 98,8 s, một pha ERASING, 79 sector, SoC vẫn `ATTACHED`, target dừng và giữ nguyên sau 2 s; 09 cho 37/37 mẫu `MATCH`; ECU chạy sau khi bật lại nguồn. Chọn `begin_program` làm lệnh flash cho adapter thật, vì `download()` đã deprecated. Hàm chạy chặn, không có callback tiến độ, nên Plan 2 phải quyết định lại cách làm Cancel.

### Thay đổi

- **`docs/winidea_api_notes.md`**: mục kết quả `begin_program`.

### Đã kiểm tra

- Đọc `v5_12_output.txt`, `12_begin_program_20261107_125053.txt`, `09_flash_compare_20261107_125753.txt` (37 `MATCH`, 0 `DIFFERENT`, 0 lỗi). Chỉ đổi tài liệu.

## Phase 1.58: Chốt quyết định cho Plan 2; spike 13 tìm option mass erase

User đồng ý: khớp `.s3` và ELF theo tên file, khóa Cancel từ lúc bắt đầu flash, so mẫu sau flash là tùy chọn mặc định tắt, lệch version chỉ cảnh báo. Python đi kèm winIDEA là 3.13.12 với `isystem.connect` 9.21.408.1. User muốn thêm checkbox "erase before download". Việc này đi ngược spec §1 (không cấu hình flash loader) và Approach A (chỉ đổi path), nên cần user chốt sau khi biết option có đọc/ghi được không. Tên option chưa biết; thêm spike 13 đọc file workspace để liệt kê field của thiết bị, rồi đọc từng field.

### Thay đổi

- **`spike/13_device_options.py`** (mới): chỉ đọc, chỉ dùng thư viện chuẩn.
- **`docs/winidea_api_notes.md`**, **`spike/README.md`**, **`docs/windows_test_guide.md`**: ghi quyết định và Vòng 6.

### Đã kiểm tra

- Chạy 13 với module giả và file `.xjrf` tự tạo: liệt kê đúng field, kể cả field lồng và phần tử danh sách; bỏ qua `DownloadFiles`; `setOption` và `getOptionJSON` không bị gọi. Cấu trúc XML thật mới được suy ra từ output spike 02. Chưa chạy trên winIDEA thật.

## Phase 1.59: Plan 2: adapter winIDEA thật

User bỏ yêu cầu checkbox mass erase: tùy chọn này theo cấu hình workspace, đúng với nguyên tắc chỉ đổi path. Viết Plan 2 dựa trên `docs/winidea_api_notes.md`. Quyết định thiết kế chính: dòng download và file symbol không có tên riêng nên adapter đặt tên theo file (`RAD_SUZ05_FFI.s3`, `App_M7/Radar_SUZ05_Gen7.elf`), nhờ vậy `FlashWorkflow` và schema profile gần như giữ nguyên; lập trình bằng `begin_program`; `connect` từ chối nếu winIDEA đang gắn với workspace khác, vì chưa chọn được instance theo id.

### Thay đổi

- **`docs/superpowers/plans/2026-11-07-wflash-real-adapter.md`** (mới): 7 task.
- **`docs/winidea_api_notes.md`**: ghi quyết định bỏ checkbox.

### Đã kiểm tra

- Đối chiếu plan với code: `MappingRow`, helper test `make_host` và `make.factory`, test cũ của `create_adapter("real")`. Chưa viết code adapter.

## Phase 2.1: Đọc file S-record và chọn mẫu so sánh

Bước đầu của Plan 2. Việc so flash sau khi ghi cần địa chỉ và nội dung của file `.s3`/`.sre`. Logic này tách khỏi winIDEA để test được trên macOS, chuyển từ spike 09 sang code chính.

### Thay đổi

- **`wflash/core/srec.py`** (mới): `parse_srec`, `sample_ranges`, `is_srec_file`.
- **`tests/test_srec.py`** (mới): 5 test.

### Đã kiểm tra

- RED rồi GREEN với `pytest tests/test_srec.py`.

## Phase 2.2: Adapter thật: danh sách instance và kết nối

`getInstanceId()` trên máy thật trả về chuỗi rỗng, nên id của instance là cổng TCP. `cmgr.connect()` gắn vào winIDEA mở gần nhất, nên sau khi kết nối phải so workspace với workspace đã chọn và từ chối nếu khác: flash nhầm ECU là lỗi tệ nhất của tool. `disconnect()` chỉ bỏ tham chiếu, vì `ConnectionMgr.disconnect` chưa từng được quan sát. Lệch version chỉ cảnh báo, theo quyết định của user.

### Thay đổi

- **`wflash/core/winidea_adapter.py`**: `RealWinIDEAAdapter` (`list_instances`, `connect`, `disconnect`, `get_info`); Protocol có thêm `download_cancellable`, `verify_flash`.
- **`tests/fake_isystem.py`** (mới): module giả dựng từ hành vi đã quan sát; `umi.write`, `erase`, `flush`, `getOptionJSON` báo lỗi ngay nếu bị gọi.
- **`tests/test_real_adapter.py`** (mới).

### Đã kiểm tra

- RED rồi GREEN với `pytest tests/test_real_adapter.py`. Chưa chạy với winIDEA thật.

## Phase 2.3: Adapter thật: đọc và đổi path

Dòng Download Files và file symbol không có tên riêng, nên adapter đặt tên theo file: `RAD_SUZ05_FFI.s3`, `App_M7/Radar_SUZ05_Gen7.elf`. Dòng không tick mang hậu tố `(disabled)`, hai dòng tick trùng tên mang `#i`; cả hai không khớp được với profile nên tool không đoán. Tool từ chối nếu thiết bị không bật hoặc không có "Program at download", vì khi đó download không ghi Winbond. File mới phải trùng tên với file đang cấu hình, và giá trị sau khi ghi được đọc lại để so.

### Thay đổi

- **`wflash/core/winidea_adapter.py`**: `read_programs`, `read_applications`, `set_program_path`, `set_symbol_path`.
- **`tests/test_real_adapter.py`**: 12 test.

### Đã kiểm tra

- RED rồi GREEN với `pytest tests/test_real_adapter.py`. Đọc `Applications[i]` tới khi hết danh sách chưa được kiểm chứng trên máy thật, có ghi `# UNVERIFIED`.

## Phase 2.4: Adapter thật: lập trình bằng begin_program và reset

`begin_program()` chạy chặn khoảng 100 s, không báo tiến độ và không dừng an toàn được, nên tiến độ chỉ là ước lượng theo thời gian (tối đa 95%), còn cancel và timeout không ngắt nó: quá hạn chỉ ghi cảnh báo. Lỗi lập trình nhắc rằng flash có thể đã bị xóa. Sau reset, target được xác nhận bằng `isStopped`, vì spike cho thấy `isHalted` vẫn là 0 khi target đã dừng, và có lần đọc ngay sau reset chưa thấy dừng.

### Thay đổi

- **`wflash/core/winidea_adapter.py`**: `download`, `reset`.
- **`tests/test_real_adapter.py`**: test adapter và test `FlashWorkflow` chạy trên adapter thật với module giả (chỉ đổi 2 path, gọi `begin_program` một lần, khôi phục cả 2 path khi lỗi, không flash nếu sai tên).

### Đã kiểm tra

- RED rồi GREEN; `pytest -k "not gui" -q`. Chưa chạy với winIDEA thật.

## Phase 2.5: So mẫu flash sau khi ghi (core)

Bước tùy chọn giữa download và reset, theo quyết định của user. Mỗi lần đọc mất khoảng 4,4 s bất kể kích thước, nên chỉ so đầu và cuối mỗi đoạn. Khi khác nhau, tool báo lỗi nhưng không khôi phục path, vì flash đã được ghi rồi và path mới mô tả đúng nội dung đó. Fake adapter có thêm `verify` để test nhánh lỗi.

### Thay đổi

- **`wflash/core/winidea_adapter.py`**, **`wflash/core/fake_adapter.py`**: `verify_flash`.
- **`wflash/core/flash_workflow.py`**: `Step.VERIFY`, `FlashRequest.verify`.
- **`tests/test_real_adapter.py`**, **`tests/test_fake_adapter.py`**, **`tests/test_flash_workflow.py`**: test mới.

### Đã kiểm tra

- RED rồi GREEN; `pytest -k "not gui" -q`. Chưa chạy với winIDEA thật.

## Phase 2.6: Khóa Cancel khi đang lập trình, ô Verify samples, hỏi lại khi đóng

Với adapter thật, Cancel bị khóa từ bước Downloading, vì dừng giữa lúc xóa chip có thể để lại ECU trống. Fake adapter mặc định vẫn hủy được, nên nhánh rollback khi hủy vẫn được test; thêm chế độ `cancellable=False` (`WFLASH_FAKE_FAIL=no_cancel`) giống adapter thật. Đóng cửa sổ khi đang khóa sẽ hỏi lại, cảnh báo ECU có thể bị trống; "Quit anyway" đi theo đường chờ có giới hạn sẵn có, nên `begin_program` treo không làm app kẹt mãi. Lúc thực hiện phát hiện thêm: `WorkerContext.progress` ném `CancelledError` khi đã có lệnh hủy, nên adapter thật phải bỏ qua lỗi này trong cả `download` và `verify_flash`, nếu không một lần bấm Cancel ngay trước khi khóa sẽ làm dừng phần so mẫu dù flash đã xong.

### Thay đổi

- **`wflash/gui/flash_mixin.py`**: `flash_locked()`, khóa Cancel, truyền `verify`.
- **`wflash/gui/main_window.py`**: câu hỏi khi đóng.
- **`wflash/gui/main_window.ui`**, **`ui_main_window.py`** (sinh lại): `checkBox_verifyFlash`.
- **`wflash/core/fake_adapter.py`**: `cancellable`, `no_cancel`.
- **`wflash/core/winidea_adapter.py`**: bỏ qua `CancelledError` từ callback tiến độ.
- **`tools/stress_test.py`**: `check_locked_flash`.
- **`tests/test_gui_flash.py`**, **`tests/test_gui_close_window.py`**, **`tests/test_real_adapter.py`**: test mới.

### Đã kiểm tra

- RED: 5 test mới lỗi. GREEN: `pytest -q`: 364 passed; `pytest -k thread -q`: 42 passed; `tools/stress_test.py`: `CHECKPOINTS=361 FAILED=0 QT_THREADING_WARNINGS=0`, `STRESS_RESULT=PASS`.

## Phase 2.7: Bật adapter thật, profile SUZ05, hướng dẫn Vòng 7

`create_adapter("real")` giờ trả về `RealWinIDEAAdapter`. Profile `suz05_m7_ffi.yaml` chỉ nhắm dòng `RAD_SUZ05_FFI.s3` và ELF của `App_M7`. Đây vẫn chưa phải chạy thật: mọi kiểm tra đều trên module giả, nên không khẳng định gì về phần cứng cho tới khi có kết quả Vòng 7, nhất là bước flash một firmware khác.

### Thay đổi

- **`wflash/core/winidea_adapter.py`**: bật adapter thật.
- **`profiles/suz05_m7_ffi.yaml`** (mới). Giá trị `gitlab.project` là mẫu, user cần đổi.
- **`README.md`**, **`docs/winidea_api_notes.md`**, **`docs/windows_test_guide.md`**: trạng thái, cách viết profile, Vòng 7.
- **`tests/test_real_adapter.py`**, **`tests/test_profile.py`**, **`tests/test_fake_adapter.py`**: test mới; bỏ phần kiểm tra lỗi cũ của `create_adapter("real")`.

### Đã kiểm tra

- RED: 2 test mới lỗi. GREEN: `pytest -q`: 366 passed; `pytest -k thread -q`: 42 passed; `tools/stress_test.py`: `CHECKPOINTS=361 FAILED=0 QT_THREADING_WARNINGS=0`, `STRESS_RESULT=PASS`; smoke `--adapter fake` và `--adapter real` (macOS, không có `isystem`) đều exit 0. Chưa chạy với winIDEA thật.

## Phase 2.8: Nạp nhiều artifact: mỗi nguồn một nút Load

User xác nhận `.s3` và ELF nằm ở hai artifact khác nhau. Trước đây mỗi lần Load thay toàn bộ firmware, nên nút Flash không bao giờ bật được. Profile giờ có thể khai báo `sources`, và mỗi đích ghi `source`. Vùng Setting có một nút Load cho mỗi nguồn; tải lại một nguồn chỉ thay nguồn đó và giữ lựa chọn thủ công của nguồn kia. Mỗi dòng mapping chỉ thấy file của nguồn đã khai báo, nên file trùng tên trong artifact kia không thể bị lấy nhầm. Profile không có `sources` vẫn chạy như cũ. Thêm cảnh báo khi hai artifact CI khác commit, không chặn flash; package không có commit nên không so được. Theo user, mọi job `build*` đều có ELF và mọi job `create_ffi*` đều có `.s3`, nên hai nguồn dùng hai bộ lọc đó. Browse jobs giờ chỉ liệt kê job thành công, vì job lỗi vẫn có thể có artifact. Ảnh chụp cho thấy hàng After flash bị cắt chữ khi có ba ô, nên Verify samples được chuyển xuống dòng riêng.

### Thay đổi

- **`wflash/core/profile.py`**: `SourceSpec`, `sources`, `job_filter_for`, kiểm tra tính nhất quán.
- **`wflash/core/file_matcher.py`**: `MappingRow.source`/`root`, `build_mapping_for_source`, `pending_rows`.
- **`wflash/core/firmware_source.py`**, **`firmware_fetch.py`**: lưu commit của pipeline.
- **`wflash/gui/mapping_table.py`**, **`main_window.py`**, **`flash_mixin.py`**, **`gitlab_dialog.py`**: dòng nguồn động, popup nhận tên nguồn và bộ lọc job riêng, cảnh báo commit.
- **`wflash/gui/main_window.ui`**, **`ui_main_window.py`** (sinh lại), **`style*.qss`**: `verticalLayout_sourceSlots`, `label_commitWarning`.
- **`profiles/suz05_m7_ffi.yaml`**, **`README.md`**, **`docs/windows_test_guide.md`**, **`tools/stress_test.py`**, test mới.

### Đã kiểm tra

- RED rồi GREEN theo từng phần. `pytest -q`: 385 passed; `pytest -k thread -q`: 42 passed; `tools/stress_test.py`: `CHECKPOINTS=371 FAILED=0 QT_THREADING_WARNINGS=0`, `STRESS_RESULT=PASS`.
- Chụp ảnh với style native macOS trong vòng lặp Qt thật: hai dòng nguồn, cảnh báo commit và ba checkbox hiện đủ chữ. Chưa thử với GitLab thật.

## Phase 2.9: Bỏ Package Registry

User cho biết chỉ cần CI artifact, nên xóa toàn bộ phần tải từ Package Registry. Popup giữ một tab CI Artifact để ít thay đổi nhất. File `settings.json` cũ có `package_project`/`package_name` vẫn nạp được vì khóa lạ bị bỏ qua. Thư mục `<cache>/packages` cũ, nếu có, không còn được dọn; nó không ảnh hưởng gì.

### Thay đổi

- **`wflash/gui/gitlab_dialog.ui`**, **`ui_gitlab_dialog.py`** (sinh lại), **`gitlab_dialog.py`**: bỏ tab và logic package.
- **`wflash/core/gitlab_client.py`**, **`firmware_fetch.py`**, **`artifact_cache.py`**, **`firmware_source.py`**, **`settings.py`**, **`wflash/gui/preferences_dialog.py`**: bỏ code package.
- **`tests`**, **`tools/stress_test.py`**, **`README.md`**, **`docs/windows_test_guide.md`**: bỏ phần package; test hỗn hợp được giữ lại cho CI.

### Đã kiểm tra

- `pytest -q`: 364 passed; `pytest -k thread -q`: 42 passed; `tools/stress_test.py`: `CHECKPOINTS=359 FAILED=0 QT_THREADING_WARNINGS=0`, `STRESS_RESULT=PASS`; smoke `--adapter fake` exit 0. Chưa thử với GitLab thật.

## Phase 2.10: Gợi ý khi gặp "Error loading monitor"

Hai lần flash thật qua WFlash đều chạy đúng: một pha ERASING, 79 sector, nạp từ cache của WFlash, lần hai là firmware khác và có so mẫu. User cho biết lỗi "Error loading monitor" chỉ hết khi tắt bật nguồn ECU, còn reset từ winIDEA thì không. Vì vậy bỏ đề xuất reset rồi thử lại, và chỉ hiện gợi ý đúng. Khi lỗi xảy ra lúc so mẫu, gợi ý nói rõ phần ghi flash đã xong, vì gợi ý mặc định "Make sure winIDEA is running" dễ gây hiểu nhầm.

### Thay đổi

- **`wflash/core/winidea_adapter.py`**: gợi ý tắt bật nguồn cho `begin_program` và `verify_flash`; lỗi đọc khi so mẫu luôn nói phần ghi đã xong.
- **`tests/fake_isystem.py`**, **`tests/test_real_adapter.py`**: 3 test.
- **`docs/winidea_api_notes.md`**: kết quả chạy thật.

### Đã kiểm tra

- RED rồi GREEN với `pytest tests/test_real_adapter.py`; `pytest -q`, `pytest -k thread -q`, `tools/stress_test.py`. Chưa kiểm chứng `begin_program` có ném lỗi khi gặp lỗi này không.

## Phase 2.11: Reset CPU trước khi flash

User đề xuất reset CPU trước khi flash. winIDEA cũng gợi ý như vậy, dù reset không gỡ được lỗi khi nó đã xảy ra. Nếu reset này lỗi hoặc target không dừng, tool chỉ cảnh báo rồi vẫn flash, vì Output cho thấy `begin_program` tự reset khi khởi động phiên. Chưa biết việc này có ngăn được lỗi không.

### Thay đổi

- **`wflash/core/winidea_adapter.py`**: `_reset_before_programming`, gọi đầu `download`.
- **`tests/fake_isystem.py`**, **`tests/test_real_adapter.py`**: 3 test.
- **`docs/winidea_api_notes.md`**: ghi quyết định.

### Đã kiểm tra

- RED rồi GREEN; `pytest -q`, `pytest -k thread -q`, `tools/stress_test.py`. Thứ tự reset rồi `begin_program` trong cùng phiên chưa chạy trên ECU thật.

## Phase 2.12: Sửa lỗi báo Done khi flash thất bại

User báo WFlash hiện `Done` khi winIDEA thực ra lỗi `Error loading monitor`. Debug bundle cho thấy nguyên nhân: `begin_program` không ném lỗi trong trường hợp này mà trả về bình thường sau 4,8 s (thành công mất 95-100 s), winIDEA chỉ in lỗi ra cửa sổ Output. Trong 21 lần flash của bundle, 15 lần trả về sau 5-6 s: 14 lần có Verify đều lỗi ngay ở lần đọc đầu, còn lần Verify tắt (14:08:43) lọt thành `Done`. Cả 3 lần flash dài có Verify đều đọc được. Giờ sau `begin_program` luôn đọc thử 16 byte ở `0x0`; đọc lỗi nghĩa là flash thất bại: khôi phục path, không báo `Done`, gợi ý tắt bật nguồn ECU. Trạng thái target sau khi flash được ghi log để xem có phân biệt được hai trường hợp không.

### Thay đổi

- **`wflash/core/winidea_adapter.py`**: `_confirm_programmed`, gọi sau `begin_program`.
- **`tests/test_real_adapter.py`**: 4 test.
- **`docs/winidea_api_notes.md`**: bằng chứng từ bundle.

### Đã kiểm tra

- RED rồi GREEN; `pytest -q`, `pytest -k thread -q`, `tools/stress_test.py`. Đọc `log.txt` trong bundle. Chưa chạy lại trên ECU, nhất là chưa tái hiện được lỗi monitor với bản mới.

## Phase 2.13: Popup lỗi ngắn gọn

User chạy bản mới: lỗi `Error loading monitor` lúc flash giờ được báo đúng, nhưng popup hiện cả mã lỗi kỹ thuật. Popup giờ chỉ có một câu ngắn và gợi ý, đúng với spec §8. Chi tiết của `isystem.connect` chỉ ghi vào log và debug bundle. Bỏ dòng nhắc Export debug bundle trong popup, vì nút đó luôn có ở tab Information.

### Thay đổi

- **`wflash/core/winidea_adapter.py`**: thông báo ngắn, `log.error` giữ chi tiết; nguyên nhân gốc vẫn ở `__cause__`.
- **`wflash/gui/main_window.py`**: `show_error` chỉ hiện thông báo và gợi ý.
- **`tests/test_real_adapter.py`**, **`tests/test_gui_main_window.py`**: cập nhật và thêm test.

### Đã kiểm tra

- RED rồi GREEN; `pytest -q`, `pytest -k thread -q`, `tools/stress_test.py`. Chưa thử lại trên ECU.

## Phase 2.14: Vòng 7 đạt trên ECU thật

User xác nhận luồng hoàn chỉnh: khi gặp lỗi monitor, WFlash báo lỗi thay vì `Done`; tắt bật nguồn ECU rồi flash lại thành công, ECU chạy đúng. Bundle cho thấy reset trước khi flash không gây hại nhưng cũng không ngăn được lỗi. Lỗi này cũng xảy ra khi flash tay, nên đây là giới hạn của môi trường chứ không do WFlash. Bundle là của bản trước khi rút gọn popup, nên popup ngắn chưa được xem trên Windows. `WFlash.exe` chưa được build lại với adapter thật.

### Thay đổi

- **`docs/winidea_api_notes.md`**: kết quả reset trước khi flash.

### Đã kiểm tra

- Đọc `wflash_debug_20261107_150629.zip`. Chỉ đổi tài liệu.

## Phase 2.15: Cập nhật CLAUDE.md

`CLAUDE.md` còn ghi "chưa có code ứng dụng" và mô tả các module đã xóa. Viết lại phần trạng thái, lệnh và kiến trúc theo code hiện tại, và ghi các điều học được trên ECU thật: không gọi `umi.write`, `begin_program` không báo lỗi khi flash thất bại, `getOptionJSON` làm mất kết nối, cách đặt tên dòng, Cancel bị khóa, nhiều nguồn.

### Thay đổi

- **`CLAUDE.md`**: các mục trên.

### Đã kiểm tra

- Đối chiếu tên file, class và method được nhắc tới với repo. Chỉ đổi tài liệu, không chạy lại test.

## Phase 3.0: Spec cho developer debug

User muốn tool phục vụ developer debug: đồng bộ firmware với commit của source repo, checkout từ app, cache theo branch, Advanced Debug để flash thêm BM và FBL từ repo riêng, CAL tự tìm cạnh workspace. Đã duyệt giao diện qua mockup. Spec nêu rõ các điểm chưa kiểm chứng phải thử trước (ghi dấu tick, các dòng chồng nhau khi flash, tìm pipeline theo commit). Chưa viết code.

### Thay đổi

- **`docs/superpowers/specs/2026-11-07-wflash-developer-debug-design.md`** (mới).
- **`docs/superpowers/mockups/developer-ui/`** (mới): bản sao mockup đã duyệt.

### Đã kiểm tra

- Tự rà soát spec theo các quyết định của user. Chỉ có tài liệu, không chạy test.

## Phase 3.1: Plan 3 cho developer debug

Viết plan 11 task theo spec đã duyệt. Task 1 là spike trên máy thật, các task lõi không phụ thuộc phần cứng làm được song song, còn phần adapter và luồng flash chỉ bắt đầu sau khi có kết quả spike. Chưa viết code ứng dụng.

### Thay đổi

- **`docs/superpowers/plans/2026-11-07-wflash-developer-debug.md`** (mới).

### Đã kiểm tra

- Tự rà soát plan theo spec. Chỉ có tài liệu.

## Phase 3.2: Spike 14, 15 và Vòng 8

Trước khi viết phần flash mới, cần biết API có ghi được dấu tick không, field nào là dấu tick của Symbol File, winIDEA xử lý các dòng chồng nhau thế nào, và GitLab có tìm được pipeline theo commit không. Chưa có gì trong số này từng chạy trên máy thật.

### Thay đổi

- **`spike/14_tick_options.py`**, **`spike/15_pipeline_sha.py`** (mới).
- **`spike/README.md`**, **`docs/windows_test_guide.md`**: mục "Vòng 8", ghi rõ phần ghi flash và cách khôi phục.

### Đã kiểm tra

- Chạy 14 và 15 với module giả: đọc in đúng, đảo rồi khôi phục đúng, token không xuất hiện trong file kết quả. Chưa chạy trên máy thật.

## Phase 3.3: Đọc source repo và checkout

Module mới gọi `git` qua `subprocess`, không dùng Qt, để đọc branch, commit, thay đổi chưa commit, liệt kê branch và commit, fetch, checkout. Checkout từ chối khi có thay đổi chưa commit và không bao giờ dùng `--force`, `stash`, `reset`, `clean`. `GIT_TERMINAL_PROMPT=0` để git không treo chờ nhập mật khẩu.

### Thay đổi

- **`wflash/core/source_repo.py`** (mới), **`wflash/core/errors.py`**: `SourceRepoError`.
- **`tests/test_source_repo.py`** (mới): chạy trên git repo tạm thật.

### Đã kiểm tra

- RED rồi GREEN với `pytest tests/test_source_repo.py`. Chưa chạy trên Windows.

## Phase 3.4: Profile có cấu hình build, vai trò và nguồn debug

Profile SUZ05 giờ khai báo 4 cấu hình build (cặp job FFI, ELF và job BM tương ứng), vai trò từng file, offset của BM và FBL, và project riêng của BM, FBL. Thứ tự trong `programs` là thứ tự flash. Lưu ý: giao diện chưa dùng phần này (Task 9), nên trong lúc phát triển profile SUZ05 chưa dùng được với nút Load cũ; nhánh này chưa merge nên không ảnh hưởng `main`.

### Thay đổi

- **`wflash/core/profile.py`**, **`wflash/core/file_matcher.py`**, **`profiles/suz05_m7_ffi.yaml`**, **`tests/test_profile.py`**.

### Đã kiểm tra

- RED rồi GREEN với `pytest tests/test_profile.py`; `pytest -q`.

## Phase 3.5: Tìm cặp job của một cấu hình build theo commit

`find_build_jobs` tìm pipeline đúng commit, lấy pipeline mới nhất có cả job FFI và ELF thành công, và không bao giờ chuyển sang commit khác. Khi không có, thông báo nêu rõ job nào và trạng thái gì. Lệnh tìm theo `sha` chờ kết quả spike 15 trên GitLab thật.

### Thay đổi

- **`wflash/core/gitlab_client.py`**: `list_pipelines_for_commit`, tham số `archived_only`.
- **`wflash/core/firmware_fetch.py`**: `find_build_jobs`.
- **`tests/test_firmware_fetch.py`**, **`tests/test_gitlab_client.py`**: test mới.

### Đã kiểm tra

- RED rồi GREEN với hai file test trên. Chưa chạy với GitLab thật.

## Phase 3.6: Cache theo branch, commit và cấu hình

Firmware tải theo commit nằm trong thư mục có tên cho biết đang debug gì: `<branch>\<commit8>_<build>\FFI`, và `BM\<ref>\<commit8>_<job>` cho BM, FBL. Ký tự Windows không cho phép được đổi thành `_`, tên quá dài được rút gọn kèm hash. Giải nén vào thư mục tạm rồi mới đổi tên. Clear cache dọn cả layout mới và layout cũ, và không đụng tới file khác trong thư mục cache. Popup GitLab vẫn dùng layout cũ.

### Thay đổi

- **`wflash/core/artifact_cache.py`**: `safe_segment`, `build_cache_path`, `debug_cache_path`, `NamedArtifactCache`.
- **`wflash/core/firmware_fetch.py`**: `fetch_named_artifact`.
- **`wflash/gui/preferences_dialog.py`**: Clear cache dùng cache mới.
- **`tests/test_artifact_cache.py`**, **`tests/test_firmware_fetch.py`**.

### Đã kiểm tra

- RED rồi GREEN; `pytest -q`.

## Phase 3.7: Kiểm tra workspace và lập kế hoạch flash

Trước khi đổi bất cứ thứ gì, `make_plan` kiểm tra đủ dòng, thứ tự FFI → CAL → BM → FBL, offset của BM và FBL, không có dòng lạ đang tick, và CAL có sẵn. Nó trả về danh sách thay đổi path và dấu tick. Đây là logic thuần, chưa gọi winIDEA, nên test được đầy đủ trên macOS. Tắt Advanced Debug thì BM và FBL bị bỏ tick và giữ nguyên path.

### Thay đổi

- **`wflash/core/flash_plan.py`**, **`tests/test_flash_plan.py`** (mới).

### Đã kiểm tra

- RED rồi GREEN với `pytest tests/test_flash_plan.py`; `pytest -q`.

## Phase 3.8: Verify với các file chồng nhau

BM và FBL ghi đè lên một phần FFI, nên so mẫu theo từng file sẽ báo lỗi sai. Verify giờ đọc cả file `.bin` theo offset, và chỉ so phần của mỗi file còn nằm trên flash sau khi các dòng sau ghi đè.

### Thay đổi

- **`wflash/core/srec.py`**: `read_image`, `visible_segments`, `is_image_file`.
- **`wflash/core/winidea_adapter.py`**: `verify_flash` dùng các hàm trên.
- **`tests/test_srec.py`**, **`tests/test_real_adapter.py`**.

### Đã kiểm tra

- RED rồi GREEN; `pytest -q`. Hành vi ghi chồng thật của winIDEA còn chờ phần B của Vòng 8.

## Phase 3.9: Adapter ghi dấu tick và luồng flash theo kế hoạch

Spike 14 cho thấy ghi được dấu tick của dòng Download Files (`.Enabled`) và của Symbol File (`.Load`), đọc lại đúng. Profile có `builds` giờ đi luồng mới: đọc toàn bộ dòng, kiểm tra bằng `make_plan`, đổi path và dấu tick, rồi flash như cũ (reset, `begin_program`, đọc xác nhận). Khi lỗi chỉ khôi phục path, dấu tick giữ nguyên theo quyết định của user. Thiếu file BM khi bật Advanced Debug thì báo lỗi trước khi đổi gì. Profile không có `builds` vẫn đi luồng cũ.

### Thay đổi

- **`wflash/core/winidea_adapter.py`**: `SYMBOL_TICK_FIELD = "Load"`, `workspace_dir`, `read_program_rows`, `read_symbol_rows`, `set_program_row`, `set_symbol_row`; Protocol cập nhật.
- **`wflash/core/fake_adapter.py`**: cùng các hàm trên.
- **`wflash/core/flash_workflow.py`**: `_run_planned`, `_finish`, `_restore_row_paths`; `FlashRequest.profile`, `advanced`, `cal_file`.
- **`wflash/core/flash_plan.py`**: báo lỗi khi file chưa nạp. **`wflash/core/debug_bundle.py`**: `snapshot_rows`.
- **`docs/winidea_api_notes.md`**: kết quả spike 14.
- **`tests/test_flash_workflow.py`**, **`tests/test_real_adapter.py`**.

### Đã kiểm tra

- RED rồi GREEN; `pytest -q`, `pytest -k thread -q`, `tools/stress_test.py`. Chưa chạy luồng mới trên ECU.

## Phase 3.10: Spike 15: tìm pipeline theo commit chạy được

GitLab thật trả về pipeline đúng commit. Trạng thái chung của pipeline là `manual` vì còn job chạy tay, nên tool chỉ xét hai job cần dùng, đúng như `find_build_jobs` đang làm. Các job `manual` và `skipped` không có artifact, và thông báo lỗi nêu rõ trạng thái đó.

### Thay đổi

- **`docs/winidea_api_notes.md`**: kết quả spike 15.

### Đã kiểm tra

- Đối chiếu kết quả với logic `find_build_jobs` và test hiện có. Chỉ đổi tài liệu.

## Phase 3.11: Giao diện developer: source repo, build, Advanced Debug, hai bảng file

Profile có `builds` giờ hiện panel developer thay cho nút Load from GitLab. Người dùng chọn thư mục source repo, WFlash đọc branch, commit và cảnh báo khi có thay đổi chưa commit (chỉ cảnh báo, không chặn). Nút "Load firmware for <commit>" tìm pipeline của commit đó, rồi tải FFI và ELF theo build đã chọn vào thư mục cache đặt theo branch. CAL được tìm cạnh file `.xjrf`. Advanced Debug thêm dòng BM và FBL; khi tắt thì ẩn hai dòng này và lúc flash sẽ bỏ tick chúng. Bảng file tách thành Program Files (có cột Offset) và Symbol Files, bỏ cột winIDEA target. Flash bị khoá khi thiếu CAL hoặc BM lấy từ job khác với job của build, kèm lý do hiện trên banner.

### Thay đổi

- **`wflash/gui/main_window.ui`** và **`ui_main_window.py`** (sinh lại): `scrollArea_setting`, `frame_developer`, `frame_application`, `frame_advancedDebug`, `tableWidget_programFiles`, `tableWidget_symbolFiles`, `label_flashBlocked`.
- **`wflash/gui/source_panel.py`** (mới): `SourcePanelMixin`; đọc repo và tải build chạy trên worker.
- **`wflash/gui/mapping_table.py`**: hai bảng, cột Source theo role.
- **`wflash/gui/flash_mixin.py`**: `source_busy`, `flash_block_reason`, `flash_request_extras`.
- **`wflash/gui/gitlab_dialog.py`**: `prepare(..., project=, cache=)` cho BM/FBL và chọn job tay.
- **`wflash/core/file_matcher.py`**, **`settings.py`**, **`firmware_source.py`**, **`fake_adapter.py`**: role, offset, `source_repos`, `last_build`, `job_name`, `workspace`.
- **`wflash/resources/style*.qss`**: màu cho các khung mới.
- **`tests/test_gui_source_panel.py`** (mới), **`tests/gui_stubs.py`**: pipeline theo commit giả.

### Đã kiểm tra

- `pytest -q` (432 passed), `pytest -k thread -q` (42 passed), `tools/stress_test.py` (PASS, 0 cảnh báo threading).
- Chụp cửa sổ offscreen ở 1280×820: bố cục hai bảng và panel cuộn đúng. Chưa xem màu QSS và chưa chạy trên Windows/ECU. Nút Checkout chưa có chức năng (Task 10).

## Phase 3.12: Checkout branch hoặc commit từ WFlash

Nút Checkout… trong panel developer mở hộp thoại liệt kê các branch (local và remote) và tối đa 50 commit mới nhất của branch đang chọn, kèm trạng thái pipeline trên GitLab. Cột Pipeline chỉ để tiện xem: nếu GitLab lỗi hoặc profile không có project thì cột hiện `-` và checkout vẫn chạy bình thường. Chọn commit đầu tiên thì checkout branch; chọn commit cũ hơn thì checkout commit đó ở trạng thái detached. Khi repo có thay đổi chưa commit, checkout bị từ chối, có giải thích và file của người dùng giữ nguyên; WFlash không bao giờ stash, reset hay force. Fetch chỉ chạy `git fetch --prune`. Sau khi checkout xong, panel đọc lại repo; nếu firmware đã nạp thuộc commit khác thì panel ghi chú "Loaded firmware is from another commit." nhưng không khoá Flash.

### Thay đổi

- **`wflash/gui/checkout_dialog.ui`** (mới) và **`ui_checkout_dialog.py`** (sinh bằng pyside6-uic).
- **`wflash/gui/checkout_dialog.py`** (mới): `CheckoutDialog`. Worker dùng key `checkout-`, có guard `_generation`, `done()` chờ tối đa 10 s và chỉ đóng hộp thoại khi worker đã xong.
- **`wflash/gui/source_panel.py`**: `open_checkout_dialog`; tín hiệu `checkedOut` gọi `refresh_source_repo`. **`main_window.py`**: `abort_for_close` khi đóng cửa sổ.
- **`wflash/resources/style*.qss`**: chữ đỏ cho `label_checkoutError`.
- **`tests/test_gui_checkout_dialog.py`** (mới), **`tests/test_gui_source_panel.py`**, **`tests/test_gui_ui_files.py`**.

### Đã kiểm tra

- `pytest -q` (442 passed), `pytest -k thread -q` (43 passed), `tools/stress_test.py` (PASS); app chạy được với `--adapter fake`.
- Test dùng repo git thật trên macOS. Chưa thử với repo thật trên Windows: thời gian `git fetch` qua mạng nội bộ và cột Pipeline với GitLab thật.

## Phase 3.13: Stress test cho luồng developer, tài liệu và Vòng 9

Stress test giờ chạy cả luồng developer trên một cửa sổ thật: dùng repo git tạm, nạp build theo commit qua GitLab giả, bật/tắt Advanced Debug ba lần, rồi flash hai lần. Lần đầu tắt Advanced Debug thì BM, FBL bị bỏ tick; lần hai bật thì BM, FBL và ELF của chúng được tick và trỏ vào file mới. Phần races có thêm hai trường hợp: đóng cửa sổ khi đang tải build, và khi đang đọc repo. Tài liệu cập nhật luồng developer, và có hướng dẫn Vòng 9 cho máy Windows.

### Thay đổi

- **`tools/stress_test.py`**: `new_dev_window`, `check_developer_flow`, `deliver_debug`; thêm race đóng cửa sổ trong lúc tải build và đọc repo.
- **`README.md`**: mục "Chế độ developer", hai bảng file, lệnh uic cho `checkout_dialog.ui`.
- **`CLAUDE.md`**: ngoại lệ của Approach A cho profile có `builds` (tick BM/FBL, đường dẫn CAL, lỗi thì chỉ trả lại path, không trả lại tick); `source_repo` không bao giờ stash, reset hay force; danh sách file GUI mới.
- **`docs/windows_test_guide.md`**: Vòng 9.

### Đã kiểm tra

- `pytest -q` (442 passed), `pytest -k thread -q` (43 passed), `tools/stress_test.py` (393 checkpoint, PASS, 0 cảnh báo threading), `main.py --adapter fake --smoke` (exit 0).
- Chưa có kết quả trên phần cứng: chờ Vòng 8 phần B và Vòng 9.

## Phase 3.14: Vòng 8 phần B đạt: flash bốn dòng chồng nhau

Người dùng chạy trên ECU thật với bốn dòng FFI, CAL, BM (`.bin`, offset `0x0`), FBL (`.bin`, offset `0xF1000`). Cả Debug → Download bấm tay và `begin_program()` đều chỉ có một lần `ERASING`, rồi ghi 79 sector và báo `OK`. Sau mỗi lần, tắt bật nguồn thì ECU chạy đúng. winIDEA chỉ cảnh báo vùng chồng nhau, và dòng nạp sau ghi đè dòng trước: spike 09 đọc được giá trị của BM ở vùng FFI bị BM che. Đây đúng là giả định `visible_segments` đang dùng. Vì vậy có thể làm tiếp Vòng 9.

### Thay đổi

- **`docs/winidea_api_notes.md`**: mục "Round 8 part B".

### Đã kiểm tra

- Đọc Output tay và Output API, `12_begin_program` (99.8 s, trả về `None`), `09_flash_compare` (FFI khớp trừ vùng BM ghi đè, CAL khớp). Chỉ đổi tài liệu. Dòng `PROGRAMMING 0 bytes` ở cuối Output của lần chạy API chưa giải thích được.

## Phase 3.15: Kết quả Vòng 9 và kiểm tra core trước khi flash

Vòng 9 đạt: ba lần flash qua luồng developer đều có một `ERASING`, và ECU chạy đúng. Debug bundle còn cho thấy 34 lần flash hỏng: `begin_program` trả về sau 5–9 giây, rồi lần đọc kiểm tra báo `Error loading monitor`. WFlash báo lỗi đúng và trả đường dẫn về như cũ, nhưng người dùng phải bấm lại nhiều lần. Người dùng nhận ra flash chỉ được khi không có core nào NOT ACCESSIBLE trong Session Explorer. Spike 16 (chỉ đọc) tìm được cách đọc trạng thái đó: `CSessionCtrl.get_status().SoCs()[0].cores()`, tên lấy từ `get_topology()`. Kiểm tra cũ bằng `getCPUStatus()` của M7_0 báo `isStopped` như nhau ở cả hai trạng thái, nên không phát hiện được. Theo quyết định của người dùng, adapter thật reset, đọc trạng thái các core, và chỉ chạy `begin_program` khi không có core nào NOT ACCESSIBLE. Trạng thái RUN, STOP, IDLE đều được chấp nhận, vì BBE32EP đang RUN mà vẫn flash được. Nếu bị chặn, `download()` báo lỗi nên workflow tự trả đường dẫn về như cũ. Nếu không đọc được trạng thái thì chỉ cảnh báo rồi vẫn flash, vì không đọc được khác với core hỏng.

### Thay đổi

- **`spike/16_core_status.py`**, **`spike/README.md`**: spike chỉ đọc, in trạng thái từng core, topology và các hằng `EStatus_*`.
- **`wflash/core/winidea_adapter.py`**: `_core_states`, kiểm tra core (đọc lại trong `CORE_WAIT_S` = 2 s, con số chưa đo), `inaccessible_cores_error`, `CORE_HINT`; gọi giữa reset và `begin_program`.
- **`wflash/core/fake_adapter.py`**: chế độ lỗi `core_inaccessible`.
- **`tests/fake_isystem.py`**: `CSessionCtrl.get_status/get_topology`, các core theo kết quả spike 16, `cores_after_reset`, `core_status_error`, `get_status_hook`.
- **`tests/test_real_adapter.py`**, **`tests/test_flash_workflow.py`**: bị chặn khi core NOT ACCESSIBLE (không gọi `begin_program`, trả đường dẫn về như cũ), core hồi lại trong khoảng chờ, không đọc được trạng thái thì vẫn flash, có ghi log trạng thái.
- **`docs/winidea_api_notes.md`**: mục "Round 9 and per-core state". **`docs/windows_test_guide.md`**: Vòng 10. **`CLAUDE.md`**: thêm mục về NOT ACCESSIBLE.

### Đã kiểm tra

- Spike 16 trên ECU thật, hai trạng thái (mọi core STOP, và có core NOT ACCESSIBLE), kết quả như bảng trong `winidea_api_notes.md`.
- Toàn bộ test, `-k thread`, stress test (kết quả ở commit). Kiểm tra trong adapter thật **chưa chạy trên phần cứng**: chờ Vòng 10. Chưa biết reset thêm lần nữa có làm hết NOT ACCESSIBLE không: 34 lần hỏng ở Vòng 9 đều đã reset một lần trước đó.

## Phase 3.16: Reset lại khi có core NOT ACCESSIBLE

Người dùng thử reset bằng winIDEA thì các core hết NOT ACCESSIBLE. Theo đó, người dùng chốt thứ tự: đặt đường dẫn, reset, đọc trạng thái mọi core; nếu có core NOT ACCESSIBLE thì reset lại, nếu không thì bắt đầu flash. Số lần reset thêm có giới hạn, `MAX_CORE_RESETS` = 3, để WFlash không lặp mãi. Hết số lần đó mà vẫn còn core NOT ACCESSIBLE thì WFlash dừng và trả đường dẫn về như cũ, như Phase 3.15. Mỗi lần reset lại đều ghi cảnh báo vào log, có trạng thái từng core.

### Thay đổi

- **`wflash/core/winidea_adapter.py`**: `_prepare_cores` (reset, đọc trạng thái, reset lại tối đa 3 lần) thay cho `_check_cores`; `_inaccessible_cores` đọc lại trạng thái trong `CORE_WAIT_S` sau mỗi lần reset. Lời nhắn lỗi nêu số lần đã reset.
- **`tests/fake_isystem.py`**: `cores_after_reset` là danh sách, mỗi lần reset lấy phần tử tiếp theo.
- **`tests/test_real_adapter.py`**: lần reset thứ ba làm hết NOT ACCESSIBLE thì flash; hết 3 lần thì dừng, không gọi `begin_program`; core tự hồi trong khoảng chờ thì không reset thêm.
- **`docs/winidea_api_notes.md`**, **`docs/windows_test_guide.md`** (Vòng 10), **`CLAUDE.md`**.

### Đã kiểm tra

- Toàn bộ test, `-k thread`, stress test (kết quả ở commit). Chưa chạy trên phần cứng. Lệnh reset dùng ở đây là `CDebugFacade.reset()`, chính lệnh đã chạy trước 34 lần hỏng ở Vòng 9. Có thể nó không giống thao tác reset bạn bấm tay trong winIDEA. Vòng 10 sẽ cho biết. Nếu nó không làm hết NOT ACCESSIBLE thì lệnh nên thử tiếp là `CSessionCtrl.begin_reset()`.
