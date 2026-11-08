# WFlash — Dùng cho developer debug — Design Spec

- Ngày: 2026-11-07
- Trạng thái: mockup đã được user duyệt, chờ review spec
- Mockup (đã duyệt): https://claude.ai/artifact/QEPKXTap9Ar3hosime1XjW, bản sao ở `docs/superpowers/mockups/developer-ui/`
- Spec trước: `2026-10-04-wflash-tool-design.md`, `2026-10-04-wflash-ui-redesign-design.md`
- Tài liệu API: `docs/winidea_api_notes.md`, các quy tắc an toàn trong `CLAUDE.md`

## 1. Mục tiêu

Người dùng chính là developer đang debug. Họ cần firmware trên ECU và symbol trong winIDEA khớp với source đang mở.

1. **Đồng bộ với source:** chọn git repo của app, tool đọc branch và commit, rồi tải đúng FFI và ELF của commit đó theo cấu hình build.
2. **Checkout từ tool:** đổi branch hoặc commit của source repo ngay trong app.
3. **Cache theo branch:** tên thư mục cache cho biết đang debug branch và commit nào.
4. **Advanced Debug:** tùy chọn flash thêm BM và FBL, lấy từ repo riêng.
5. **CAL tự động:** tìm file CAL trong thư mục chứa `.xjrf`.

### Ngoài phạm vi

- Tự kích hoạt job trên GitLab. Job chưa chạy thì tool chỉ báo.
- Tự stash, commit hoặc xóa thay đổi trong source repo.
- Chọn firmware từ file local, trừ file CAL trong thư mục workspace.
- Package Registry (đã bỏ).
- Tạo dòng mới trong Download Files hoặc Symbol Files. Thiếu dòng thì báo cho người dùng tự thêm.
- Đổi mass erase, verify, hay offset trong workspace.

## 2. Quyết định của user

| Chủ đề | Quyết định |
|---|---|
| Tải firmware | Tự động theo commit của source repo và cấu hình build (cách C) |
| Cache | Mỗi commit và cấu hình một thư mục con dưới thư mục branch |
| BM và FBL | Một checkbox chung **Advanced Debug**, luôn flash cùng nhau |
| Nguồn BM, FBL | Repo riêng, người dùng tự chọn branch và commit |
| Thứ tự flash | FFI → CAL → BM → FBL, BM và FBL ghi đè lên FFI |
| Tắt Advanced Debug | Bỏ tick các dòng BM, FBL trong workspace và **giữ nguyên sau khi flash**, không trả về |
| Bật Advanced Debug | Tick dòng `.bin` và tick ELF của BM, FBL trong `App_M7` |
| CAL | Bắt buộc khi flash cùng FFI; thiếu thì cảnh báo và không flash |
| Job BM không hợp với Build | Khóa nút Flash |
| Checkout khi có thay đổi chưa commit | Từ chối và cảnh báo |
| Giao diện | Bảng Program Files và Symbol Files riêng, không hiện cột winIDEA target |

## 3. Giao diện

Theo mockup đã duyệt. Tóm tắt:

- **Source repo:** đường dẫn, **Browse**, branch, commit, trạng thái thay đổi chưa commit, nút **Checkout…**.
- **Application:** combo **Build**, nút **Load firmware for `<commit>`**, trạng thái FFI và ELF, nút **Choose job in GitLab…**.
- **Advanced Debug:** checkbox, hai dòng BM và FBL, mỗi dòng có **Load…** và trạng thái job, branch, commit.
- **winIDEA**, **After flash** và **Preferences…** giữ như hiện tại.
- **Program Files:** cột `#`, Source, File, Offset, theo thứ tự flash. Tắt Advanced Debug thì ẩn dòng BM, FBL.
- **Symbol Files:** cột `#`, Source, File. Tắt Advanced Debug thì ẩn dòng BM, FBL.
- **Dải đỏ** phía trên khi chưa flash được, nêu lý do và cách sửa ngắn gọn. Nút Flash bị khóa.

Vùng Setting cao hơn hiện tại, nên nội dung của nó phải cuộn được trên màn hình thấp (`QScrollArea`). Layout nằm trong `.ui`; riêng các dòng trong bảng vẫn tạo bằng code.

## 4. Profile

Thay `sources` hiện tại bằng cấu hình build và nguồn debug. Profile `suz05_m7_ffi.yaml` sẽ có:

```yaml
name: SUZ05_M7_FFI
gitlab:
  project: alm/projects_group/e-ad_group/e-ad_radar_cust_suz05_group/SUZ05_APP_Application_Software-Impl
builds:
  - {name: stingray_3p5mb,         ffi_job: create_ffi_stingray_3p5mb,         elf_job: build,                             bm_job: build_STINGRAY_3P5MB}
  - {name: stingray_3p5mb_no_HTSM, ffi_job: create_ffi_stingray_3p5mb_no_HTSM, elf_job: build,                             bm_job: build_STINGRAY_3P5MB}
  - {name: stingray_uds27_bypass,  ffi_job: create_ffi_stingray_uds27_bypass,  elf_job: build_STINGRAY_3P5MB_UDS27_BYPASS, bm_job: build_STINGRAY_3P5MB}
  - {name: strx_3p5mb_no_HTSM,     ffi_job: create_ffi_strx_3p5mb_no_HTSM,     elf_job: build_STRX_3P5MB,                  bm_job: build_STRX_3P5MB}
programs:
  - {role: ffi, winidea_entry: RAD_SUZ05_FFI.s3, pattern: "**/RAD_SUZ05_FFI.s3"}
  - {role: cal, pattern: "*_CAL_T008_*.sre"}
  - {role: bm,  winidea_entry: FBL_M7_LIP_RfeClock_Image.bin, pattern: "out/bin/FBL_M7_LIP_RfeClock_Image.bin", offset: 0x0}
  - {role: fbl, winidea_entry: Radar_SUZ05_Gen7_FBL.bin, pattern: "out/bin/Radar_SUZ05_Gen7_FBL.bin", offset: 0xF1000}
applications:
  - {role: elf, winidea_app: App_M7/Radar_SUZ05_Gen7.elf,     pattern: "**/Radar_SUZ05_Gen7.elf"}
  - {role: bm,  winidea_app: App_M7/Radar_SUZ05_Gen7_BM.elf,  pattern: "out/bin/Radar_SUZ05_Gen7_BM.elf"}
  - {role: fbl, winidea_app: App_M7/Radar_SUZ05_Gen7_FBL.elf, pattern: "out/bin/Radar_SUZ05_Gen7_FBL.elf"}
debug_sources:
  bm:  {project: alm/projects_group/e-ad_group/e-ad_radar_cust_suz05_group/SUZ05_BM_Boot_Manager-Impl}
  fbl: {project: alm/projects_group/e-ad_group/e-ad_radar_cust_suz05_group/SUZ05_FBL_Flash_Boot_Loader-Impl, job: build}
```

Thứ tự trong `programs` là thứ tự flash. Profile cũ không có `builds` vẫn chạy theo luồng hiện tại, bằng nút Load from GitLab.

## 5. Source repo

**Đọc trạng thái.** `wflash/core/source_repo.py` gọi `git` bằng `subprocess`, không import Qt, chạy trên worker, có timeout. Lấy branch, commit, và danh sách thay đổi chưa commit. Đường dẫn repo lưu trong `settings.json` theo từng profile. Tool đọc lại khi chọn repo, sau checkout, và ngay trước khi flash.

| Tình huống | Xử lý |
|---|---|
| Không tìm thấy `git`, hoặc thư mục không phải repo | Báo lỗi ngắn; vẫn dùng được **Choose job in GitLab…** |
| Có thay đổi chưa commit | Cảnh báo, vẫn cho tải và flash |
| Detached HEAD | Hiện commit; dùng thư mục cache `detached` |
| Source đổi commit sau khi tải firmware | Cảnh báo firmware không khớp, vẫn cho flash |

**Checkout.** Hộp thoại chọn branch và commit, có **Fetch** và cột trạng thái pipeline.

- Có thay đổi chưa commit: từ chối trước khi gọi `git checkout`, liệt kê tối đa vài file để người dùng kiểm tra.
- Chọn đầu branch: chuyển sang branch đó, tạo tracking branch nếu mới chỉ có trên remote. Chọn commit cũ: `git checkout --detach`.
- Không bao giờ dùng `--force`, `stash`, `reset` hay `clean`.
- `git fetch` dùng thông tin đăng nhập có sẵn của git và đặt `GIT_TERMINAL_PROMPT=0`. Token GitLab của WFlash không đi vào lệnh git.
- Không cho checkout trong lúc đang flash.

## 6. Tải firmware của app

**Load firmware for `<commit>`** chạy trên worker:

1. Tìm các pipeline của project có đúng commit (`GET /projects/:id/pipelines?sha=`), mới nhất trước.
2. Trong pipeline đầu tiên có đủ `ffi_job` và `elf_job` thành công, tải cả hai.
3. Nếu không có, báo lý do cụ thể và không tự chuyển sang commit khác:
   - Commit chưa có pipeline (có thể chưa push).
   - Job chưa chạy, ví dụ job chạy tay.
   - Job lỗi.
4. Điền bảng mapping. Các pattern vẫn phải khớp đúng một file; không thì hiện dòng đỏ.

**Choose job in GitLab…** mở popup hiện tại, cho từng nguồn FFI và ELF. Artifact khác commit với source thì cảnh báo, không chặn.

Lệnh tìm pipeline theo commit chưa được thử trên GitLab thật (mục 11).

## 7. BM và FBL

- Bật Advanced Debug mới cho chọn BM và FBL. Popup hiện tại dùng lại với project trong `debug_sources`; project có commit riêng, không so với source repo của app.
- FBL chỉ dùng job `build`. BM chỉ hiện job có trong các `bm_job` của profile.
- Job BM phải đúng `bm_job` của Build đang chọn, sai thì khóa Flash. Đổi Build sau khi đã nạp BM cũng được kiểm tra lại.
- Bật Advanced Debug nhưng chưa nạp đủ BM và FBL: khóa Flash.

## 8. Kiểm tra trước khi flash

Sau khi kết nối winIDEA và trước khi đổi bất cứ thứ gì. Một mục sai là không flash, và workspace không bị đổi. Dòng được khớp theo tên file, kể cả dòng đang bỏ tick.

| Kiểm tra | Yêu cầu |
|---|---|
| Dòng FFI, CAL | Có đúng một dòng khớp |
| Dòng BM, FBL | Có đúng một dòng khớp, kiểm tra cả khi tắt Advanced Debug để bỏ tick được |
| Thứ tự | FFI → CAL → BM → FBL trong Download Files |
| Offset | BM `0x0`, FBL `0xF1000`, so với workspace |
| Symbol | Có `App_M7/Radar_SUZ05_Gen7.elf`; bật Advanced Debug thì có thêm ELF của BM, FBL |
| Dòng khác | Dòng đang tick mà không thuộc profile: báo lỗi, vì winIDEA sẽ flash cả dòng đó |
| Thiết bị | Như hiện tại: đang bật, có "Program at download" |

**CAL.** Tìm `*_CAL_T008_*.sre` ngay trong thư mục chứa `.xjrf`. Không có thì báo lỗi; đúng một file thì dùng; nhiều file thì hiện dòng đỏ để người dùng chọn. Vì tên CAL có thể đổi, dòng CAL được khớp theo pattern, và không áp dụng quy tắc "file mới phải trùng tên". Path được ghi bằng tên file tương đối, như workspace đang dùng.

Khi thiếu dòng, thông báo nêu đúng tên file, offset và vị trí cần thêm.

## 9. Luồng flash

1. Đọc lại trạng thái source repo.
2. Kiểm tra theo mục 8.
3. Lưu path cũ, rồi đổi path các dòng được quản lý.
4. Đặt dấu tick: FFI, CAL luôn tick; ELF app luôn tick; BM, FBL (cả `.bin` và ELF) theo Advanced Debug.
5. Reset CPU, `begin_program`, đọc xác nhận như hiện tại. **Không đổi cách flash và không gọi `umi.write`.**
6. So mẫu nếu bật Verify, rồi reset hoặc run theo tùy chọn.

**Khi lỗi:** path trở về như cũ theo cơ chế rollback hiện tại. Dấu tick **không** trả về, theo quyết định của user: tick luôn phản ánh cấu hình trên WFlash.

**Verify.** Trước đây mỗi dòng được so riêng. Giờ BM và FBL ghi đè lên FFI, nên phải bỏ qua phần của một dòng đã bị dòng sau ghi đè, nếu không sẽ báo lỗi sai. Dòng `.bin` được so ở `offset` của nó.

**Ngoại lệ của Approach A.** Trước đây tool chỉ đổi path. Giờ tool đổi thêm dấu tick của các dòng trong profile và path của dòng CAL. Vẫn không tạo dòng, không đổi offset, mass erase hay các tùy chọn thiết bị.

## 10. Cache

```
<cache>\Release_DD_05_03_01\8ebd595d_stingray_3p5mb_no_HTSM\FFI\out\FFI\RAD_SUZ05_FFI.s3
<cache>\Release_DD_05_03_01\8ebd595d_stingray_3p5mb_no_HTSM\ELF\out\bin\Radar_SUZ05_Gen7.elf
<cache>\BM\<branch>\<commit8>_<job>\...
<cache>\FBL\<branch>\<commit8>_<job>\...
```

- Ký tự không hợp lệ trên Windows, gồm `/`, được đổi thành `_`.
- Tải vào thư mục tạm rồi đổi tên, nên tải hỏng không để lại bản dở.
- Giới hạn số bản giữ lại trong Preferences áp dụng trên toàn cache, xóa bản cũ nhất nhưng không xóa bản đang nạp.
- **Clear cache** dọn cả layout mới và thư mục cũ dạng `<project_id>\<job_id>`.
- Đường dẫn dài hơn 240 ký tự thì cắt bớt tên branch và thêm hash ngắn, vì Windows có giới hạn độ dài đường dẫn.
- Thư mục cache được đặt theo commit nên artifact tải bằng popup cũng cần commit; nếu ref không có branch thì dùng tên ref đã chọn.

## 11. Rủi ro và thứ tự kiểm chứng

Các điểm dưới đây chưa từng chạy trên máy thật. Theo Rule zero trong `CLAUDE.md`, chúng được thử bằng spike trước khi viết code phụ thuộc vào chúng.

| Điểm cần thử | Cách thử | Ghi flash? |
|---|---|---|
| Ghi `.Enabled` của dòng Download Files, đọc lại | Spike, tự khôi phục | Không |
| Field tick của Symbol File (có thể là `SymbolFiles.File[j].Load`), ghi và đọc lại | Spike, tự khôi phục | Không |
| winIDEA ghi đúng thứ tự khi các dòng chồng nhau | Tick BM, FBL rồi Debug → Download bấm tay, xem Output, rồi so mẫu | **Có** |
| `begin_program` với 4 dòng vẫn 1 lần xóa, ECU chạy | Spike 12 với cấu hình đó | **Có** |
| Tìm pipeline theo `sha` | Chạy trên GitLab thật | Không |

Với các bước có ghi flash: cách khôi phục đã biết là Debug → Download bấm tay với cấu hình FFI, CAL. Nếu một bước thất bại, thiết kế phần đó phải xem lại trước khi làm tiếp.

## 12. Kiểm thử

- **Core, không cần winIDEA:** `source_repo` trên git repo tạm thật; profile mới; đường dẫn cache; kiểm tra thứ tự, offset, dòng thừa; CAL với 0, 1, nhiều file; so mẫu có vùng ghi đè; tìm pipeline qua GitLab giả.
- **Adapter:** mở rộng `tests/fake_isystem.py` theo kết quả spike. Test phải chứng minh tắt Advanced Debug thì bỏ tick, và dấu tick không trở về khi lỗi.
- **GUI:** Build, Load, Advanced Debug, khóa Flash khi sai job BM, từ chối Checkout khi có thay đổi chưa commit, ẩn dòng, cuộn vùng Setting.
- **Stress test:** thêm luồng tải theo commit và bật tắt Advanced Debug trong lúc đang chạy.
- **Trên Windows:** một vòng thử mới trong `docs/windows_test_guide.md`, ghi rõ bước nào ghi flash.
