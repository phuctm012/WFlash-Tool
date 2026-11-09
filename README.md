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

Tham số: `--adapter real|fake`, `--verbose` (không cần nữa: lời gọi winIDEA luôn được ghi vào log file), `--smoke` (mở rồi tự đóng sau 1,5 s, để kiểm tra khởi động).

Fake adapter giả lập lỗi qua biến môi trường `WFLASH_FAKE_FAIL` (nối bằng dấu phẩy):
`list_instances` (không có instance), `connect`, `connection_lost`, `read_programs`, `read_applications`,
`set_path` (đổi path bị từ chối — cả lúc rollback, nên GUI hiện cảnh báo ROLLBACK FAILED), `download` (lỗi ở 50%), `reset`, `verify` (so mẫu flash lỗi), `no_cancel` (download không hủy được, giống adapter thật).
`WFLASH_FAKE_DOWNLOAD_S=10` đổi thời gian download giả lập.

## Cấu hình

Mọi cài đặt nằm ở tab **Setting** (không còn popup Preferences) và được lưu ngay khi rời ô:

1. **Profile**: chọn profile (**Reload** đọc lại thư mục), **Profiles folder** (Browse), **Download folder** (để trống = mặc định `%LOCALAPPDATA%\WFlash\cache`; app giữ 10 bản tải gần nhất).
2. **GitLab connection**: **GitLab URL** gồm cả group (ví dụ `https://gitlab.hella.com/alm/projects_group/e-ad_group/e-ad_radar_cust_suz05_group`; profile có thể cho sẵn URL này) và **Access token** (scope `read_api`, lưu trong Windows Credential Manager / keychain theo host, không bao giờ ghi ra file). Chứng chỉ HTTPS luôn được kiểm tra theo kho chứng chỉ của Windows (thư viện `truststore`), nên chứng chỉ nội bộ mà IT đã cài vào Windows dùng được ngay.
3. **winIDEA**: instance (**Refresh**, hoặc F5) và **After flash**: Reset target, Run after reset, Verify samples.
4. **Profile** (`profiles/*.yaml`): project GitLab (tên ngắn thì được ghép với group trong GitLab URL), filter tên job, pattern file, và tên đích trong winIDEA. `winidea_entry` là tên file của dòng đang tick trong Download Files của thiết bị flash; `winidea_app` là `<Application>/<tên file symbol>`. File trong artifact phải trùng tên với file đang cấu hình. Nếu các file nằm ở nhiều artifact, khai báo `sources` và ghi `source` cho từng đích: tab Flash có một nút Load cho mỗi nguồn, mỗi dòng mapping chỉ thấy file của nguồn đó, và Flash chỉ bật khi đủ mọi nguồn. Hai artifact CI khác commit thì app hiện cảnh báo nhưng vẫn cho flash. Xem `profiles/suz05.yaml`.

Mở lại app thì mọi thứ của phiên trước được khôi phục: profile, repo, chế độ Firmware và job chọn tay của từng phần, Advanced Debug, After flash, kích thước cửa sổ, tab đang mở. Firmware theo commit được tải lại (hoặc lấy từ cache); app **không bao giờ tự flash**.

## Giao diện

- Một cửa sổ duy nhất. Phần đầu: nút **Flash** lớn (khi đang flash, chính nút đó thành **Cancel** màu đỏ), thanh tiến trình, nhãn `phần trăm | ETA | Speed` và `Step: …`. Thanh này cũng hiện tiến trình tải artifact và checkout; xong thì kết quả flash trước đó hiện lại.
- Thanh menu: **File** (Export debug bundle Ctrl+E, Open flash history, Open log folder, Open download folder, Exit Ctrl+Q), **View** (Dark mode, Flash/GitLab/Setting Ctrl+1/2/3), **Tools** (Test GitLab connection, Check winIDEA cores — chỉ đọc, Refresh winIDEA instances F5), **Help** (User Guide F1 — hướng dẫn HTML tiếng Anh, About WFlash).
- Ba tab, phần đầu và tab Information dùng chung:
  - **Flash** (việc hằng ngày): khung **Firmware to flash** (mỗi phần một khối: From commit/Manual, Build/Job, Branch, Commit, Status; dòng Advanced Debug on/off), hoặc **Load from GitLab…** với profile không có `builds`; hai bảng file bên phải.
  - **GitLab** (chỉ với profile có `builds`): App, Boot Manager, Flash Bootloader — xem mục dưới.
  - **Setting**: xem mục Cấu hình.
- Hai bảng của tab Flash: **Program Files** (cột Offset) và **Symbol Files**, mỗi bảng có cột `#` và cột Source (FFI, CAL, BM, FBL, ELF…); dòng đỏ là dòng chưa có file. Thanh trạng thái hiện version và tác giả.
- Theme **Teal** sáng (mặc định) hoặc tối (View → Dark mode). Speed/ETA chỉ là **ước lượng**: winIDEA chỉ báo phần trăm, còn số byte lấy từ kích thước file `.s3` trên đĩa.
- Khi cửa sổ không được chọn: flash xong (Done/Failed/Cancelled) hoặc firmware đã sẵn sàng sau khi chờ pipeline thì app hiện thông báo khay hệ thống và nháy nút trên taskbar.

## Quy trình

1. Chọn profile → **Load from GitLab…**:
   - Project (mặc định lấy từ profile; sửa thì app nhớ theo từng profile) → **Load branches/tags** → chọn branch/tag → **Browse jobs…** rồi bấm **Download** ở dòng muốn tải (hoặc nhấp đúp), hoặc bấm **Download Selected Artifact**: tải job đang chọn, nếu chưa chọn dòng nào thì tải job thành công mới nhất khớp branch/tag + job name.
   - **Stop** hủy lần tải đang chạy (popup vẫn mở); **Cancel** hủy rồi đóng popup. Tải xong popup tự đóng, cửa sổ chính dựng bảng mapping. Có cache theo job/version (nút ghi **Cached**).
2. Kiểm tra bảng mapping; dòng đỏ (0 hoặc nhiều file khớp) phải chọn file thủ công — nút Flash chỉ bật khi mọi dòng đã có file.
3. Chọn instance winIDEA đang mở (tab Setting) → **Flash**. Lỗi hoặc **Cancel** trong lúc đổi path/download sẽ khôi phục đường dẫn cũ trong workspace. Nếu chính việc khôi phục thất bại, cửa sổ hiện dải đỏ **ROLLBACK FAILED**: kiểm tra lại danh sách download/symbol file trong winIDEA trước khi flash tiếp.
4. Đóng cửa sổ khi đang flash: tool hỏi xác nhận, hủy flash, chờ rollback xong rồi mới đóng.
5. Mỗi lần flash ghi một dòng vào `%LOCALAPPDATA%\WFlash\flash_history.csv` (thời gian, profile, firmware từng phần, số lần reset/thử, thời gian lập trình, kết quả; giữ 5000 dòng). Mở bằng File → Open flash history; file cũng nằm trong debug bundle.

## Tab GitLab (profile có `builds`)

Profile khai báo `builds` (ví dụ `profiles/suz05.yaml`) thì có tab **GitLab** với ba phần: **App** (bắt buộc), **Boot Manager** và **Flash Bootloader** (repo không bắt buộc, chỉ hiện khi bật **Advanced Debug**). Mỗi phần có:

1. **Project** (tên ngắn, ghép với group trong GitLab URL) và **Repository** (thư mục gốc của source, git; Browse). App hiện **Branch** (nút **Checkout**) và **Commit** (nút **Reload**), cảnh báo nếu có thay đổi chưa commit (chỉ cảnh báo). App đọc lại repo khi bấm Reload và mỗi khi bạn quay lại cửa sổ WFlash.
2. **Checkout**: chọn branch hoặc commit, kèm trạng thái pipeline. Ô Branch cho gõ một phần tên để lọc. App **từ chối** checkout khi repo có thay đổi chưa commit, và không bao giờ stash, reset hay force. **Fetch** chỉ chạy `git fetch --prune`.
3. **Build**: App chọn cấu hình build; job của Boot Manager đi theo build của App, job của Flash Bootloader lấy từ profile.
4. **Firmware**: ◉ **From checked-out commit** — app tự tìm pipeline của đúng commit, tải job vào cache `cache/<branch>/<commit>_<build>/…`. Pipeline còn đang chạy (created, pending, running…) thì app chờ, hỏi lại mỗi 30 giây, tối đa 60 phút, và không tải trong lúc đang flash. Job `manual`, `skipped`, `failed` thì báo một lần, không tự thử lại cho tới khi bấm Reload. ○ **Manual** — **Choose Job** mở Load from GitLab cho phần đó; lựa chọn được nhớ qua lần mở app sau.
5. Dòng trạng thái: `<ROLE>: <job> · <branch> · <commit> · Cached|Downloaded`.

**CAL** bắt buộc, lấy từ thư mục chứa file `.xjrf` của workspace; không có thì Flash bị khóa. Advanced Debug bật thì app tick dòng `.bin` và ELF của BM, FBL trong workspace; tắt thì bỏ tick và **giữ nguyên trạng thái đó sau khi flash**. Thứ tự trong workspace là FFI → CAL → BM → FBL; BM và FBL ghi đè lên vùng của FFI. Khi flash lỗi, app trả lại đường dẫn cũ nhưng giữ dấu tick đã đặt.

## Log và gửi lỗi

- Tab **Information** ở dưới cửa sổ: hiện INFO, WARNING, ERROR (màu theo level và theo theme), không có bộ lọc level; DEBUG chỉ ghi vào log file và debug bundle. Copy chép đúng các dòng đang hiện, Clear xóa khung. Popup GitLab có ô **GitLab log** riêng; các dòng đó cũng nằm trong log file. Mọi lời gọi winIDEA luôn được ghi vào log file (không còn tùy chọn Verbose).
- Log file: `%LOCALAPPDATA%\WFlash\logs\` (Windows), `~/Library/Logs/WFlash/` (macOS), giữ 20 file gần nhất.
- **File → Export debug bundle** (Ctrl+E): tạo `wflash_debug_<thời gian>.zip` gồm log, môi trường, profile, mapping, nguồn firmware (`source.json`), trạng thái workspace trước/sau, flash history và traceback. Token đã được che (`***`). Không xuất được trong lúc đang flash.

## Phát triển

- Layout GUI nằm trong các file Qt Designer `wflash/gui/main_window.ui`, `wflash/gui/gitlab_dialog.ui`, `wflash/gui/checkout_dialog.ui`. Sau khi sửa `.ui`:

      ~/.venvs/wflash/bin/pyside6-uic wflash/gui/main_window.ui -o wflash/gui/ui_main_window.py
      ~/.venvs/wflash/bin/pyside6-uic wflash/gui/gitlab_dialog.ui -o wflash/gui/ui_gitlab_dialog.py
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

Script chạy toàn bộ test, `-k thread`, stress test rồi PyInstaller. Kết quả: `dist\WFlash\WFlash.exe` (copy cả thư mục `dist\WFlash`; thư mục `wflash\resources` chứa theme và icon đã được gói kèm). `WFlash.exe` mang icon `wflash\resources\icons\wflash_chip_teal.ico`; khi chạy, mọi cửa sổ dùng icon đó (bản `.svg` cho kích thước lớn).
