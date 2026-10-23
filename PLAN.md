# PLAN — Vibe Rescue V1.0 architecture-first rescue

<!-- markdownlint-disable MD013 -->

Owner intent (2026-10-23): cứu repo bằng **bản đồ kiến trúc có diễn giải** và
**audit harness/rủi ro theo bằng chứng**, không chỉ liệt kê source. Mục tiêu ổn
định ở [Product North Star](docs/PRODUCT_NORTH_STAR.md). Trạng thái làm việc ở
[STATUS.md](STATUS.md); plan này ghi tiêu chí và trình tự, không là tuyên bố hoàn
thành.

## Baseline và scope

- Tool repo: `vibe_rescue`; entry hiện có `scripts/logic_atlas.py`,
  `scripts/repo_explorer.py`, `scripts/fanout.py`, harness FIX. Generic Source
  Explorer có hàm/call/guard/raise nhưng chưa nối docs → khối chức năng → hành
  trình → hàm, và chưa audit agent/swarm/sensitive-data theo control.
- Target chứng minh: một repo thật do nhóm chọn (không công bố tên), chỉ đọc source/docs trong scope được duyệt,
  artifact dưới `VIBE_RESCUE/`. Target đang có thay đổi của team; không sửa code,
  không lấy test pass trên commit khác làm chứng nhận snapshot hiện tại.
- Trong V1.0, Python có source-level call/parameter index; JS/TS/Rust/Go/Java/
  PHP/C# dùng mức parser có sẵn và phải báo phần không phân giải. Đích là kiến
  trúc trung thực, không hứa tự hiểu 100% dynamic dispatch hay lâm sàng.

## Các gói việc và cổng hoàn thành

| Gói | Thay đổi | Verification và điều kiện xong |
| --- | --- | --- |
| A. Evidence model | Đọc README/architecture/design theo allowlist và giới hạn byte; trích purpose, journey step, source anchor. Tách `documented`, `source_observed`, `suggested`, `unknown`; ghi manifest coverage. | Fixture docs sai/lỗi thời, không có docs, symlink/ngoài scope và text chứa HTML độc; không overclaim. |
| B. Functional architecture | Nhóm file thành area/block có tên, mục đích và provenance; nối block bằng call/import thật, nêu ví dụ callsite và cạnh động chưa rõ. Liên kết từng bước tài liệu tới code bằng exact anchor hoặc nhãn gợi ý. | Fixture hai block gọi nhau, block chỉ có docs, cross-language boundary, không có đường gọi; click được từ overview tới bước/hàm. |
| C. HTML/SVG journey | Trang offline: overview → block → documented journey → function detail (tham số, caller/callee, guard/raise, source, config/prompt/test candidates). SVG tải được, search và deep link. Mọi graph lớn có index/phân trang. | Browser visual QA 1440×900 và 1600×1000; link local, XML SVG, keyboard/search, no script injection. |
| D. Harness/sensitive audit | Catalog control cho agent harness, swarm, PII/PHI/medical và billing: planner/tool/timeout/cancel/budget/retry/judge; intake/masking/egress/storage/audit/final audit/subject/tenant/authorization. Mỗi control có evidence hoặc `not located in scope`, khuyến nghị probe/fault test. | Fixture có tên `mask` nhưng đường egress thiếu vẫn **không** được green; multi-agent label không thành swarm-ready; missing control ra recommendation cụ thể. |
| E. Real-repo proof | Chạy trên target riêng với source/docs được phép. Tạo `architecture.html`, machine JSON, SVG, control report trong target; đối chiếu ít nhất một journey với source và ghi unknown. | Snapshot/dirty count, file counts, parse errors, doc coverage, unresolved edges, control evidence và giới hạn được công bố; không đổi runtime target. |
| F. Release/docs | README EN/VI ghi đúng one-line install, lệnh tạo architecture/audit, ví dụ HTML/SVG và expected output; STATUS, design, test receipts, screenshot thật. | Focused + full pytest, Ruff, Markdownlint, link checks, browser visual; review độc lập trước claim V1.0. |

## Quy tắc suy luận và recommendation

- Tên file/hàm, README hoặc scanner chỉ cho **candidate**. Một control được
  `runtime_verified` khi có trace/probe gắn commit+cấu hình; test receipt chỉ
  chứng minh case đó. Không tính phần trăm “safe” từ số từ khóa tìm thấy.
- Mỗi finding phải ghi `ID | ảnh hưởng | evidence file:line | confidence |
  điều chưa biết | fix/probe | STOP condition`. Không có bằng chứng thì ghi gap
  khảo sát, không gọi là lỗ hổng đã xác nhận.
- Profile nhạy cảm có thể gợi từ docs nhưng phải ghi `candidate`; người chạy
  chọn/duyệt profile trước khi kết luận control nào áp dụng. Không lấy PHI mẫu.

## STOP conditions

Dừng claim hoàn thành nếu tài liệu không khớp source, parser bỏ file mà không
báo, diagram có cạnh không có provenance, sensitive control được đánh dấu xanh
chỉ vì tên hàm/test tồn tại, HTML lộ nội dung bị loại trừ, hoặc suite regression
đỏ. Giữ bản đồ `partial` kèm unknown thay vì tạo độ chắc chắn giả. Không push
artifact chứa source target vào repo public.

## Tiến độ tại 2026-10-23

- A/B: bounded docs, source docstring, block grouping, cross-block Python
  call/import và phân biệt test/runtime đã chạy trên fixture và target riêng. Import
  theo suffix duy nhất là suy luận tĩnh có nhãn, không là runtime binding.
- C: HTML offline có overview → block → source function, SVG từng block tải
  được; Playwright đã kiểm chọn block, query/deep link, control filter, export
  SVG và không có page error trên target riêng. Sơ đồ workflow public qua Archify
  9/9 và visual-check.
- D: catalog control và probe recommendation đã có, mọi mục unverified. Chưa
  có source-to-egress proof hay trace/fault receipt tích hợp, nên chưa đạt gate D.
  Handoff EN/VI nay tạo tự động từ Atlas; phiếu review giữ owner, receipt và
  quyết định khi chạy lại. Runtime proof vẫn là việc reviewer phải làm.
- E: V3 target riêng có nhiều block/quan hệ tĩnh, nhưng phần lớn bước tài liệu
  chưa bound; báo cáo riêng ghi rõ khoảng trống. Gói handoff generic đã chạy
  trên target và ví dụ public; chưa chứng minh một request path end-to-end.
- F: README EN/VI và design doc đã cập nhật; full pytest/Ruff/Markdownlint/
  link/browser QA của handoff generic pass trên demo public. Bản `v0.8-preview` ghi rõ hợp đồng
  portability và phần reviewer phải làm; review release V1.0 còn mở. Không gắn
  nhãn V1.0 hoàn tất khi D/E còn mở.
