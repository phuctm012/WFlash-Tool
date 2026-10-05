# WFlash Tool

Tool desktop (Python + PySide6) để flash ECU **NXP SAF85xx** qua **winIDEA 9.21** (`isystem.connect`):
chọn artifact từ GitLab CI, tự map file `.s3`/`.elf` vào workspace winIDEA đang mở, download vào external flash Winbond, reset + halt.

> Trạng thái: GUI, GitLab, cache, mapping, workflow (kèm rollback) và log đã chạy với **fake adapter**.
> Adapter winIDEA thật (Plan 2) sẽ được viết sau khi có kết quả spike (`spike/README.md`).
> Toàn bộ các bước cần thử trên Windows và cách gửi kết quả: `docs/windows_test_guide.md`.

## Chạy từ source

macOS (dev, fake adapter) — venv nằm **ngoài** OneDrive:

    python3 -m venv ~/.venvs/wflash          # Python 3.11 trở lên
    ~/.venvs/wflash/bin/pip install -e ".[dev]"
    ~/.venvs/wflash/bin/python -m wflash --adapter fake

Windows với conda (Miniforge), cách khuyến nghị: xem `docs/windows_test_guide.md` Phần 0 (`conda create -n wflash python=3.12`, `conda activate wflash`, `python -m pip install -e ".[dev]"`; chọn version Python khớp wheel `isystem.connect`). `scripts\build_windows.bat` dùng env conda đang active.

Windows với venv (Python cùng bitness với winIDEA, thường là 64-bit):

    py -3 -m venv %USERPROFILE%\.venvs\wflash
    %USERPROFILE%\.venvs\wflash\Scripts\python -m pip install -e ".[dev]"
    %USERPROFILE%\.venvs\wflash\Scripts\python -m wflash            (mặc định --adapter real: chưa dùng được, xem lưu ý dưới)
    %USERPROFILE%\.venvs\wflash\Scripts\python -m wflash --adapter fake

> **Lưu ý:** adapter winIDEA thật **chưa có** (Plan 2, viết sau spike), nên chạy `python -m wflash` không tham số (mặc định `--adapter real`) hiện sẽ báo lỗi. Tạm thời dùng `python -m wflash --adapter fake`. Với bản `WFlash.exe` đã build, tạo shortcut với tham số `--adapter fake` (Target: `...\WFlash.exe --adapter fake`).

`isystem.connect` **không** cài từ PyPI: cài từ thư mục cài đặt winIDEA 9.21 (xem `spike/README.md`) để version khớp với winIDEA.

Cũng có thể chạy bằng file `main.py` ở thư mục gốc repo (cùng app, cùng tham số; chạy được cả khi đứng ở thư mục khác):

    ~/.venvs/wflash/bin/python main.py --adapter fake                          (macOS)
    %USERPROFILE%\.venvs\wflash\Scripts\python main.py --adapter fake          (Windows)

Tham số: `--adapter real|fake`, `--verbose` (log mọi lời gọi winIDEA), `--smoke` (mở rồi tự đóng sau 1,5 s, để kiểm tra khởi động).

Fake adapter giả lập lỗi qua biến môi trường `WFLASH_FAKE_FAIL` (nối bằng dấu phẩy):
`list_instances` (không có instance), `connect`, `connection_lost`, `read_programs`, `read_applications`,
`set_path` (đổi path bị từ chối — cả lúc rollback, nên GUI hiện cảnh báo ROLLBACK FAILED), `download` (lỗi ở 50%), `reset`.
`WFLASH_FAKE_DOWNLOAD_S=10` đổi thời gian download giả lập.

## Cấu hình

1. **Load from GitLab…** (popup, mở từ vùng *Setting*): GitLab URL, Personal Access Token (scope `read_api`, lưu trong Windows Credential Manager / keychain, không bao giờ ghi ra file), ô **Verify TLS certificate** (mặc định bật; chỉ tắt khi ở mạng tin cậy — app ghi một dòng WARNING mỗi phiên), CA bundle nếu GitLab dùng chứng chỉ nội bộ.
2. **Preferences…**: thư mục cache + số bản tải giữ lại + nút **Clear cache** (xóa cả artifact CI lẫn package), thư mục profile, verbose, **Dark mode** (áp dụng ngay và được lưu lại).
3. **Profile** (`profiles/*.yaml`): project GitLab, filter tên job, tên entry download và tên Application trong winIDEA, pattern file. Xem `profiles/saf85xx_example.yaml`.

## Giao diện

- Một cửa sổ duy nhất. Phần đầu: nút **Flash** lớn (khi đang flash, chính nút đó thành **Cancel** màu đỏ), thanh tiến trình, nhãn `phần trăm | ETA | Speed` và `Step: …`.
- Vùng **Setting** (trái): profile, nguồn firmware (**Load from GitLab…** và thẻ cho biết đang dùng artifact/package nào), instance winIDEA, Reset/Run sau khi flash, **Preferences…**.
- Bảng mapping (phải) có cột `#`; dòng đỏ là dòng chưa có file. Dưới cùng là tab **Information** (log). Thanh trạng thái hiện version và tác giả.
- Theme **Teal** sáng (mặc định) hoặc tối. Speed/ETA chỉ là **ước lượng**: winIDEA chỉ báo phần trăm, còn số byte lấy từ kích thước file `.s3` trên đĩa.

## Quy trình

1. Chọn profile → **Load from GitLab…**:
   - Tab **CI Artifact**: project (mặc định lấy từ profile; sửa thì app nhớ theo từng profile) → **Load branches/tags** → chọn branch/tag → **Browse jobs…** rồi bấm **Download** ở dòng muốn tải (hoặc nhấp đúp), hoặc bấm **Download Selected Artifact**: tải job đang chọn, nếu chưa chọn dòng nào thì tải job thành công mới nhất khớp branch/tag + job name.
   - Tab **Package Registry**: project + tên package → **Fetch Latest Version**, hoặc **Browse versions…** rồi tải một version (file đầu tiên của version; zip được giải nén, file thường được giữ nguyên).
   - **Stop** hủy lần tải đang chạy (popup vẫn mở); **Cancel** hủy rồi đóng popup. Tải xong popup tự đóng, cửa sổ chính dựng bảng mapping. Có cache theo job/version (nút ghi **Cached**).
2. Kiểm tra bảng mapping; dòng đỏ (0 hoặc nhiều file khớp) phải chọn file thủ công — nút Flash chỉ bật khi mọi dòng đã có file.
3. Chọn instance winIDEA đang mở → **Flash**. Lỗi hoặc **Cancel** trong lúc đổi path/download sẽ khôi phục đường dẫn cũ trong workspace. Nếu chính việc khôi phục thất bại, cửa sổ hiện dải đỏ **ROLLBACK FAILED**: kiểm tra lại danh sách download/symbol file trong winIDEA trước khi flash tiếp.
4. Đóng cửa sổ khi đang flash: tool hỏi xác nhận, hủy flash, chờ rollback xong rồi mới đóng.

## Log và gửi lỗi

- Tab **Information** ở dưới cửa sổ (màu theo level và theo theme, lọc level, Copy, Clear). Popup GitLab có ô **GitLab log** riêng; các dòng đó cũng nằm trong log file.
- Log file: `%LOCALAPPDATA%\WFlash\logs\` (Windows), `~/Library/Logs/WFlash/` (macOS), giữ 20 file gần nhất.
- **Export debug bundle…**: tạo `wflash_debug_<thời gian>.zip` gồm log, môi trường, profile, mapping, nguồn firmware (`source.json`), trạng thái workspace trước/sau và traceback. Token đã được che (`***`). Không xuất được trong lúc đang flash.

## Phát triển

- Layout GUI nằm trong các file Qt Designer `wflash/gui/main_window.ui`, `wflash/gui/gitlab_dialog.ui`, `wflash/gui/preferences_dialog.ui`. Sau khi sửa `.ui`:

      ~/.venvs/wflash/bin/pyside6-uic wflash/gui/main_window.ui -o wflash/gui/ui_main_window.py
      ~/.venvs/wflash/bin/pyside6-uic wflash/gui/gitlab_dialog.ui -o wflash/gui/ui_gitlab_dialog.py
      ~/.venvs/wflash/bin/pyside6-uic wflash/gui/preferences_dialog.ui -o wflash/gui/ui_preferences_dialog.py

  Không sửa tay `ui_*.py`.
- Theme: `wflash/resources/style.qss` (sáng) và `style_dark.qss` (tối) dùng đúng các màu trong `wflash/gui/theme.py` (`THEMES`); sửa màu thì sửa cả ba.
- Test:

      ~/.venvs/wflash/bin/pytest -q
      ~/.venvs/wflash/bin/pytest -k thread -v        # vòng đời worker — không bao giờ bỏ qua
      ~/.venvs/wflash/bin/pytest -k "not gui" -q     # chỉ core
      ~/.venvs/wflash/bin/python tools/stress_test.py   # stress test headless, in STRESS_RESULT=PASS/FAIL

## Build .exe (Windows)

    scripts\build_windows.bat

Script chạy toàn bộ test, `-k thread`, stress test rồi PyInstaller. Kết quả: `dist\WFlash\WFlash.exe` (copy cả thư mục `dist\WFlash`; thư mục `wflash\resources` chứa theme đã được gói kèm).
