# WFlash Tool — Design Spec

- Ngày: 2026-10-04
- Trạng thái: Đã duyệt thiết kế, chờ review spec

## 1. Mục tiêu

WFlash là tool desktop (Python + PySide6) giúp người dùng flash ECU **NXP SAF85xx** qua **winIDEA 9.21.x** (thư viện `isystem.connect`):

1. Duyệt GitLab (self-hosted) theo branch/tag → pipeline → job, tải artifact.
2. Tự động chọn file `.s3` (để flash) và các file `.elf` (symbol cho từng core) dựa trên profile.
3. Cập nhật đường dẫn file trong workspace winIDEA đang mở, chạy download (nạp vào external QSPI flash Winbond), load symbol, reset + halt.
4. Hiển thị log đầy đủ, xuất được "debug bundle" để gửi đi debug từ xa.

### Ngoài phạm vi (YAGNI)

- Tự cấu hình external flash device / flash loader trong winIDEA (workspace đã cấu hình sẵn, flash tay chạy OK).
- Tự khởi động winIDEA hoặc mở workspace.
- Xử lý địa chỉ/offset cho `.s3` (file nạp thẳng).
- Chọn file `.s3`/`.elf` cục bộ không qua GitLab.
- Hỗ trợ winIDEA khác 9.21.x.

## 2. Bối cảnh & ràng buộc

| Hạng mục | Quyết định |
|---|---|
| Target | NXP SAF85xx, đa core, mỗi core/Application có `.elf` riêng |
| Flash | External QSPI NOR Winbond; workspace winIDEA đã cấu hình flash loader, flash tay OK |
| `.s3` | Địa chỉ khớp sẵn vùng external flash, nạp thẳng |
| winIDEA | 9.21.x; tool **attach** vào instance đang mở (user tự mở workspace) |
| GitLab | Self-hosted, xác thực bằng Personal Access Token cá nhân (scope `read_api`), lưu bằng `keyring` (Windows Credential Manager) |
| Cache | `cache/<project_id>/<job_id>/`, giới hạn N job, có nút xóa cache |
| Post-flash | Reset + halt (mặc định); checkbox tùy chọn "Run after flash" |
| Phân phối | Chạy từ source (dev) và bản `.exe` PyInstaller (người dùng cuối) |
| Môi trường dev | macOS (không có winIDEA) → cần fake adapter; test thật trên Windows |

## 3. Cách điều khiển winIDEA (Approach A)

Tool **không** flash từng file bằng API rời rạc. Thay vào đó:

1. Đọc cấu hình session hiện có trong workspace: danh sách download file (Programs) và symbol file (Applications).
2. Tìm entry tương ứng theo profile (`winidea_entry`, `winidea_app`). **Chỉ thay đường dẫn file**, giữ nguyên mọi thuộc tính khác (target device = external flash, verify, offset, load mode).
3. Không tìm thấy entry khớp → lỗi `MappingError`, **không** tự tạo entry mới.
4. Backup path cũ trước khi sửa; rollback khi set path hoặc download thất bại.
5. Gọi `CLoaderController.download()`, theo dõi tiến trình, áp timeout từ profile.
6. Reset target, để CPU halted (hoặc run nếu user chọn).

Vì tên option path cụ thể trong winIDEA 9.21 chưa được xác minh, **Phase 0 là spike chạy trên Windows** để xác định chúng (xem mục 9).

## 4. Kiến trúc

```
wflash/
├── core/                    # Không phụ thuộc Qt
│   ├── errors.py            # GitLabError, ArtifactError, MappingError, WinIDEAError, FlashError
│   ├── gitlab_client.py     # requests + GitLab REST v4: branch/tag → pipeline → job có artifact; tải zip
│   ├── artifact_cache.py    # cache theo job_id, giải nén, giới hạn số job, xóa cache
│   ├── profile.py           # đọc/validate profile YAML (pydantic)
│   ├── file_matcher.py      # match file trong artifact theo pattern → mapping entry/core
│   ├── winidea_adapter.py   # Protocol WinIDEAAdapter + RealWinIDEAAdapter (import isystem.connect)
│   ├── fake_adapter.py      # FakeWinIDEAAdapter cho macOS/test
│   ├── flash_workflow.py    # điều phối các bước, phát sự kiện tiến trình, rollback
│   ├── logging_setup.py     # handler file + handler Qt, bộ lọc che token
│   └── debug_bundle.py      # đóng gói zip debug
├── gui/
│   ├── main_window.py       # GitLab browser | bảng mapping | log panel + nút Flash
│   ├── log_panel.py         # hiển thị log có màu, lọc level, copy/clear
│   ├── workers.py           # QThread/QRunnable cho tải artifact và flash
│   └── settings_dialog.py   # GitLab URL, PAT, thư mục cache, chọn profile, verbose
├── profiles/
│   └── saf85xx_example.yaml
├── spike/                   # script độc lập chạy trên Windows (Phase 0)
└── main.py                  # entry point, tham số --adapter real|fake
```

### Quy tắc ranh giới

- Chỉ `winidea_adapter.py` import `isystem.connect`.
- GUI không gọi GitLab/winIDEA trực tiếp; mọi thao tác qua `core` và chạy trên worker thread.
- `--adapter`: mặc định `real` trên Windows, `fake` trên OS khác.

### Interface adapter (dự kiến, chốt sau spike)

```python
class WinIDEAAdapter(Protocol):
    def list_instances(self) -> list[InstanceInfo]: ...
    def connect(self, instance_id: str) -> None: ...
    def get_info(self) -> dict: ...                     # version winIDEA, workspace path
    def read_programs(self) -> list[FileEntry]: ...      # download files hiện tại
    def read_applications(self) -> list[FileEntry]: ...  # symbol files theo core
    def set_program_path(self, entry: str, path: Path) -> None: ...
    def set_symbol_path(self, app: str, path: Path) -> None: ...
    def download(self, progress_cb, cancel_token, timeout_s: int) -> None: ...
    def reset(self, run: bool) -> None: ...
    def disconnect(self) -> None: ...
```

## 5. Profile

```yaml
name: SAF85xx_Radar
gitlab:
  project: group/saf85xx-sw        # path hoặc id
  job_filter: "build_*"            # glob tên job hiển thị
programs:                          # entry download có sẵn trong workspace (trỏ tới Winbond)
  - winidea_entry: "App"
    pattern: "**/*App*.s3"
applications:                      # symbol cho từng Application/core
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

Tên entry/Application trong ví dụ là giả định; giá trị thật lấy từ kết quả spike.

Quy tắc match: mỗi entry phải match **đúng 1** file. 0 hoặc >1 → ô tô đỏ trên GUI, user chọn tay từ danh sách file trong artifact. Nút Flash chỉ bật khi mọi entry đã được gán.

## 6. Luồng dữ liệu

```
Chọn profile
 → Kết nối GitLab (PAT) → chọn branch/tag → pipeline → job có artifact
 → Tải artifact (dùng cache nếu có job_id) → giải nén
 → file_matcher tạo mapping → user xác nhận/sửa trên bảng
 → [Flash]
     connect winIDEA (chọn instance)
     → đọc programs/applications, kiểm tra entry tồn tại
     → backup path cũ
     → set path .s3 / .elf
     → download() (tiến trình, cancel, timeout)
     → reset + halt (hoặc run)
     → DONE
   lỗi ở set path / download → rollback path cũ → báo lỗi
```

Mỗi bước là một trạng thái hiển thị trên GUI (stepper/status bar).

## 7. Logging & debug từ xa

- **Log panel**: màu theo level, lọc DEBUG/INFO/WARN/ERROR, nút Copy và Clear, tự cuộn tới lỗi, popup tóm tắt khi có lỗi.
- **Log file**: `%LOCALAPPDATA%/WFlash/logs/wflash_YYYYMMDD_HHMMSS.log` (macOS: `~/Library/Logs/WFlash/`), luôn ghi ở mức DEBUG, giữ 20 file gần nhất.
- **Export debug bundle** (zip):
  - log của phiên hiện tại và traceback đầy đủ
  - thông tin môi trường: OS, Python, PySide6, `isystem.connect`, version winIDEA, workspace path
  - profile đang dùng, bảng mapping
  - dump option download/symbol đọc được từ workspace **trước và sau** khi sửa
- **Che dữ liệu nhạy cảm**: filter logging thay PAT và header `PRIVATE-TOKEN` bằng `***` trong mọi log và bundle.
- **Verbose mode**: log mọi lời gọi `isystem.connect` kèm tham số và kết quả.

## 8. Xử lý lỗi

- Exception theo tầng: `GitLabError`, `ArtifactError`, `MappingError`, `WinIDEAError`, `FlashError`. GUI hiển thị thông điệp ngắn kèm gợi ý xử lý, chi tiết nằm trong log.
- Rollback path workspace khi set path hoặc download thất bại.
- `sys.excepthook` và `threading.excepthook` bắt lỗi không lường trước → ghi log + dialog, không crash im lặng.
- Lỗi GitLab thường gặp có gợi ý riêng: 401 (PAT sai/hết hạn), 403 (thiếu quyền), 404 (artifact đã hết hạn), lỗi SSL (cert nội bộ — cho phép cấu hình CA bundle).

## 9. Phase 0 — Spike trên Windows

Script trong `spike/`, chạy trên máy Windows có winIDEA 9.21 + workspace SAF85xx, mỗi script ghi kết quả ra file text để gửi lại:

1. `01_connect.py`: liệt kê instance winIDEA, connect, in version và workspace path.
2. `02_dump_options.py`: dump cây option liên quan download/symbol files, Applications, Programs.
3. `03_set_paths.py`: đổi path của một entry `.s3` và một entry `.elf`, đọc lại để xác nhận, rồi khôi phục.
4. `04_download.py`: gọi `download()` với path hiện tại, đo thời gian, ghi lại cách đọc tiến trình và trạng thái.
5. `05_reset.py`: reset + halt và kiểm tra trạng thái các core.

Kết quả spike chốt interface `WinIDEAAdapter` và tên entry thật trong profile.

## 10. Testing

- pytest cho `core/`:
  - `profile` (schema hợp lệ/không hợp lệ)
  - `file_matcher` (glob, match 0 file, match nhiều file)
  - `artifact_cache` (hit/miss, giới hạn số job, xóa)
  - `gitlab_client` (mock HTTP bằng `responses`)
  - `flash_workflow` với `FakeWinIDEAAdapter`, gồm các nhánh rollback và timeout
  - filter che token
- pytest-qt: smoke test cửa sổ chính, log panel, luồng flash với fake adapter.
- Adapter thật: checklist kiểm tra thủ công trên Windows (connect, set path, download, reset, rollback khi lỗi).

## 11. Đóng gói

- `pyproject.toml` (Python 3.11+), dependency: `PySide6`, `requests`, `pydantic`, `PyYAML`, `keyring`; `isystem.connect` là dependency tùy chọn chỉ trên Windows.
- PyInstaller spec tạo `.exe` một thư mục (onedir) cho Windows.
