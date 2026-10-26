# Phân tích sổ hẹn khám mẫu

- **Dự án:** sổ hẹn khám mẫu
- **Ngày:** 01/01/2026
- **Người đọc:** PO
- **Kết luận:** Dùng nội bộ được. Chưa mở cho khách.
- **Trạng thái:** Vàng nếu dùng nội bộ, Đỏ nếu mở cho khách.
- **Thời gian đọc:** lướt phần in đậm 5 phút, đọc hết 10 phút
- **Số chính:** 120 lịch hẹn mẫu; 3/9 tính năng đánh giá Yếu; 5 việc ưu tiên cao

Dữ liệu giả, chỉ dùng để kiểm thử script dựng.
- Mọi điểm mặc định là **đã xác minh trong code**: đọc code thấy đúng, chưa thử trên hệ thống thật.
- Mã như [P1] dẫn tới bằng chứng trong phụ lục cho dev.

---

## 1. Tóm tắt

**Hiện tại**

- **Đặt lịch và nhắc lịch đã chạy trên dữ liệu mẫu.**
- **Khách có thể thấy lịch hẹn của người khác.** [P1]
- **Tin nhắn nhắc lịch gửi trùng hai lần.** [P2]

**Cần cải thiện trước nhất**

1. Chặn xem lịch của người khác (effort nhỏ).
2. Ghi lại tin nhắn đã gửi (effort nhỏ).

> Chưa thử trên hệ thống thật; dev xác nhận được trong khoảng 10 phút.

---

## 2. Sản phẩm giải bài toán gì

- **Khách hàng:** phòng khám nhỏ.
- **Vấn đề:** ghi lịch hẹn bằng sổ giấy, **hay trùng giờ**.
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

### 3.1 Xem lịch hẹn (rủi ro cao)

**Hiện tại**

- **Khách có thể thấy lịch hẹn của người khác.** [P1]

**Cần cải thiện**

- Chặn xem lịch của người khác (effort nhỏ).

### 3.2 Nhắc lịch (rủi ro cao)

**Hiện tại**

- **Tin nhắn gửi trùng hai lần**, khách gọi lại hỏi. [P2]

**Cần cải thiện**

- Ghi lại tin đã gửi (effort nhỏ).

---

## 4. Rủi ro tổng thể

**Cao, làm trước khi mở cho khách:**

1. **Lộ thông tin khách** (3.1). Effort nhỏ.
2. **Nhắc lịch trùng** (3.2). Effort nhỏ.

### 4.1 Phân quyền nhân viên (cao)

**Hiện tại**

- **Ai cũng sửa được lịch**, kể cả nhân viên mới. [P5]

**Cần cải thiện**

- Thêm phân quyền theo vai trò (effort vừa).

### 4.2 Trùng giờ hẹn (trung bình)

**Hiện tại**

- **Đặt trùng giờ không có cảnh báo.** [P3]

**Cần cải thiện**

- Báo khi giờ đã có người đặt (effort nhỏ).

---

## 5. Phần thừa cần dọn

- **Rà được 12 mục:** 5 xóa ngay được, 7 cần PO quyết.

---

## 6. Việc nên làm tiếp

| # | Việc | Ưu tiên | Effort | Ai làm |
|---|---|---|---|---|
| 1 | Chặn xem lịch của người khác | Cao | Nhỏ | Dev |
| 2 | Thêm phân quyền theo vai trò | Cao | Vừa | Dev |
| 3 | Báo cho bác sĩ khi khách hủy | Trung bình | Nhỏ | Dev |
| 4 | Dọn phần thừa | Thấp | Nhỏ | Dev, PO |

---

## 7. Lần này chưa kiểm

- **Hệ thống thật:** chưa chạy thử.
- **Khách thật:** chưa có số liệu sử dụng.

---

## 8. Câu hỏi cho team dev

1. Tin nhắn nhắc lịch gửi qua dịch vụ nào?
2. Có bản sao lưu dữ liệu tự động không?

---

## 9. Phụ lục cho dev

Phụ lục có chi tiết kỹ thuật về lỗ hổng. Khi chia sẻ báo cáo ra ngoài team, bỏ phần này.

| Mã | Rủi ro | file:dòng | Ghi chú kỹ thuật |
|---|---|---|---|
| P1 | Thấy lịch của người khác | `app/api/lich.py:10-20` | Truy vấn thiếu điều kiện lọc theo khách. Nhãn: đã xác minh trong code. |
| P2 | Nhắc lịch gửi trùng | `app/jobs/nhac_lich.py:5` | Lịch chạy hai lần mỗi giờ. Nhãn: đã xác minh trong code. |
| P3 | Trùng giờ không báo | `app/api/dat_lich.py:30` | Khóa trùng là `ma|ngay`, thiếu giờ. Nhãn: đã xác minh trong code. |
| P4 | Hủy lịch không báo bác sĩ | `app/api/huy.py:12` | Không gọi hàm gửi tin. Nhãn: suy luận. |
| P5 | Ai cũng sửa được lịch | `app/auth/quyen.py:1-40` | Chưa có kiểm vai trò. Nhãn: đã xác minh trong code. |
