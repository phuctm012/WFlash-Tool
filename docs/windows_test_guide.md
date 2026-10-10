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
| 5 | GitLab thật (CI Artifact + Package Registry) | Không | Không | 15 phút |
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
4. Tab **Package Registry**: nhập project + tên package → Fetch Latest Version, rồi thử Browse versions… Nếu báo 403, ghi lại; có thể token thiếu quyền hoặc project không bật Package Registry.
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
