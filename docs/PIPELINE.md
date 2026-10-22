# PIPELINE — MAP → PROVE → PLAN → REPAIR → LOCK

> Nguồn nghiên cứu: tổng hợp từ shadcn/improve (advisor/executor separation),
> Anthropic harvest, uk AISI inspect, và bài học "không đốt nhà vì scanner đỏ".
> Chi tiết stack: xem `docs/REFERENCE_STACK.md`.

## Phase 0 — Quarantine (bắt buộc trước mọi việc)

Trên repo mục tiêu (repo bị cứu), với chủ repo:

```bash
git tag  pre-rescue-<ngay>            # mốc quay lại
git switch -c rescue/baseline         # nhánh làm việc
```

- Tắt auto-merge, tắt background autonomous coding, không shell unrestricted trên host chính.
- Capture: build/test/run/lint/deploy lệnh hiện tại; test nào đang fail TRƯỚC rescue;
  request/response API quan trọng (nếu có).
- KHÔNG sửa gì. Output: `.rescue/BASELINE.md`.

## Phase 1 — MAP (bóc tách blackbox)

```bash
python3 tools/meta/context_pack.py --target <repo> --outdir .rescue   # repomix/fallback
python3 tools/meta/recon.py       --target <repo> --out    .rescue/recon.json
```

Artifacts bắt buộc (`.rescue/`):

```
BASELINE.md          # trạng thái trước rescue, test fail trước, lệnh build/test
SYSTEM_MAP.md        # entrypoint, service/package, file quá lớn, generated, rules rải ở đâu
UNKNOWNS.md          # danh sách thứ không ai hiểu — được phép ghi "không biết"
AGENT_ASSETS.md      # inventory rules/skills/tools/MCP:
                     #   mỗi mục: owner | version | last_verified | applies_to |
                     #   trigger_test | supersedes | trạng thái (used/stale/duplicate/contradicts)
```

**Gate**: chủ repo xác nhận SYSTEM_MAP không sai lệch với thực tế họ biết.

## Phase 2 — PROVE (bằng chứng định lượng)

```bash
# Nhanh nhất — MAP+PROVE trọn theo registry (tự lưu baseline lần đầu):
python3 scripts/run_target.py --name self --sarif reports/targets/self/findings.sarif

# Hoặc thủ công:
python3 scripts/fanout.py --target <repo> --tools all --outdir reports/run-<ts>
python3 scripts/merge_findings.py --rundir reports/run-<ts> [--sarif out.sarif]
python3 scripts/delta_gate.py --baseline .rescue/evidence/findings.json \
                              --current reports/run-<ts>/findings.json
```

- Scanner chạy SONG SONG (độc lập); mỗi tool → `reports/run-<ts>/raw/<tool>.json`
  dạng normalized: `{tool, severity, file, line, rule, message, evidence}`.
- Lưu baseline evidence `.rescue/evidence/` (SARIF/JSON tùy tool).
- Lần đầu: ghi nợ, KHÔNG block. Từ đó về sau: chỉ block finding MỚI (delta_gate exit 2).
- Bổ sung theo loại target (binary cài bằng `scripts/install_binaries.py`):
  - Infra/Docker/K8s → **trivy** (vuln/misconfig/secret/license).
  - API/OpenAPI → **schemathesis** (đánh contract từ ngoài, junit).
  - Test nghiêm trọng → **mutmut** trên module critical (auth/permission/data-transform).
  - Agent/harness → **promptfoo** behavioral (--config) + **MCP conformance** (--scenario).
  - Secrets/agent supply-chain → **gitleaks**; snyk/agent-scan trong container disposable.
  - Docs → **lychee** link chết (kiểm cùng markdownlint).

## Phase 3 — PLAN (advisor, read-only)

```bash
claude -p "$(cat agents/advisor.md)" --append-system-prompt \
  "TARGET=<repo>; .rescue evidence: <paths>"  # → .rescue/PLAN-<id>.md
python3 scripts/plan_check.py --plan .rescue/PLAN-<id>.md --target <repo>/worktree
```

Format PLAN (advisor PHẢI theo đúng; plan_check.py kiểm):

```
# PLAN-<id>: <một outcome duy nhất>
Plan SHA:   <git rev của target lúc lập plan>
Scope:      [app/service.cs, +web/new.vue]  # '+' cho file mới; path tương đối, không glob/symlink
Out-of-scope: [file/API/deps cấm đụng]
Baseline evidence: [finding IDs được xử lý]
Steps:
  N. Mô tả nhỏ (≤ 1 file / 1 concern) — Verification: lệnh máy (pytest/gate)
  ...
STOP conditions: [điều kiện dừng ngay + báo cáo, ví dụ test X fail, diff > budget]
Rollback:   [lệnh cụ thể]
Done criteria: [máy kiểm được: lệnh + output mong đợi]
```

**Gate**: chủ repo (human) duyệt OK → mới được vào REPAIR. Không OK = advisor sửa plan.

## Phase 4 — REPAIR (executor bị khóa, reviewer 4-eyes)

```bash
# Tự động (state machine: worktree → executor → scope → gates → reviewer → verdict):
python3 scripts/rescue_loop.py --target <repo> --plan .rescue/PLAN-001.md \
    --baseline .rescue/evidence/findings.json \
    --probe "python3 -m pytest -q" [--max-rounds 3]
# -> logs_audit/PLAN-001.loop.json: result APPROVE | REVISE_LIMIT | BLOCK

# Hoặc thủ công:
git worktree add ../worktrees/plan-001 -b rescue/plan-001   # disposable
# executor chỉ sửa file trong Scope; chạy verification sau mỗi bước;
# không thêm dep, không đổi public API, không sửa tests để pass, không push/merge
python3 scripts/plan_check.py --plan .rescue/PLAN-001.md --target ../worktrees/plan-001
#   → kiểm "actual diff ⊆ intended scope" (chỉ file trong Scope thay đổi)
# re-run: toàn bộ tests + delta_gate (0 finding mới) + architecture/security gates
codex exec "$(cat agents/reviewer.md)" --append-system-prompt "DIR=../worktrees/plan-001"
#   → verdict viết vào logs_audit/PLAN-001.md: APPROVE | REVISE(lý do) | BLOCK
```

REVISE → executor sửa cho tới khi APPROVE (rescue_loop tự lặp). Lệnh
`rescue_loop.py` chạy riêng không hỏi owner; chỉ gọi khi đã được ủy quyền.
Worktree không cô lập lệnh executor khỏi host. Human merge. Mỗi PR một outcome.

> rescue_loop COMMIT thay đổi của executor lên branch `rescue/<plan>` (bắt buộc —
> nếu không branch rỗng, merge "Already up to date" và revert vô nghĩa). Merge = owner
> quyết (voyage hỏi), mọi merge ghi CHANGES.log + REVERT.md.

## Phase 5 — LOCK (chống tái phát)

1. **Rules single-source-of-truth**: `scripts/lock_rulesync.py --target <repo> --mode drift`
   (rulesync 16.17.0: generate cho claude/codex/cursor/copilot + `git diff --exit-code`;
   `--mode doctor` kiểm tra read-only). Không sửa trực tiếp file generated.
2. **Architecture fitness functions**: semgrep/import-linter/dependency-cruiser vào CI
   (block finding mới; baseline giảm dần) — findings xuất SARIF
   (`merge_findings --sarif`) cho GitHub/code-scanning consume.
3. **Skills/tools**: mỗi skill/tool có `owner | version | last_verified | trigger_test | supersedes`
   + smoke test; thiếu metadata = stale debt, không phải guidance.
4. **Behavioral evals**: promptfoo scenarios (tool nào bắt buộc được gọi, tool destructive cấm),
   chạy trong CI; MCP conformance với scenario `tools/mcp/`.
5. **Docs**: markdownlint + lychee trong CI; mỗi generated doc có lệnh verify.
6. **Registry mục tiêu**: `targets/registry.toml` (repo, baseline SHA, gates bật).

## Tiêu chí "rescue thành công" (định nghĩa nghiêm ngặt)

- Toàn bộ test suite xanh (những test xanh TRƯỚC rescue phải xanh SAU).
- delta_gate: 0 finding mới; baseline giảm, không tăng.
- Verdict CODEX trong logs_audit = APPROVE.
- Human merge. Cập nhật STATUS.md/README của mục tiêu.
