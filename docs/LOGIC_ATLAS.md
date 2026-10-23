# LOGIC ATLAS — đọc repo đa ngôn ngữ theo hành vi thật

Muốn hiểu **chính harness Vibe Rescue**, mở
[Source Atlas](assets/repo-explorer.html) và
[diễn giải runtime/rủi ro](REPO_RUNTIME_ATLAS.md). Atlas dưới đây là công cụ MAP
cho repo target bất kỳ; nó chưa tự dựng đầy đủ journey UI→API→worker→data.

Mục tiêu: người mới lần được từ thao tác UI/API tới quyết định backend/worker,
dữ liệu, lỗi và kết quả cuối. Graph import không tự chứng minh điều đó. Atlas là
evidence của MAP, không phải verdict chất lượng.

## Đã có trong repo

- `scripts/bootstrap_logic_tools.py` tải source upstream đúng SHA trong
  `tools/manifest.toml` vào `tools/upstream/` (gitignored): CodeBoarding, Pyan3,
  cargo-modules. dependency-cruiser đã là tool JS core.
- `scripts/logic_atlas.py` chạy local trên file **Git-tracked** trong một `--scope`:
  Python call graph (Pyan), frontend JS/TS import graph (dependency-cruiser)
  **và** function/direct-call graph JS/TS/JSX/TSX (Tree-sitter),
  Rust/Go/Java/PHP/C# symbol và cạnh gọi rõ ràng trong cùng file (Tree-sitter).
  Mỗi nhóm có HTML/SVG tự chứa; `--pdf` xuất PDF nếu có `wkhtmltopdf` hoặc
  Chromium/Chrome. Kết quả ở `reports/logic-atlas/`, không sửa target.
- `JOURNEY_TEMPLATE.md` nối graph thành sequence theo hành vi, kèm file:line,
  điều kiện nhánh và test/trace đối chứng.

## Bắt đầu nhanh

```bash
cd vibe_rescue  # thư mục đã clone
python3 -m pip install tree-sitter-language-pack==0.13.0  # nếu cần Rust/Go/Java/PHP/C#
python3 scripts/logic_atlas.py --target /path/to/repo --scope path/to/feature --pdf
# mở INDEX.md được in ra; xem manifest.json nếu báo INCOMPLETE
```

Python graph cần `uvx`; frontend cần `npx`. `--pdf` cần `wkhtmltopdf` hoặc
Chromium/Chrome; nếu không có, HTML vẫn có nút In / lưu PDF. Source CodeBoarding
không cần cài để chạy atlas; chỉ khi muốn khảo sát upstream mới dùng
`python3 scripts/bootstrap_logic_tools.py` rồi `--check` để xác nhận SHA.

Scope Python trên 400 file hoặc có graph vượt 5 MB được chia thành shard; mở
`python-shards/INDEX.md` để xem HTML/SVG của từng phần. Cả khi mọi file đã có
map, manifest vẫn báo `partial` vì lời gọi qua shard chưa được giải quyết. Các
ngôn ngữ khác trên 400 file vẫn cần chia `--scope`. `--inventory-only` chỉ đếm,
lập template và kiểm kê path của rules/prompts/config/pipeline/harness, không đọc
nội dung asset.

Mỗi trang **SVG** hiển thị tối đa 120 symbol; **HTML liên kết tất cả trang SVG**
và giữ catalog đầy đủ mọi symbol/cạnh parser trả về, tìm theo tên/file/ID và xem
incoming/outgoing, unknown. Cạnh qua trang chỉ có trong HTML catalog, không
thành mũi tên nối hai trang. `manifest.json` báo `partial` khi có giới hạn hiển
thị, import unresolved hoặc parser thiếu; catalog không làm cho parse thiếu trở
thành đầy đủ. Chia scope để có sơ đồ dễ đọc cho phần cần cứu. PDF là bản in tĩnh
của HTML; dùng HTML để tra cứu catalog tương tác và tải SVG offline.

Nếu cần chỉ mục hàm Python kèm tham số, biến, guard, raise và static caller/callee
cho một target, dùng `python scripts/repo_explorer.py --generic --root /path/to/repo
--sources src tests --out reports/source-explorer.html`. Đây vẫn là phân tích
tĩnh, không chạy target và không dựng hành trình lâm sàng tự động.
Atlas ghi HEAD và số file Git-tracked đã sửa; số khác 0 nghĩa graph phản ánh
working tree, **không phải** snapshot chính xác của commit ghi bên cạnh.

## Vai trò từng tool và giới hạn

| Tool | Bằng chứng | Chưa chứng minh |
| --- | --- | --- |
| [CodeBoarding](https://github.com/CodeBoarding/CodeBoarding) | Gợi ý nhóm chức năng, sơ đồ nhiều tầng cho Python/JS/TS/Rust/Go/Java/PHP/C# | Đường runtime, mọi nhánh, tính đúng của diễn giải LLM |
| [Pyan3](https://github.com/Technologicat/pyan) | Call graph tĩnh Python | Callback/factory/dynamic dispatch chắc chắn chạy |
| [dependency-cruiser](https://github.com/sverweij/dependency-cruiser) | Import/dependency JS/TS, kể cả frontend | Event handler → API request → backend behavior |
| [tree-sitter-language-pack](https://github.com/xberg-io/tree-sitter-language-pack) | Hàm và cạnh gọi trực tiếp trong cùng file của JS/TS/JSX/TSX; syntax call Rust/Go/Java/PHP/C# | Cross-file resolution, event/HTTP, dispatch động, `cfg`/feature/runtime |
| [cargo-modules](https://github.com/regexident/cargo-modules) | Cấu trúc/module dependencies Rust, chỉ chạy trong sandbox | Mọi call path, mọi `cfg`/feature/runtime |
| [OpenTelemetry](https://opentelemetry.io/docs/) | Trace request qua service đã instrument | Nhánh không chạy trong mẫu trace |

CodeBoarding dùng LLM. Sau `bootstrap_logic_tools.py`, source có trong
`tools/upstream/codeboarding/`; môi trường Python/dependencies cần cài riêng
theo hướng dẫn upstream. **Atlas không tự gọi model hoặc gửi source ra ngoài.**
Muốn sinh overview: tạo snapshot riêng của target, cấu hình
provider được phép (local Ollama nếu cần giữ code local), rồi chạy upstream
`codeboarding full --local <snapshot> --render md`. Upstream ghi `.codeboarding/`
vào snapshot; không chạy trực tiếp trên target trong phase MAP. Có thể tắt
telemetry bằng `CODEBOARDING_TELEMETRY=false` nếu phiên bản upstream hỗ trợ.
Mọi nhóm chức năng LLM đề xuất phải đối chiếu source và trace trước khi nâng
trạng thái `DRAFT`. Kiểm chính sách dữ liệu của provider trước khi gửi source.

**Rust:** Atlas dùng Tree-sitter, chỉ parse source. `cargo-modules` upstream
`src/analyzer.rs` gọi `run_build_scripts` nên không tự chạy trên target chưa tin
cậy. Muốn có module-dependency graph sâu hơn, dùng snapshot trong container cô
lập, mount source read-only, bỏ network và giới hạn resource; xem xét build
scripts/dependencies trước. Có thể cài binary đúng pin: `cargo install
cargo-modules --version 0.27.0 --locked`. Tree-sitter không chạy build script.
Pyan3 là GPL-2.0-or-later,
cargo-modules MPL-2.0, CodeBoarding MIT; các checkout gitignored là tool upstream
độc lập, không copy source của chúng vào harness.

Frontend import graph dùng `--no-config` để không thực thi file
`.dependency-cruiser.*` của target. Nếu target dùng alias qua config, graph có
thể thiếu cạnh; import unresolved được ghi `unknown` và làm exit code 2. Vue và
Svelte hiện chỉ có inventory/unknown vì chưa có parser tương ứng trong lệnh này.
Function graph frontend vẫn chạy local nếu thiếu `npx`; nó nhận function
declaration, method, arrow/function gán biến và direct call duy nhất trong cùng
file. Member/dynamic call để `unknown`, không suy thành call tới method chỉ vì
trùng tên. Chỉ
chạy config của target sau khi đã review trong sandbox.

**Giới hạn quan trọng:** Graph hiển thị không phải bản đồ hành vi end-to-end.
Nó chưa nối JS event → HTTP → Python/Rust API, chưa thấy dynamic import,
reflection, queue, feature flag hay lỗi runtime. Dùng `JOURNEY_TEMPLATE.md` để
nối các cạnh bằng `file:line` và trace/test; cạnh chưa có chứng cứ giữ `unknown`.

## Quy tắc bản đồ chức năng (Harness²)

1. **Intent**: tên theo hành vi người dùng, không theo tên thư mục. Ghi UI event,
   endpoint, worker, external provider và data store liên quan.
2. **Map từ source**: mỗi cạnh có `file:line`, commit, flag và loại cạnh (`call`,
   `await`, `event`, `queue`, `HTTP`, `write`). Chỉ đoán từ tên hàm/LLM thì ghi
   `inferred`.
3. **Probe đối chứng**: happy path, lỗi/timeout/cancel, cấu hình khác. Trace/test
   dùng dữ liệu tổng hợp; không lưu PHI/token. Ghi ID artifact và kết quả.
4. **Compose**: sửa sequence theo probe. Mâu thuẫn giữa source/trace thì sửa sơ
   đồ; unknown ở lại danh sách unknown.
5. **Lock**: PR đổi cạnh nào cập nhật journey đó và chạy test tương ứng. Tool
   exit 0 không đủ để claim “toàn bộ logic chính xác”.

Repo lớn cần một index chung và nhiều journey. Người mới phải tìm được trigger →
branch decision → side effect → failure mode → output trong vài phút.
