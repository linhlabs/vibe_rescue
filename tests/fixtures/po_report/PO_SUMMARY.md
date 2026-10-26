# Phân tích sổ hẹn khám mẫu

- **Dự án:** sổ hẹn khám mẫu
- **Ngày:** 01/01/2026
- **Người đọc:** PO
- **Kết luận:** Dùng nội bộ được. Chưa mở cho khách.
- **Trạng thái:** Vàng nếu dùng nội bộ, Đỏ nếu mở cho khách.
- **Thời gian đọc:** khoảng 3 phút
- **Số chính:** 120 lịch hẹn mẫu; 3/9 tính năng đánh giá Yếu; 3 nhóm rủi ro cao; 4 việc cần làm trước

Dữ liệu giả, chỉ dùng để kiểm thử script dựng.
- Mã như [P1] dẫn tới bằng chứng trong phụ lục cho dev.

---

## 1. Tóm tắt

**Hiện tại**

- **Đặt lịch và nhắc lịch đã chạy trên dữ liệu mẫu.**
- **Khách có thể thấy lịch hẹn của người khác.** [P1]
- **Tin nhắn nhắc lịch gửi trùng hai lần.** [P2]

Chưa thử trên hệ thống thật.

---

## 2. Sản phẩm giải bài toán gì

- **Khách hàng:** phòng khám nhỏ, đang **ghi lịch hẹn bằng sổ giấy**.
- **Giải pháp:** sổ hẹn trên web, nhắc lịch qua tin nhắn.
- **Thu tiền:** thuê bao theo tháng; **giá chưa chốt**.

---

## 3. Tính năng và đánh giá

- **9 tính năng** theo hành trình khách.

| # | Tính năng | Trạng thái | Đánh giá | Rủi ro chính |
|---|---|---|---|---|
| 1 | Đăng ký phòng khám | Đang dùng | Tốt | Thấp. |
| 2 | Đặt lịch | Đang dùng | Tạm | **Trung bình.** Trùng giờ không báo [P3] |
| 3 | Xem lịch hẹn | Đang dùng | Yếu | **Cao.** Thấy lịch của người khác [P1] |
| 4 | Nhắc lịch | Đang dùng | Yếu | **Cao.** Gửi trùng hai lần [P2] |
| 5 | Hủy lịch | Làm dở | Tạm | **Trung bình.** Không báo cho bác sĩ [P4] |
| 6 | Báo cáo tháng | Đang dùng | Tốt | Thấp. |
| 7 | Phân quyền nhân viên | Làm dở | Yếu | **Cao.** Ai cũng sửa được lịch [P5] |
| 8 | Xuất Excel | Đang dùng | Tốt | Thấp. |
| 9 | Đổi giờ hẹn | Đang dùng | Tạm | **Trung bình.** Tin nhắn cũ không bị thu hồi [P2, P4] |

- **Đang ổn:** đăng ký, báo cáo tháng, xuất Excel.

---

## 4. Rủi ro cao

3 nhóm cần xử lý trước khi mở cho khách.

### 4.1 Lộ thông tin khách (rủi ro cao)

**Hiện tại**

- **Khách có thể thấy lịch hẹn của người khác.** [P1]
- **Ai cũng sửa được lịch**, kể cả nhân viên mới. [P5]

**Cần cải thiện**

- Chặn xem lịch của người khác (effort nhỏ).
- Thêm phân quyền theo vai trò (effort vừa).

### 4.2 Nhắc lịch (rủi ro cao)

**Hiện tại**

- **Tin nhắn gửi trùng hai lần.** [P2]

**Cần cải thiện**

- Ghi lại tin đã gửi (effort nhỏ).

### 4.3 Hủy lịch (rủi ro cao)

**Hiện tại**

- **Bác sĩ không biết lịch đã hủy.** [P4]

**Cần cải thiện**

- Báo cho bác sĩ khi khách hủy (effort nhỏ).

---

## 5. Việc cần làm

| # | Việc | Effort | Ai làm |
|---|---|---|---|
| 1 | Chặn xem lịch của người khác | Nhỏ | Dev |
| 2 | Thêm phân quyền theo vai trò | Vừa | Dev |
| 3 | Ghi lại tin nhắn đã gửi | Nhỏ | Dev |
| 4 | Quyết có mở cho khách trong tháng này không | Nhỏ | PO |

---

## 6. Phần thừa

- **Rà được 12 mục:** 5 xóa ngay được, 7 cần PO quyết.

---

## 7. Lần này chưa kiểm

- **Hệ thống thật:** chưa chạy thử.
- **Khách thật:** chưa có số liệu sử dụng.

---

## 8. Câu hỏi cho team dev

1. Tin nhắn nhắc lịch gửi qua dịch vụ nào?
2. Có bản sao lưu dữ liệu tự động không?
