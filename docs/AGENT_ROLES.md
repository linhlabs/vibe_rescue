# AGENT_ROLES — Vai trò agent trong harness

> Build = Claude Code CLI (`claude -p`), Audit = Codex CLI (`codex exec`)
> — profile 2-phase mặc định: một AI viết, một AI khác kiểm; máy và owner quyết định.
> Mỗi contract nằm ở `agents/<role>.md`, tải nguyên văn khi gọi agent.

## Ma trận vai trò

| Role | Agent file | CLI | Ghi file target? | Viết ở đâu? |
|---|---|---|---|---|
| orchestrator | `agents/orchestrator.md` | claude | KHÔNG | reports/, .rescue/, logs_audit/ |
| auditor_sec | `agents/auditor_sec.md` | claude | KHÔNG | .rescue/findings/<ngach>.md |
| auditor_arch | `agents/auditor_arch.md` | claude | KHÔNG | .rescue/findings/ |
| auditor_deps | `agents/auditor_deps.md` | claude | KHÔNG | .rescue/findings/ |
| auditor_docs | `agents/auditor_docs.md` | claude | KHÔNG | .rescue/findings/ |
| auditor_tests | `agents/auditor_tests.md` | claude | KHÔNG | .rescue/findings/ |
| auditor_assets | `agents/auditor_assets.md` | claude | KHÔNG | .rescue/AGENT_ASSETS.md |
| auditor_api | `agents/auditor_api.md` | claude | KHÔNG | .rescue/findings/ |
| auditor_infra | `agents/auditor_infra.md` | claude | KHÔNG | .rescue/findings/ |
| advisor | `agents/advisor.md` | claude | KHÔNG | .rescue/PLAN-<id>.md |
| executor | `agents/executor.md` | claude | Scope allowlist, worktree rời | worktree |
| reviewer | `agents/reviewer.md` | **codex** | KHÔNG | logs_audit/PLAN-<id>.md |
| crosscheck | `agents/crosscheck.md` | vai verify (config.toml) | KHÔNG | review/EVIDENCE/cross-check.md |

## Luồng điều phối (orchestrator chịu trách nhiệm)

```
quarantine (human, phase 0)
  → MAP: context_pack + recon + AGENT_ASSETS (auditor_assets)
  → PROVE: fanout (máy) + merge + baseline
  → PLAN: advisor (1 nhóm findings / 1 plan; plan_check máy)
      ↓                        ↑ (REVISE)
  human OK ──────────────── NOT OK
      ↓
  REPAIR: executor (worktree) → plan_check (diff ⊆ scope) → gates re-run (delta 0)
      → reviewer (codex verdict logs_audit/)   [REVISE → executor loop]
      → human merge
  → LOCK: rulesync + CI gates + skills metadata + STATUS/README target cập nhật
```

## Quy tắc giao việc (v1)

1. Mỗi auditor_* nhận: `system_map` + `recon.json` + `raw/<tool>.json` liên quan ngách
   + danh sách finding liên quan (đã normalize). Đầu ra: findings ngách theo format RULES R3.
2. Auditor PHẢI tự mở lại từng file:line để loại false positive trước khi ghi.
3. Advisor chỉ được lấy finding ĐÃ nằm trong evidence (không tự chế), gộp thành plan.
4. Executor nhận plan đã duyệt + SHA pin; mọi lệnh verification trong plan bắt buộc chạy.
5. Reviewer (codex) KHÔNG nhận lời "agent khác đã test rồi" — tự chạy gates, tự đọc diff.

## Tiêu chí pass/fail

- Auditor ngách: pass nếu mọi finding có evidence + không false positive đã biết.
- Advisor: pass nếu plan_check.py exit 0.
- Executor: pass nếu re-run gates xanh + delta 0 + diff ⊆ scope.
- Reviewer: pass = verdict APPROVE; REVISE → vòng lặp executor.
