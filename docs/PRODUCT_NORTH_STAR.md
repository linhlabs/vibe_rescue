# Vibe Rescue — mục tiêu sản phẩm bền vững

Vibe Rescue giúp một team **hiểu và cứu một repo lộn xộn** trước khi sửa nó.
Người mới phải mở một HTML offline và lần được: sản phẩm giải quyết việc gì,
các khối chức năng tồn tại vì sao, một hành trình đi qua những khối nào, hàm
nào gọi hàm nào với tham số gì, guard/side effect/audit ở đâu, và điều gì còn
chưa được chứng minh. Danh sách file/hàm hoặc một graph import đứng riêng không
đạt mục tiêu này.

## Hợp đồng trải nghiệm V1.0

1. **Kiến trúc trước, chi tiết sau.** Trang đầu hiển thị mục đích của repo,
   nhóm chức năng có tên dễ hiểu, quan hệ giữa nhóm và các hành trình được
   tài liệu mô tả. Click nhóm → trách nhiệm, đầu vào/đầu ra, config/prompt liên
   quan, các cạnh gọi/import; click bước → hàm, file:dòng, tham số, caller/callee,
   guard, lỗi và test liên quan. Có đường quay lại tầng trên.
2. **Tài liệu và code phải được nối bằng bằng chứng.** Đọc README/architecture/
   design trong scope đã duyệt; giữ trích dẫn `file:line`. Cạnh gọi được parser
   xác định phải có callsite. Lời mô tả từ tài liệu là *claim của tài liệu*,
   không tự biến thành sự thật runtime. Liên kết ngữ nghĩa do model gợi ý phải
   gắn nhãn `suggested` đến khi source/trace/test xác nhận.
3. **Không bỏ sót trong im lặng.** Manifest ghi file, ngôn ngữ, parser, shard,
   lỗi parse, cạnh động/cross-shard, tài liệu chưa đọc, bước chưa nối được,
   mã không hỗ trợ. HTML/SVG có thể chia trang; mọi phần vẫn tìm được từ index.
4. **Audit agent harness và swarm thực chất.** Tìm intent/plan, tool boundary,
   fan-out/concurrency, budget, timeout, cancel, retry, termination, evidence,
   judge/auditor, audit trail, rollback và owner authority. Nhiều agent hoặc
   `asyncio.gather` chỉ là dấu vết, không chứng minh swarm production-ready.
5. **Profile nhạy cảm.** Với PII/PHI/medical/billing, dẫn người review qua
   intake → storage → provider/tool egress → writer/final answer → logs/telemetry.
   Kiểm masking/redaction, subject/tenant isolation, consent/authorization,
   audit từng bước, final audit, fault path và retention. Không suy ra an toàn
   chỉ từ tên hàm `mask` hay một test xanh; cần trace và fault injection.
6. **Khuyến nghị có thể giao việc.** Mỗi gap nêu tác động, độ tin cậy, bằng
   chứng hoặc lý do chưa có, nơi cần xác minh, test/probe đề xuất, STOP condition
   và owner. Handoff của team có phiếu ghi người phụ trách, receipt theo đúng
   build và quyết định; chạy lại bản đồ không xóa phần reviewer đã điền. Không
   biến hàng nghìn warning scanner thành hàng nghìn bug.
7. **Portable và local-first.** Core chạy deterministic/offline trên Git repo,
   nhiều ngôn ngữ ở mức parser hỗ trợ. Model OpenAI-compatible tự host là tùy
   chọn để diễn giải bằng chứng, không là điều kiện lập bản đồ. Không gửi source,
   PII/PHI hay secrets tới provider nếu chưa có cấu hình/ủy quyền rõ ràng.

## Từ vựng bằng chứng bắt buộc

<!-- markdownlint-disable MD013 -->

| Trạng thái | Nghĩa |
| --- | --- |
| `documented` | Tài liệu trong scope nói như vậy, có `file:line`; chưa đối chứng code. |
| `source_observed` | Parser tìm thấy định nghĩa/call/import/guard tại `file:line`; chưa là runtime. |
| `suggested` | Ghép mục đích/bước/hàm bằng heuristic hoặc LLM; phải xác minh. |
| `runtime_verified` | Trace/probe trên snapshot và cấu hình cụ thể xác nhận nhánh đó. |
| `test_verified` | Test có receipt trên snapshot cụ thể; chỉ chứng minh case đã chạy. |
| `unknown` | Không đủ bằng chứng hoặc scope/parser không bao phủ. |

<!-- markdownlint-enable MD013 -->

`not located in scope` không đồng nghĩa với “không tồn tại”. Không có trạng thái
`production-ready` do static scanner tự cấp. Quyết định release thuộc owner sau
review độc lập và phép thử của chính repo mục tiêu.

## Điều không được hy sinh

Không sửa source repo mục tiêu trong EXPLORE/AUDIT. Không xuất dữ liệu nhạy cảm
vào HTML public. Không đọc kho dữ liệu/log/audit archive chỉ để tăng coverage.
Không giấu cạnh không phân giải được, không vẽ đường runtime từ tên hàm, không
đổi kiểm thử chỉ để có màu xanh. Sửa code Vibe Rescue phải có fixture phản chứng
và chạy suite phù hợp.
