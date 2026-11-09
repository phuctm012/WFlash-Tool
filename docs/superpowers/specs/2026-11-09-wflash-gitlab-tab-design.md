# WFlash — Tab GitLab, Setting mới và menu bar — Design Spec

- Ngày: 2026-11-09
- Trạng thái: mockup đã được user duyệt qua từng chi tiết, chờ review spec
- Mockup: https://claude.ai/artifact/QEPKXTap9Ar3hosime1XjW, artboard 8–11 (hàng "GitLab tab: App, BM, FBL")
- Spec trước: `2026-11-07-wflash-developer-debug-design.md` (luồng developer), `2026-10-04-wflash-ui-redesign-design.md`
- Quy tắc an toàn và luồng: `CLAUDE.md`, `docs/winidea_api_notes.md`

## 1. Mục tiêu

1. Gom mọi thứ về nguồn firmware (repo, commit, build, cách chọn job) vào **một tab GitLab**, cho cả App, Boot Manager và Flash Bootloader.
2. Cho Boot Manager và Flash Bootloader cũng lấy firmware **theo commit của repo local**, như App, khi có repo.
3. Đưa cấu hình (kết nối GitLab, các thư mục, winIDEA) vào **tab Setting**; bỏ hộp Preferences.
4. Thêm **menu bar** cho các lệnh dùng chung.
5. Người dùng mới chọn profile là có sẵn GitLab URL và các project; mở lại app là gần như sẵn sàng flash.

**Phần flash không đổi**: `flash_workflow`, `flash_plan`, `RealWinIDEAAdapter.download` (kiểm tra core, thử lại, rollback) giữ nguyên như đã đạt trên ECU ở Vòng 10–12.

### Ngoài phạm vi

- Tự bấm Flash. WFlash chỉ tự **nạp** firmware, không bao giờ tự flash.
- Tự chạy job trên GitLab, tự stash/commit/reset repo (như spec 2026-11-07).
- Chọn file firmware từ máy, trừ CAL cạnh workspace.
- Đổi gì trong phần lập trình winIDEA.

## 2. Quyết định của user

| Chủ đề | Quyết định |
|---|---|
| Thứ tự tab | Flash \| GitLab \| Setting |
| Repo | App bắt buộc; Boot Manager và Flash Bootloader không bắt buộc |
| Cách chọn firmware | Mỗi phần một dòng **Firmware: ◉ From checked-out commit ○ Manual** và nút **Choose Job** |
| From checked-out commit | Sau Checkout, hoặc khi repo đổi commit (Reload, quay lại cửa sổ), tự tìm pipeline của commit và nạp artifact |
| Manual | Chọn job bằng popup như hiện nay |
| Không có repo | From checked-out commit bị mờ, Manual được chọn |
| Build của Boot Manager | Chỉ hiển thị, suy ra từ Build của App (`bm_job`) |
| Advanced Debug | Nút gạt trên tab GitLab; bật thì hiện Boot Manager, Flash Bootloader |
| Tiến trình | Tải artifact và Checkout hiện trên thanh tiến trình Flash |
| Tên | "Boot Manager", "Flash Bootloader" ở tiêu đề khung; BM/FBL ở chỗ hẹp; "Manual" thay "by hand"; nút "Checkout", "Choose Job" |
| GitLab URL | Gồm cả đường dẫn group; ô Project chỉ ghi tên ngắn |
| Verify TLS | Bỏ; luôn kiểm tra chứng chỉ (kho của Windows qua `truststore`) |
| Verbose | Bỏ ô; luôn ghi lệnh winIDEA vào log file |
| Preferences | Bỏ hộp thoại; nội dung chuyển vào tab Setting, có hiệu lực ngay |
| Download | Đổi tên từ Cache; để trống = thư mục mặc định; bỏ Clear downloads và Downloads to keep (vẫn tự giữ 10 bản) |
| Dark mode | Chỉ ở menu View |
| Menu Tools | Test GitLab connection, Check winIDEA cores, Refresh winIDEA instances (F5) |
| Menu Help | User Guide (F1): hướng dẫn tiếng Anh, HTML có hình minh họa, từng bước; About WFlash |
| Profile | File `profiles/suz05.yaml`, `name: SUZ05`; mặc định GitLab URL và Project lấy từ profile |
| Lưu cấu hình | Lưu toàn bộ lựa chọn; mở lại app thì khôi phục và tự nạp lại firmware |
| Ghi chú trên giao diện | Bỏ các dòng giải thích (gợi ý Verify, chứng chỉ, "Updated when…", v.v.) |

## 3. Giao diện

### 3.1 Khung chung

- **Menu bar** (trong `main_window.ui`):
  - **File:** Export debug bundle… (Ctrl+E), Open flash history, Open log folder, Open download folder, Exit (Ctrl+Q).
  - **View:** Dark mode (checkable), Flash / GitLab / Setting (Ctrl+1/2/3).
  - **Tools:** Test GitLab connection, Check winIDEA cores, Refresh winIDEA instances (F5).
  - **Help:** User Guide (F1), About WFlash.
- Phần đầu (nút Flash, thanh tiến trình, dòng Step, các dải cảnh báo) và khung Information nằm ngoài tab, như hiện nay.
- Tab GitLab chỉ hiện với profile có `builds`. Profile thường giữ tab Flash cũ (nút Load from GitLab, thẻ nguồn).

### 3.2 Tab GitLab

Ba khung cùng một bố cục: **App**, và khi Advanced Debug bật, **Boot Manager** và **Flash Bootloader** cạnh nhau.

| Dòng | Nội dung | Nút |
|---|---|---|
| Project | tên project ngắn (sửa được) | |
| Repository | thư mục repo; trống ghi "Optional" (BM, FBL) | Browse |
| Branch/Tag | branch hiện tại, hoặc `(detached)` | Checkout |
| Commit | commit ngắn · "No local changes." / "N file(s) have local changes." | Reload |
| Build | App: ô chọn build. BM: tên job (`bm_job` của build App). FBL: tên job trong profile | |
| Firmware | ◉ From checked-out commit ○ Manual | Choose Job |
| (trạng thái) | `<phần>: <job> · <branch> · <commit> · Cached \| Downloaded`, hoặc lỗi | |

- Không có repo: Branch/Tag và Commit ghi `-`; Checkout, Reload và "From checked-out commit" bị mờ.
- "From checked-out commit" được chọn: Choose Job mờ. "Manual": Choose Job bật, mở popup Load from GitLab với project của phần đó.
- Nút gạt **Advanced Debug** nằm giữa App và hai khung còn lại. Tắt thì ẩn hai khung; khi flash, các dòng BM/FBL bị bỏ tick như hiện nay.

### 3.3 Tab Flash (profile có `builds`)

- Bên trái: khung **Firmware to flash**, chỉ để xem. Mỗi phần một khối:
  - Tiêu đề kèm nhãn chế độ **From commit** hoặc **Manual**.
  - Các dòng Build (App) hoặc Job, Branch, Commit, Status (Loading…, Cached, Downloaded, hoặc lỗi).
  - Không có CAL. Dòng cuối: "Advanced Debug: on/off".
- Bên phải: hai bảng **Program Files**, **Symbol Files**, không có chữ phụ.
- Nút Flash tắt khi đang tải hoặc Checkout.

### 3.4 Tab Setting

Ba nhóm, trải hết bề ngang:

| Nhóm | Dòng |
|---|---|
| **Profile** | Profile + Reload; Profiles folder + Browse; Download folder (trống = `%LOCALAPPDATA%\WFlash\cache`) + Browse |
| **GitLab connection** | GitLab URL (kèm group); Access token |
| **winIDEA** | Instance + Refresh; After flash: Reset target, Run after reset, Verify samples |

Mỗi ô lưu và có hiệu lực khi sửa xong. Đường dẫn sai báo ngay cạnh ô và không lưu.

## 4. Hành vi

### 4.1 Ba "phần" và trạng thái của chúng

Mỗi phần (App, Boot Manager, Flash Bootloader) có: project, repo, chế độ Firmware, kết quả đọc repo, firmware đã nạp, và một lần chạy nền đang chạy (nếu có). Mã dùng chung cho cả ba; khác nhau chỉ ở:

| | App | Boot Manager | Flash Bootloader |
|---|---|---|---|
| Vai trò file | `ffi`, `elf` | `bm` | `fbl` |
| Job | `ffi_job`, `elf_job` của build | `bm_job` của build App | `debug_sources.fbl.job` |
| Repo | bắt buộc | không bắt buộc | không bắt buộc |
| Chỉ dùng khi | luôn | Advanced Debug bật | Advanced Debug bật |

### 4.2 From checked-out commit

- Kích hoạt khi: chọn chế độ này; đọc repo xong và commit khác commit của firmware đang nạp; Checkout xong; mở app (khôi phục, mục 4.6); đổi build (App, và BM vì `bm_job` theo build).
- Đọc repo xảy ra khi: Reload, Checkout xong, cửa sổ được kích hoạt lại, đổi repo, mở app. Mỗi phần mỗi lúc chỉ một lần đọc; không đọc và không nạp khi đang flash.
- Tìm pipeline của **đúng commit** (`find_build_jobs` / `fetch_named_artifact`, như hiện nay), dùng cache nếu có.
- Commit chưa có pipeline, hoặc job `manual`/`skipped`/đang chạy: dòng trạng thái báo rõ một lần, không lặp lại khi cửa sổ được kích hoạt lại nếu commit chưa đổi.
- Thay đổi chưa commit chỉ cảnh báo, như hiện nay.

### 4.3 Manual

- Choose Job mở popup Load from GitLab (đã bỏ phần kết nối, xem 4.5) với project của phần đó; job lọc mặc định theo job của phần đó.
- Firmware chọn tay được giữ cho tới khi chọn lại, kể cả khi repo đổi commit.

### 4.4 Tiến trình trên thanh Flash

- Tải artifact: phần trăm thật, `Step: Downloading <phần> <FFI/ELF/…> artifact (<job> · <commit>) — NN%`, số MB.
- Checkout: thanh chạy kiểu bận, `Step: Checking out <branch/commit>…`.
- Nhiều phần cùng tải: thanh hiện phần đang chạy gần nhất; xong hết thì về `Step: Idle`.
- Flash không chạy song song với tải/Checkout (nút Flash tắt), nên không chồng tiến trình.

### 4.5 GitLab URL có kèm group

- `https://gitlab.hella.com/alm/.../e-ad_radar_cust_suz05_group` được tách: máy chủ `https://gitlab.hella.com` (gọi API), group `alm/.../e-ad_radar_cust_suz05_group`.
- Đường dẫn project = group + `/` + tên. Nếu tên đã chứa `/` thì dùng nguyên (profile cũ, project ở group khác).
- Token gắn với **máy chủ** trong keyring, nên đổi group không phải nhập lại token. Token cũ (lưu theo URL cũ) được dùng nếu máy chủ trùng.
- Giả định GitLab chạy ở gốc tên miền; đúng với `gitlab.hella.com`.

### 4.6 Lưu và khôi phục

Lưu ngay khi đổi, trong `settings.json`:

- Chung: profile, GitLab URL theo profile (khi khác mặc định), thư mục profile và Download, Dark mode, Reset/Run/Verify, Advanced Debug, kích thước cửa sổ, tab đang mở.
- Theo profile và từng phần: repo, project (khi khác mặc định), chế độ Firmware, build (App), job chọn tay (Manual: project, job id, tên job, branch, commit, đường dẫn cache).

Mở app:

1. Chọn lại profile, tab, kích thước, các tùy chọn.
2. Mỗi phần có repo: đọc repo.
3. From checked-out commit: nạp firmware của commit đó (thường từ cache).
4. Manual: nạp lại bản đã chọn nếu thư mục cache còn; không còn thì để trống.
5. Không bao giờ tự flash. Instance winIDEA vẫn dò lại; chỉ một instance thì tự chọn.

**Chuyển đổi một lần:** khóa cài đặt `suz05_m7_ffi.yaml` được đổi sang `suz05.yaml` khi đọc settings, nếu khóa mới chưa có.

### 4.7 Tools

- **Test GitLab connection:** gọi một API chỉ đọc bằng URL và token hiện tại (`GET /projects/<project App>`); báo OK hoặc lỗi cụ thể (401, 403, 404, SSL, không kết nối được) vào khung Information. Không chạy khi đang flash.
- **Check winIDEA cores:** kết nối instance đang chọn, đọc `CSessionCtrl.get_status()` và `get_topology()` (đã kiểm chứng ở spike 16, đang dùng mỗi lần flash), in trạng thái từng core, rồi ngắt. **Chỉ đọc:** không reset, không lập trình. Không chạy khi đang flash. Phương thức mới `core_states()` thêm vào Protocol, adapter giả trước, rồi adapter thật.
- **Refresh winIDEA instances:** như nút Refresh.

### 4.7b User Guide (user, 2026-11-09)

- File `wflash/resources/help/user_guide.html`, tiếng Anh, tự chứa (CSS và hình minh họa vẽ bằng HTML ngay trong file, không cần mạng, không ảnh rời), sáng/tối theo hệ thống.
- **Help → User Guide** (F1) mở file bằng trình duyệt mặc định (`QDesktopServices.openUrl`). Thiếu file thì báo trong khung Information.
- Gói kèm qua `pyproject.toml` (`resources/help/*`) và `wflash.spec` (thư mục `wflash/resources` đã được gói).
- Nội dung từng bước, ngắn: chuẩn bị, cấu hình lần đầu (Setting), chọn firmware (GitLab), flash (Flash), khi gặp lỗi, gửi lỗi (debug bundle, lịch sử flash), phím tắt. Cập nhật khi giao diện đổi.

### 4.8 Chờ pipeline đang chạy (user, 2026-11-09)

- Chỉ ở chế độ From checked-out commit. Job của commit đang `created`, `pending` hoặc `running`: dòng trạng thái ghi `Waiting for pipeline: <job> is <trạng thái>…`, WFlash hỏi lại GitLab mỗi 30 giây và tự nạp khi job `success`.
- `manual`, `skipped`: không chờ (cần người bấm), chỉ báo. `failed`, `canceled`: báo lỗi, không chờ.
- Dừng chờ khi: commit đổi, chuyển sang Manual, đổi profile hoặc build, đóng app, hoặc sau 60 phút (báo "Stopped waiting after 60 min").
- Job xong khi đang flash: chỉ nạp sau khi flash kết thúc, để bảng file không đổi giữa chừng.
- Việc hỏi lại chạy nền như các lần tải khác (WorkerRegistry, generation guard); một bộ đếm thời gian trên luồng GUI khởi động mỗi lần hỏi.

### 4.9 Thông báo khi xong (user, 2026-11-09)

- Khi flash **Done**, **lỗi** hoặc **bị hủy**, và khi firmware nạp xong sau lúc chờ pipeline: hiện thông báo Windows (`QSystemTrayIcon.showMessage`) và làm biểu tượng taskbar nhấp nháy (`QApplication.alert`).
- Chỉ khi cửa sổ WFlash **không** được kích hoạt; đang nhìn WFlash thì không báo.
- Nội dung ngắn: "Flash done — SUZ05", "Flash failed: <lỗi ngắn>", "Firmware ready: App 2885986f". Hệ thống không hỗ trợ khay thông báo thì chỉ nhấp nháy taskbar.

### 4.10 Lịch sử flash (user, 2026-11-09)

Không hiển thị trong WFlash. Mỗi lần bấm Flash, khi workflow kết thúc (Done, lỗi hoặc hủy), WFlash thêm **một dòng** vào `%LOCALAPPDATA%\WFlash\flash_history.csv` (UTF-8 có BOM để Excel đọc đúng):

| Cột | Ví dụ |
|---|---|
| time | `2026-11-09 14:32:05` |
| profile | `SUZ05` |
| winidea | `SUZ_7G5_M7.xjrf (5315)` |
| app | `stingray_3p5mb_no_HTSM · tranph9_R5_LED · 2885986f` (build · branch · commit) |
| app_mode | `From commit` / `Manual` |
| bm, fbl | `build_STINGRAY_3P5MB · development · c54f8484`, trống khi Advanced Debug tắt |
| bm_mode, fbl_mode | như app_mode |
| cal | tên file CAL |
| advanced_debug | `on` / `off` |
| resets | số lần reset trước khi lập trình |
| tries | số lần gọi `begin_program` |
| program_s | thời gian lập trình (giây) |
| verify | `on` / `off` |
| result | `Done` / `Failed` / `Cancelled` |
| error | lời nhắn lỗi ngắn (như popup), không có chi tiết binding, không có token |

- Giữ 5000 dòng gần nhất; quá thì bỏ các dòng cũ nhất.
- **File → Open flash history** mở file bằng ứng dụng mặc định (thường là Excel). Chưa có file thì báo trong khung Information.
- Debug bundle kèm file này (`flash_history.csv`), qua cùng bộ lọc che token.
- Số lần reset, số lần thử và thời gian lập trình do adapter cung cấp sau `download()` (thuộc tính `program_stats`, có ở adapter giả và adapter thật). Lỗi khi ghi file chỉ cảnh báo trong log, không làm hỏng lần flash.
- Ghi trên luồng GUI, trong slot kết thúc của worker flash, sau khi worker đã xong.

## 5. Dữ liệu

### 5.1 Profile

```yaml
name: SUZ05
gitlab:
  url: https://gitlab.hella.com/alm/projects_group/e-ad_group/e-ad_radar_cust_suz05_group
  project: SUZ05_APP_Application_Software-Impl
debug_sources:
  bm:  {project: SUZ05_BM_Boot_Manager-Impl}
  fbl: {project: SUZ05_FBL_Flash_Boot_Loader-Impl, job: build}
```

- `gitlab.url` mới, không bắt buộc. Có thì là mặc định của GitLab URL cho profile đó.
- `profiles/suz05_m7_ffi.yaml` đổi tên thành `profiles/suz05.yaml`. `profiles/saf85xx_example.yaml` giữ nguyên.
- Ô Profile hiện `name` của profile (tên file khi trùng `name`).

### 5.2 Settings

- Thêm: các trường của mục 4.6, nhóm theo profile.
- Giữ nhưng không dùng: `ca_bundle`, `verify_tls`, `verbose`, `max_cached_jobs` (vẫn đọc; mặc định 10), để file cũ đọc được.

## 6. Mã nguồn

| File | Thay đổi |
|---|---|
| `wflash/gui/main_window.ui` | Menu bar và action; tab GitLab; tab Flash mới; tab Setting mới; bỏ nút Preferences |
| `wflash/gui/gitlab_tab.py` (mới) | Mixin tab GitLab: ba khung, chế độ Firmware, tự nạp |
| `wflash/gui/source_panel.py` | Tách phần đọc repo, nạp theo commit thành logic dùng chung cho một "phần"; App là một trường hợp |
| `wflash/gui/checkout_dialog.py` | Dùng cho từng phần (repo và project truyền vào); tiến trình lên thanh Flash |
| `wflash/gui/gitlab_dialog.ui/.py` | Bỏ phần kết nối (URL, token, Verify TLS); chỉ còn chọn branch/tag và job |
| `wflash/gui/preferences_dialog.*` | Xóa |
| `wflash/gui/menu_actions.py` (mới) | Mixin nối các action menu |
| `wflash/gui/flash_mixin.py` | Tiến trình tải/Checkout dùng thanh Flash; khóa Flash khi đang tải |
| `wflash/core/profile.py` | `gitlab.url`; ghép tên project ngắn với group |
| `wflash/core/settings.py` | Trường mới, chuyển khóa profile cũ |
| `wflash/core/gitlab_client.py` | Tách máy chủ/group từ URL; token theo máy chủ |
| `wflash/core/logging_setup.py`, `wflash/main.py` | Luôn ghi lệnh winIDEA |
| `wflash/core/winidea_adapter.py`, `fake_adapter.py`, `tests/fake_isystem.py` | `core_states()`, `program_stats` |
| `wflash/resources/help/user_guide.html` (mới) | Hướng dẫn sử dụng tiếng Anh |
| `wflash/core/flash_history.py` (mới) | Ghi và cắt bớt `flash_history.csv`; không import Qt |
| `wflash/core/debug_bundle.py` | Kèm `flash_history.csv` |

Tuân theo các quy tắc trong `CLAUDE.md`: `.ui` trước, tên widget rõ nghĩa, core không import Qt, luồng nền theo quy tắc threading (generation guard trước khi hủy, slot là bound method, QObject tạo trên luồng GUI, đóng cửa sổ chờ có giới hạn).

## 7. Lỗi

| Tình huống | Hiển thị |
|---|---|
| Commit chưa có pipeline | Dòng trạng thái của phần đó: "No pipeline for <commit> yet." + gợi ý push/chờ |
| Job `manual`/`skipped`/đang chạy | "Job <tên> of <commit> is <trạng thái>." |
| Repo không phải git / thiếu | Dòng Commit báo lỗi; From checked-out commit không chạy |
| Checkout bị từ chối (có thay đổi) | Như hiện nay, trong popup Checkout |
| GitLab 401/403/404/SSL | Thông báo cụ thể như hiện nay |
| Thư mục profile/Download không tồn tại | Báo cạnh ô, không lưu |
| Firmware Manual đã bị xóa khỏi cache | Để trống, dòng trạng thái: "Previous job is no longer in the download folder." |

## 8. Kiểm thử

- Core: tách URL/group, ghép project, chuyển khóa settings, lưu/khôi phục, profile `gitlab.url`.
- Adapter: `core_states()` trên adapter giả và `fake_isystem` (đọc được, không đọc được).
- GUI: từng khung (có/không repo, hai chế độ), tự nạp khi đổi commit, không nạp khi đang flash, Manual giữ lựa chọn, khôi phục khi mở lại, menu (Dark mode, chuyển tab, Exit đi qua `closeEvent`), Setting có hiệu lực ngay, tiến trình trên thanh Flash.
- Luồng: đóng cửa sổ khi đang đọc repo/tải ở cả ba phần; kích hoạt cửa sổ liên tục; đổi chế độ khi đang tải (kết quả cũ bị bỏ).
- Chờ pipeline: chuyển `running` → `success` thì tự nạp; dừng khi commit đổi, khi đóng app, khi quá hạn; job xong lúc đang flash thì nạp sau. Thông báo: chỉ khi cửa sổ không active.
- Lịch sử flash: một dòng cho Done, Failed, Cancelled; giữ 5000 dòng; lỗi ghi file không làm hỏng flash; không có token; có trong debug bundle.
- Stress test: thêm luồng ba phần, Advanced Debug bật/tắt, kích hoạt cửa sổ, menu, chờ pipeline rồi đóng app.
- Windows (Vòng 13): chọn profile SUZ05 trên máy mới (chỉ nhập token), Test GitLab connection, Check winIDEA cores, hai chế độ Firmware cho BM và FBL, mở lại app và flash ngay. Phần flash không đổi, nên chỉ một lần flash để xác nhận.
