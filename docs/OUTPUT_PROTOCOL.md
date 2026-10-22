# OUTPUT_PROTOCOL — output ra cho TEAM đọc (không jargon, hiểu ngay, fix ngay)

> Mọi phiên `rescue_voyage` PHẢI kết thúc bằng bộ 3 artifact tại
> `<target>/.rescue/voyage/review/` — team chỉ cần mở 1 nơi duy nhất.
> (đội muốn chuyển vào `audit_claude/` của mình thì copy sau khi xem — harness
> không tự ghi vào tree của target khi chưa đồng ý, PACT P1.)

## Bộ 3 artifact (thứ tự đọc)

| File | Cho ai | Nội dung | Ngôn ngữ |
|---|---|---|---|
| `README.md` | Team + PM (đọc đầu tiên, 2 phút) | Tình hình 1 trang: Điều tốt · Điều cần sửa (top 5-7, mức ưu tiên) · Số liệu đã đọc từ đâu | Tiếng Việt, không jargon |
| `PROPOSALS.md` | Engineer (đọc là fix được) | Từng thẻ: **ID · Vấn đề (lời thường) · Bằng chứng (file:line / tool) · Sửa sao (từng bước) · Rủi ro · Verify · Ưu tiên** + **TL;DR (EN)** 1 dòng | Tiếng Việt + TL;DR EN |
| `EVIDENCE/` | Auditor / ML | raw scanner JSON + `findings.json` + SARIF + archgraph (máy, không edit) | máy |

## Luật "không jargon" (bắt buộc — RULES R2)

- Không thuật ngữ kỹ thuật trừ khi có phiên giải trong ngoặc (vd "god-file (1 file quá to,
  chứa quá nhiều việc)").
- Mỗi vấn đề: kể được bằng 1 câu "file X làm A, B, C luôn — đổi C phải đọc cả A, B".
- Mỗi proposal kèm: `làm gì` (1 câu) + `giống lệnh nào` (verify command) + `không làm gì`
  (out-of-scope, RULES R9).
- KHÔNG ghi "nên clean", "nên refactor" trống — luôn kèm bằng chứng + cách làm cụ thể.

## Khi nào viết được proposal tốt

- Máy cung cấp evidence (fanout/archgraph) → LLM agent (stage `review`) đọc evidence + code
  hot-spot → viết/điền 2 file. Agent không chạy được (thiếu CLI) → harness tạo template
  đã có sẵn số liệu + cột trống — team/owner điền tiếp, không chặn.

## Lộ trình của một phiên từng phase → artifact nào

| Phase | Artifact |
|---|---|
| map | `map/context.txt`, `map/recon.json` (đều đã redact khóa) |
| prove | `prove/findings.json` + `.sarif` + `raw/*.json` (đã redact ở nguồn) + baseline |
| review | `review/README.md` + `review/PROPOSALS.md` + `review/EVIDENCE/` (bản đọc được của team) |
| plan | `PLAN-*.md` (máy kiểm) |
| repair | `logs/` verdict + `CHANGES.log` + `REVERT.md` |

## v0.4 — niềm tin có cơ chế, không phải lời hứa

Ba cơ chế tự động chạy ngay sau stage `review`, người đọc nhìn vào là biết tin đến đâu:

1. **Máy kiểm số — `EVIDENCE/number-check.md`** (`scripts/check_review_numbers.py`).
   Mỗi con số LLM nêu trong README/PROPOSALS được máy đối chiếu với JSON scanner
   (radon/gitleaks/ruff/… + AST cho "N hàm con"): ✓ khớp · ✗ lệch (ghi số thật) ·
   ? máy không kiểm được. Số lệch KHÔNG bị xóa — giữ nguyên và gắn nhãn, người đọc tự thấy.
2. **EVIDENCE tự chứa — `EVIDENCE/summary.md` + `raw/*.json`** (`scripts/collect_evidence.py`).
   Copy JSON đã redact vào EVIDENCE/ kèm 1 lệnh mẫu tự kiểm lại — không phụ thuộc việc
   bạn có đứng ở máy chạy hay không.
3. **Mắt thứ hai — `EVIDENCE/cross-check.md`** (`agents/crosscheck.md` + vai verify).
   LLM KIỂM độc lập chấm chéo bản review: số sai, mâu thuẫn, thiếu bằng chứng; verdict
   1 dòng `CROSSCHECK: CLEAN` hay `CROSSCHECK: N ISSUE`. Fail-open — thiếu mắt thứ hai
   không chặn phiên, nhưng phải thấy được (file ghi rõ vì sao không chạy).

Và một cảnh báo PACT in ra terminal nếu target chưa gitignore `.rescue/` — harness
KHÔNG tự sửa `.gitignore` của target (PACT P1), owner quyết.
