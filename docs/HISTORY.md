# History of the working state

Moved here on 2026-10-24 from `STATUS.md`, which now holds the current state only. Entries are dated and were true when written; do not read them as the state of the latest commit. Passages that described runs on a private target were removed.

## 2026-10-23 — Generic team handoff validated locally

- `repo_explorer.py --generic` now writes English and Vietnamese
  `handoff.html` + `HANDOFF.md` beside the Atlas and Source Explorer. Editable
  EN/VI review worksheets are created once, so reruns keep assigned owners and
  receipts. The generated packet includes every block, anchored function leads, documented
  journeys, control candidates with next probes, config/prompt path inventory,
  scope/coverage/unknowns and Git snapshot identity when the selected root is
  a Git root. The packet runs offline and does not execute target code.
- The public synthetic support-ticket example yields 6 blocks, 8 source
  relations and 5/5 exact journey bindings; its actual EN/VI handoff pages and
  block views were captured in `docs/assets/v0.8-handoff.*.png` and
  `docs/assets/v0.8-blocks.*.png`. 
- A focused fixture exposed a wrapped-list documentation fragment mistaken for
  a block purpose. Purpose extraction now prefers a complete early North Star
  paragraph, retaining its documentation provenance. Full pytest reached
  100% with exit 0; focused handoff/Atlas tests passed; Ruff, Markdownlint on
  edited docs and generated demo, local links, browser page errors and 59
  handoff links per language passed. Source-only public snapshot: 166 files;
  pinned Gitleaks 8.30.1 found 0 issues in the extracted source tree. The
  separate snapshot manifest contains content hashes that Gitleaks flags as
  three generic-key pattern matches, not source leaks.

<a id="current-preview-gaps"></a>

## 2026-10-23 — v0.8-preview capability boundary

- Package label is `0.8.0-preview` (PEP 440 tools may normalize this to
  `0.8.0rc0`). The portable offline `--generic` Atlas was smoke-tested from a
  different working directory against a separate synthetic Python/TypeScript/
  config repo: 3 code files, 3 blocks, 2 source-level relations, and 2/2
  explicitly named journey functions bound. Full function IDs in backticks now
  bind by exact match; an unknown ID remains unknown. This is an EXPLORE
  compatibility receipt, not a cross-language call graph or live request trace.
- Focused Architecture Atlas tests: 9 passed. Full Vibe Rescue pytest reached
  100% with exit 0 after the exact-ID binding fix (runner omitted a totals line).
- A generated handoff is not an independent human audit. The generic
  generator emits candidates, provenance and missing-proof prompts; it does
  **not** automatically reproduce that judgment for every team or certify
  agent harness, swarm, medical, PII/PHI or billing safety. Owner-gated repair,
  external provider policy, isolation and target-specific test/trace receipts
  remain deployment responsibilities. See `docs/V0.8_PREVIEW.md`.
- Current preview gaps: UI-to-API and other cross-language edges; stale-doc
  detection beyond exact anchors; runtime/fault proof for sensitive controls;
  independent reviewer evidence as a hard release gate; sandboxing of
  untrusted executor/scanner commands; and target-specific owner authorization.
  Do not advertise unattended auto-repair or universal production readiness.
- Distribution is source-checkout only. `python -m build --wheel --no-isolation`
  fails because setuptools finds ambiguous top-level packages in the flat
  layout; no wheel or `pip install` claim is made for this preview.
- Source-only preview snapshot contains 166 files; pinned Gitleaks 8.30.1
  scanned the extracted tree with 0 findings (exit 0). This is a pattern scan,
  not a manual publication or privacy review.

## 2026-10-23 — V1.0 architecture-first objective in progress

- Owner requested a persistent product objective and plan. Added
  `docs/PRODUCT_NORTH_STAR.md` and root `PLAN.md`; `AGENTS.md` now points every
  agent at them. The contract requires architecture → documented journey →
  source function navigation, plus evidence-graded harness/swarm and
  PII/PHI/medical/billing control review. A function list or keyword match
  cannot establish production readiness.
- The new generic command writes `architecture.html/.json` beside the Python
  Source Explorer. Bounded docs, module docstrings, directory blocks, static
  calls/imports, config/prompt/workflow path leads, numbered documented steps,
  harness/swarm/sensitive control candidates and explicit coverage are present.
  `docs/ARCHITECTURE_ATLAS.md` records the model and limits. The public workflow
  diagram passed Archify 9/9 composition checks (0 errors/warnings) and browser
  containment; its 1440×900 screenshot was visually inspected.
- Focused Architecture Atlas tests: 8 passed, including root-scope grouping.
  Full pytest reached 100% with exit 0
  (runner omitted a totals line); Ruff changed Python files, Markdownlint on
  both README files and new docs, `git diff --check`, and local-link checks
  passed. Playwright checked 72 block buttons, the overview SVG, block
  selection, 4 PII cards, 2 journeys/8 unknown notes, Source Explorer query
  deep link and a parsable downloaded SVG with no page errors. Exclusion
  fixtures cover `test_e2e` and generated SOTA-run paths. Final release review
  and runtime control proofs remain. This is **partial V1.0 progress**, not a
  production-ready claim.
- The source-only public snapshot included 139 files. Pinned Gitleaks 8.30.1
  scanned that extracted source tree with 0 findings (exit 0). A scan of the
  whole local working folder found 10 leads only in ignored old reports,
  `.rescue/` and `tools/upstream`; those are excluded from the public snapshot.

> Trạng thái sống của nhánh làm việc. Bằng chứng cũ trong `reports/` là artifact
> sinh tự động và không thuộc gói public. Các số test bên dưới chỉ đúng tại lần
> chạy được ghi rõ; không dùng chúng để suy ra trạng thái của commit mới.

## 2026-10-23 — atlas phân trang và Source Explorer

- `logic_atlas.py` nay tự chia Python scope lớn, giữ số file đã map/chưa map và
  ghi rõ lời gọi qua shard chưa được giải quyết. HTML dẫn tới mọi trang SVG,
  mỗi trang tối đa 120 symbol; cạnh qua trang ở catalog HTML. Path inventory
  cho rules/prompts/config/pipeline/harness không đọc nội dung asset. Generic
  Python Source Explorer lưu HTML/JSON và vẽ SVG caller → hàm → callee khi
  chọn một hàm; không thực thi target. Radon path normalization đã sửa để
  finding trỏ về file đúng. Tài liệu EN/VI và LOGIC_ATLAS đã cập nhật.
- Validation của lượt này: full pytest 100% exit 0 sau thay đổi Source Explorer;
  focused tests 35 passed sau thay đổi SVG edge count. Ruff pass trên source và
  test đã đổi; Markdownlint README EN/VI và LOGIC_ATLAS pass; 138 SVG parse được; Source Explorer đã
  xem trong Chromium và JS qua `node --check`. Atlas exit 2 khi kết quả
  `partial` (cross-page/unresolved/unsupported) là đúng, không phải lỗi chạy tool.
  Markdownlint toàn STATUS còn lỗi dòng dài/inline HTML từ các mục lịch sử.
  Trạng thái commit và remote xem Git; không suy từ mục lịch sử này.

## 2026-10-23 — README: phạm vi EXPLORE

- README EN/VI được sửa cùng nội dung: phân biệt scanner finding với defect, nêu
  giới hạn hiển thị graph tĩnh, sửa đường dẫn `prove/run.summary.json`, và hướng
  dẫn giới hạn scope khi repo có dữ liệu riêng tư. Hai README có local link hợp
  lệ; `git diff --check` pass. Chưa chạy full pytest vì chỉ sửa tài liệu.

## 2026-10-22 — public-readiness đang thực hiện

- **Đã công khai** repo `thusinh1969/vibe_rescue` với lịch sử sạch (1 commit, quét gitleaks thư mục và lịch sử: 0 finding). Lịch sử cũ được giữ riêng tư ở repo `vibe_rescue_private_old`. Các ghi chú "private" bên dưới là lịch sử làm việc trước khi công khai. Điểm chặn R1–R4 và phần xác thực owner ở chế độ file vẫn mở: vẫn KHÔNG quảng bá tự sửa không giám sát.
- Adapter `scripts/openai_agent.py` (stdlib): cho phép `cli = "openai"` trong `config.toml` chạy các vai audit/write/verify qua BẤT KỲ server OpenAI-style có tool calling (model mở tự host hoặc model host sẵn). Công cụ: list_dir, read_file, grep (chỉ đọc, nội dung được `redact`), write_file (giới hạn theo từng task: review→`$REVIEW_DIR`, crosscheck→đúng `cross-check.md`, execute→worktree không vào `.git`, verdict→đúng `$VERDICT_FILE`, plan→không ghi), git_diff. Không có shell; harness tự chạy probe/scanner/scope và đưa "biên nhận" cho reviewer. Khóa chỉ đọc từ biến môi trường, không in ra. Nối qua `VIBE_AGENT_TASK` (rescue_voyage/rescue_loop) và `llm_config.build_cmd`. Test: `tests/test_openai_agent.py` (14 test, server giả theo kịch bản). Chạy thật 1 lượt đầy đủ (review→plan→2 lần owner accept→execute→probe/scanner→reviewer APPROVE→merge→REVERT.md) trên dự án mẫu 2 file với một model host sẵn (`deepseek-flash`); lượt trước đó dừng đúng chỗ vì plan lỗi (trùng file trong Scope) và vì probe để lại `__pycache__/` — cả hai gate đều chặn, không đổi gì. Chưa thử: Gemma/Qwen trên server thật, repo thật. Một lượt là quan sát, không phải thống kê. Full pytest trên máy này: 137 passed, 8 skipped; test semgrep duy nhất không chạy được ở đây vì glibc cũ không cài được wheel semgrep (hạn chế môi trường, không phải lỗi mã).
- `llms.txt` được thêm ở gốc theo yêu cầu của owner (tóm tắt trung thực: không cho là capability chưa có, nêu repo đang private). Đây là quy ước đề xuất; chưa có bằng chứng trong repo rằng công cụ tìm kiếm hay LLM nào đọc nó, và repo private thì không ai index được. Ghi chú trước đó "không dùng `llms.txt` giả SEO" nghĩa là không dùng file này để thổi phồng; nội dung hiện tại chỉ lặp lại README.
- README EN/VI được rút gọn quanh ba việc chính: lập bản đồ, lấy bằng chứng và
  sửa có owner gate. Bảng model nay nói rõ Gemma 4 31B/Qwen 3.8 27B chỉ đi
  qua gateway trong synthetic eval; `config.toml` chọn CLI cho voyage thật,
  không có OpenAI-compatible HTTP adapter. Có lệnh và artifact cụ thể cho từng
  đường chạy. Markdownlint, link local, parity lệnh/TOML hai bản và
  `git diff --check` pass. Đây là sửa tài liệu, không mở thêm capability runtime.
- README gốc nay hoàn toàn tiếng Anh, `README.vi.md` là bản tiếng Việt cùng
  phạm vi nội dung và lệnh chạy. Source Atlas có HTML/SVG/ảnh chụp riêng cho
  hai ngôn ngữ, cùng 5 journey, 43 bước và source anchor; generator hỗ trợ
  `--lang en|vi`, `--check` cho từng bản. Nội dung hành trình tiếng Anh được
  biên tập trực tiếp vì gateway dịch trả 401; test kiểm parity của ID, tên
  hàm được gọi, source và số bước. Ảnh thật được chụp từ hai HTML đã sinh.
  Full pytest 100% exit 0, Ruff pass, markdownlint cả hai README pass, hai
  atlas `--check` pass, mọi liên kết local tồn tại và 10 khối Bash giống nhau
  sau khi bỏ phần chú thích ngôn ngữ. Đây là kiểm tài liệu/generator, không
  thay đổi gate repair của harness.
- README onboarding đã bổ sung một dòng clone+venv+uv/Tree-sitter+smoke,
  lệnh cụ thể cho Python/frontend atlas, MAP/PROVE, REVIEW, PLAN và tên artifact
  kỳ vọng; hướng dẫn cài/auth Claude/Codex và `config.local.toml` (ignored).
  One-liner được thử trong clone+venv mới; repo mẫu Git Python cho inventory,
  atlas, MAP/PROVE đều exit 0 và tạo đúng file ghi trong README. Repo mẫu TS
  tạo import/function HTML/SVG nhưng exit 2 `partial` do cross-file unknown;
  REVIEW với CLI giả lỗi tạo template và báo `agent_wrote=False` như README.
  Chỉ Claude/Codex có command template rõ; DeepSeek raw gateway vẫn chỉ eval,
  chưa phải adapter voyage. Đây là sửa onboarding/config comments, không thay
  đổi cơ chế runtime. README qua markdownlint 0 lỗi, 32 link local không thiếu,
  ví dụ TOML parse được; focused config/explorer/atlas tests, Ruff và atlas
  `--check` pass. Screenshot Source Atlas đã sinh lại theo fingerprint mới.
- Ứng viên source đã commit và push lên `origin/master` PRIVATE. GitHub About
  có mô tả ngắn và 8 topics liên quan codebase visualization, static analysis,
  call graph, code audit và agent harness. Google/AI Search chưa thể index repo
  private; release public vẫn chờ lịch sử sạch và các blocker ở dưới.
- README đã được biên tập cho người dùng public: lệnh thử atlas và MAP/PROVE,
  ranh giới evidence/agent, bảng chức năng, hai tài liệu theo ngôn ngữ và hai
  ảnh browser thật của Source Atlas (`docs/assets/source-atlas-preview.en.png`,
  `docs/assets/source-atlas-preview.vi.png`). Ảnh
  là HTML source map hiện tại, không phải mockup. Tên/mô tả/keywords nói rõ
  codebase visualization, static analysis, call graph và owner-gated repair để
  người và công cụ tìm kiếm hiểu đúng khả năng; không dùng `llms.txt` giả SEO.
  Snapshot pre-push đã qua full pytest (exit 0), Ruff 0.16.5, atlas `--check`,
  kiểm liên kết README và Gitleaks quét >1.6 MB với 0 finding.
  Remote `origin` hiện PRIVATE;
  push vào remote này không đồng nghĩa public release. Lịch sử cũ vẫn không
  được đưa thành public; quy trình source-only ở `docs/PUBLIC_RELEASE.md`.
- Source Atlas mới thay thế sơ đồ 6 phase cho onboarding kỹ thuật: 5 journey
  chi tiết (điều phối/config/owner, evidence, prompt/review, repair, logic atlas/
  release) với hàm, source anchor, guard, artifact, failure và risk; explorer
  Python toàn source + tests có biến, caller/callee tĩnh và unknown. Xem
  `docs/REPO_RUNTIME_ATLAS.md`, chạy `python3 scripts/repo_explorer.py --check`.
  Đây là tài liệu và công cụ đọc source, chưa là runtime trace cho target.
- Atlas sinh từ 54 file Python với 350 định nghĩa hàm (source + tests), không
  giới hạn 120 node; 5 SVG đã parse hợp lệ và đã xem bằng browser ở 1440px.
  HTML dùng fingerprint source, không nhúng Git HEAD; `--check` chạy được trên
  snapshot không có `.git`. Vision QA qua `deepseek-flash` trên screenshot repair
  góp ý mũi tên và tương phản; đã sửa generator cả 5 SVG, parse XML và focused
  explorer tests pass. Khoảng trắng model nêu là viewport screenshot, không
  là lỗi SVG.
  Số đếm phản ánh working tree tại lần sinh; `--check` phải chạy lại khi đổi
  source. `python3 -m pytest -q` sau sửa gate: 100%, exit 0 (runner không in
  totals line); Ruff 0.16.5: pass; `git diff --check`: pass.
- Audit atlas phát hiện ba blocker mới. File-mode owner answer replay đã được
  vá bằng random ID + nonce/binding + one-time consume, timeout hữu hạn; PLAN
  và merge kiểm lại SHA sau lúc owner trả lời. Focused voyage tests pass.
  File mode vẫn cần ACL/kênh xác thực owner. Scanner fatal exit nay bị chặn
  theo chính sách exit code, report thiếu của jscpd/promptfoo/lychee/markdownlint
  không còn thành zero finding; `run_target.py` dừng khi MAP/recon/fanout/merge
  lỗi hoặc tất cả scanner skipped. Test phản chứng pass. Parser schema, scan
  coverage bytes và required/optional scanner policy còn mở; xem risk register
  ở `docs/REPO_RUNTIME_ATLAS.md`.
- Gitleaks scan public snapshot từng báo 0 finding nhưng thực tế scan 0 byte do
  allowlist `.rescue/` khớp cả tên repo `vibe_rescue/`. Đã sửa config, thêm test
  tránh skip root/parent `reports`, scan lại source (>1.6 MB): 0 finding,
  exit 0. Xem `docs/REPO_RUNTIME_ATLAS.md` và `docs/PUBLIC_RELEASE.md`.
- Lõi deterministic không cần frontier LLM. `scripts/model_rescue_eval.py`
  đã chạy trên gateway OpenAI-compatible với alias `deepseek-flash` (DeepSeek
  V4.1 Flash theo docs chính thức): prompt đầu lộ đáp án MAP/REVIEW nên điểm
  cũ không đo reasoning; prompt sửa lại có MAP 4/4, PLAN 4/4, REVIEW 3/4 raw
  và 4/4 sau khi sửa grader bỏ sót `amount == balance`. Một plan nhóm cũ dùng
  placeholder SHA/finding và bị checker chặn. Xem `docs/SMALL_MODEL_EVAL.md`.
  Probe image_url với PNG đỏ tổng hợp qua gateway trả đúng `Red` (1/1), nên đường
  multimodal cơ bản hoạt động; chưa kiểm visual reasoning/diagram QA.
  Chưa có adapter raw API đủ cho executor và chưa có eval end-to-end voyage;
  không công bố small-model rescue production-ready.
- Đã đối chiếu source Google Harness2 (`1cfe254...`) theo adapter/channel,
  evidence isolation, validated retry, selector/judge, ledger và schedule.
  Crosswalk ở `docs/REPO_RUNTIME_ATLAS.md` chỉ rõ phần đã có và guard còn thiếu;
  không mang invariant benchmark 4k/3k hay chính sách bỏ judge lỗi vào production.
- Repair gate đang được gia cố: plan approval gắn hash và HEAD; candidate probe,
  scanner, delta, reviewer và merge phải có kết quả rõ. Kiểm lại toàn bộ suite
  trước khi gọi bản này phát hành.
- Logic atlas: graph tĩnh Python, JS/TS và syntax graph Rust/Go/Java/PHP/C#;
  JS/TS nay có thêm function/direct-call graph Tree-sitter (chạy được khi thiếu
  npx, member/dynamic giữ unknown); HTML có full symbol/edge/unknown catalog
  ngay cả khi SVG preview 120 node bị cắt; PDF tùy renderer,
  template journey nối source với probe.
  `partial`, `unmapped` và `unknown` hiện rõ. `cargo-modules` vẫn không chạy tự
  động vì có thể chạy build script của target.
- Binary installer khóa tag, tên asset và SHA-256 của archive trong manifest;
  mismatch bị chặn trước khi giải nén. Đã tải/thử `ast-grep 0.51.0` từ pin.
- Workflow HTML dùng Archify: 9/9 artifact checks, composition 0 lỗi/0 cảnh báo;
  browser containment pass ở 1440×900, 1600×1000, 1920×1080, 2048×1320.
- `python3 -m pytest -q`: 106/106 pass, exit 0 ở mốc rc1 trước Source Atlas;
  `git diff --check`: pass (2026-10-22). Fixture Python/TS/Rust đã sinh HTML,
  SVG và PDF bằng `wkhtmltopdf`.
- Snapshot source không chứa Git history đã tạo qua `public_snapshot.py`.
  SHA-256 của tarball nằm trong receipt ở `reports/public-release/` (không commit).
  Bản giải nén chạy full pytest 100%, Ruff pass. Gitleaks trên bản snapshot
  mới quét thực sự >1.6 MB, 0 finding; kết quả 0 finding trước khi sửa regex
  **không có giá trị** vì coverage bằng 0. Đây là kiểm tra tự động, vẫn cần
  owner duyệt nội dung trước khi public.
- 62 file `reports/**` đã bỏ khỏi Git index, giữ nguyên trên đĩa local; `reports/`
  được ignore. Registry public chỉ có target `self`; người dùng truyền `--path`
  hoặc tạo entry target của mình.
- `SECURITY.md` ghi rõ worktree không phải sandbox, redaction best effort, agent
  CLI có thể gửi source ra provider, và rollback Git không undo side effect ngoài
  Git.

<a id="public-release-blockers"></a>

### Lịch sử blocker trước lần công khai đầu

Danh sách bên dưới là trạng thái tại lần chuẩn bị public ban đầu. Lịch sử
public sạch đã thay thế nhánh cũ; xem `current-preview-gaps` ở đầu file để biết
những giới hạn **đang mở** của `v0.8-preview`. Không dùng mục lịch sử này làm
quyết định phát hành hiện tại.

0. **Owner authentication và false-green evidence**: đóng phần còn lại R1–R4 trong
   `docs/REPO_RUNTIME_ATLAS.md`, thêm test phản chứng, rồi chạy lại suite trên
   source snapshot. Trước đó không quảng bá harness an toàn cho auto-repair.
1. **Lịch sử Git cũ** vẫn chứa các report và ghi chú của target nội bộ dù commit
   mới đã xóa chúng. Trước khi push public, tạo lịch sử public sạch hoặc audit +
   rewrite lịch sử, rồi kiểm lại toàn bộ Git objects và tags. Không push nhánh
   hiện tại như thể xóa file ở HEAD là đủ.
2. Owner rà nội dung snapshot source sạch, license và provider-data policy trước
   khi tạo remote public. Máy đã test/lint/secret-scan snapshot này; scan không
   thay thế kiểm duyệt nội dung nhạy cảm dạng văn bản tự do.
3. Pin binary lấy từ release metadata GitHub, chưa xác minh attestation/chữ ký
   độc lập của nhà phát hành. Bộ asset tùy chọn hiện chỉ khóa Linux x86-64.
4. Logic atlas là phân tích tĩnh. End-to-end journey (UI → HTTP → backend → data)
   cần trace/test thực tế cho từng repo; không tuyên bố tự suy ra toàn bộ logic.

## Mốc lịch sử của harness

| Phiên bản | Mốc đã thực hiện |
| --- | --- |
| v0.1–v0.2 | MAP, PROVE, PLAN gate, scanner fanout, delta gate và registry |
| v0.3 | Voyage có owner dialogue, repair worktree và revert record |
| v0.4.0 | Redaction theo mẫu, number check, evidence package |
| v0.4.1 | Sửa lỗi import khi chạy từ cwd ngoài repo và đường dẫn evidence |
| v0.4.2 | Sửa parser/severity/scope; 74 test pass lúc phát hành |
| v0.5.0rc1 | Ứng viên public: repair fail-closed, atlas đa ngôn ngữ, snapshot source sạch |
| v0.8-preview | Atlas generic; control candidate, FIX cần owner |

Mọi gate là bằng chứng cho phạm vi probe và scanner đã chọn. Verdict reviewer và
owner merge vẫn cần xem diff, unknown, và side effect ngoài Git.
