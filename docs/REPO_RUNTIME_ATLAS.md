# Vibe Rescue: bản đồ vận hành từ source

Mở [Source Atlas](assets/repo-explorer.html) để xem 5 sơ đồ SVG chi tiết và tìm **mọi định nghĩa hàm Python** theo tên, biến cục bộ, field, static caller/callee và `file:line`. Sinh lại bằng `python3 scripts/repo_explorer.py`; `--check` phát hiện HTML lỗi thời. Atlas đọc working tree, không thực thi target hoặc gọi LLM. SVG có nút tải từ HTML; dùng Print trong browser để lưu PDF. Bản chỉ mục toàn repo này khác `logic_atlas.py`, vốn phân tích một repo **target** đa ngôn ngữ theo scope.

Trạng thái chứng cứ: các cạnh trong 5 journey là diễn giải đã đối chiếu source; caller/callee ở thẻ hàm là **tham chiếu tĩnh**; cạnh không giải được được liệt kê `unresolved`. Không có trace runtime thì không được gọi toàn bộ graph là đường chạy chắc chắn. Một file prompt tồn tại không có nghĩa voyage đã thực thi prompt đó. Đây là điểm team cần phân biệt để cứu repo vibe-code mà không tự lừa mình.

## Tìm đường trong 3 phút

| Muốn biết | Bắt đầu | Đi tiếp | Artifact quyết định |
|---|---|---|---|
| Lệnh đầy đủ chạy thế nào | `scripts/rescue_voyage.py:448` → `STAGE_FUNCS` | `Ctx`, `Dialogue`, từng `_stage_*` | `<target>/.rescue/voyage/voyage.json` |
| Scan ra finding thế nào | `scripts/fanout.py:35` → `one` | `tools/meta/scan.py:_run_tool` → `collect_findings` → `tools/meta/parsers.py` | `raw/<tool>.json`, `run.summary.json` |
| Nợ cũ/new gate thế nào | `scripts/merge_findings.py:121` | `load_raw` → `merge` → `delta_gate.gate` | `findings.json/.md/.sarif` |
| Ai duyệt sửa/merge | `rescue_voyage._stage_plan/_stage_repair` | `Dialogue.ask`, hash plan, `rescue_loop.main` | `approvals/*.json`, `*.loop.json`, `CHANGES.log` |
| Candidate có thể đổi gì | `scripts/plan_check.py:81` | `scope_entries`, `check_worktree` | `Scope`, Git status/diff |
| Auditor nào chạy thật | `rescue_voyage._stage_review` | `agents/auditor_architecture.md`; các prompt khác là asset/manual | `review/README.md`, `PROPOSALS.md` |
| Target đa ngôn ngữ được map sao | `scripts/logic_atlas.py:160` | `tracked_files`, Pyan, depcruise, `syntax_map`, `atlas_render` | `<outdir>/manifest.json`, HTML/SVG/PDF |
| Public MIT từ đâu | `scripts/public_snapshot.py:44` | `docs/PUBLIC_RELEASE.md`, `LICENSE` | source tarball + `SNAPSHOT_MANIFEST.json` |

`scripts/run_target.py` là lối MAP+PROVE khác, **không** dùng owner dialogue; `scripts/rescue_loop.py` chạy độc lập cũng **không** có owner gate. Trách nhiệm owner chỉ có trong `rescue_voyage.py` khi chạy đúng stage. Xem ma trận rủi ro dưới trước khi dùng lối tắt.

## Tầng cấu hình, prompt, quyền thực thi

`targets/registry.toml` chọn đường target, scanner, probe và owner mode. `rescue_voyage.load_registry` đọc nó khi có `--name`; `--path` lấy đường explicit. `tools/manifest.toml` là pin và thứ tự scanner, thêm rule option, binary SHA và nguồn logic-map. `fanout.ALL` kết hợp core, tier3, binary và MCP từ manifest; `scan.precheck` quyết định chạy hay skip. `config.toml` gán ba vai `write`, `verify`, `audit`; `llm_config.load_config` merge default và cho đổi file bằng `VIBE_LLM_CONFIG`. `llm_config.build_cmd` dựng CLI; lệnh này có quyền máy người chạy, không được coi là sandbox. `pyproject.toml` là cấu hình packaging/test/lint, không phải nơi định nghĩa quyền owner.

| Prompt | Ai nạp tự động trong code | Vai trò / giới hạn |
|---|---|---|
| `agents/advisor.md` | `_stage_plan` | Viết PLAN trong evidence; plan chỉ hợp lệ khi `plan_check` và owner OK. |
| `agents/executor.md` | `rescue_loop.main` | Sửa worktree theo Scope; code máy kiểm tên file, không kiểm mọi nội dung. |
| `agents/reviewer.md` | `rescue_loop.main` | Verdict độc lập; parser chỉ thấy text `Result: APPROVE/REVISE/BLOCK`. |
| `agents/auditor_architecture.md` | `_stage_review` | Viết README/PROPOSALS; không có file mới thì template fallback. |
| `agents/crosscheck.md` | `_crosscheck` | Chấm chéo review, **fail-open**, không là release gate. |
| `agents/orchestrator.md` | Không có call trực tiếp trong voyage | Playbook thủ công cho agent điều phối. |
| `agents/auditor_api/assets/dependencies/docs/infra/security/tests.md` | Không có fan-out tự động trong voyage | Prompt chuyên ngách; muốn coi là audit đã làm phải có run record và artifact riêng. |

`docs/RULES.md`, `docs/OWNER_PACT.md`, `docs/PIPELINE.md`, `docs/VOYAGE.md`, `docs/OUTPUT_PROTOCOL.md` là hợp đồng người/agent. Chúng **không tự biến thành guard** nếu code không thực thi. `tools/rules/*.yaml` là Semgrep rules; `tools/mcp/scenarios.example.json` và `tools/promptfoo/example.yaml` là ví dụ, không chứng minh MCP/behavioral eval đang bật. `tools/rulesync/example-rulesync.jsonc` chỉ là mẫu target. Inventory file thực tế ở tab Config · prompts · tests của explorer.

## Luồng runtime và data contract

1. `rescue_voyage.main` xác nhận Git target, tạo `<target>/.rescue/voyage/{logs,dialogue}`, nạp role CLI, ghi `voyage.json`. Vòng `for s in STAGES` chạy **thứ tự cố định**, chỉ chạy stage đã chọn; nonzero/exception viết `blocked_*` hoặc `error_*` rồi trả 2. `--stages` có thể bỏ qua stage, nên downstream phải tự kiểm preflight. `Ctx` mang `target`, `session`, `reg`, `scan_tools`, `probe_cmds`, các command, `d`, `log`.
2. MAP: `_stage_map` gọi `context_pack.py` và `recon.py`; cần exit 0 và `recon.json`. `context_pack.collect` giới hạn file/budget, `recon` kiểm Git, ngôn ngữ, file lớn, agent assets. Inventory chỉ là sự tồn tại và cấu trúc, không chứng minh hành vi.
3. PROVE: `_stage_prove` gọi `fanout.py` với `scan_tools`. `fanout` tạo `run.conf.json`, mỗi `one(tool)` gọi `scan.py` qua subprocess, tổng hợp `run.summary.json`; sau đó `merge_findings` tạo findings và SARIF. Nếu có baseline: `_coverage_problems` so list/status, `delta_gate` so key `(tool,file,rule)`. Nếu chưa có: copy findings thành baseline đầu tiên. **Skipped không đồng nghĩa scanned**; xem status từng tool.
4. REVIEW: `_stage_review` đặt `PROMPT_AGENT`, `TARGET_DIR`, `EVIDENCE_DIR`, `REVIEW_DIR`, gọi `review_cmd`. Nếu agent không tạo README/REVIEW và PROPOSALS mới theo mtime, tạo template có notice. `check_review_numbers` chỉ advisory; `collect_evidence` lỗi thì block; `_crosscheck` thiếu/lỗi thì chỉ in thông báo. Kiểm `.rescue/` trong target `.gitignore` chỉ cảnh báo.
5. PLAN: `_stage_plan` gọi adviser hoặc template, `plan_check` kiểm section, SHA, Scope và Verification từng step. `Dialogue.ask` hỏi `accept/edit/reject` tối đa 3 lần; chỉ `accept` khi checker exit 0 mới lưu SHA-256 plan và target HEAD trong `approvals/`. PLAN **chưa chạy verification**, chỉ kiểm plan có lệnh dạng text.
6. REPAIR: `_stage_repair` kiểm probe, baseline, approval hash/HEAD; hỏi owner cho thực thi. `rescue_loop` kiểm target tracked-clean, baseline SHA/coverage, probe xanh, plan hợp lệ; tạo worktree; mỗi round chạy executor → scope diff → commit → probe candidate → fanout/merge/coverage/delta → reviewer → final scope. Chỉ `APPROVE` với candidate SHA mới về voyage. Sau đó owner hỏi merge, kiểm SHA lại, merge `--no-ff`, probe sau merge; lệch thì chỉ auto-revert nếu HEAD còn đúng và tracked tree sạch. `track_change` viết `CHANGES.log` và `REVERT.md`. External side effect không rollback.
7. LOCK: `_stage_lock` hỏi owner rồi gọi `lock_rulesync.py --mode drift` khi config tồn tại. Nó không tự cài CI gate hay behavioral eval; các mục đó trong PIPELINE là công việc tiếp theo.

Các biến nối stage quan trọng: `Ctx.scan_tools` quyết định scanner baseline/candidate; `Ctx.probe_cmds` và `reg['probe']` quyết định phép so trước/sau; `approval.plan_sha256` và `approval.target_head` ràng buộc plan với target; `state.candidate_sha` và `before_sha` bảo vệ trước merge; `state.probe_before` dùng sau merge; `meta.tools`/`meta.tool_status` xác định coverage; `findings` cung cấp delta. Explorer cho phép tìm từng field và hàm nơi đọc/ghi; với field động hoặc dict key, kiểm source trực tiếp.

## Từng module đang làm gì

| Nhóm | Module | Trách nhiệm và đầu ra |
|---|---|---|
| Điều phối | `rescue_voyage.py`, `run_target.py` | Entry point đầy đủ có owner gate; entry point MAP+PROVE rút gọn. |
| Điều phối | `dialogue.py`, `llm_config.py`, `exec_util.py` | Quyết định owner; ánh xạ role→CLI; subprocess runner. |
| MAP | `context_pack.py`, `recon.py`, `archgraph.py` | Gói context, inventory repo, import graph/cycles Python. |
| PROVE | `fanout.py`, `scan.py`, `parsers.py` | Parallel execution, precheck/command, parser chuẩn hóa. |
| Evidence | `merge_findings.py`, `delta_gate.py`, `redact.py` | Dedupe/redact/SARIF, so baseline, mask heuristic. |
| REVIEW | `check_review_numbers.py`, `collect_evidence.py` | Cross-check số claim, gói evidence. |
| PLAN/REPAIR | `plan_check.py`, `rescue_loop.py`, `guards.py` | Plan/diff gate, candidate loop, probe/backup/revert record. |
| LOCK/tooling | `lock_rulesync.py`, `install_binaries.py` | Rulesync check; tải binary pinned SHA. |
| Logic atlas | `logic_atlas.py`, `syntax_map.py`, `atlas_render.py`, `bootstrap_logic_tools.py` | Graph target đa ngôn ngữ; JS/TS import + function graph; HTML catalog đầy đủ parser output, SVG preview/PDF; checkout upstream pinned. |
| Public/docs | `repo_explorer.py`, `public_snapshot.py`, `model_rescue_eval.py` | Atlas của chính harness; source-only tarball; smoke gate model tiết kiệm trên fixture tổng hợp. |

Tests nằm trong `tests/` và được index cùng source; không được dùng tên test để suy ra “đã cover” khi chưa xem assertion. `docs/REFERENCE_STACK.md` mô tả tool và license bên ngoài. `SECURITY.md` là threat model vận hành; source snapshot không tự giải quyết credential/PHI.

## Risk register: đúng, sai, thiếu và ưu tiên

| ID / mức | Bằng chứng source | Hậu quả | Fix gốc + verification cần có |
|---|---|---|---|
| R1 **CRITICAL** owner answer replay/auth | `scripts/dialogue.py:parse_answer,Dialogue.ask/_ask_file` nay dùng ID random, nonce, binding, timeout 300s và tiêu thụ answer; `rescue_voyage._stage_plan/_stage_repair` kiểm lại hash/HEAD/candidate sau owner wait. | Replay answer cũ đã bị chặn; **tiến trình khác có quyền ghi answer directory vẫn có thể giả owner**. | Unit/integration test đã cover stale answer, wrong ID/nonce và voyage; thêm test concurrent/cross-stage và TOCTOU. Chỉ cho owner/ủy quyền ghi thư mục hoặc dùng kênh approval có xác thực, rồi mới mở auto-merge cho target không tin cậy. |
| R2 **HIGH**, một phần đã vá: false green scanner | `tools/meta/scan.py:_run_tool` nay ghi exit code, chỉ chấp nhận 1 (vulture: 3) cho tool có findings hợp lệ, chặn mọi fatal exit khác; jscpd/promptfoo/lychee/markdownlint thiếu report không còn thành 0 findings. | Partial artifact với exit 1 và parser quá dễ dãi vẫn có thể gây false green; số byte scan Gitleaks của target chưa là máy gate. | Chốt schema hoàn chỉnh cho từng parser/report, pinned exit contract theo phiên bản, bytes/files scanned >0 khi target có file áp dụng; test crash exit 1 + JSON một phần, 0-byte scan, nonzero findings hợp lệ. |
| R3 **HIGH**, đã vá đường fatal: baseline lỗi | `scripts/run_target.py:main` nay xóa artifact cũ, kiểm rc + artifact mới MAP/recon/merge, fanout rc và summary `ok>0, failed=0`. | Lỗi subprocess hoặc stale findings không còn tạo baseline; scanner `skipped` khi vẫn có một tool `ok` còn phụ thuộc R4. | Test phản chứng cho từng subprocess và all-skipped đã xanh. Thêm required/optional scanner policy của R4 trước khi coi baseline đủ coverage. |
| R4 **HIGH** skipped coverage | `scripts/rescue_loop.py:59-73` chấp nhận `skipped` trước/sau; `scan.precheck` có nhiều skip, kể cả unknown tool. | 0 finding mới dù scanner thiết yếu không chạy. | Policy `required/optional` explicit trong manifest/plan; required skip phải fail; snapshot exact tool version/config/coverage; test ok→skip và skip→skip theo policy. |
| R5 **HIGH** lệnh agent không sandbox | `scripts/rescue_loop.py:169-183`, `exec_util.py:22-38`; worktree chỉ cách ly Git tree. | CLI và verification có quyền host/network, có thể đổi dữ liệu ngoài scope. | Chạy target/agent trong container/VM giới hạn mount/network/credential; kiểm resource/timeout; test side effect ngoài worktree bị chặn. Không dùng “safe” chỉ vì worktree. |
| R6 **MEDIUM** audit chứng cứ yếu | `rescue_voyage.py:182-225`: mtime xác định agent_wrote; number check/crosscheck fail-open; chỉ auditor_architecture được nạp. | Template hoặc review thiếu evidence vẫn trông đầy đủ; các ngách security/API chưa được chạy. | Review manifest ghi provider, command result, artifact hash và scanner SHA; required audit modules theo target; machine validate citation/file:line và verdict trước PLAN. Test CLI exit 0 nhưng không artifact, artifact cũ, crosscheck failed. |
| R7 **MEDIUM** static diagram không là runtime | `logic_atlas.py:160`, `syntax_map.py:42`, `atlas_render.py:121`: parser/120-node SVG preview/unknown. | Team suy sai event→HTTP→handler/worker/storage hoặc bỏ qua nhánh động. | Journey có trace/test ID cho từng cạnh, `unknown` tồn tại đến khi xác minh; HTML nay giữ full catalog parser trả về, nhưng parse thiếu vẫn thiếu. JS/TS có function/direct-call view, chưa tự nối event→API. Explorer riêng của **harness** không cắt hàm Python. |
| R8 **HIGH** model tiết kiệm chưa chạy toàn voyage | `llm_config.py:30-69` chỉ đổi CLI/model; `agents/*.md` đòi đọc nhiều tài liệu. `model_rescue_eval.py` mới chỉ smoke tổng hợp. | DeepSeek V4.1 Flash (`deepseek-flash`) qua revised MAP/PLAN/REVIEW 4/4 sau chấm lại trên **một** fixture; nhóm prompt cũ lộ đáp án, invalid để đo reasoning. Raw HTTP chưa có adapter tool/patch cho executor, Gemma chưa thử; vision PNG đơn giản pass, chưa là visual reasoning. | Schema ngắn + renderer canonical, role adapter giới hạn capability, golden eval 2 model trên ≥3 fixture repo; đo map, plan, scope, evidence, reviewer false-approve, token/cost/latency và visual diagram QA. Không claim SOTA tới khi đạt gate end-to-end. |
| R9 **MEDIUM** nguồn public | `docs/PUBLIC_RELEASE.md`, `scripts/public_snapshot.py`; Git history cũ chứa internal reports. | Push nhầm history/asset nội bộ làm rò data. | Review tarball source mới, scan secret/license, sinh Git history mới rồi mới public. MIT áp dụng source của repo; upstream/binary có license riêng. |

**Lỗi audit đã sửa trong lượt này:** `.gitleaks.toml` từng có allowlist regex
`.rescue/` (dấu chấm không escape), khớp tên `vibe_rescue/` và làm Gitleaks bỏ
qua **toàn bộ source**. “0 leaks” lúc ấy là false green. Đã bỏ allowlist
`reports/`/`.rescue/` toàn cục và escape checkpoint; test
`tests/test_gitleaks_config.py` chặn regex match root. Scan lại source snapshot
115 file ghi `scanned 1.67 MB`, 0 finding, exit 0; đây mới là bằng
chứng scanner chạy, vẫn cần review nội dung thủ công.

Điểm đang đúng: `rescue_voyage` có chốt hash plan/HEAD, gate owner cho run và merge; `rescue_loop` kiểm candidate SHA, scope, probe và delta trước verdict; merge kiểm HEAD lại và ghi revert; snapshot loại history/report; atlas tĩnh giữ unknown. Những cơ chế này giảm rủi ro; R1 còn ranh giới xác thực người ghi file, R2 còn schema/coverage, R3 còn phụ thuộc R4, và R4–R5 còn mở. Việc công bố “production-ready/safe” phải chờ fix và chạy bài test phản chứng tương ứng.

## Đối chiếu Harness2: nguyên lý nào đã thành guard, nguyên lý nào còn thiếu

Đối chiếu source Google Harness2 tại commit `1cfe254e8d25b15f37048c3730134686abe60335` (Apache-2.0). Đây là tham chiếu thiết kế, **không** copy code hay coi benchmark research là chứng nhận an toàn production. Tên file bên trái thuộc `harness2/core/` của Harness2; tên bên phải là code Vibe Rescue. Quan trọng nhất: Harness2 phân tách **method, substrate, benchmark, proposer channel** trong `spec.py`, rồi mới chạy nhiều rollout và chấm chọn. Vibe Rescue phải phân tách **target, evidence, model role, executor capability và owner authority** tương tự.

| Ranh giới Harness2 / nguồn | Vibe Rescue hiện tại | Việc cần làm và gate chấp nhận |
|---|---|---|
| `spec.py:BenchSpec`, `BenchmarkAdapter`, `ChannelSpec` định nghĩa task, deliverable, channel/model độc lập | `targets/registry.toml` + `llm_config.py` + prompt role; CLI model đổi được nhưng raw HTTP không làm executor được | Adapter target/role tường minh: path đọc, artifact ghi, công cụ được gọi, timeout, version model. Capability sai hoặc thiếu phải block trước voyage; chạy cùng fixture trên hai provider. |
| `context.py:build`, `assert_no_leak_paths`, `assert_no_grader_verdicts` tạo evidence tree và chặn đáp án/judge vào context | `context_pack.py`, `redact.py`, review/evidence package; chưa có hợp đồng cô lập grader/probe verdict khỏi writer | Manifest evidence có file hash, line anchor, budget và nhãn nhạy cảm. Test context writer không chứa secret, answer key, reviewer verdict hay expected score; fail trước model call. |
| `recursion.py:_run_stage`, `_accept_tree` giới hạn hai lần đề xuất, chỉ nhận tree qua validator, fail thì dùng tree trước | `rescue_loop.py` có scope/probe/delta/reviewer, nhưng R1–R5 có thể làm gate sai | Mọi attempt có immutable input hash, bounded retry, lỗi validator cụ thể; invalid proposal không được merge. Test candidate đổi file ngoài scope, scanner chết, owner answer replay, probe đỏ. |
| `selection.py:run_selection` chọn artifact đã tạo qua ID ẩn; `judge.py:judge_one` chấm **sau** khi chọn | Reviewer xem diff của một candidate; smoke eval có grader nhưng chưa là voyage gate | Nếu thêm recursive self-improvement, tách proposer, selector và judge; selector chỉ xem artifact/probe cho phép, không thấy đáp án. Production gate phải coi judge unavailable là **block**, dù Harness2 research loại `None` khỏi mẫu số thống kê. |
| `ledger.py:Ledger.assert_identity`, `proposer.py:Proposer.call` ghi attempts/cost, fingerprint/cache, timeout | `model_rescue_eval.py` ghi token/latency trên fixture; voyage chưa có receipt đầy đủ và hard budget per role | Mỗi model call có model ID, prompt/evidence hash, token/cost/latency, cache provenance; đặt trần ngân sách/timeout và kiểm số run thực tế. Không dùng tổng 4k/3k của Harness2 máy móc: đó là invariant riêng của experiment. |
| `schedule.py:run_task` có namespace và parallel/sequential modes; `tree.py` validate editable surface | `fanout.py` song song scanner; voyage stage nối tiếp, worktree/scope gate nhưng host vẫn có quyền | Giữ PLAN→owner→REPAIR→owner merge tuần tự; chỉ parallelize scanner/independent eval. Cách ly executor ở container/VM và pin namespace/session để kết quả cũ không thể đè lượt mới. |

Thứ tự fix theo mức nguy hiểm: **R1–R4 trước mọi auto-repair**, rồi R5 và evidence isolation; sau đó adapter raw API + receipt/budget và fixture end-to-end. Multi-candidate selection/recursive improvement chỉ nên bật khi các gate đó đã pass. Harness2 đặt grader ngoài method; Vibe Rescue cũng phải giữ đánh giá độc lập khỏi agent đang viết. Một model Flash qua MAP/REVIEW tổng hợp không được tự duyệt chất lượng atlas hay candidate của chính nó.

## Contract để model 31B/Flash cũng cứu được repo

Lõi MAP, scanner, parser, baseline, diff, plan schema, owner gate, probe và release gate phải chạy deterministic trước khi gọi model. Model chỉ nhận **một intent, một scope, một evidence packet có ID và file:line**; nó trả JSON/Markdown schema ngắn cho đúng một nhiệm vụ. Harness validate schema, source anchor và allowlist; invalid output được trả lỗi máy cụ thể để thử lại tối đa N lần, không tự diễn giải thành pass. Vai writer và verifier dùng model/phiên riêng; reviewer không nhận kết luận writer như sự thật. Không gửi toàn repo hoặc credential vào context. Khi model không biết, output `unknown` với đề nghị probe, không bịa citation.

Điều kiện chấp nhận trên fixture: (a) tìm đúng entrypoint→call→side effect và đánh dấu edge chưa chứng minh; (b) plan pin SHA, Scope, STOP, rollback, verification máy; (c) executor chỉ sửa allowlist, test cũ vẫn xanh; (d) reviewer bác một diff nguy hiểm đã cài sẵn; (e) không nhận stale owner answer; (f) scanner chết không làm baseline xanh. Chạy cùng fixture trên Gemma và DeepSeek cấu hình thực tế, ghi version/quantization/CLI, seed/temperature, token, latency và pass/fail. [Smoke eval DeepSeek Flash](SMALL_MODEL_EVAL.md) hiện chỉ đo MAP/PLAN/REVIEW trên fixture tổng hợp; revised prompt qua 4/4 sau chấm lại, nhưng runtime chưa có adapter raw API hoàn chỉnh. Đổi `cli` trong TOML chưa đủ để cam kết rescue end-to-end.

## Phát hành MIT

`LICENSE` hiện là MIT. HTML/SVG mới không gọi CDN và chỉ nhúng dữ liệu từ source hiện hành; sơ đồ cũ có Archify runtime kèm `docs/assets/ARCHIFY_LICENSE`. Các binary/upstream checkout trong manifest **không** được nhập vào archive như code MIT của repo. Bản phát hành phải dùng `public_snapshot.py` và quy trình `docs/PUBLIC_RELEASE.md`, rà cả source/diagram/prompt/config, không push lịch sử Git hiện tại. Atlas trong working tree có fingerprint SHA-256 của file Python được index; chạy `python3 scripts/repo_explorer.py --check` sau đổi source để tránh sơ đồ cũ.
