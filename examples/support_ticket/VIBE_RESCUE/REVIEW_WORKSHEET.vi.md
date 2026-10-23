<!-- markdownlint-disable MD013 -->

# Phiếu review

Điền theo đúng một build và cấu hình đang chạy. Giữ receipt nhạy cảm trong workspace được kiểm soát; tại đây chỉ link bằng chứng đã che dữ liệu. Chạy lại Atlas sẽ giữ nguyên file này.

- Build / commit:
- Cấu hình đang chạy:
- Reviewer / ngày:
- Hành trình và trace được serve:

## Quyết định theo control

| ID | Người phụ trách | Receipt runtime / fault | Kết quả | Quyết định |
| --- | --- | --- | --- | --- |
| H01 — Ý định và kế hoạch | Chưa giao | Thiếu | Chưa rõ | MỞ |
| H02 — Quyền gọi tool và scope | Chưa giao | Thiếu | Chưa rõ | MỞ |
| H03 — Timeout, hủy và kết thúc | Chưa giao | Thiếu | Chưa rõ | MỞ |
| H04 — Retry và ngân sách | Chưa giao | Thiếu | Chưa rõ | MỞ |
| H05 — Bằng chứng và kiểm cuối | Chưa giao | Thiếu | Chưa rõ | MỞ |
| H06 — Audit từng bước | Chưa giao | Thiếu | Chưa rõ | MỞ |
| S01 — Phân việc song song | Chưa giao | Thiếu | Chưa rõ | MỞ |
| S02 — Review độc lập | Chưa giao | Thiếu | Chưa rõ | MỞ |
| S03 — Cô lập lỗi worker | Chưa giao | Thiếu | Chưa rõ | MỞ |
| P01 — Đầu vào dữ liệu nhạy cảm | Chưa giao | Thiếu | Chưa rõ | MỞ |
| P02 — Che dữ liệu trước egress | Chưa giao | Thiếu | Chưa rõ | MỞ |
| P03 — Lưu trữ, thời hạn và đồng ý | Chưa giao | Thiếu | Chưa rõ | MỞ |
| P04 — Che dữ liệu trong audit | Chưa giao | Thiếu | Chưa rõ | MỞ |

## Quy tắc bàn giao

Giữ control MỞ nếu thiếu đường chạy thật, đường lỗi hoặc receipt đúng build. Dấu vết source hay unit test xanh chưa đủ để quyết định phát hành.
