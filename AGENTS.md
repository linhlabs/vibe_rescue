# vibe_rescue — AGENTS (canonical agent contract)

Mục tiêu sản phẩm bền vững: [docs/PRODUCT_NORTH_STAR.md](docs/PRODUCT_NORTH_STAR.md).
Kế hoạch V1.0 hiện hành: [PLAN.md](PLAN.md). EXPLORE phải nối kiến trúc,
hành trình và hàm theo bằng chứng; tên hàm/scanner không chứng nhận harness,
swarm hoặc an toàn PII/PHI/billing.

> **Audience:** mọi LLM/agent mở repo này (Claude · ChatGPT · Codex · future).
> Đây là contract canonical, không phụ thuộc tool. File tool-specific
> (`CLAUDE.md`, `GEMINI.md`) CHỈ là con trỏ 1 dòng — không bao giờ lặp nội dung.

## Onboarding (bắt buộc, theo thứ tự)

1. Đọc hết `README.md` — pipeline MAP → PROVE → PLAN → REPAIR → LOCK và 6 nguyên tắc sắt.
2. Đọc `STATUS.md` — trạng thái sống: cái gì xong, cái gì đang làm, cái gì pending.
   Sau mỗi bước bạn thực hiện PHẢI cập nhật file này.
3. Đọc `docs/RULES.md` — đây là LUẬT, nó override convenience. Nếu vi phạm = chấp nhận REVISE.
4. Đọc `docs/OWNER_PACT.md` + `docs/VOYAGE.md` — pact với owner: không đổi gì chưa đồng ý,
   backup+revert, never-break; protocol chạy autonomous, cách trả lời dialogue.
5. Đọc `docs/PIPELINE.md` — entry/exit criteria từng phase + format finding/plan.
6. Tìm vai trò của bạn trong `agents/` đúng tên, đọc đầy đủ trước khi làm.

## Bạn được phép / không được phép

- ĐƯỢC: đọc mọi file; chạy tool scanner (read-only); chạy `scripts/*` để gom bằng chứng;
  VIẾT trong `reports/`, `logs_audit/`, và `.rescue/<target>/` **của phiên chạy**;
  đề xuất thay đổi harness qua diff + cập nhật STATUS.md.
- KHÔNG ĐƯỢC: ghi/đổi file của repo mục tiêu trong phase MAP/PROVE/PLAN;
  sửa code target ngoài executor trong worktree rời với plan đã duyệt;
  tự tuyên bố "xong" — chỉ máy (gates/delta) hoặc reviewer xác nhận;
  ghi dữ liệu nhạy cảm (PII/PHI, khóa) ra ngoài `.rescue/`, `reports/`, `logs_audit/`.
- Kết luận về nội dung có ý nghĩa pháp lý bằng regex (xem `docs/RULES.md` R6).

## Conventions

- Không emoji trong code/file.
- Tài liệu dùng tiếng Việt; tiếng Anh OK cho audit handoff (logs_audit/).
- Mọi lỗi loud, rõ [WHAT]/[WHY]/[HOW], fail-closed.
- Findings có evidence; plan có STOP conditions; đồng ý trước khi cam kết.
