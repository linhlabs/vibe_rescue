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

## Hiển thị output cuối cùng cho PO và business (RULES R13)

Áp dụng khi người đọc cuối là PO, chủ sản phẩm hoặc business user không đọc code.
`README.md` và `PROPOSALS.md` ở trên vẫn là output cho team kỹ thuật; khi owner cần
báo cáo cho PO/business thì giao thêm 2 bản dưới đây (tên gợi ý: `review/PO_SUMMARY.md`
và `review/PO_DETAIL.md`, kèm HTML dựng từ chúng).

Nguồn gốc: lần rà soát thật đầu tiên với owner (2026-10-27). Bản đầu dài khoảng 5.600 chữ,
viết thành đoạn văn và lẫn thuật ngữ code nên PO không đọc được; bản được chấp nhận
dài khoảng 1.200 chữ, gạch đầu dòng, chia "Hiện tại" / "Cần cải thiện".

### Giao 2 bản, trỏ qua lại

| Bản | Để làm gì | Độ dài | Hiển thị |
|---|---|---|---|
| Bản ngắn | đọc nhanh, ra quyết định | khoảng 1.200 chữ, đọc 3 phút | slide 16:9 xếp dọc, cuộn chuột để đọc (không bấm next/prev); in PDF mỗi slide một trang |
| Bản chi tiết | tra cứu, giao việc | đầy đủ | trang một cột kiểu Notion; phụ lục cho dev thu gọn trong toggle |

- Mã bằng chứng (P1, P2...) trên bản ngắn mở đúng dòng trong phụ lục của bản chi tiết.
- Bìa bản ngắn có liên kết sang bản chi tiết; bản chi tiết có liên kết quay lại bản ngắn.

### Cấu trúc bản ngắn (slide)

1. Bìa: tên project, ngày, kết luận 1 câu (ví dụ "Demo được. Chưa nên thu tiền khách.") và 4 con số chính.
2. Tóm tắt: tối đa 5 dòng "Hiện tại".
3. Sản phẩm giải bài toán gì: 3 dòng (khách hàng và vấn đề, giải pháp, cách thu tiền).
4. Tính năng và đánh giá: bảng `# | Tính năng | Trạng thái | Đánh giá | Rủi ro chính`, tối đa 7 dòng mỗi slide.
5. Rủi ro cao: gộp theo nhóm, mỗi nhóm 1 slide hai cột "Hiện tại" / "Cần cải thiện"; nhóm ngắn ghép 2 nhóm một slide.
6. Việc cần làm: tối đa 6 việc, cột `# | Việc | Effort | Ai làm`.
7. Phần thừa và phần chưa kiểm: mỗi bên tối đa 3 dòng.
8. Câu hỏi cho team dev: tối đa 3 câu.

Rủi ro trung bình chỉ có 1 dòng trong bảng tính năng. Việc ưu tiên thấp không đưa vào bản ngắn.

### Cấu trúc bản chi tiết (trang)

Đầu trang: tiêu đề, danh sách thuộc tính (phiên bản, ngày, người đọc, kết luận, thời gian
đọc, các con số chính), khung "Cách đọc", mục lục. Sau đó 9 phần:

1. Tóm tắt
2. Sản phẩm giải bài toán gì
3. Tính năng và đánh giá: bảng, rồi một mục cho mỗi tính năng có rủi ro
4. Rủi ro tổng thể: thứ tự ưu tiên, rồi một mục cho mỗi rủi ro
5. Phần thừa cần dọn
6. Việc nên làm tiếp: cột `# | Việc | Ưu tiên | Effort | Ai làm`
7. Lần này chưa kiểm
8. Câu hỏi cho team dev
9. Phụ lục cho dev: bảng `Mã | Rủi ro | file:dòng | Ghi chú kỹ thuật`, thu gọn mặc định

### Luật viết (cả hai bản)

- Kết luận trước, 1 câu.
- Gạch đầu dòng 1-2 câu, in đậm ý chính của từng dòng. Chỉ in đậm: không gạch chân, không tô nền.
- Mỗi tính năng hoặc rủi ro chia "Hiện tại" (vấn đề) và "Cần cải thiện" (đề xuất kèm effort nhỏ, vừa hoặc lớn).
- Mỗi rủi ro chỉ viết chi tiết 1 lần; chỗ khác dẫn tới số mục.
- Phần chính không có tên file, tên hàm, thuật ngữ code chưa giải thích (R2 "không jargon" ở trên vẫn áp dụng). Bằng chứng `file:dòng` chỉ nằm trong phụ lục, dẫn bằng mã P.
- Mức chắc chắn: mặc định là "đã xác minh trong code" (đọc code thấy đúng, chưa thử trên hệ thống thật); chỗ khác ghi "(suy luận)" hoặc "(chưa kiểm)" ngay cạnh. Không nâng nhãn khi gộp hay rút gọn.
- Lỗ hổng bảo mật: phần chính chỉ nói ảnh hưởng (ví dụ "có thể tự tăng credit"), không mô tả cách khai thác. Chi tiết kỹ thuật để trong phụ lục, kèm dòng nhắc bỏ phụ lục khi chia sẻ ra ngoài team.
- Không bịa số: effort chỉ ghi nhỏ, vừa, lớn; mọi con số phải có nguồn trong evidence.
- Tránh văn kiểu AI: câu "X lại chính là Y: ...", "không chỉ... mà còn...", ẩn dụ, câu đối gọn ("sai nhỏ bị bắt, sai lớn lọt"), mở đầu "Điều đáng chú ý là".
- Không đưa vào: mật khẩu, khóa, mã người dùng, mã dự án, URL database.

### Luật hiển thị

- Light mode, nền trắng tối giản, chữ xám đậm, một màu nhấn (teal). Không gradient, không đổ bóng nặng.
- Mức độ và đánh giá dùng tag màu pastel: đỏ cho Cao và Yếu, vàng cho Trung bình và Tạm, xanh cho Thấp và Tốt.
- Bản chi tiết: một cột khoảng 760px, khung callout nền nhạt có icon, bảng kẻ ô xám nhạt, phụ lục dạng toggle. Icon vẽ bằng CSS hoặc SVG, không dùng emoji (AGENTS.md).

### Dựng và kiểm trước khi giao

- LLM viết nội dung Markdown theo cấu trúc trên; HTML dựng từ Markdown bằng script deterministic, LLM không tự viết HTML. Script dựng chưa có trong repo (STATUS.md, mục Open gaps).
- Không slide nào tràn chữ ở khổ màn hình 1024 đến 1920px.
- Mọi mã P mở đúng dòng trong phụ lục.
- In PDF ra đúng số slide, mỗi slide một trang.
- Quét lại cả hai bản: không có khóa, mật khẩu, dữ liệu cá nhân.
