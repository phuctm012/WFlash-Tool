# WFlash — Thiết kế lại giao diện (UI redesign) — Design Spec

- Ngày: 2026-10-04
- Trạng thái: mockup đã được user duyệt, chờ review spec
- Mockup (đã duyệt): https://claude.ai/artifact/HtWLmnET9nmRy2ZY4UnS3a — artboard "Main window" và "Load from GitLab (popup)", tweak `mode` Light/Dark
- Spec gốc: `docs/superpowers/specs/2026-10-04-wflash-tool-design.md` (phạm vi tính năng vẫn giữ nguyên, trừ phần bổ sung Package Registry ở §5)
- Tham chiếu: project SFlash (`02_WORK/01_STUDY/06_PYSIDE6`) — `gui/main_window.ui`, `gui/gitlab_dialog.py`, `communication/gitlab_client.py`, `resources/style.qss`, `resources/style_dark.qss`

## 1. Mục tiêu

Đưa giao diện WFlash về bố cục quen thuộc của SFlash để người dùng SFlash dùng được ngay, nhưng có **màu riêng (Teal)** để không nhầm hai tool:

1. Chỉ **một cửa sổ chính**, không có tab chuyển trang (bỏ kiểu Single/Parallel/Configure).
2. Phần đầu giữ như SFlash: **nút Flash lớn**, **thanh tiến trình**, nhãn **tiến độ / ETA / tốc độ**.
3. Hai bảng Step/Datablock của SFlash được thay bằng **vùng Setting** của WFlash.
4. Dưới cùng chỉ một tab **Information** (log).
5. Nút **Load from GitLab…** mở **popup** cấu hình và tải firmware (tab CI Artifact + tab Package Registry), giống dialog của SFlash.
6. Theme **Teal Light** (mặc định) và **Teal Dark**, bật tay trong Preferences.

### Ngoài phạm vi

- Menu bar, thanh công cụ, nhiều tab.
- Tự đổi theme theo giao diện hệ điều hành.
- Parallel/Batch flash, bảng Step/Datablock/Trace của SFlash.
- Chọn file firmware cục bộ (vẫn là non-goal của spec gốc §1).
- Thay đổi core workflow (Approach A, rollback) — không đổi.

## 2. Bố cục cửa sổ chính

```
┌ WFlash v0.1 ──────────────────────────────────────────────────────────────┐
│ ┌───────────────────────────────────────────────────────────────────────┐ │
│ │ [ Flash ]  [██████████░░░░░░░░░░░░░]  42% | ETA: 01:12 | Speed: 85 KB/s │ │
│ │  90×70     Step: Downloading to external flash (Winbond QSPI)         │ │
│ │ ┌ ROLLBACK FAILED banner (chỉ hiện khi rollback thất bại) ─────────┐ │ │
│ │ ┌ Setting ──────────────┐ ┌ # │Type │winIDEA target│Pattern│File ┐ │ │
│ │ │ Profile [combo][Reload]│ │ 1 │Program│App │**/*App*.s3│[combo▾]│ │ │
│ │ │ Firmware source        │ │ 2 │Symbols│CM7_0 │...      │[combo▾]│ │ │
│ │ │ [Load from GitLab…]    │ │ 3 │Symbols│CM7_1 │...      │[đỏ ▾]  │ │ │
│ │ │ ┌ thẻ nguồn firmware ┐ │ │                                       │ │ │
│ │ │ winIDEA [combo][Refresh]│ │ (gợi ý: dòng đỏ cần chọn file)       │ │ │
│ │ │ After flash ☑Reset ☐Run │ └──────────────────────────────────────┘ │ │
│ │ │          [Preferences…]│                                           │ │
│ └───────────────────────────────────────────────────────────────────────┘ │
│                         [ Information ]                                    │
│ ┌ Log level [INFO▾]                 [Copy] [Clear] [Export debug bundle…] ┐ │
│ │ log có màu theo level                                                   │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│ Version: v0.1                                     Author: tranph9 (TRAN Phuc)│
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Phần đầu (flash header)

- `pushButton_flash`: 90×70, chữ "Flash". Khi đang flash, **cùng nút** đổi chữ thành "Cancel" và màu đỏ; bấm lúc đó = hủy (thay cho nút `pushButton_cancelFlash` riêng hiện tại).
- `progressBar_flash`: cao 20 px, không hiện chữ trong thanh (giống SFlash).
- `label_flashStats`: `"<p>% | ETA: mm:ss | Speed: x.x KB/s"`; lúc nghỉ `"ETA: -- | Speed: --"`; xong `"100% | Time: mm:ss | Speed: x.x KB/s"`; lỗi `"Failed | Time: mm:ss | Speed: --"`; hủy `"Cancelled | Time: mm:ss"`.
- `label_step`: `"Step: <Step.value>"` — "Idle", các bước của workflow, "Done", "Failed", "Cancelled".
- `label_rollbackWarning`: banner đỏ hiện khi `rollback_failed` (giữ hành vi hiện có).

**Cách tính ETA / Speed** (module thuần, không Qt: `wflash/core/progress.py`, class `ProgressEstimator`):
- `start(total_bytes)` khi bước DOWNLOAD bắt đầu; `total_bytes` = tổng kích thước các file program (`.s3`) đang map (kích thước file trên đĩa; ghi rõ trong code là ước lượng vì `.s3` là text).
- `update(percent, now)` → `elapsed`, `eta_s = elapsed * (100 - p) / p` (khi `p > 0`), `speed_kbps = total_bytes * p / 100 / 1024 / elapsed`.
- Trước khi có `p > 0`: `"ETA: calculating… | Speed: --"`. Percent `None` (không xác định): giữ ETA/Speed cũ, thanh chuyển dạng busy.
- Test: thuần Python, thời gian giả (`now` truyền vào).

### 2.2 Vùng Setting (trái, rộng cố định ~360 px)

| Widget | Tên trong `.ui` | Ghi chú |
|---|---|---|
| Header "Setting" | `label_settingHeader` | kiểu header bảng (nền soft, gạch accent) |
| Profile | `comboBox_profile`, `pushButton_reloadProfiles` | như hiện tại |
| Firmware source | `pushButton_loadFromGitlab` | viền + chữ màu primary |
| Thẻ nguồn firmware | `label_sourceTitle`, `label_sourceDetail`, `label_sourceCache` trong `frame_sourceCard` | VD: "CI artifact · job #7 build_app" / "group/saf85xx-sw · main · pipeline #100" / "Cached · 3 files"; package: "Package · saf85xx-firmware 1.4.0" / "group/saf85xx-packages · 2026-10-04 09:20" / "Downloaded · 3 files"; chưa có: "No firmware loaded — use Load from GitLab…" |
| winIDEA instance | `comboBox_instance`, `pushButton_refreshInstances` | như hiện tại (currentData là dict) |
| After flash | `checkBox_reset` ("Reset target"), `checkBox_run` ("Run after reset") | như hiện tại |
| Preferences | `pushButton_preferences` | mở Preferences dialog (§4) |

### 2.3 Bảng mapping (phải)

- `tableWidget_mapping`, cột: `#` (số dòng, nền soft), `Type`, `winIDEA target`, `Pattern` (font monospace), `File` (QComboBox mỗi dòng — nội dung động, dựng bằng Python như hiện tại).
- Dòng chưa có file: combo nền đỏ nhạt (Light `#ffcdd2` / Dark `#4a2a2c`), giữ quy tắc "0 hoặc nhiều match → người dùng chọn".
- `label_mappingHint` dưới bảng: "Red rows need a file before Flash is enabled." / "All rows mapped — Flash enabled." / khi chưa có firmware: "Load firmware to fill the mapping."

### 2.4 Information

- `tabWidget_output` với **một** tab `tab_information` ("Information").
- Trong tab: hàng công cụ (`label_logLevel`, `comboBox_logLevel`, `pushButton_copyLog`, `pushButton_clearLog`, `pushButton_exportBundle`) + `plainTextEdit_log`. Hành vi LogPanelMixin giữ nguyên.
- Màu log theo theme (DEBUG/WARNING/ERROR) — xem §6.

### 2.5 Status bar

- `statusBar_main` chứa 2 QLabel cố định thêm bằng code (Designer không thêm được widget vào status bar): trái `"Version: v<__version__>"`, phải `"Author: tranph9 (TRAN Phuc)"`. Hằng `APP_AUTHOR` đặt trong `wflash/__init__.py`.
- Thông báo tạm (`showMessage`) vẫn dùng như hiện tại.

### 2.6 Bỏ khỏi cửa sổ chính

`groupBox_gitlab` và toàn bộ widget duyệt GitLab (`comboBox_ref`, `listWidget_pipelines`, `listWidget_jobs`, `pushButton_downloadArtifact`, `progressBar_artifact`, …), `pushButton_settings`, `pushButton_cancelFlash`, `splitter_*`. Phần duyệt GitLab chuyển sang popup (§3).

## 3. Popup "Load from GitLab"

Dialog modal riêng: `wflash/gui/gitlab_dialog.ui` + `ui_gitlab_dialog.py` (sinh bằng `pyside6-uic`) + `wflash/gui/gitlab_dialog.py` (`GitlabDialog(QDialog)`). Logic duyệt/tải chuyển từ `GitlabBrowserMixin` vào dialog; mixin bị xóa.

### 3.1 GitLab Connection (`groupBox_connection`)

- `lineEdit_gitlabUrl` (Instance URL), `lineEdit_token` (password; lưu keyring qua `set_token`, không bao giờ ghi file/log).
- `checkBox_verifyTls` ("Verify TLS certificate (recommended)", mặc định bật). Tắt → `GitLabClient(..., verify=False)` và log WARNING một lần mỗi phiên.
- `lineEdit_caBundle` + `pushButton_browseCa` (tùy chọn, như Settings hiện tại).
- `label_connectionHint`: "Required token scope: read_api (branches/tags, pipelines, jobs, artifacts, packages). The token is stored in the system keyring (Windows Credential Manager), never in a file."
- URL/CA/verify được lưu vào `AppSettings` khi dialog đóng hoặc khi bắt đầu một thao tác (không lưu token vào settings).

### 3.2 Tab CI Artifact (`tab_ciArtifact`)

- `lineEdit_ciProject` (mặc định = `profile.gitlab.project`; người dùng sửa thì lưu `AppSettings.ci_project_override` theo tên profile; để trống = dùng profile) + nhãn "from profile" khi đang dùng giá trị profile.
- `comboBox_ref` + `pushButton_loadRefs` ("Load branches/tags").
- `comboBox_jobName` (editable; gợi ý tên job lấy từ danh sách job có artifact; lọc theo `profile.gitlab.job_filter`).
- `pushButton_downloadSelected` ("Download Selected Artifact", nút primary): tải artifact của job đang chọn trong bảng; nếu bảng chưa có dòng chọn → tải job mới nhất thành công khớp ref + job name.
- `pushButton_browseJobs` ("Browse jobs…"): nạp bảng.
- `tableWidget_jobs`, cột `Pipeline | Job | Ref | Status | When | Download`; cột Download là nút từng dòng ("Download" / "Cached" nếu đã có trong cache / "Downloading…" khi đang tải). Nhấp đúp dòng = tải.
- Dữ liệu từ `GitLabClient` hiện có (`list_refs`, `list_pipelines`, `list_jobs`, `download_artifacts`), cache bằng `ArtifactCache` như hiện tại.

### 3.3 Tab Package Registry (`tab_packageRegistry`) — mới

Làm **giống SFlash**: package generic, mỗi version có file đính kèm (thường là 1 file zip); tải file đầu tiên của version.

- `lineEdit_pkgProject`, `lineEdit_packageName` (lưu vào `AppSettings`: `package_project`, `package_name`).
- `pushButton_fetchLatest` ("Fetch Latest Version", primary), `pushButton_browseVersions` ("Browse versions…").
- `tableWidget_versions`, cột `Version | Uploaded | Download` (nút từng dòng; nhấp đúp = tải).

Core (`wflash/core/gitlab_client.py`, `requests`, phân trang `X-Next-Page` như hiện có), thêm:

```python
@dataclass(frozen=True)
class PackageVersion:
    id: int            # package id
    name: str
    version: str
    created_at: str

def list_package_versions(self, project_id: int, package_name: str, limit: int = 20) -> list[PackageVersion]
    # GET /projects/:id/packages?package_type=generic&package_name=<name>&order_by=created_at&sort=desc
    # chỉ giữ đúng tên (API lọc theo tiền tố)
def download_package(self, project_id: int, package: PackageVersion, dest: Path,
                     progress_cb=None, cancel=None) -> Path
    # GET /projects/:id/packages/:package_id/package_files → file đầu tiên (file_name)
    # GET /projects/:id/packages/generic/:name/:version/:file_name (stream, .part, cancel, lỗi → GitLabError/ArtifactError)
```

- Không có version → `GitLabError("No versions of package '<name>' found", hint="Check the package project and name in Load from GitLab.")`; version không có file → `GitLabError` tương tự.
- Cache: `ArtifactCache(<cache_dir>/packages)` với key `(project_id, package.id)`. Thêm `ArtifactCache.store_file(project_id, key, path)` cho file không phải zip (đặt nguyên file vào `files/`). Zip → `store_zip` như artifact.

### 3.4 Chung cho dialog

- `progressBar_download` + `label_downloadStatus` ("Downloading 12.4 / 19.3 MB") + `pushButton_stopDownload` ("Stop" — hủy tải, dialog vẫn mở).
- `plainTextEdit_gitlabLog` ("GitLab log"): nhật ký riêng của dialog, cũng đi qua logger `wflash.gitlab` (nên có trong log file/bundle, đã che token).
- `pushButton_cancel` ("Cancel"): hủy tải đang chạy (nếu có) rồi đóng.
- **Tải xong** → dialog phát `firmwareReady(path: Path, source: FirmwareSource)` và tự đóng; cửa sổ chính gọi `on_artifact_ready` (đổi tên thành `on_firmware_ready`) để dựng mapping và cập nhật thẻ nguồn.
- `FirmwareSource` (dataclass trong `wflash/core/firmware_source.py`): `kind` ("ci" | "package"), `project`, `title`, `detail`, `cache_note` — dùng cho thẻ nguồn và debug bundle (`ctx.source`).
- Lỗi: hiện trong dialog (`label_downloadStatus` đỏ + dòng log) và `show_error` như hiện tại (message + hint đã redact).
- Threading: dùng `WorkerRegistry` của cửa sổ chính (dialog nhận registry), giữ đủ 8 quy tắc CLAUDE.md: guard flag trước khi hủy, slot là bound method, `closeEvent` của dialog hủy và chờ có giới hạn. Không mở dialog khi đang flash (nút Load from GitLab bị tắt); không flash khi dialog đang tải (dialog là modal nên không bấm được Flash).

## 4. Preferences dialog

Đổi `SettingsDialog` thành `PreferencesDialog` (`preferences_dialog.ui` / `ui_preferences_dialog.py` / `preferences_dialog.py`; xóa `settings_dialog.*`):

- `lineEdit_cacheDir` + Browse, `spinBox_maxCachedJobs`, `pushButton_clearCache` (giữ hành vi R21 an toàn).
- `lineEdit_profilesDir` + Browse.
- `checkBox_verbose`.
- `checkBox_darkMode` ("Dark mode") — áp dụng ngay khi OK, lưu `AppSettings.dark_mode`.
- Bỏ GitLab URL/token/CA khỏi dialog này (đã chuyển sang popup).

## 5. Thay đổi `AppSettings`

Thêm field (giữ cơ chế kiểm kiểu khi load):

| Field | Kiểu | Mặc định |
|---|---|---|
| `verify_tls` | bool | `True` |
| `dark_mode` | bool | `False` |
| `ci_project_overrides` | dict[str, str] | `{}` (tên file profile → project) |
| `ci_job_name` | str | `""` |
| `package_project` | str | `""` |
| `package_name` | str | `""` |

`dict` cũng được kiểm kiểu (phải là dict str→str, sai thì về mặc định + warning).

## 6. Theme Teal

File: `wflash/resources/style.qss` (Light) và `wflash/resources/style_dark.qss` (Dark), loader `wflash/gui/style.py` (`load_stylesheet(dark: bool) -> str`, trả `""` nếu thiếu file — giống SFlash). `main.py` áp theme trước khi tạo `MainWindow`; Preferences đổi theme gọi lại `app.setStyleSheet(...)`. PyInstaller spec thêm `wflash/resources` vào `datas`.

| Token | Light | Dark |
|---|---|---|
| ground (nền cửa sổ) | `#f2f6f6` | `#1b2023` |
| surface (card, bảng, input) | `#ffffff` | `#232a2d` |
| panel (khung connection, tab chưa chọn) | `#e3eceb` | `#262e31` |
| border | `#d7dde5` | `#3a464a` |
| line (kẻ dòng) | `#e9edf2` | `#2e383b` |
| text / muted | `#1a1a1a` / `#5a6472` | `#e4eceb` / `#9aaaa8` |
| primary (nút Flash, nút chính) | `#0f6b63` | `#138277` |
| primary hover | `#1f9488` | `#1a988b` |
| accent (tiến trình, gạch header) | `#1f9488` | `#2bb3a3` |
| head (chữ header bảng, tab đang chọn) | `#0f6b63` | `#6fd3c6` |
| soft (nền header bảng, dòng chọn) | `#e7f3f1` | `#22383a` |
| cancel (nút Cancel khi flash, thanh lỗi) | `#b23b3b` | `#c24b45` |
| done (thanh hoàn tất) | `#3f8f5f` | `#3a8a5c` |
| log debug / warn / error | `#8a8a8a` / `#c77700` / `#d32f2f` | `#7d8b8a` / `#e0a03b` / `#ef7b74` |
| mapping dòng đỏ (nền / viền) | `#ffcdd2` / `#d1574f` | `#4a2a2c` / `#c96058` |
| banner rollback (nền / viền / chữ) | `#fdecea` / `#e6a5a0` / `#8f1d17` | `#3a2324` / `#7a3a37` / `#f3b1ac` |

- Chữ trắng trên primary đạt ≥ 4.5:1 ở cả hai chế độ.
- Màu trạng thái động (nút Flash đổi Cancel, màu thanh tiến trình, dòng mapping đỏ, màu log) lấy từ một bảng token Python `wflash/gui/theme.py` (`THEMES = {"light": {...}, "dark": {...}}`, `current_theme()`), để QSS và code dùng cùng giá trị. QSS dùng objectName (`#pushButton_flash`, `#pushButton_loadFromGitlab`, …) và dynamic property (`state="flashing"`) để đổi màu nút Flash, không set stylesheet rải rác.

## 7. Kiến trúc GUI sau khi đổi

```
wflash/gui/main_window.ui        cửa sổ chính (Designer)
wflash/gui/main_window.py        MainWindow(MappingTableMixin, FlashMixin, LogPanelMixin)
wflash/gui/mapping_table.py      mixin (đổi tên hook on_firmware_ready, cột #)
wflash/gui/flash_mixin.py        mixin (nút Flash/Cancel một nút, ETA/Speed qua ProgressEstimator)
wflash/gui/log_panel.py          mixin (màu theo theme)
wflash/gui/gitlab_dialog.ui/.py  popup Load from GitLab (CI + Package)
wflash/gui/preferences_dialog.ui/.py
wflash/gui/style.py, theme.py    theme
wflash/resources/style.qss, style_dark.qss
wflash/core/progress.py          ProgressEstimator (thuần Python)
wflash/core/firmware_source.py   FirmwareSource
```

`GitlabBrowserMixin` bị xóa (logic chuyển vào `GitlabDialog`). Các quy tắc CLAUDE.md giữ nguyên: Designer-first, tên widget có nghĩa, `ui_*.py` chỉ sinh bằng uic, core không import Qt.

## 8. Xử lý lỗi

- Không đổi taxonomy lỗi. Lỗi mới: package không có version / không có file (`GitLabError` có hint).
- Dialog đóng giữa chừng: hủy worker (guard flag + `CancelToken`), chờ có giới hạn, không nạp firmware nữa.
- Theme file thiếu: chạy với style mặc định của Qt, log WARNING (không crash).

## 9. Kiểm thử

- Core: `ProgressEstimator` (ETA/speed, p=0, p=None, hoàn tất), `list_package_versions`/`download_package` với `responses` (phân trang, lọc đúng tên, không version, không file, cancel, lỗi ổ đĩa), `ArtifactCache.store_file`, `AppSettings` field mới + kiểm kiểu dict.
- GUI (pytest-qt, `-k gui`): bố cục `.ui` (tên widget có nghĩa, file sinh khớp), nút Flash đổi Cancel và hủy được, nhãn stats/step theo trạng thái, thẻ nguồn cập nhật sau khi tải, dialog: tab CI (refs → jobs → tải → `firmwareReady` → đóng), tab Package (versions → tải → zip/non-zip), Stop/Cancel giữa chừng (guard flag), dark mode áp dụng và lưu, Preferences không còn trường GitLab.
- Test thread (`-k thread`) cho worker của dialog và đóng dialog khi đang tải.
- Cập nhật `tools/stress_test.py`: luồng GitLab đi qua dialog (CI và Package), đổi theme giữa chừng, đóng dialog khi đang tải; vẫn fail khi có cảnh báo threading của Qt.
- Smoke: `python main.py --adapter fake --smoke` exit 0 ở cả Light và Dark.

## 10. Rủi ro / ghi chú

- Package Registry cần token có quyền đọc package (`read_api` đủ cho GitLab hiện hành); sẽ kiểm chứng trên GitLab thật ở bước test Windows.
- Speed là **ước lượng** (winIDEA chỉ báo %), hiển thị đúng như SFlash nhưng tài liệu ghi rõ.
- Đổi tên/xóa widget kéo theo sửa nhiều test GUI hiện có và stress test — đây là phần lớn khối lượng việc.
