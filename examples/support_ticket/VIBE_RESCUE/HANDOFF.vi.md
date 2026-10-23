<!-- markdownlint-disable MD013 -->

# Bàn giao cho team — support_ticket

**Gói bằng chứng, chưa là phán quyết sẵn sàng.** Mở bản đồ kiến trúc, lần theo source rồi giao các phép thử bên dưới. Lệnh này không chạy test hay trace runtime của target.

[Phiếu review](REVIEW_WORKSHEET.vi.md) · [Architecture Atlas](architecture.html) · [Source Explorer](source-explorer.html) · [Machine JSON](architecture.json)

## Tổng quan

- Git HEAD: `unknown`; file đã đổi: `unknown`. Bằng chứng worktree chưa là định danh build đang deploy.
- Dấu vân tay Atlas: `dd33c0294b011e9e60f539b99a4200b7ad2d2feaed3dbffe901a8d5da0bf5f3b`; scope source được duyệt: `.`.
- 6 file code; 6 khối; 8 quan hệ giữa khối; hành trình tài liệu: 1; bước chưa nối: 0.

## Mục đích theo tài liệu

A synthetic support-ticket workflow accepts a message, classifies its intent, builds a tool plan and returns a small audit event. The example contains no real customer data and makes no claim that its PII controls are sufficient.

Nguồn: [README.md:3](../README.md#L3)
**Tài liệu có thể đã cũ.**

## Việc tiếp theo cho team

- Trace UI/API và cạnh khác ngôn ngữ; Atlas mới kiểm kê các file đó. Xem [coverage](handoff.vi.html#coverage).
- Với từng control đã chọn, lấy receipt runtime/fault trên đúng build; tên hàm và test chỉ là dấu vết. Xem [controls](handoff.vi.html#controls).

## Khối chức năng

### `actions` · Actions

The name is a control candidate, not proof of authorization enforcement. (source_docstring).
Nguồn: [actions/tools.py:1](../actions/tools.py#L1).
1 file; 1 hàm Python đã index. [Mở khối](architecture.html?block=actions).
Hàm để bắt đầu đọc: [actions.tools.allowed_tool](source-explorer.html?function=actions.tools.allowed_tool) [actions/tools.py:4](../actions/tools.py#L4).

### `audit` · Audit

A synthetic audit stub; storage and retention are outside this example. (source_docstring).
Nguồn: [audit/events.py:1](../audit/events.py#L1).
1 file; 1 hàm Python đã index. [Mở khối](architecture.html?block=audit).
Hàm để bắt đầu đọc: [audit.events.redact_event](source-explorer.html?function=audit.events.redact_event) [audit/events.py:4](../audit/events.py#L4).

### `domain` · Domain

A placeholder classifier, not a production intent model. (source_docstring).
Nguồn: [domain/policy.py:1](../domain/policy.py#L1).
1 file; 1 hàm Python đã index. [Mở khối](architecture.html?block=domain).
Hàm để bắt đầu đọc: [domain.policy.classify_intent](source-explorer.html?function=domain.policy.classify_intent) [domain/policy.py:4](../domain/policy.py#L4).

### `gateway` · Gateway

Synthetic API boundary for the public handoff example. (source_docstring).
Nguồn: [gateway/api.py:1](../gateway/api.py#L1).
1 file; 2 hàm Python đã index. [Mở khối](architecture.html?block=gateway).
Hàm để bắt đầu đọc: [gateway.api.respond](source-explorer.html?function=gateway.api.respond) [gateway/api.py:15](../gateway/api.py#L15), [gateway.api.submit](source-explorer.html?function=gateway.api.submit) [gateway/api.py:8](../gateway/api.py#L8).

- → `audit` · import · 1 tham chiếu; [gateway/api.py:3](../gateway/api.py#L3) (exact_lexical).
- → `audit` · static_call · 1 tham chiếu; [gateway/api.py:11](../gateway/api.py#L11) (exact_lexical).
- → `domain` · import · 1 tham chiếu; [gateway/api.py:4](../gateway/api.py#L4) (exact_lexical).
- → `domain` · static_call · 1 tham chiếu; [gateway/api.py:9](../gateway/api.py#L9) (exact_lexical).
- → `orchestrator` · import · 1 tham chiếu; [gateway/api.py:5](../gateway/api.py#L5) (exact_lexical).

### `orchestrator` · Orchestrator

An intentionally small planning step; no model is called. (source_docstring).
Nguồn: [orchestrator/agent.py:1](../orchestrator/agent.py#L1).
1 file; 1 hàm Python đã index. [Mở khối](architecture.html?block=orchestrator).
Hàm để bắt đầu đọc: [orchestrator.agent.build_plan](source-explorer.html?function=orchestrator.agent.build_plan) [orchestrator/agent.py:6](../orchestrator/agent.py#L6).

- → `actions` · import · 1 tham chiếu; [orchestrator/agent.py:3](../orchestrator/agent.py#L3) (exact_lexical).
- → `actions` · static_call · 1 tham chiếu; [orchestrator/agent.py:7](../orchestrator/agent.py#L7) (exact_lexical).

### `web` · Web

No purpose statement located in approved documentation or module docstrings. (unknown).
1 file; 0 hàm Python đã index. [Mở khối](architecture.html?block=web).

## Hành trình theo tài liệu

### Request journey

Nguồn: [README.md:7](../README.md#L7).

1. `gateway.api.submit` receives the message and email address. — [gateway.api.submit](source-explorer.html?function=gateway.api.submit) [gateway/api.py:8](../gateway/api.py#L8); [README.md:9](../README.md#L9).
2. `domain.policy.classify_intent` labels the request. — [domain.policy.classify_intent](source-explorer.html?function=domain.policy.classify_intent) [domain/policy.py:4](../domain/policy.py#L4); [README.md:10](../README.md#L10).
3. `orchestrator.agent.build_plan` asks an allowed tool for a response. — [orchestrator.agent.build_plan](source-explorer.html?function=orchestrator.agent.build_plan) [orchestrator/agent.py:6](../orchestrator/agent.py#L6); [README.md:11](../README.md#L11).
4. `audit.events.redact_event` prepares an audit event without the email address. — [audit.events.redact_event](source-explorer.html?function=audit.events.redact_event) [audit/events.py:4](../audit/events.py#L4); [README.md:12](../README.md#L12).
5. `gateway.api.respond` returns a ticket result. — [gateway.api.respond](source-explorer.html?function=gateway.api.respond) [gateway/api.py:15](../gateway/api.py#L15); [README.md:13](../README.md#L13).

## Control harness và dữ liệu nhạy cảm

**Chỉ là dấu vết. Chưa chứng minh đường chạy.**

### H01 · Ý định và kế hoạch (agent)

Trạng thái: `source_candidate` (dấu vết source); 2 dấu vết.

- source_candidate: [domain/policy.py:4](../domain/policy.py#L4) · [domain.policy.classify_intent](source-explorer.html?function=domain.policy.classify_intent)
- source_candidate: [orchestrator/agent.py:6](../orchestrator/agent.py#L6) · [orchestrator.agent.build_plan](source-explorer.html?function=orchestrator.agent.build_plan)

**Cần chứng minh:** Trace đầu vào tới intent/plan có cấu trúc, gồm trường hợp mơ hồ và planner lỗi.

### H02 · Quyền gọi tool và scope (agent)

Trạng thái: `source_candidate` (dấu vết source); 1 dấu vết.

- source_candidate: [actions/tools.py:4](../actions/tools.py#L4) · [actions.tools.allowed_tool](source-explorer.html?function=actions.tools.allowed_tool)

**Cần chứng minh:** Chứng minh agent chỉ gọi tool được duyệt và không ghi ngoài scope.

### H03 · Timeout, hủy và kết thúc (agent)

Trạng thái: `not_located_in_scope` (chưa thấy trong scope); 0 dấu vết.

- Chưa thấy trong scope được duyệt.

**Cần chứng minh:** Tiêm lỗi timeout/hủy; chứng minh trạng thái cuối có giới hạn và không còn việc mồ côi.

### H04 · Retry và ngân sách (agent)

Trạng thái: `not_located_in_scope` (chưa thấy trong scope); 0 dấu vết.

- Chưa thấy trong scope được duyệt.

**Cần chứng minh:** Đo giới hạn retry/token/chi phí; chứng minh lỗi không lặp vô hạn hoặc bị bỏ qua.

### H05 · Bằng chứng và kiểm cuối (agent)

Trạng thái: `not_located_in_scope` (chưa thấy trong scope); 0 dấu vết.

- Chưa thấy trong scope được duyệt.

**Cần chứng minh:** Trace một claim từ nguồn qua writer tới phán quyết kiểm cuối.

### H06 · Audit từng bước (agent)

Trạng thái: `documented_only` (chỉ có tài liệu); 1 dấu vết.

- documented: [README.md:3](../README.md#L3)

**Cần chứng minh:** Kiểm mọi quyết định và lỗi đều có event audit đúng thứ tự, đã che dữ liệu.

### S01 · Phân việc song song (swarm)

Trạng thái: `not_located_in_scope` (chưa thấy trong scope); 0 dấu vết.

- Chưa thấy trong scope được duyệt.

**Cần chứng minh:** Nếu dùng nhiều agent song song, chứng minh giới hạn fan-out, thứ tự và backpressure.

### S02 · Review độc lập (swarm)

Trạng thái: `not_located_in_scope` (chưa thấy trong scope); 0 dấu vết.

- Chưa thấy trong scope được duyệt.

**Cần chứng minh:** Chỉ ra reviewer khác biệt, cách xử lý bất đồng và không có đường tự duyệt.

### S03 · Cô lập lỗi worker (swarm)

Trạng thái: `not_located_in_scope` (chưa thấy trong scope); 0 dấu vết.

- Chưa thấy trong scope được duyệt.

**Cần chứng minh:** Dừng một worker giữa chừng; kiểm sibling, shared state và câu trả lời cuối fail-safe.

### P01 · Đầu vào dữ liệu nhạy cảm (pii)

Trạng thái: `documented_only` (chỉ có tài liệu); 1 dấu vết.

- documented: [README.md:3](../README.md#L3)

**Cần chứng minh:** Xác định entrypoint và loại dữ liệu mà không chép PII thật vào báo cáo.

### P02 · Che dữ liệu trước egress (pii)

Trạng thái: `source_candidate` (dấu vết source); 1 dấu vết.

- source_candidate: [audit/events.py:4](../audit/events.py#L4) · [audit.events.redact_event](source-explorer.html?function=audit.events.redact_event)

**Cần chứng minh:** Tiêm lỗi masker tại mọi ranh giới outbound; chứng minh không lộ định danh thô.

### P03 · Lưu trữ, thời hạn và đồng ý (pii)

Trạng thái: `not_located_in_scope` (chưa thấy trong scope); 0 dấu vết.

- Chưa thấy trong scope được duyệt.

**Cần chứng minh:** Test consent, cách ly chủ thể, xóa/TTL và chính sách lưu trữ.

### P04 · Che dữ liệu trong audit (pii)

Trạng thái: `source_candidate` (dấu vết source); 1 dấu vết.

- source_candidate: [audit/events.py:4](../audit/events.py#L4) · [audit.events.redact_event](source-explorer.html?function=audit.events.redact_event)

**Cần chứng minh:** Kiểm audit từng bước/cuối và telemetry bằng định danh giả; không còn giá trị thô.

## Đường dẫn config, prompt và workflow

Chỉ kiểm kê đường dẫn; loader và thứ tự ưu tiên đang chạy chưa được chứng minh.

## Độ phủ và điều chưa biết

- Đã đọc 1 tài liệu có giới hạn; bỏ qua 0; 0 lỗi parse Python; 1 file ngoài Python chỉ được map ở mức file.
- Documentation claims may be stale.
- Static calls/imports do not prove a runtime request path.
- Unique module-suffix bindings assume one indexed local module; dynamic sys.path can load another module.
- Function parameters/guards are indexed for Python only; other languages retain file-level blocks.
- Control candidates are not a security or production-readiness verdict.
