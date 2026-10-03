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

- Nhiều instance winIDEA: thêm `--instance <id>` (id lấy từ output 01).
- URL cho bước 03 lấy từ các dòng `getOptionStr ... -> '...elf'` thành công trong output 02.

## Gửi kết quả

Nén thư mục `spike\results\` và gửi lại.
