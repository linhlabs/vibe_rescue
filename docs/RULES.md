# RULES — Luật ràng buộc của vibe_rescue (binding law)

> Mọi agent mở repo này phải đọc. Luật này override sự tiện lợi.
> Nguồn gốc: bài học từ nghiên cứu rescue harness
> (xem docs/REFERENCE_STACK.md — mục "không first responder").

## R1. Mục đích duy nhất

Harness này cứu repo hỗn loạn. Nó KHÔNG viết feature mới, KHÔNG refactor theo sở thích,
KHÔNG thay thế CI của repo mục tiêu. Mỗi phiên chạy có một intent duy nhất, nêu ra đầu tiên.

## R2. Phân quyền ghi (write authority)

| Vai trò | Được ghi vào target? |
|---|---|
| auditor_* (đọc/kiểm) | KHÔNG BAO GIỜ |
| advisor (lập plan) | KHÔNG BAO GIỜ — chỉ viết trong `.rescue/` của phiên |
| executor | CHỈ file trong allowlist của plan, trên git worktree rời |
| reviewer / codex | KHÔNG — chỉ viết verdict vào `logs_audit/` |
| orchestrator | CHỈ artifacts (reports/, .rescue/, logs_audit/) |

Ai ghi ngoài quyền = REVISE ngay, không tranh luận. Đây là ràng buộc vận hành;
worktree Git và kiểm tra diff phát hiện một số vi phạm, không cách ly lệnh CLI
khỏi quyền filesystem/network của host (xem `SECURITY.md`).

## R3. Evidence-first

Finding không có `file:line` = không tồn tại. Trường bắt buộc:

```
ID | category | file:line | evidence (rule id / output scanner) | reproduction
impact | confidence | fix_risk | dependencies | verification_command
```

"Nhìn khó hiểu", "repo này bẩn" → KHÔNG phải finding. Phải quy về:
từ khoá nào, file nào, rule nào, chạy lệnh gì để thấy lại.

## R4. Máy trước, LLM sau (deterministic authority)

1. Chạy scanner (scripts/fanout.py) → raw evidence.
2. LLM đọc evidence, diễn giải, xếp hạng — KHÔNG tự sinh "bằng chứng" từ đầu.
3. Kiểm tra "text ⊂ page" là string containment, không phải pattern-scan.

## R5. No-fix trong phase audit

MAP/PROVE/PLAN không chủ động sửa source target. Executor chỉ được sửa candidate
worktree từ plan đã duyệt (human OK). Không có ngoại lệ "tiện thể sửa nhẹ".
Scanner/agent bên thứ ba có thể tạo side effect; dùng môi trường cô lập khi
target chưa tin cậy.

## R6. Regex chỉ ở tầng cơ khí, không kết luận về ý nghĩa pháp lý

Regex/pattern chỉ được dùng ở tầng cơ khí không quyết định nội dung (che khóa, whitespace,
slug URL, tìm tên file). Việc xác định nội dung có ý nghĩa pháp lý (tên/số luật, điều khoản,
trích dẫn, ngày ký) do người hoặc LLM đọc kèm trích dẫn nguyên văn và kiểm lại, không do regex.

→ Hệ quả trong harness này: scanner tìm dependencies/license/secrets thì OK (structural);
tìm "vi phạm luật X tại điều Y" thì người/LLM đọc, không viết rule regex.

## R7. Baseline-first (không đốt nhà vì scanner đỏ)

- Lần đầu scan = ghi BẢN baseline nợ (debt). CI block CHỈ finding MỚI.
- Dọn nợ theo module, giảm baseline dần. Cấm "rewrite toàn bộ vì scanner đỏ".

## R8. Plan machine-checkable

Plan không có: scope allowlist + out-of-scope + từng bước nhỏ có verification +
STOP conditions + rollback + done criteria máy kiểm được → advisor phải viết lại
(plan_check.py exit 2). Một plan không có STOP condition = chưa production-ready.

## R9. Một PR một outcome

Cấm PR kiểu "refactor toàn bộ + update deps + rewrite docs + add framework".
Cấm executor sửa tests chỉ để tests pass. Không "cleanup tiện thể".

## R10. Four-eyes (bắt buộc)

Mọi thay đổi sau REPAIR phải có verdict Codex độc lập trong `logs_audit/`
(file riêng, không ghi đè). Cho phép lưu: APPROVE / REVISE(ghi lý do) / BLOCK.
REVISE chặn merge cho tới khi đóng.

## R11. Fail-closed, loud

Tool hỏng → dừng bước đó, ghi rõ [WHAT]/[WHY]/[HOW], không bỏ qua lặng lẽ.
Output tiếng Việt cho người dùng cuối; tiếng Anh OK cho audit handoff.

## R12. Harness không thành repo xấu

- Core = stdlib Python + scripts + markdown contracts. Thêm capability = thêm 1 file nhỏ,
  không khung framework. (Bài học autogen: 60k sao nhưng 4 tháng không commit.)
- Mỗi script mới phải có test trong tests/; chạy trước khi merge.
- Cập nhật STATUS.md thật — không phấn nến.
