# SECURITY — ranh giới an toàn của vibe_rescue

Repo này điều phối scanner, lệnh test và CLI agent trên máy của người vận hành.
**Worktree Git là nơi tách thay đổi để kiểm tra, không phải sandbox bảo mật.**
Chỉ chạy toàn bộ voyage trên code và cấu hình bạn tin cậy. Với repo chưa tin cậy,
chạy trong máy/container cô lập, bỏ network khi có thể, và không cấp credential
không cần thiết.

## Những gì code hiện kiểm tra

- Voyage yêu cầu owner chấp thuận plan, hành động repair, và merge. Approval plan
  gắn SHA-256 của plan với HEAD target; đổi một trong hai thì phải duyệt lại.
  `rescue_loop.py` chạy riêng là lệnh vận hành trực tiếp, không có dialogue owner;
  người gọi phải tự bảo đảm đã được phép sửa target.
- Repair tạo candidate trong Git worktree. Probe phải xanh trên base, rồi chạy lại
  trên candidate; scanner và delta gate cũng chạy trên candidate. Lỗi ở các gate
  chặn verdict/merge. Kiểm tra phạm vi sửa và trạng thái Git phát hiện nhiều thay
  đổi ngoài plan, nhưng **không thể ngăn** subprocess có quyền host sửa file khác,
  đọc credential, gọi network hay làm side effect ngoài Git.
- `tools/meta/redact.py` che một số mẫu khóa đã biết trong context và findings
  do harness tạo. Redaction là best effort; token custom, thông tin bệnh nhân,
  dữ liệu cá nhân trong văn bản tự do, output thô của CLI và artifact của bên thứ
  ba có thể còn nguyên. Không coi `.rescue/`, `reports/`, `logs_audit/` là nơi
  lưu dữ liệu public. Kiểm tra trước khi chia sẻ; thêm `.rescue/` vào ignore của
  target theo chính sách của bạn.

## Network và dữ liệu gửi ra ngoài

`uvx`, `npx`, installer binary và bootstrap source tải code từ bên thứ ba.
Một số scanner đọc hoặc thực thi cấu hình của target; probe và agent CLI có thể
thực thi code target. Stage `review`, `plan`, `repair` và cross-check có thể gửi
source/evidence tới provider của CLI đã cấu hình. Chỉ bật các stage đó khi bạn
được phép gửi dữ liệu; dùng provider local hoặc bản sao đã lọc khi cần giữ source
nội bộ. `logic_atlas.py` không tự gọi LLM; graph tĩnh vẫn có thể chứa tên hàm,
đường dẫn và literal nhạy cảm, nên cũng phải kiểm trước khi chia sẻ.

Installer binary chọn release tag + asset chính xác từ `tools/manifest.toml`, so
SHA-256 của archive trước khi giải nén và từ chối mismatch. Pin lấy từ metadata
GitHub release, chưa có xác minh chữ ký/attestation độc lập; môi trường yêu cầu
bảo đảm supply chain cao hơn phải kiểm thêm chứng thực từ nhà phát hành. Các pin
binary hiện chỉ bao phủ một bộ asset Linux x86-64; scanner Python/Node core có
cách cài riêng qua manifest. Xem trạng thái installer trong `STATUS.md`.

## Vận hành và báo cáo lỗ hổng

1. Dùng bản sao target và quyền tối thiểu; không đặt token production trong env
   của scanner/agent nếu không cần.
2. Giữ `.rescue/`, `reports/`, `logs_audit/` private, và xóa/rotate credential
   nếu thấy nó từng xuất hiện trong artifact.
3. Trước khi public hóa fork/repo, rà cả working tree **và lịch sử Git**. Xóa file
   ở commit mới không xóa dữ liệu ở commit cũ.
4. Báo lỗ hổng qua GitHub Security Advisory của repo phát hành; đừng đăng exploit
   hoặc credential thật vào issue công khai.

## English

Git worktrees separate candidate changes; they are **not security sandboxes**.
Scanners, probes, third-party tools and agent CLIs may execute target code or
send data over the network. Redaction is best effort. Use an isolated environment
for untrusted repositories, review artifacts before sharing, and audit Git history
before publishing.
