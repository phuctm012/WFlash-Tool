# WFlash Tool

Tool desktop (Python + PySide6) để flash ECU **NXP SAF85xx** qua **winIDEA 9.21** (`isystem.connect`):
chọn artifact từ GitLab CI, tự map file `.s3`/`.elf` vào workspace winIDEA đang mở, download vào external flash Winbond, reset + halt.

> Trạng thái: adapter winIDEA thật đã viết theo kết quả spike (`docs/winidea_api_notes.md`) nhưng **chưa chạy thử trọn luồng trên ECU**. Các bước thử trên Windows và cách gửi kết quả: `docs/windows_test_guide.md`, mục "Vòng 7".

## Chạy từ source

macOS (dev, fake adapter) — venv nằm **ngoài** OneDrive:

    python3 -m venv ~/.venvs/wflash          # Python 3.11 trở lên
    ~/.venvs/wflash/bin/pip install -e ".[dev]"
    ~/.venvs/wflash/bin/python -m wflash --adapter fake

Windows với conda (Miniforge), cách khuyến nghị: xem `docs/windows_test_guide.md` Phần 0 (`conda create -n wflash python=3.12`, `conda activate wflash`, `python -m pip install -e ".[dev]"`; chọn version Python khớp wheel `isystem.connect`). `scripts\build_windows.bat` dùng env conda đang active.

Windows với venv (Python cùng bitness với winIDEA, thường là 64-bit):

    py -3 -m venv %USERPROFILE%\.venvs\wflash
    %USERPROFILE%\.venvs\wflash\Scripts\python -m pip install -e ".[dev]"
    %USERPROFILE%\.venvs\wflash\Scripts\python -m wflash            (mặc định --adapter real)
    %USERPROFILE%\.venvs\wflash\Scripts\python -m wflash --adapter fake

> **Lưu ý khi flash thật:** chỉ mở một winIDEA, với đúng workspace đã chọn; nếu khác, tool báo lỗi và không flash. Tùy chọn mass erase theo cấu hình workspace. Cancel bị khóa từ lúc bắt đầu lập trình (khoảng 100 s), vì dừng giữa lúc xóa có thể để lại ECU trống. Không có winIDEA thì dùng `--adapter fake`.

`isystem.connect` **không** cài từ PyPI: cài từ thư mục cài đặt winIDEA 9.21 (xem `spike/README.md`) để version khớp với winIDEA.

Cũng có thể chạy bằng file `main.py` ở thư mục gốc repo (cùng app, cùng tham số; chạy được cả khi đứng ở thư mục khác):

    ~/.venvs/wflash/bin/python main.py --adapter fake                          (macOS)
    %USERPROFILE%\.venvs\wflash\Scripts\python main.py --adapter fake          (Windows)

Tham số: `--adapter real|fake`, `--verbose` (log mọi lời gọi winIDEA), `--smoke` (mở rồi tự đóng sau 1,5 s, để kiểm tra khởi động).

Fake adapter giả lập lỗi qua biến môi trường `WFLASH_FAKE_FAIL` (nối bằng dấu phẩy):
`list_instances` (không có instance), `connect`, `connection_lost`, `read_programs`, `read_applications`,
`set_path` (đổi path bị từ chối — cả lúc rollback, nên GUI hiện cảnh báo ROLLBACK FAILED), `download` (lỗi ở 50%), `reset`, `verify` (so mẫu flash lỗi), `no_cancel` (download không hủy được, giống adapter thật).
`WFLASH_FAKE_DOWNLOAD_S=10` đổi thời gian download giả lập.

## Cấu hình

1. **Load from GitLab…** (popup, mở từ tab *Flash*): GitLab URL, Personal Access Token (scope `read_api`, lưu trong Windows Credential Manager / keychain, không bao giờ ghi ra file), ô **Verify TLS certificate** (mặc định bật; chỉ tắt khi ở mạng tin cậy — app ghi một dòng WARNING mỗi phiên). Chứng chỉ được kiểm tra theo kho chứng chỉ của Windows (thư viện `truststore`), nên chứng chỉ nội bộ mà IT đã cài vào Windows dùng được ngay, không cần file CA bundle.
2. **Preferences…**: thư mục cache + số bản tải giữ lại + nút **Clear cache** thư mục profile, verbose, **Dark mode** (áp dụng ngay và được lưu lại).
3. **Profile** (`profiles/*.yaml`): project GitLab, filter tên job, pattern file, và tên đích trong winIDEA. `winidea_entry` là tên file của dòng đang tick trong Download Files của thiết bị flash; `winidea_app` là `<Application>/<tên file symbol>`. File trong artifact phải trùng tên với file đang cấu hình. Nếu các file nằm ở nhiều artifact, khai báo `sources` và ghi `source` cho từng đích: tab Flash có một nút Load cho mỗi nguồn, mỗi dòng mapping chỉ thấy file của nguồn đó, và Flash chỉ bật khi đủ mọi nguồn. Hai artifact CI khác commit thì app hiện cảnh báo nhưng vẫn cho flash. Xem `profiles/suz05_m7_ffi.yaml`.

## Giao diện

- Một cửa sổ duy nhất. Phần đầu: nút **Flash** lớn (khi đang flash, chính nút đó thành **Cancel** màu đỏ), thanh tiến trình, nhãn `phần trăm | ETA | Speed` và `Step: …`.
- Hai tab **Flash** và **Setting**, phần đầu và tab Information dùng chung cho cả hai.
  - **Flash** (việc hằng ngày): nguồn firmware (**Load from GitLab…** và thẻ cho biết đang dùng artifact nào; hoặc panel developer) bên trái, hai bảng file bên phải.
  - **Setting**: profile, source repo (Browse, **Reload**, **Checkout…**), instance winIDEA, Reset/Run/Verify sau khi flash, **Preferences…**. Trang cuộn được, thêm cài đặt sau này không làm tab Flash dài ra.
- Hai bảng bên phải tab Flash: **Program Files** (cột Offset) và **Symbol Files**, mỗi bảng có cột `#` và cột Source (FFI, CAL, BM, FBL, ELF…); dòng đỏ là dòng chưa có file. Dưới cùng là tab **Information** (log). Thanh trạng thái hiện version và tác giả.
- Theme **Teal** sáng (mặc định) hoặc tối. Speed/ETA chỉ là **ước lượng**: winIDEA chỉ báo phần trăm, còn số byte lấy từ kích thước file `.s3` trên đĩa.

## Quy trình

1. Chọn profile → **Load from GitLab…**:
   - Tab **CI Artifact**: project (mặc định lấy từ profile; sửa thì app nhớ theo từng profile) → **Load branches/tags** → chọn branch/tag → **Browse jobs…** rồi bấm **Download** ở dòng muốn tải (hoặc nhấp đúp), hoặc bấm **Download Selected Artifact**: tải job đang chọn, nếu chưa chọn dòng nào thì tải job thành công mới nhất khớp branch/tag + job name.
   - **Stop** hủy lần tải đang chạy (popup vẫn mở); **Cancel** hủy rồi đóng popup. Tải xong popup tự đóng, cửa sổ chính dựng bảng mapping. Có cache theo job/version (nút ghi **Cached**).
2. Kiểm tra bảng mapping; dòng đỏ (0 hoặc nhiều file khớp) phải chọn file thủ công — nút Flash chỉ bật khi mọi dòng đã có file.
3. Chọn instance winIDEA đang mở → **Flash**. Lỗi hoặc **Cancel** trong lúc đổi path/download sẽ khôi phục đường dẫn cũ trong workspace. Nếu chính việc khôi phục thất bại, cửa sổ hiện dải đỏ **ROLLBACK FAILED**: kiểm tra lại danh sách download/symbol file trong winIDEA trước khi flash tiếp.
4. Đóng cửa sổ khi đang flash: tool hỏi xác nhận, hủy flash, chờ rollback xong rồi mới đóng.

## Chế độ developer (profile có `builds`)

Profile khai báo `builds` (ví dụ `profiles/suz05_m7_ffi.yaml`) thì tab Flash thay nút Load from GitLab bằng panel developer, còn Source repo và Checkout nằm ở tab Setting:

1. **Source repo** (tab Setting): chọn thư mục gốc của source (git). App hiện branch, commit và cảnh báo nếu có thay đổi chưa commit (chỉ cảnh báo, vẫn cho tải và flash). App đọc lại repo khi bấm **Reload** và mỗi khi bạn quay lại cửa sổ WFlash (ví dụ vừa commit hay đổi branch trong terminal).
2. **Checkout…**: chọn branch hoặc commit, kèm trạng thái pipeline trên GitLab. Ô Branch cho gõ một phần tên để lọc danh sách (không phân biệt hoa thường); Enter để chọn. App **từ chối** checkout khi repo có thay đổi chưa commit, và không bao giờ stash, reset hay force. **Fetch** chỉ chạy `git fetch --prune`.
3. **Application**: chọn Build (cấu hình), bấm **Load firmware for <commit>**: app tìm pipeline của đúng commit đó, tải job FFI và job ELF của build vào cache `cache/<branch>/<commit>_<build>/FFI|ELF`. Commit chưa có pipeline, hoặc job chưa chạy (`manual`, `skipped`) thì app báo rõ. **Choose job in GitLab…** cho phép chọn job bằng tay.
4. **CAL**: bắt buộc, lấy từ thư mục chứa file `.xjrf` của workspace. Không có thì Flash bị khóa.
5. **Advanced Debug**: thêm dòng BM và FBL (repo riêng trong `debug_sources`, tải bằng nút Load của từng dòng). Bật thì app tick dòng `.bin` và ELF của BM, FBL trong workspace; tắt thì bỏ tick và **giữ nguyên trạng thái đó sau khi flash**. BM lấy từ job khác với job của Build thì Flash bị khóa.

Thứ tự trong workspace là FFI → CAL → BM → FBL; BM và FBL ghi đè lên vùng của FFI. Khi flash lỗi, app trả lại đường dẫn cũ nhưng giữ dấu tick đã đặt.

## Log và gửi lỗi

- Tab **Information** ở dưới cửa sổ: hiện INFO, WARNING, ERROR (màu theo level và theo theme), không có bộ lọc level; DEBUG chỉ ghi vào log file và debug bundle. Copy chép đúng các dòng đang hiện, Clear xóa khung. Popup GitLab có ô **GitLab log** riêng; các dòng đó cũng nằm trong log file.
- Log file: `%LOCALAPPDATA%\WFlash\logs\` (Windows), `~/Library/Logs/WFlash/` (macOS), giữ 20 file gần nhất.
- **Export debug bundle…**: tạo `wflash_debug_<thời gian>.zip` gồm log, môi trường, profile, mapping, nguồn firmware (`source.json`), trạng thái workspace trước/sau và traceback. Token đã được che (`***`). Không xuất được trong lúc đang flash.

## Phát triển

- Layout GUI nằm trong các file Qt Designer `wflash/gui/main_window.ui`, `wflash/gui/gitlab_dialog.ui`, `wflash/gui/preferences_dialog.ui`, `wflash/gui/checkout_dialog.ui`. Sau khi sửa `.ui`:

      ~/.venvs/wflash/bin/pyside6-uic wflash/gui/main_window.ui -o wflash/gui/ui_main_window.py
      ~/.venvs/wflash/bin/pyside6-uic wflash/gui/gitlab_dialog.ui -o wflash/gui/ui_gitlab_dialog.py
      ~/.venvs/wflash/bin/pyside6-uic wflash/gui/preferences_dialog.ui -o wflash/gui/ui_preferences_dialog.py
      ~/.venvs/wflash/bin/pyside6-uic wflash/gui/checkout_dialog.ui -o wflash/gui/ui_checkout_dialog.py

  Không sửa tay `ui_*.py`.
- Theme: `wflash/resources/style.qss` (sáng) và `style_dark.qss` (tối) dùng đúng các màu trong `wflash/gui/theme.py` (`THEMES`); sửa màu thì sửa cả ba.
- Test:

      ~/.venvs/wflash/bin/pytest -q
      ~/.venvs/wflash/bin/pytest -k thread -v        # vòng đời worker — không bao giờ bỏ qua
      ~/.venvs/wflash/bin/pytest -k "not gui" -q     # chỉ core
      ~/.venvs/wflash/bin/python tools/stress_test.py   # stress test headless, in STRESS_RESULT=PASS/FAIL

## Build .exe (Windows)

    scripts\build_windows.bat

Script chạy toàn bộ test, `-k thread`, stress test rồi PyInstaller. Kết quả: `dist\WFlash\WFlash.exe` (copy cả thư mục `dist\WFlash`; thư mục `wflash\resources` chứa theme và icon đã được gói kèm). `WFlash.exe` mang icon `wflash\resources\icons\wflash_probe_chip_teal.ico`; khi chạy, mọi cửa sổ dùng icon đó (bản `.svg` cho kích thước lớn).
