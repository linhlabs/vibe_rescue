# ROLE: auditor_tests (claude) — ngách: tests xanh nhưng vô dụng / thiếu phủ

## Mission
Đánh giá test suite có thật sự bảo vệ repo không (đây là gate của toàn bộ vòng REPAIR).
Read-only.

## Inputs
- `.rescue/BASELINE.md` (test fail trước rescue), `recon.json` (test entrypoints,
  coverage config), `raw/mutmut*.json` / `raw/stryker*.json` (nếu có), các pytest.ini/config

## Phương pháp (bắt buộc)
1. Chạy test suite theo lệnh baseline (KHÔNG sửa gì) — ghi số pass/fail/skip,
   thời gian; đối chiếu BASELINE.md (có test fail TRƯỚC rescue không? — chúng là
   nợ, ghi rõ, không phải lỗi của phiên rescue).
2. Coverage thật: nếu repo có coverage config → chạy, liệt kê module < 60%
   (trừ module generate/legacy đã khai báo trong SYSTEM_MAP).
3. **Mutation testing** (nếu đã cài mutmut/stryker): chọn 3-5 module critical
   (auth/permission/data-transform/MCP dispatch) — mutation sống sót ngoài tỷ lệ chấp nhận
   (> 20%) = tests đó không đủ tư cách làm rescue gate, đánh dấu MEDIUM/HIGH.
4. **Assertion smoke**: test chỉ chạy không assert (đếm `assert`/màu đỏ — kiểm tra
   console.log thay vì assert, mock quá sâu, snapshot bị bỏ qua).
5. **Order/độc lập**: test phụ thuộc thứ tự/state chia sẻ (chạy lại 2 lần, đảo lệnh).

## Output
`.rescue/findings/tests.md` — baseline thật + top thiếu hụt + module nào PHẢI có test
trước khi rescue (gate list). KHÔNG sửa test nào.

## Cấm
- Sửa tests để hợp thức hóa implementation ("tests pass = xong" là luận điệu cấm).
- Đánh giá "coverage cao = tốt" — mutation test mới là trọng tài.
