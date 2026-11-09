# Hướng dẫn thử nghiệm WFlash trên Windows

File này tổng hợp **mọi thứ cần chạy trên máy Windows** trước khi viết được adapter winIDEA thật (Plan 2). Làm lần lượt từ Phần 0 đến Phần 6, rồi gửi lại gói kết quả theo Phần 7.

Mỗi bước có ghi rõ **có đụng tới ECU/workspace hay không**. Bước nào không chạy được thì ghi lại lỗi rồi làm tiếp bước sau, đừng dừng cả buổi: lỗi cũng là kết quả cần gửi.

| Phần | Nội dung | Cần winIDEA/ECU? | Đụng ECU/workspace? | Thời gian ước tính |
|---|---|---|---|---|
| 0 | Chuẩn bị máy, Miniforge, env conda `wflash` | Không | Không | 15 phút |
| 1 | Cài `isystem.connect` và kiểm tra version/bitness | Cài winIDEA | Không | 10 phút |
| 2 | Ghi thông tin workspace bằng tay | Có | Không | 10 phút |
| 3 | Spike 01–05 (quan trọng nhất) | Có | **03 đổi tạm path, 04 flash, 05 reset** | 30–45 phút |
| 4 | Test tự động + chạy app với fake adapter | Không | Không | 10 phút |
| 5 | GitLab thật (CI Artifact) | Không | Không | 15 phút |
| 6 | Build `.exe` | Không | Không | 10 phút |
| 7 | Đóng gói và gửi kết quả | – | – | 5 phút |

> **Mục tiêu thật sự** của buổi thử: (1) biết chính xác API `isystem.connect` trên winIDEA 9.21 của bạn (Phần 3), (2) xác nhận phần đã viết chạy đúng trên Windows (Phần 4–6). Phần 3 quyết định Plan 2; các phần còn lại là kiểm tra hồi quy.

---

## Phần 0: Chuẩn bị

**Cần có:**

- Máy Windows có **winIDEA 9.21.x**, probe iSYSTEM/TASKING, ECU **SAF85xx** cấp nguồn và nối probe.
- Workspace SAF85xx **đã flash tay vào Winbond thành công** (bằng nút Download trong winIDEA). Spike dựa vào cấu hình này.
- **Một bản firmware "biết chắc là tốt"** đang được trỏ tới trong workspace. Bước 04 sẽ flash đúng các file mà workspace đang trỏ tới.
- **Miniforge3** cho Windows x86_64 (bản 64-bit), tải từ <https://github.com/conda-forge/miniforge/releases> (file `Miniforge3-Windows-x86_64.exe`). Không cần cài Python riêng: conda sẽ tạo Python trong env.
- Mạng nội bộ vào được GitLab, và một Personal Access Token (scope `read_api`) cho Phần 5.
- Repo WFlash chép sang Windows (git clone branch `feat/wflash-plan1`, hoặc copy cả thư mục). **Nên để ngoài OneDrive**, ví dụ `C:\work\WFlash-Tool`.

### 0.1. Cài Miniforge

1. Chạy `Miniforge3-Windows-x86_64.exe`, chọn **Just Me**, giữ thư mục mặc định `%USERPROFILE%\miniforge3`. **Không** tick "Add Miniforge3 to my PATH" (bộ cài cũng khuyên không tick).
2. Mở Start menu → **Miniforge Prompt**. Mọi lệnh trong hướng dẫn này chạy trong cửa sổ đó (là `cmd` đã nạp sẵn conda). Dòng lệnh bắt đầu bằng `(base)`.
3. (Tùy chọn) để dùng conda trong `cmd` thường hoặc terminal của VS Code: `conda init cmd.exe`, đóng và mở lại cửa sổ.

### 0.2. Chọn version Python khớp với `isystem.connect`

File package `isystem.connect` trong thư mục winIDEA có thể chỉ build cho vài version Python. Xem tên file trước (cách tìm file ở Phần 1, bước 1):

- Tên có dạng `isystem.connect-9.21.x-cp312-cp312-win_amd64.whl` → cần **Python 3.12** (`cp312`), 64-bit (`win_amd64`).
- `cp311` → 3.11, `cp313` → 3.13. Nếu tên có `py3-none-any`, hoặc là file `.tar.gz`, dùng **3.12**.
- WFlash cần Python **3.11 trở lên**. Nếu wheel chỉ có cho version thấp hơn 3.11, dừng lại và báo mình.

Ghi version đã chọn vào `00_manual.txt` (Phần 2).

### 0.3. Tạo env `wflash`

Trong Miniforge Prompt (thay `3.12` bằng version đã chọn ở 0.2):

```bat
conda create -n wflash python=3.12 -y
conda activate wflash
cd /d C:\work\WFlash-Tool
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Từ đây trở đi, mọi lệnh `python` đều chạy **trong env này**: dòng lệnh phải bắt đầu bằng `(wflash)`, không phải `(base)`. Mở cửa sổ mới thì chạy lại `conda activate wflash`.

Lưu ý:

- **Cài các thư viện của WFlash bằng `pip`** (lệnh trên), không cài thêm `pyside6`/`qt` bằng `conda install`. Hai bản Qt trong cùng một env (một từ conda, một từ pip) là nguyên nhân hay gặp của lỗi `Could not find the Qt platform plugin "windows"`.
- **Không cài vào env `base`.** Script build `.exe` sẽ từ chối chạy khi đang ở `base`.
- Kiểm tra nhanh đúng env: `where python` phải in dòng đầu tiên là `%USERPROFILE%\miniforge3\envs\wflash\python.exe`.
- `spike/README.md` dùng venv riêng `wflash-spike`. Bỏ qua phần đó: dùng chung env `wflash` cho cả spike, app và build.

---

## Phần 1: Cài `isystem.connect` và kiểm tra môi trường

`isystem.connect` **không cài từ PyPI** (`pip install isystem.connect` sẽ lấy bản không khớp winIDEA). Phải cài từ chính thư mục cài đặt winIDEA 9.21.

1. Tìm thư mục SDK Python trong thư mục cài winIDEA, thường dạng `C:\iSYSTEM\winIDEA9\...\sdk\python` (máy mỗi người một khác). Trong đó có file package (`.whl` hoặc `.tar.gz`, tên chứa `isystem.connect` / `isystem_connect`).
2. Cài (trong env `wflash`, **dùng `pip`**, không dùng `conda install`):

   ```bat
   python -m pip install "<đường dẫn đầy đủ tới file package>"
   ```

3. Chạy và **chép toàn bộ output** vào file `spike\results\00_env.txt` (tạo thư mục `spike\results` nếu chưa có):

   ```bat
   mkdir spike\results
   (
   python -c "import sys, platform; print(sys.version); print(platform.architecture()); print(platform.platform())"
   python -c "import isystem.connect as ic; print(ic.__file__)"
   python -c "import importlib.metadata as m; print(m.version('isystem.connect'))"
   python -c "import isystem.connect as ic; print(ic.getModuleVersion())"
   python -c "import isystem.connect as ic; print([n for n in dir(ic) if n.startswith('C')])"
   ) > spike\results\00_env.txt 2>&1
   ```

   Lệnh `getModuleVersion()` có thể báo không tồn tại. Không sao, cứ để lỗi trong file.

**Tự kiểm tra ngay:**

- `platform.architecture()` phải là `64bit` (trừ khi winIDEA của bạn là 32-bit: bitness Python phải **khớp** winIDEA).
- Version `isystem.connect` phải là **9.21.x**, khớp winIDEA (xem Help → About trong winIDEA).
- Nếu `pip install` báo `is not a supported wheel on this platform`, version Python của env không khớp tag `cpXY` của wheel. Tạo lại env đúng version: `conda deactivate`, `conda env remove -n wflash -y`, rồi làm lại Phần 0.3.
- Nếu `import isystem.connect` lỗi kiểu `DLL load failed`, gần như chắc chắn là lệch bitness hoặc lệch version. Ghi nguyên văn lỗi, đừng tự sửa bằng cách cài bản khác từ PyPI.

---

## Phần 2: Ghi thông tin workspace bằng tay

Trong winIDEA (workspace SAF85xx đang mở), ghi vào file `spike\results\00_manual.txt`:

1. **Version winIDEA** chính xác (Help → About), loại probe.
2. **Đường dẫn file workspace** (`.xjrf`).
3. **Danh sách download file**: mở hộp thoại cấu hình download (thường ở Debug → Configure Session / Files for download). Với mỗi entry ghi:
   - tên entry (đúng chữ hoa/thường),
   - đường dẫn file hiện tại (`.s3`),
   - target/device mà entry nạp vào (để xác nhận là Winbond QSPI chứ không phải internal flash),
   - các tùy chọn đáng chú ý (verify, offset, load symbols/code).
4. **Danh sách Application / symbol file**: với mỗi core (CM7_0, CM7_1, …) ghi tên Application và đường dẫn file `.elf`.
5. **Flash tay một lần** bằng nút Download của winIDEA, ghi lại **thời gian flash** (bấm đồng hồ) và kích thước file `.s3`.
6. **Chụp màn hình** hai hộp thoại ở bước 3 và 4, lưu vào `spike\results\`.

Tên entry và Application ở đây sẽ được dùng để viết profile thật (`profiles/*.yaml`, các khóa `winidea_entry` và `winidea_app`).

---

## Phần 3: Chạy spike 01 → 05

Mở winIDEA với workspace SAF85xx, ECU đã nối. Trong Miniforge Prompt đã `conda activate wflash`:

```bat
cd /d C:\work\WFlash-Tool\spike
```

Mỗi script tự in ra màn hình **và** ghi một file `spike\results\<tên>_<thời gian>.txt`. Không cần chép tay output, chỉ cần chạy đúng thứ tự. Nếu có lỗi, script vẫn ghi traceback vào file rồi kết thúc.

Nếu đang mở **nhiều winIDEA**, thêm `--instance <id>` vào mọi lệnh (lấy `id` trong output của 01). Tốt nhất là chỉ mở một winIDEA.

### 3.1. `01_connect.py`: kết nối, version, API (không đụng gì)

```bat
python 01_connect.py
```

Kiểm tra trong output: có dòng `instance: {...}` với workspace đúng, và `isAttached -> True`. Nếu connect lỗi, **dừng Phần 3 ở đây**, gửi kết quả 00 + 01. Không có connect thì các bước sau vô nghĩa.

### 3.2. `02_dump_options.py`: tìm nơi lưu đường dẫn `.s3`/`.elf` (không đụng gì)

```bat
python 02_dump_options.py
```

Script đọc file workspace XML, in mọi chỗ chứa `.s3`/`.elf`, rồi thử đọc từng chỗ đó qua `getOptionStr`.

- Nếu output có dòng `workspace file not found`, chạy lại và chỉ đường dẫn `.xjrf` ở Phần 2:

  ```bat
  python 02_dump_options.py --workspace "C:\duong\dan\toi\workspace.xjrf"
  ```

- Tìm trong output các dòng dạng `getOptionStr /IDE/... -> '...\xxx.s3'` hoặc `-> '...\xxx.elf'` (**thành công**, có mũi tên `->` và đường dẫn file). Đó là các **URL** dùng cho bước 3.3. Ghi lại một URL của `.s3` và một URL của `.elf`.
- Nếu **không có dòng nào thành công**, vẫn gửi kết quả. Mình sẽ đọc phần XML để đoán URL đúng, gửi lại lệnh cho bạn chạy thêm (`--url ...`).

### 3.3. `03_set_paths.py`: đổi path rồi tự khôi phục (đổi tạm workspace)

Tạo một file giả để làm path mới (không cần là firmware thật, script **không** flash):

```bat
mkdir C:\tmp
copy NUL C:\tmp\wflash_test.elf
copy NUL C:\tmp\wflash_test.s3
```

Chạy với URL lấy từ bước 3.2 (thay `<URL_ELF>`, `<URL_S3>`):

```bat
python 03_set_paths.py --url "<URL_ELF>" --new-path C:\tmp\wflash_test.elf
python 03_set_paths.py --url "<URL_S3>" --new-path C:\tmp\wflash_test.s3
```

**Sau khi chạy, kiểm tra trong winIDEA** rằng đường dẫn trong hộp thoại download/symbol đã **về lại như cũ** (so với Phần 2). Đây đúng là cơ chế backup/rollback mà WFlash dùng.

- Nếu path **không** được khôi phục: giá trị gốc nằm trong file kết quả `03_set_paths_*.txt`. Sửa tay lại trong winIDEA rồi **không lưu workspace** cho tới khi đã đúng. Ghi lại hiện tượng.
- Mở lại hộp thoại trong winIDEA **giữa lúc** script chạy là không cần thiết; chỉ cần kiểm tra trước và sau.

### 3.4. `04_download.py`: flash bằng cấu hình hiện tại (**FLASH ECU**)

> ⚠️ Bước này **ghi vào Winbond** đúng các file workspace đang trỏ tới, giống bấm Download trong winIDEA. Trước khi chạy: xác nhận path đã về đúng firmware tốt (sau bước 3.3) và ECU đang cấp nguồn ổn định.

```bat
python 04_download.py
```

- Script in `... still downloading, Ns` mỗi 5 giây, cuối cùng in `elapsed`. **So thời gian với lần flash tay ở Phần 2.**
- Trong lúc chạy, **nhìn winIDEA**: có hiện thanh tiến trình/hộp thoại flash không? Ghi lại vào `00_manual.txt`.
- Nếu `download` lỗi ngay (không phải lỗi flash), chạy thêm cách thứ hai và gửi cả hai file:

  ```bat
  python 04_download.py --facade
  ```

- **Thử thêm một lần (khuyến nghị):** chạy lại `04_download.py`, giữa chừng (khoảng 10–20 s) bấm **Stop/Abort** trong winIDEA nếu có nút đó, hoặc nhấn `Ctrl+C` trong `cmd`. Ghi lại hiện tượng (download có dừng không, winIDEA báo gì, có treo không). Sau đó **flash lại đầy đủ một lần** (bằng tay hoặc chạy lại 04) để ECU không nằm ở trạng thái flash dở. Thông tin này quyết định cách WFlash xử lý nút Cancel khi flash thật.

### 3.5. `05_reset.py`: reset + halt (**RESET ECU**)

```bat
python 05_reset.py
python 05_reset.py --run
```

Kiểm tra trong output: trạng thái `after reset` (mong đợi đang dừng/halted) và `after run` (đang chạy). Nhìn thêm trong winIDEA xem **từng core** (CM7_0, CM7_1, …) ở trạng thái nào sau mỗi lệnh, ghi vào `00_manual.txt`.

---

## Phần 4: Test tự động và chạy app với fake adapter

Quay về thư mục gốc repo:

```bat
cd /d C:\work\WFlash-Tool
set QT_QPA_PLATFORM=offscreen
python -m pytest -q                          > test_results\pytest_all.txt 2>&1
python -m pytest -k thread -v                > test_results\pytest_thread.txt 2>&1
python tools\stress_test.py                  > test_results\stress.txt 2>&1
set QT_QPA_PLATFORM=
```

(Tạo thư mục trước: `mkdir test_results`.) Mong đợi: dòng cuối `pytest_all.txt` là `... passed` không có `failed`; `stress.txt` có `STRESS_RESULT=PASS`. Nếu có `failed`/`FAIL`, cứ gửi file, không cần tự sửa.

**Chạy app bằng tay** (fake adapter, không cần winIDEA):

```bat
python main.py --adapter fake
```

Kiểm tra nhanh:

1. Giao diện hiển thị đủ, không bị ép dòng (đặc biệt popup **Load from GitLab…**), theme Teal. Chụp màn hình cửa sổ chính và popup.
2. **Preferences… → Dark mode** bật/tắt, đóng app mở lại vẫn giữ.
3. Chọn profile ví dụ → (sau khi có artifact ở Phần 5) bấm **Flash**: tiến trình chạy, nút thành **Cancel** đỏ. Thử bấm Cancel giữa chừng.
4. Thử một lỗi giả lập rồi xem tab Information và hint:

   ```bat
   set WFLASH_FAKE_FAIL=download
   python main.py --adapter fake
   set WFLASH_FAKE_FAIL=
   ```

5. Nút **Export debug bundle…** (tab Information) → lưu file zip vào `test_results\`.

Ghi các điểm bất thường (chữ bị cắt, font, kích thước cửa sổ trên màn hình scale 125%/150%) vào `test_results\notes.txt`, kèm ảnh chụp.

---

## Phần 5: GitLab thật

Vẫn dùng `python main.py --adapter fake` (phần GitLab không phụ thuộc winIDEA).

1. **Chuẩn bị profile thật**: copy `profiles\saf85xx_example.yaml` thành `profiles\saf85xx.yaml`, sửa:
   - `gitlab.project`: path project thật (ví dụ `group/subgroup/project`),
   - `gitlab.job_filter`: glob tên job build,
   - `programs[].winidea_entry` và `applications[].winidea_app`: **đúng tên đã ghi ở Phần 2**,
   - `pattern`: glob khớp tên file `.s3`/`.elf` trong artifact.
2. **Load from GitLab…** → nhập URL GitLab, token (scope `read_api`). **Verify TLS** để bật. Nếu lỗi SSL, chỉ đường dẫn CA bundle nội bộ (file `.pem`/`.crt`) ở ô CA bundle; chỉ tắt Verify TLS nếu không có CA bundle (app sẽ ghi WARNING).
3. Tab **CI Artifact**: Load branches/tags → chọn branch → Browse jobs… → tải một artifact. Kiểm tra bảng mapping: dòng nào đỏ, file nào được tự chọn có đúng không.
5. Thử lỗi có chủ đích: token sai (mong đợi thông báo 401 rõ ràng), project sai (404).
6. **Export debug bundle…** sau khi tải xong → lưu vào `test_results\`.

Ghi lại vào `test_results\notes.txt`: thời gian tải, kích thước artifact, cấu trúc thư mục trong artifact (danh sách file `.s3`/`.elf`), và mọi thông báo lỗi khó hiểu.

> Token chỉ được lưu trong Windows Credential Manager, log và debug bundle đã che token (`***`). Trước khi gửi, bạn vẫn có thể mở zip ra kiểm tra.

---

## Phần 6: Build `.exe`

```bat
scripts\build_windows.bat > test_results\build.txt 2>&1
```

Chạy trong env `wflash` đã activate: script dùng Python của env conda đang active (biến `CONDA_PREFIX`), chạy lại test + stress test rồi PyInstaller. Nếu thành công, có `dist\WFlash\WFlash.exe`. Chạy thử:

```bat
dist\WFlash\WFlash.exe --adapter fake
```

Kiểm tra app mở được, theme đúng (sáng và tối), Load from GitLab hoạt động. Nếu build lỗi, file `build.txt` là đủ.

> Lưu ý: chạy `WFlash.exe` **không có** `--adapter fake` hiện sẽ báo "real winIDEA adapter is not available": đúng như mong đợi, adapter thật là Plan 2.

---

## Phần 7: Đóng gói và gửi kết quả

Nén thành một file, ví dụ `wflash_windows_results.zip`, gồm:

```
spike\results\          00_env.txt, 00_manual.txt, ảnh chụp, 01_..05_*.txt (mọi lần chạy)
test_results\           pytest_all.txt, pytest_thread.txt, stress.txt, build.txt,
                        notes.txt, ảnh chụp, các wflash_debug_*.zip
```

Kèm thêm (nếu tiện):

- File profile thật `profiles\saf85xx.yaml` (không chứa token).
- Log app: thư mục `%LOCALAPPDATA%\WFlash\logs\`.
- **Không gửi** file workspace `.xjrf` nếu nó chứa thông tin nội bộ không muốn chia sẻ; output của spike 02 đã có đủ phần cần thiết.

### Checklist trước khi gửi

- [ ] `00_env.txt`: Python 64-bit (khớp winIDEA), version `isystem.connect` = 9.21.x
- [ ] `00_manual.txt`: tên entry download, tên Application từng core, device Winbond, thời gian flash tay
- [ ] `01_connect_*.txt`: `isAttached -> True`
- [ ] `02_dump_options_*.txt`: có URL đọc ra được path `.s3`/`.elf` (hoặc ghi chú là không có)
- [ ] `03_set_paths_*.txt`: path đã tự khôi phục (đã kiểm tra trong winIDEA)
- [ ] `04_download_*.txt`: thời gian download, kết quả lần thử dừng giữa chừng
- [ ] `05_reset_*.txt`: trạng thái từng core sau reset và sau run
- [ ] `pytest_all.txt`, `pytest_thread.txt`, `stress.txt` (PASS hay FAIL đều gửi)
- [ ] Debug bundle sau khi tải artifact GitLab thật
- [ ] `build.txt` và kết quả chạy `WFlash.exe`

### Sau khi nhận kết quả, mình sẽ

1. Ghi lại API thật vào `docs/winidea_api_notes.md`.
2. Viết Plan 2: `RealWinIDEAAdapter` (đọc/ghi path entry, download có cancel/timeout, reset/halt từng core, báo lỗi rõ khi lệch version/bitness).
3. Sửa các lỗi Windows (nếu có) tìm thấy ở Phần 4–6.
4. Gửi lại bản mới để thử flash thật bằng WFlash.

---

## Vòng 2 (sau kết quả ngày 2026-10-06)

Vòng 1 đã cho biết: connect, đọc path symbol file, download, reset và run đều chạy. Còn thiếu ba thứ (chi tiết ở `docs/winidea_api_notes.md`, mục *Open questions*):

- File `.s3` nằm trong danh sách **Download Files của thiết bị Winbond** (Hardware → Winbond W25Q64JW SPI → Configure…), không nằm trong danh sách download của Debug. Chưa biết URL để đọc/ghi danh sách đó.
- Bước 03 vòng 1 đã truyền **đường dẫn file** vào `--url`, nên chưa thử được việc ghi path. `--url` phải là **option URL**, dạng `/IDE/...`.
- `isystem.connect` đang là **9.26.11**, còn winIDEA là **9.21.408**.

Làm theo thứ tự, trong env đã dùng ở vòng 1:

**V2.1. Version `isystem.connect`.** Tìm trong `C:\Data\_Devtools\Winidea408\` file package Python (tên chứa `isystem.connect` hoặc `isystem_connect`, đuôi `.whl` hoặc `.tar.gz`), thường trong thư mục con `sdk` hoặc `python`:

```bat
dir /s /b C:\Data\_Devtools\Winidea408\*isystem*connect* > spike\results\v2_sdk_search.txt
```

- Nếu **có** file: tạo env mới để không phá env đang chạy được, cài file đó, rồi chạy lại `python 01_connect.py`:
  ```bat
  conda create -n wflash921 python=3.12 -y
  conda activate wflash921
  python -m pip install "<đường dẫn file tìm được>"
  cd spike
  python 01_connect.py
  ```
  Nếu 01 vẫn `isAttached -> True` thì dùng env `wflash921` cho các bước sau.
- Nếu **không có** file: ghi "không có" vào `00_manual.txt` và dùng tiếp env cũ (9.26.11).

**V2.2. Dò danh sách file của Winbond (chỉ đọc):**

```bat
python 06_probe_umi.py
```

**V2.3. Thử ghi path symbol file** (đổi tạm, script tự khôi phục; không flash):

```bat
copy NUL C:\Data\tmp\wflash_test.elf
python 03_set_paths.py --url "/IDE/System.Debug.Applications[0].SymbolFiles.File[1].Path" --new-path C:\Data\tmp\wflash_test.elf --keep
```

Có `--keep` nên path **không** tự khôi phục. Mở *Debug → Configure Session → App_M7 → Symbol Files* và xem dòng thứ hai có thành `C:\Data\tmp\wflash_test.elf` không (chụp màn hình `v2_symbol_changed.png`). Sau đó **khôi phục** bằng giá trị cũ in ở dòng `read old -> '...'` trong file kết quả 03:

```bat
python 03_set_paths.py --url "/IDE/System.Debug.Applications[0].SymbolFiles.File[1].Path" --new-path "<giá trị read old>" --keep
```

Mở lại dialog để chắc chắn đã về như cũ. **Đừng lưu workspace** trong lúc path đang là file test.

**V2.4. Download có ghi Winbond không?** Mở cửa sổ *View → Output* (hoặc Progress) của winIDEA, chạy `python 04_download.py`, rồi chụp màn hình Output (`v2_download_output.png`). Sau đó bấm tay *Hardware → Winbond W25Q64JW SPI → Program*, ghi thời gian và chụp Output (`v2_program_output.png`). So sánh hai lần là biết download của Debug có ghi Winbond hay không.

**V2.5. Bổ sung `00_manual.txt`** (lần trước file trống): danh sách **đầy đủ** Download Files của thiết bị Winbond (kéo thanh cuộn, ghi từng dòng: path đầy đủ, offset, có tick hay không), và tên file thực tế trong artifact GitLab cần nạp vào từng dòng.

**V2.6. Phần 4–6 của hướng dẫn** (test tự động, app, GitLab, build `.exe`) vẫn chưa có kết quả. Làm nếu có thời gian; không chặn Plan 2.

Gửi lại `spike\results\` (cả file cũ và mới) như vòng 1.

---

## Vòng 3 (sau kết quả ngày 2026-10-10)

Vòng 2 đã tìm được URL đọc path `.s3` của Winbond: `/iOPEN/UMIConfig.Devices.Devices[0].DownloadFiles[i].Path`. Vòng này kiểm tra việc **ghi** path và việc **program** Winbond qua API. Lấy bản mới của nhánh (`git pull`) để có `spike\07_umi_details.py` và `spike\08_umi_program.py`.

> Ở vòng 2, ngay sau lệnh JSON của script 06, winIDEA ngừng trả lời. Nếu lúc đó winIDEA bị treo hoặc crash, ghi lại vào `00_manual.txt`. Các script vòng 3 không dùng lệnh đó.

Mở winIDEA với workspace bạn dùng ở vòng 2, rồi trong thư mục `spike`:

**V3.1. Đọc chi tiết (chỉ đọc):**

```bat
python 07_umi_details.py
```

**V3.2. Thử ghi path `.s3`** (đổi tạm, script tự khôi phục; không flash). Dùng dòng 0 (`Radar_SUZ05_Gen7.s3`):

```bat
copy NUL C:\Data\tmp\wflash_test.s3
python 03_set_paths.py --url "/iOPEN/UMIConfig.Devices.Devices[0].DownloadFiles[0].Path" --new-path C:\Data\tmp\wflash_test.s3
```

Không có `--keep`, nên script tự đổi rồi khôi phục. Trong file kết quả, dòng `read back` phải là path test, còn `read after restore` phải là `Radar_SUZ05_Gen7.s3`. Mở lại dialog Configure của Winbond để chắc chắn path dòng đầu vẫn đúng.

**V3.3. Thử ghi path `.elf`** (workspace này `App_M7` chỉ có 1 file nên dùng `File[0]`):

```bat
copy NUL C:\Data\tmp\wflash_test.elf
python 03_set_paths.py --url "/IDE/System.Debug.Applications[0].SymbolFiles.File[0].Path" --new-path C:\Data\tmp\wflash_test.elf
```

Kiểm tra tương tự trong *Debug → Configure Session → App_M7 → Symbol Files*.

**V3.4. Program Winbond qua API** (⚠️ **ghi external flash**, giống bấm *Hardware → Winbond → Program*). Trước đó kiểm tra các file đang tick trong Download Files là firmware tốt.

```bat
python 08_umi_program.py
```

Script in danh sách file, tên thiết bị, rồi hỏi xác nhận. Gõ `YES` để ghi. Nếu script dừng với dòng "device index or program mode not found", chỉ cần gửi kết quả 07 và 08. So thời gian với lần bấm Program tay (V2.4 nếu đã làm).

**V3.5.** Nếu chưa làm V2.4/V2.5 ở vòng 2 thì làm luôn: ảnh Output khi download và khi Program tay, và danh sách đầy đủ Download Files của Winbond (path, offset, tick) vào `00_manual.txt`.

Gửi lại `spike\results\` như các vòng trước.

### Bổ sung vòng 3 (sau kết quả ngày 2026-11-07)

Lần chạy `08_umi_program.py` đầu tiên dừng ở `no device found -> stop` và **chưa ghi gì vào flash**: thiết bị Winbond có `Name` rỗng nên không lấy được danh sách tên. Script đã sửa để dùng chỉ số thiết bị 0, và chỉ ghi khi thiết bị đó đang bật và đúng model `W25Q64JW`. Lấy bản mới của nhánh rồi chạy lại V3.4. Nếu chưa chạy V3.2 và V3.3 (ghi path), chạy chúng trước.

## Vòng 4 (đã thay đổi sau sự cố ngày 2026-11-07)

> ⛔ **Không chạy `08_umi_program.py` với từ 2 file đang tick** (script đã tự từ chối). Lần chạy đó có 2 pha ERASING, và user báo chip bị xóa hết, ECU không chạy được.
>
> *Hardware → Winbond → Program* bấm tay với 2 file đang tick đã khôi phục được ECU, chỉ có 1 lần erase (user xác nhận). Cách bấm tay là cách flash an toàn đã biết. Bản cảnh báo trước đó về menu này quá thận trọng.

**Chưa cần chạy lại `09_flash_compare.py`, và không dùng `--full` (mỗi lần đọc mất khoảng 4,4 s, toàn bộ khoảng 80 phút).** Bản lấy mẫu đã chạy được. `umi.read` không phải đọc thụ động: lần chạy `--full` báo `Error loading monitor`, tức là nó nạp monitor vào target. Khi ECU đang chạy, thao tác này có thể làm dừng firmware. Sau khi đã chạy 09, tắt nguồn ECU rồi bật lại để kiểm tra firmware.

Chạy script chỉ đọc tài liệu API và menu (không flash, không đụng target):

```bat
python 10_program_api_docs.py
```

Sau `10`, chạy `python 11_find_examples.py` (không kết nối winIDEA, không đụng ECU), rồi gửi `results\examples\` và file kết quả. Nếu winIDEA cài ở chỗ khác, thêm `--root <thư mục>`.

## Vòng 5: flash qua API giống Debug → Download

Debug → Download bấm tay chỉ có 1 pha ERASING và ECU chạy tốt. Vòng này kiểm tra API có làm giống vậy không. ⚠️ Mỗi bước `04` và `12` **ghi vào flash**. Nếu ECU không chạy sau một bước, khôi phục bằng Debug → Download bấm tay rồi báo lại, không chạy bước tiếp.

Với mỗi script: xóa Output của winIDEA, chạy script, chép Output vào file, chạy `python 09_flash_compare.py` (không `--full`, khoảng 3 phút), rồi tắt bật nguồn và kiểm tra firmware.

1. `python 04_download.py`, Output lưu thành `results\v5_04_output.txt`.
2. Chỉ khi bước 1 tốt: `python 12_begin_program.py`, gõ `YES`, Output lưu thành `results\v5_12_output.txt`.

## Vòng 6: tìm option "Mass erase before download"

Chỉ đọc, không flash. Chạy bằng Python đi kèm winIDEA (`isystem.connect` 9.21.408.1), trong thư mục `spike`:

```bat
C:\Data\_Devtools\Winidea408\Python\python.exe 13_device_options.py
```

Gửi lại `results\13_device_options_*.txt`.

## Vòng 7: thử WFlash thật

⚠️ Bước 3 trở đi **ghi vào flash**. Nếu ECU không chạy, khôi phục bằng Debug → Download bấm tay rồi gửi log.

1. Lấy bản mới. Mở một winIDEA duy nhất với workspace `R_04_01_01`. `python -m pip install -e ".[dev]"`, rồi `python main.py --verbose`.
2. Chọn profile `SUZ05_M7_FFI`. Dùng nút Load của **FFI (.s3)** để tải artifact chứa `RAD_SUZ05_FFI.s3`, rồi nút Load của **M7 (.elf)** để tải artifact chứa `Radar_SUZ05_Gen7.elf`. Nhập GitLab URL `https://gitlab.hella.com` trong popup. Kiểm tra bảng mapping và chọn instance. Nếu thấy cảnh báo khác commit, kiểm tra lại đã chọn đúng cặp artifact chưa. Thử **cùng firmware đang có trên ECU trước**.
3. Bấm Flash. Kiểm tra: Cancel bị khóa khi bước Downloading bắt đầu; Output của winIDEA có đúng 1 `ERASING`; xong thì target dừng.
4. Tắt bật nguồn ECU, kiểm tra firmware. Kiểm tra trong winIDEA: dòng `.s3` và ELF `App_M7` trỏ tới file trong cache, dòng CAL và ELF khác giữ nguyên.
5. Không đóng app, bấm Flash lần nữa với tick **Verify samples** (thêm khoảng 3 phút). Mong đợi xong không lỗi.
6. Tải artifact **firmware khác**, Flash, tắt bật nguồn, kiểm tra ECU đúng là chạy firmware mới. Đây là bước đầu tiên chứng minh firmware mới thật sự được ghi.
7. Thử lỗi: trong winIDEA tạm bỏ tick dòng `RAD_SUZ05_FFI.s3`, rồi bấm Flash. Mong đợi báo lỗi không tìm thấy entry, không có `ERASING`, path giữ nguyên. Sau đó tick lại dòng đó.
8. Export debug bundle, gửi lại cùng Output của winIDEA.

## Vòng 8: kiểm chứng cho tính năng developer debug

Lấy bản mới của nhánh `feat/developer-debug`. Trong workspace, các dòng phải nằm theo thứ tự FFI, CAL, BM, FBL, BM ở offset `0x0`, FBL ở offset `0xF1000`. Trong `App_M7` có sẵn ELF của BM và FBL. Làm trong thư mục `spike`.

**Phần A: không ghi flash**

1. Đọc dấu tick:
   ```bat
   python 14_tick_options.py
   ```
2. Thử đảo dấu tick của dòng BM (thay `<i>` bằng số dòng BM trong kết quả bước 1, script tự khôi phục):
   ```bat
   python 14_tick_options.py --toggle-row <i>
   ```
3. Thử đảo dấu tick ELF của BM. Thay `<j>` bằng số dòng của `Radar_SUZ05_Gen7_BM.elf`, và `<field>` bằng field đọc ra `true` hoặc `false` ở bước 1 (thường là `Load`):
   ```bat
   python 14_tick_options.py --toggle-symbol <j> --field <field>
   ```
   Trong lúc script chạy không cần làm gì. Sau đó mở *Debug → Configure Session → App_M7 → Symbol Files* để chắc chắn dấu tick đúng như trước.
4. Tìm pipeline theo commit. Token chỉ nằm trong biến môi trường, không vào file kết quả:
   ```bat
   set GITLAB_TOKEN=<token>
   python 15_pipeline_sha.py --project alm/projects_group/e-ad_group/e-ad_radar_cust_suz05_group/SUZ05_APP_Application_Software-Impl --sha <commit đầy đủ>
   set GITLAB_TOKEN=
   ```
   `<commit đầy đủ>` lấy từ `git rev-parse HEAD` trong source repo, ví dụ commit có pipeline đã chạy. Nếu báo lỗi SSL, thêm `--ca-bundle <file chứng chỉ>`.

Gửi kết quả phần A trước. Nếu không ghi được dấu tick thì **chưa làm phần B**.

**Phần B: có ghi flash**

⚠️ Hai bước dưới **ghi vào flash**, gồm cả BM và FBL. Cách khôi phục: bỏ tick BM và FBL, chỉ tick FFI và CAL, rồi Debug → Download bấm tay. Nếu gặp `Error loading monitor`, tắt bật nguồn ECU trước. Chọn BM và FBL là bản tốt, và đúng cặp với FFI.

5. Trong winIDEA tick FFI, CAL, BM, FBL. Xóa Output, bấm Debug → Download. Chép Output vào `results\v8_manual_output.txt`. Tắt bật nguồn, kiểm tra ECU. Rồi chạy `python 09_flash_compare.py` (không `--full`). Phần FFI bị BM hoặc FBL ghi đè sẽ báo `DIFFERENT`, đó là dự kiến; các file BM và FBL là `.bin` nên script này bỏ qua hoặc báo lỗi đọc file, cứ gửi kết quả.
6. Xóa Output, chạy `python 12_begin_program.py`, xem danh sách file rồi gõ `YES`. Chép Output vào `results\v8_api_output.txt`. Tắt bật nguồn, kiểm tra ECU, và kiểm tra ECU đúng là đang chạy BM và FBL đã chọn nếu có cách phân biệt.

Gửi lại `spike\results\`, kèm: Output có đúng 1 `ERASING` không, và ECU có chạy đúng không.

## Vòng 9: thử chế độ developer trong WFlash

Làm **sau khi phần B của Vòng 8 đạt**. Phần đó chứng minh winIDEA flash được bốn dòng FFI, CAL, BM, FBL trong một lần. Lấy bản mới của nhánh `feat/developer-debug`, cài lại (`python -m pip install -e ".[dev]"`), chạy `python main.py --verbose` từ thư mục repo. Mở một winIDEA duy nhất với workspace SUZ05 M7; file CAL `.sre` nằm cùng thư mục với file `.xjrf`.

⚠️ Các bước ghi **(FLASH)** sẽ ghi vào flash. Cách khôi phục: trong winIDEA bỏ tick BM và FBL, chỉ tick FFI và CAL, chọn lại các file tốt đã biết, rồi Debug → Download bấm tay. Gặp `Error loading monitor` thì tắt bật nguồn ECU rồi làm lại.

**Phần A: không ghi flash**

1. Chọn profile `SUZ05_M7_FFI`. Vùng Setting phải hiện panel developer (Source repo, Application, Advanced Debug), không còn nút Load from GitLab. Bảng bên phải tách thành **Program Files** (FFI, CAL; cột Offset) và **Symbol Files** (ELF).
2. **Browse…** chọn thư mục gốc source SUZ05. Kiểm tra Branch, Commit đúng với `git log -1` trong repo, và dòng "No local changes".
3. Sửa tạm một file trong repo (chưa commit). Bấm vào ô Source repo rồi nhấn Enter. Mong đợi: cảnh báo "local changes" nhưng nút Load vẫn bấm được.
4. Vẫn còn thay đổi đó, bấm **Checkout…**, chọn branch khác, chọn commit đầu, bấm Checkout. Mong đợi: bị **từ chối**, có thông báo đỏ, file đã sửa giữ nguyên. Trả file về như cũ (`git checkout -- <file>` do bạn tự làm).
5. **Checkout…** lần nữa: thử **Fetch**, chọn branch có pipeline, kiểm tra cột Pipeline (Passed/Failed/Manual…). Chọn commit đầu, bấm Checkout. Panel phải hiện branch mới. Rồi Checkout lại về branch ban đầu.
6. Chọn Build `stingray_3p5mb_no_HTSM`, bấm **Load firmware for <commit>**. Mong đợi: tải FFI và ELF, dòng trạng thái ghi job và commit; thư mục cache có dạng `<cache>\<branch>\<commit>_stingray_3p5mb_no_HTSM\FFI` và `...\ELF`. Dòng CAL tự lấy file `.sre` cạnh workspace.
7. Chọn Build mà job chưa chạy (ví dụ `strx_3p5mb_no_HTSM`, job `create_ffi_strx_3p5mb_no_HTSM` đang `skipped`), bấm Load. Mong đợi: thông báo rõ job chưa chạy, không tải gì. Chọn lại build stingray.
8. Đổi tạm tên file CAL `.sre` cạnh workspace, chọn lại instance winIDEA. Mong đợi: dòng CAL đỏ, Flash bị khóa với lý do thiếu CAL. Đổi lại tên file, chọn lại instance.
9. Tick **Advanced Debug**. Bảng có thêm dòng BM, FBL (offset `0x0` và `0xF1000`) và ELF của BM, FBL. Load BM từ job **sai** (ví dụ `build_STRX_3P5MB` nếu có, hoặc job khác `build_STINGRAY_3P5MB`). Mong đợi: Flash bị khóa, dải đỏ nêu job cần dùng. Load lại BM từ `build_STINGRAY_3P5MB` và FBL từ job `build`: Flash bật lại.

**Phần B: có ghi flash**

10. **(FLASH)** Bỏ tick Advanced Debug, bấm Flash. Mong đợi: Output winIDEA có đúng 1 `ERASING`; xong thì trong workspace dòng BM, FBL và ELF của BM, FBL **không tick**, dòng FFI trỏ vào thư mục cache theo branch. Tắt bật nguồn, kiểm tra ECU chạy.
11. **(FLASH)** Tick Advanced Debug (BM, FBL đã nạp ở bước 9), bấm Flash. Mong đợi: 1 `ERASING`; dòng BM, FBL và ELF của chúng **được tick** và trỏ vào cache. Tắt bật nguồn, kiểm tra ECU chạy, và nếu có cách thì kiểm tra đúng BM, FBL vừa chọn.
12. **(FLASH)** Checkout một commit khác có pipeline (firmware khác), Load firmware, bỏ Advanced Debug, Flash. Tắt bật nguồn, kiểm tra ECU đúng là chạy firmware mới.
13. Export debug bundle, gửi lại cùng Output winIDEA của các bước 10–12 và ảnh chụp panel developer.

## Vòng 10: kiểm tra core trước khi flash

Vòng 9 đã đạt (3 lần flash, ECU chạy đúng). Nhưng trước đó có 34 lần flash hỏng sau 5–9 giây, và lần nào cũng có core **NOT ACCESSIBLE** trong Session Explorer. Spike 16 đọc được trạng thái đó qua API. Bây giờ WFlash: đặt đường dẫn → reset → đọc trạng thái mọi core → nếu có core NOT ACCESSIBLE thì **reset lại**, nếu không thì flash. Mỗi lần bấm Flash có tối đa **10 lần reset**, tính cả lần đầu. Hết 10 lần mà vẫn còn thì WFlash dừng, báo tên core, trả đường dẫn về như cũ, và không ghi gì vào flash.

Lấy branch `feat/core-check`, chạy `python main.py --verbose`.

⚠️ Bước 2 và 3 có ghi flash. Bằng chứng: chuỗi gọi xuống winIDEA giống Vòng 9 (đặt path, reset, `begin_program`), chỉ thêm hai lệnh đọc `get_topology`/`get_status` mà spike 16 đã chạy. Cách khôi phục vẫn là Debug → Download bấm tay, và tắt bật nguồn khi có core NOT ACCESSIBLE.

1. **(FLASH nếu reset làm hết NOT ACCESSIBLE)** Làm cho có core NOT ACCESSIBLE (như ảnh 2 của bạn), rồi bấm Flash. Có hai kết quả có thể xảy ra, kết quả nào cũng ghi lại:
   - Log có `Cores not accessible (...) after reset 1 of 10; resetting again`, sau đó là `Cores before programming: ...` không còn NOT ACCESSIBLE, và flash xong như Vòng 9. Nghĩa là lệnh reset của API làm được như reset bấm tay.
   - Sau khoảng 30–35 giây báo "Flash not started: ... still not accessible after 10 resets.". Output winIDEA không có `ERASING`, workspace giữ đường dẫn cũ. Nghĩa là lệnh reset của API **khác** reset bấm tay. Hãy ghi rõ bạn reset bằng nút hay menu nào trong winIDEA.
2. **(FLASH)** Tắt bật nguồn ECU cho tới khi Session Explorer không còn NOT ACCESSIBLE, bấm Flash. Mong đợi: log có `Cores before programming: M7_0 STOP, ...`, flash xong như Vòng 9 (1 `ERASING`), ECU chạy.
3. **(FLASH)** Bấm Flash lần nữa ngay sau bước 2, không tắt nguồn. Ghi lại WFlash báo gì: flash được, hay bị chặn vì core NOT ACCESSIBLE.
4. Gửi debug bundle, Output winIDEA của bước 2–3, và ảnh Session Explorer ở bước 1 và 3.

**Kết quả Vòng 10 (2026-11-09): đạt.** Cả hai lần bấm Flash, lúc bắt đầu A53 và BBE32EP đều NOT ACCESSIBLE. Lần 1, WFlash reset 4 lần thì hết; lần 2, reset 2 lần thì hết. Sau đó cả hai lần flash xong khoảng 100 giây, rồi Done. Không phải tắt bật nguồn. Người dùng xác nhận ECU chạy bình thường sau cả hai lần.

## Vòng 11: giao diện hai tab, Reload repo, lọc branch, chứng chỉ Windows

Không ghi flash, trừ bước 6. Lấy branch `feat/ui-tabs`, cài lại vì có thư viện mới `truststore`:

```bat
git fetch
git checkout feat/ui-tabs
python -m pip install -e ".[dev]"
python main.py --verbose
```

1. **Hai tab.** Cửa sổ có tab **Flash** và **Setting**. Tab Flash: dòng Branch/Commit, khung Application, Advanced Debug, hai bảng file. Tab Setting: Profile, Source repo (Browse, **Reload**, Checkout…), winIDEA instance, After flash (Reset, Run, Verify samples), Preferences…. Nút Flash, thanh tiến trình và khung Information luôn hiện ở cả hai tab.
2. **Reload.** Trong terminal, commit thử hoặc đổi branch trong repo APP. Quay lại WFlash: dòng Branch/Commit tự cập nhật, không cần bấm gì. Làm lại lần nữa rồi bấm **Reload** ở tab Setting: cũng cập nhật.
3. **Lọc branch.** Setting → **Checkout…**, gõ một phần tên (ví dụ `r5_led`, chữ thường cũng được): danh sách chỉ còn các branch có chữ đó. Chọn một dòng hoặc gõ đủ tên rồi Enter: bảng commit đổi theo. Gõ tên không có thật rồi Enter: báo "No branch named …", nút Checkout tắt.
4. **Chứng chỉ Windows.** Mở Load from GitLab (nút Choose job in GitLab… hoặc Load… của BM): không còn ô CA bundle. Để **Verify TLS certificate** bật, bấm Load branches/tags. Mong đợi: tải được danh sách, không lỗi SSL. Trong log đầu phiên có dòng `HTTPS certificates are checked against the system certificate store`. Nếu lỗi SSL: gửi lại log, và cho biết trước đây bạn có dùng file CA bundle hay đã tắt Verify TLS.
5. **Log.** Khung Information không còn ô Log level, chỉ hiện INFO, WARNING, ERROR. Export debug bundle: `log.txt` trong đó vẫn có các dòng DEBUG (ví dụ `wflash.calls`).
6. **(FLASH)** Flash một lần như Vòng 10, trong lúc chờ thì chuyển qua lại giữa hai tab. Mong đợi: flash xong bình thường; trong lúc flash, các ô ở tab Setting bị khóa. Bằng chứng an toàn: phần flash không đổi so với Vòng 10, chỉ giao diện đổi. Khôi phục như cũ: Debug → Download bấm tay.
7. **Icon.** Thanh tiêu đề WFlash, các popup và **taskbar** hiện icon chip màu teal (không phải icon Python), kể cả khi chạy bằng `python main.py`.
8. **(tùy chọn) Build exe.** `scripts\build_windows.bat`. Mong đợi: `dist\WFlash\WFlash.exe` có icon chip trong Explorer; mở exe thì cửa sổ và taskbar cũng có icon đó.
9. Gửi ảnh hai tab, ảnh popup Checkout khi đang lọc, ảnh taskbar, và debug bundle.
