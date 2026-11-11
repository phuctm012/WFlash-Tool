# Spike winIDEA (chạy trên Windows)

Mục đích: xác minh API `isystem.connect` trên winIDEA 9.21 + workspace SAF85xx trước khi viết adapter thật.

## Chuẩn bị

1. Cài Python 3.11+ (64-bit) trên Windows.
2. `py -m venv %USERPROFILE%\.venvs\wflash-spike`
3. `%USERPROFILE%\.venvs\wflash-spike\Scripts\activate`
4. Cài `isystem.connect` từ thư mục cài đặt winIDEA 9.21:
   - Tìm thư mục SDK Python trong cài đặt winIDEA (mỗi cài đặt có đường dẫn khác nhau)
   - Tìm file package Python trong thư mục SDK đó
   - Chạy: `pip install "<đường dẫn đầy đủ tới file package>"`
   - Xác minh cài đặt thành công:
     - `python -c "import isystem.connect as ic; print(ic.__file__)"`
     - `python -c "import importlib.metadata as m; print(m.version('isystem.connect'))"`
     - Nếu hàm `getModuleVersion()` tồn tại: `python -c "import isystem.connect as ic; print(ic.getModuleVersion())"`
   - Kiểm tra bitness Python khớp với winIDEA (cả 64-bit): `python -c "import platform; print(platform.architecture())"`
5. Mở winIDEA với workspace SAF85xx, kiểm tra flash tay hoạt động.

## Chạy theo thứ tự (trong thư mục `spike`)

| Lệnh | Tác dụng | Có thay đổi target/workspace? |
|---|---|---|
| `python 01_connect.py` | liệt kê instance, version, API | Không |
| `python 02_dump_options.py` | tìm option chứa đường dẫn .s3/.elf | Không |
| `python 03_set_paths.py --url <URL> --new-path C:\tmp\test.elf` | đổi path rồi tự khôi phục | Đổi tạm, tự khôi phục |
| `python 04_download.py` | flash bằng cấu hình hiện tại, đo thời gian | **Có: flash ECU** |
| `python 05_reset.py` | reset + halt | **Có: reset ECU** |
| `python 06_probe_umi.py` | dò danh sách file của external flash (Winbond/UMI), chữ ký các class UMI/storage | Không (chỉ đọc) |
| `python 07_umi_details.py` | đọc đủ danh sách file của Winbond, field offset/tick, tên thiết bị, hằng số program mode | Không (chỉ đọc) |
| `python 08_umi_program.py` | program Winbond bằng `CUMIController.write()` (hỏi xác nhận, gõ `YES`), rồi reset. **Từ chối chạy nếu số dòng đang tick khác 1: với 2 dòng, chip đã bị xóa hết** | **Có: ghi external flash** |
| `python 09_flash_compare.py` | so flash với file đang tick. **Tạm thời không chạy:** `umi.read` nạp monitor vào target | Không ghi flash, **có đụng target** |
| `python 10_program_api_docs.py` | in tài liệu API, đọc cấu trúc menu | Không |
| `python 12_begin_program.py` | flash qua `CSessionCtrl.begin_program()` (hỏi `YES`), in trạng thái sau đó | **Có: ghi external flash** |
| `python 13_device_options.py` | liệt kê option của thiết bị Winbond từ file workspace và đọc từng option | Không (chỉ đọc) |
| `python 14_tick_options.py` | đọc dấu tick của Download Files và Symbol Files; `--toggle-row`, `--toggle-symbol` đảo rồi khôi phục | Đổi tạm, tự khôi phục; không flash |
| `python 15_pipeline_sha.py` | tìm pipeline và job theo commit trên GitLab; token lấy từ biến `GITLAB_TOKEN` | Không |
| `python 16_core_status.py --label all_stopped` | đọc trạng thái từng core (Session Explorer) qua `CSessionCtrl.get_status()` và `getCPUStatus`; in API cho từng core. Chạy một lần khi mọi core STOP, một lần khi có core NOT ACCESSIBLE (`--label not_accessible`) | Không (chỉ đọc) |
| `python 17_umi_cache_flush.py` | **Đã bỏ: flush hay lỗi sau khi đã xoá flash (Round 15).** thử ghi Winbond giống *Hardware → Winbond → Program*: `umi.write(0, wProgCache)` nạp các dòng tick vào cache, bạn xem Output (không được có ERASING), rồi `umi.flush(0)` xoá và ghi một lần; đọc 16 byte ở 0x0, reset. Hỏi YES trước mỗi bước | **Có, bước 2 ghi flash.** Khôi phục: *Hardware → Winbond → Program* hoặc Debug → Download bằng tay |
| `python 11_find_examples.py` | tìm ví dụ và tài liệu `isystem.connect` trên máy, chép vào `results\examples` (không kết nối winIDEA) | Không |

- Nhiều instance winIDEA: thêm `--instance <id>` (id lấy từ output 01).
- URL cho bước 03 lấy từ các dòng `getOptionStr ... -> '...elf'` thành công trong output 02.

## Gửi kết quả

Nén thư mục `spike\results\` và gửi lại.

> Lưu ý: `06_probe_umi.py` gọi `getOptionJSON` trên cả cây `Applications`, và sau lệnh này kết nối bị mất (`ICONNECT_E_ROUTING`), dù winIDEA không treo. Script 07 không gọi lệnh đó (trừ khi thêm `--json`).
