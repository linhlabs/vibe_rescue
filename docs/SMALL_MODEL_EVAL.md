# Small-model rescue gate — kết quả DeepSeek Flash

Mục tiêu: kiểm xem model nhỏ có thể nhận một evidence packet giới hạn và trả
đúng hợp đồng máy cho MAP, PLAN, REVIEW. Đây là **smoke eval tổng hợp**, chưa
phải bằng chứng model có thể tự sửa repo thật hoặc bảo vệ owner gate. Code eval
ở `scripts/model_rescue_eval.py`; fixture source và grader nằm cùng file,
grader có test phản chứng trong `tests/test_model_rescue_eval.py`.

## Cách chạy lại

Đặt `VIBE_EVAL_API_KEY` trong môi trường của bạn bằng credential đúng cho gateway
được tin cậy. Không ghi key vào `config.toml`, command line, report hoặc Git.

```bash
python3 scripts/model_rescue_eval.py \
  --base-url "$VIBE_EVAL_BASE_URL" --model "$VIBE_EVAL_MODEL" \
  --max-tokens 1800 --plan-retries 1
# Với gateway HTTP nội bộ đã được tin cậy, thêm --allow-http.
# Report riêng: reports/model-eval/last.json (gitignored).
```

Script tạo Git fixture tạm, chỉ gửi source giả lập và finding giả lập. Prompt
MAP **không cho sẵn call path/bug ID**; grader đòi model suy ra
`api.post_charge → service.charge`, nhận ra amount âm và giữ unknown.
PLAN phải qua chính `plan_check.check_plan` với SHA/Scope cụ thể và không thêm
file. REVIEW phải bác diff làm hỏng exact-balance dù test yếu vẫn xanh. Một lần
PLAN trượt có tối đa một lượt sửa với lỗi checker; feedback phải giữ nguyên
task gốc chứa SHA và finding ID. Không có auto-approve.

## Chạy thực tế ngày 2026-10-22

Gateway nội bộ trả model ID `deepseek-flash`. [Tài liệu chính thức của
DeepSeek](https://api-docs.deepseek.com/quick_start/pricing/) ánh xạ ID này tới
**DeepSeek-V4.1-Flash-1017**, hỗ trợ cả vision. Gateway nội bộ chỉ công bố alias,
không công bố backend version riêng, nên xác nhận phiên bản runtime nội bộ còn
phụ thuộc cấu hình router. ID cũ `deepseek-v4-flash` trên gateway này trả 404;
dùng **`deepseek-flash`** như tài liệu chính thức. Không ghi hostname nội bộ
hoặc credential vào gói public.

Probe vision riêng cùng ngày: gửi ảnh PNG đỏ tổng hợp 64×64 qua content part
`image_url` tới alias `deepseek-flash`; response `model=deepseek-flash`,
`finish_reason=stop`, trả lời `Red` (1/1). Điều này kiểm được đường ảnh của
gateway trên fixture đơn giản, chưa kiểm visual reasoning trên diagram phức tạp.

Đã gửi screenshot SVG `repo-repair.svg` thật qua cùng đường vision để rà bố
cục. Model chỉ ra cạnh thiếu mũi tên và chữ phụ hơi tối; kiểm ảnh bằng mắt thấy
đúng nên generator đã thêm arrowheads, tăng tương phản chữ và làm rõ header hai
cột cho cả 5 SVG. Model cũng báo khoảng trắng lớn; đây là phần **viewport của
Chromium screenshot**, không thuộc SVG gốc. Visual QA chỉ chấm hình, không
chứng minh call graph hay guard trong sơ đồ đúng source.

| Lượt | MAP | PLAN | REVIEW | Kết luận |
|---|---|---|---|---|
| exploratory, giới hạn 350 tokens | content rỗng | — | — | 350 token bị tiêu hết ở reasoning, không có đáp án để chấm |
| exploratory, prompt lỏng 1500 tokens | đúng lỗi âm nhưng sai kiểu JSON | — | — | Không được coi là pass schema |
| original trial 1–4 | 4/4 | 3/4 | 4/4 | **Không dùng để chấm suy luận:** prompt MAP cho sẵn đúng call path/bug ID, REVIEW nói sẵn regression. Trial 3 PLAN dùng `{{HEAD_SHA}}` và bị checker chặn đúng. |
| revised prompt trial 1–4 | 4/4 | 4/4 | 3/4 raw; 4/4 chấm lại | Prompt bỏ đáp án; REVIEW trial 1 trả `BLOCK` và giải thích `amount == balance`, nhưng grader cũ bỏ sót ký hiệu `==`. |

Raw report ở `reports/model-eval/trial1..4.json` và
`reports/model-eval/unleaked_trial1..4.json` local, không đưa vào source public.
Code grader hiện chấp nhận cả `amount == balance`, có test phản chứng; chấm lại
4 output REVIEW mới được 4/4, **không gọi model thêm để tạo 4 lượt mới**. Cả
hai nhóm là quan sát trên **một fixture tổng hợp**, không là ước lượng độ tin
cậy thống kê. MAP revised được kiểm đúng `file:line` của fixture thay vì source
giả có số dòng lệch. Vẫn cần nhiều repo fixture, phiên bản backend được pin và
cấu hình sampling cố định trước khi tuyên bố đủ cho production. Failure PLAN
ở nhóm cũ vẫn minh họa model có thể xuất template với placeholder; checker
đúng khi block.

## Fix gốc cho small-model harness

1. **PLAN:** model trả object có schema ngắn (`outcome`, `scope`, `steps`,
   `stop`, `rollback`, `verify`) với source anchors. Harness tự chèn SHA/finding
   IDs từ evidence và render Markdown canonical; `plan_check` chạy sau render.
   Không nhờ model nhớ format/HEAD và không cho model tự đặt provenance.
2. **Executor:** mỗi lần chỉ một file/concern trong allowlist; model trả patch,
   máy `git apply --check`, kiểm path/symlink/scope, chạy probe, scan rồi mới
   commit candidate. Output sai → feedback máy cụ thể, giới hạn lượt/token.
3. **Reviewer:** model nhận plan đã pin, diff giới hạn, probe/scanner receipts;
   verdict phải có claim→source/test. Machine gate vẫn quyết định scope, delta,
   integrity; reviewer không được thay owner.
4. **Runtime adapter:** *(2026-10-22: `scripts/openai_agent.py` đã thêm, xem STATUS.md; phần còn lại dưới đây vẫn là việc cần đo: pass rate/chi phí/độ trễ trên nhiều repo và model.)* `llm_config.build_cmd` trước đó chỉ chọn CLI. Raw HTTP model chưa
   có tool-capable adapter để đọc evidence, ghi file và sửa candidate trong
   `rescue_voyage`/`rescue_loop`. Một smoke eval API pass **không** chứng minh
   model đã chạy được toàn voyage. Thêm adapter với role-specific capability,
   fixture end-to-end, rồi đo pass rate/chi phí/độ trễ trước khi mở mặc định.

Lõi scanner, parser, SHA, scope, owner dialogue, probe và delta không cần
frontier LLM. LLM là worker trong ranh giới này; nếu fail schema hoặc thiếu
bằng chứng, harness dừng thay vì gán nhãn “đã cứu”.
