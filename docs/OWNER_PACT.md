# OWNER_PACT — hợp đồng giữa vibe_rescue và OWNER repo mục tiêu

> Đây là LUẬT cao nhất của mọi phiên autonomous. Mọi agent (LLM) đọc repo này
> để đi tiếp PHẢI tuân theo — vi phạm = xóa quyền "agent đáng tin".

## P1. Không đổi gì khi chưa được đồng ý

- MAP/PROVE có mục tiêu chỉ đọc source, ghi evidence vào `.rescue/voyage/`.
  Scanner bên thứ ba có thể chạy cấu hình hoặc ghi cache của target; môi trường
  chưa tin cậy phải được cô lập theo `SECURITY.md`.
- PLAN/REPAIR/merge/LOCK: **PHẢI** có owner đồng ý qua dialogue trước khi thực thi.
  "Owner vắng mặt" ≠ "đồng ý": hết hạn timeout → DỪNG (fail-closed), không tự quyết.
- Approval PLAN được ghi kèm SHA-256 của nội dung plan và HEAD của target. Sửa plan
  hoặc đổi HEAD sau khi duyệt làm approval hết hiệu lực; phải duyệt lại.
- Không có chế độ auto-approve trong code. (Ai muốn tự động phải tự viết — coi là vi phạm.)

## P2. Backup trước mọi thay đổi + revert được từng bước

- Trước mỗi repair: tạo backup tag trên target; sau merge ghi SHAs
  (before/after) vào `CHANGES.log` (JSONL) và `REVERT.md` (lệnh revert cụ thể).
- Harness yêu cầu executor sửa trong **git worktree rời** (branch `rescue/<plan>`).
  Worktree không giới hạn quyền của lệnh executor với filesystem/network của host;
  chạy trên môi trường cô lập nếu code/agent chưa tin cậy.
- Owner xem diff và xóa candidate branch chưa merge khi không cần. Sau merge,
  `REVERT.md` ghi `git revert -m 1 <merge-sha>` cho phần thay đổi Git; side effect
  ngoài Git (network, database, file khác) không được lệnh revert khôi phục.

## P3. NEVER BREAK WHAT IS WORKING

- Repair cần baseline PROVE và ít nhất một probe owner chọn qua registry `probe`
  hoặc các cờ `--probe` lặp lại. Probe chạy trên target trước, trên **candidate
  worktree** sau sửa. Khớp = (rc + sha256 output); baseline probe phải xanh.
- Probe hoặc gate candidate lệch → **không merge**; loop cố xóa candidate branch
  khi kết quả không APPROVE và ghi trạng thái vào loop JSON. Probe chạy lần nữa
  sau merge; nếu lệch, harness tự revert merge khi HEAD/tracked files còn nguyên,
  hoặc block và yêu cầu owner xử lý khi có thay đổi đồng thời. Đây là chứng cứ của probe đã chọn,
  không phải chứng minh toàn bộ hành vi đúng. Nghiêm cấm "sửa test để xanh" (RULES R9).

## P4. Dialogue protocol (agent tiếp-nhận đọc đây để trả lời thay owner)

- Harness viết atomic `<target>/.rescue/voyage/dialogue/QUESTION-<id>.json`:
  `{id, nonce, binding, phase, question, options, context, answer_file}`.
  `id` có hậu tố random riêng mỗi câu hỏi; `binding` khóa phase/question/options/context.
- Agent/owner trả lời bằng cách ghi `ANSWER-<id>.json`:
  `{"id": ..., "nonce": ..., "binding": ..., "choice": "accept|reject|edit", "note": "..."}`.
  Sao chép chính xác `id`, `nonce`, `binding` từ QUESTION hiện hành. Ghi file tạm
  rồi atomic rename sang `answer_file`; không điền trước câu trả lời cũ.
- Choice phải nằm trong `options`; answer sai ID/nonce/binding bị xóa. Answer
  hợp lệ được tiêu thụ một lần; file mode hết hạn mặc định sau 300 giây.
- File mode chứng minh một tiến trình **có quyền ghi thư mục** đã trả lời, không
  xác thực danh tính owner. Chỉ dùng thư mục ACL riêng hoặc cơ chế phê duyệt
  đã xác thực; không giao quyền ghi cho agent/executor chưa được owner ủy quyền.
- Interactive mode: câu hỏi in ra tty, `input()` đọc trực tiếp.

## P5. Evidence & trung thực

- Mọi finding có bằng chứng máy (RULES R3); harness không tự tuyên bố "xong"
  (chỉ gates/phản review quyết định).
- STATUS.md của TARGET được cập nhật sau phiên do OWNER phê duyệt nội dung
  (harness đề xuất, owner xác nhận — P1).
