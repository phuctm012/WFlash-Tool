# WFlash Tool

Tool desktop (Python + PySide6) để flash ECU **NXP SAF85xx** qua **winIDEA 9.21** (`isystem.connect`):
chọn artifact từ GitLab CI, tự map file `.s3`/`.elf` vào workspace winIDEA đang mở, download vào external flash Winbond, reset + halt.

> Trạng thái: GUI, GitLab, cache, mapping, workflow (kèm rollback) và log đã chạy với **fake adapter**.
> Adapter winIDEA thật (Plan 2) sẽ được viết sau khi có kết quả spike (`spike/README.md`).

## Chạy từ source

macOS (dev, fake adapter) — venv nằm **ngoài** OneDrive:

    python3 -m venv ~/.venvs/wflash          # Python 3.11 trở lên
    ~/.venvs/wflash/bin/pip install -e ".[dev]"
    ~/.venvs/wflash/bin/python -m wflash --adapter fake

Windows (Python cùng bitness với winIDEA, thường là 64-bit):

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

1. **Settings…**: GitLab URL, Personal Access Token (scope `read_api`, lưu trong Windows Credential Manager / keychain, không bao giờ ghi ra file), CA bundle nếu GitLab dùng chứng chỉ nội bộ, thư mục cache + số job giữ lại + nút **Clear cache**, thư mục profile, verbose.
2. **Profile** (`profiles/*.yaml`): project GitLab, filter tên job, tên entry download và tên Application trong winIDEA, pattern file. Xem `profiles/saf85xx_example.yaml`.

## Quy trình

1. Chọn profile → **Refresh** → chọn branch/tag → pipeline → job → **Download artifact** (có cache theo job, **Cancel** để hủy).
2. Kiểm tra bảng mapping; dòng đỏ (0 hoặc nhiều file khớp) phải chọn file thủ công — nút Flash chỉ bật khi mọi dòng đã có file.
3. Chọn instance winIDEA đang mở → **Flash**. Lỗi hoặc **Cancel** trong lúc đổi path/download sẽ khôi phục đường dẫn cũ trong workspace. Nếu chính việc khôi phục thất bại, cửa sổ hiện dòng đỏ **ROLLBACK FAILED**: kiểm tra lại danh sách download/symbol file trong winIDEA trước khi flash tiếp.
4. Đóng cửa sổ khi đang flash: tool hỏi xác nhận, hủy flash, chờ rollback xong rồi mới đóng.

## Log và gửi lỗi

- Log panel ở dưới cửa sổ (màu theo level, lọc level, Copy, Clear).
- Log file: `%LOCALAPPDATA%\WFlash\logs\` (Windows), `~/Library/Logs/WFlash/` (macOS), giữ 20 file gần nhất.
- **Export debug bundle…**: tạo `wflash_debug_<thời gian>.zip` gồm log, môi trường, profile, mapping, trạng thái workspace trước/sau và traceback. Token đã được che (`***`). Không xuất được trong lúc đang flash.

## Phát triển

- Layout GUI nằm trong `wflash/gui/main_window.ui` và `wflash/gui/settings_dialog.ui` (Qt Designer). Sau khi sửa `.ui`:

      ~/.venvs/wflash/bin/pyside6-uic wflash/gui/main_window.ui -o wflash/gui/ui_main_window.py
      ~/.venvs/wflash/bin/pyside6-uic wflash/gui/settings_dialog.ui -o wflash/gui/ui_settings_dialog.py

  Không sửa tay `ui_*.py`.
- Test:

      ~/.venvs/wflash/bin/pytest -q
      ~/.venvs/wflash/bin/pytest -k thread -v        # vòng đời worker — không bao giờ bỏ qua
      ~/.venvs/wflash/bin/pytest -k "not gui" -q     # chỉ core
      ~/.venvs/wflash/bin/python tools/stress_test.py   # stress test headless, in STRESS_RESULT=PASS/FAIL

## Build .exe (Windows)

    scripts\build_windows.bat

Script chạy toàn bộ test, `-k thread`, stress test rồi PyInstaller. Kết quả: `dist\WFlash\WFlash.exe` (copy cả thư mục `dist\WFlash`).
