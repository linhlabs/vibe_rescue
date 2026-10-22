# REFERENCE_STACK — Stack scanner của vibe_rescue

> Nguồn: nghiên cứu (ChatGPT tổng hợp) + verify thực tế qua pip/npm index cùng ngày.
> Nguyên tắc: **tối thiểu trước, thêm theo nhu cầu target** — không import hàng trăm
> skills từ marketplace, không bật toàn bộ scanner blocking ngay ngày đầu.

## Tầng 1 — Tối thiểu (bắt buộc, v0.1 core)

| # | Tool / repo | Lệnh gọi | Việc nó làm | Trạng thái |
|---|---|---|---|---|
| 1 | [repomix](https://github.com/yamadashy/repomix) 1.18.0 | `npx repomix` | Pack repo → artifact LLM-friendly; INTAKE, không phải truth | npm verified |
| 2 | [semgrep](https://github.com/semgrep/semgrep) 1.175.0 | `uvx --from semgrep==1.175.0` | Generic pattern rules (policy violation → CI gate) | pip verified |
| 3 | [import-linter](https://github.com/seddonym/import-linter) 2.13 | `uvx` | Contract tầng (package nào được import package nào) | pip verified |
| 4 | [deptry](https://github.com/osprey-oss/deptry) 0.25.1 | `uvx` | Dependency thiếu/thừa/sai scope | pip verified |
| 5 | [ruff](https://github.com/astral-sh/ruff) 0.16.5 | `uvx` | Lint + dead code + complexity | pip verified |
| 6 | [trivy](https://github.com/aquasecurity/trivy) | `scripts/install_binaries.py` | Dep/container/IaC/secret/license | v0.2 wired |
| 7 | [rulesync](https://github.com/dyoshikawa/rulesync) 16.17.0 | `scripts/lock_rulesync.py` | Single source of truth rules/MCP/skills → generate mọi harness | v0.2 wired |

## Tầng 2 — Phổ quát v1.0

| # | Tool | Ngách | Ghi chú |
|---|---|---|---|
| 8 | [vulture](https://github.com/jendrikseipp/vulture) 2.16 | dead code Python | pip verified |
| 9 | [radon](https://github.com/rubik/radon) 6.0.1 | complexity (C901) | pip verified |
| 10 | [bandit](https://github.com/PyCQA/bandit) 1.9.4 | security static Python | pip verified |
| 11 | [jscpd](https://github.com/kucherenko/jscpd) 5.0.16 | copy-paste | npm verified |
| 12 | [knip](https://github.com/webpro-nl/knip) 6.32.3 | unused files/exports JS/TS | npm verified |
| 13 | [dependency-cruiser](https://github.com/sverweij/dependency-cruiser) 18.2.0 | cycles/orphan/forbidden | npm verified |
| 14 | [markdownlint-cli](https://github.com/DavidAnson/markdownlint-cli) 0.49.1 | docs kém | npm verified |
| 15 | [lychee](https://github.com/lycheeverse/lychee) | `scripts/install_binaries.py` | link chết | v0.2 wired |
| 16 | [vale](https://github.com/errata-ai/vale) | binaries | prose/terminology | chưa wire lệnh (LOCK tay) |
| 17 | [gitleaks](https://github.com/gitleaks/gitleaks) | `scripts/install_binaries.py` | secrets | v0.2 wired |
| 18 | [osv-scanner](https://github.com/google/osv-scanner) | `scripts/install_binaries.py` | vulnerable deps (+license summary) | v0.2 wired |
| 19 | [ast-grep](https://github.com/ast-grep/ast-grep) | binaries | AST codemod an toàn (REPAIR, không dùng regex) | chưa wire lệnh (LOCK tay) |

## Tầng 3 — Khi target có API / harness

| # | Tool | Khi nào dùng |
|---|---|---|
| 20 | [schemathesis](https://github.com/schemathesis/schemathesis) 4.25.2 | OpenAPI/GraphQL — đánh từ NGOÀI, test contract | v0.2 wired |
| 21 | [mutmut](https://github.com/boxed/mutmut) 3.7.0 / [stryker-js](https://github.com/stryker-mutator/stryker-js) | mutation testing: tests "xanh nhưng vô dụng" — chạy trên auth/billing/permission/data-transform, KHÔNG chạy monorepo ngay | v0.2 wired (mutmut) |
| 22 | [promptfoo](https://github.com/promptfoo/promptfoo) 0.122.2 | behavioral regression "tool phải được gọi / cấm gọi destructive" — config mẫu `tools/promptfoo/example.yaml` | v0.2 wired |
| 23 | [MCP Conformance](https://github.com/modelcontextprotocol/conformance) 0.1.16 | protocol-gate MCP (baseline expected-failures) — scenario mẫu `tools/mcp/scenarios.example.json` | v0.2 wired (--scenario) |
| 24 | [MCP Inspector](https://github.com/modelcontextprotocol/inspector) | manual inspection — không thay conformance | official |
| 25 | [snyk/agent-scan](https://github.com/snyk/agent-scan) | scan MCP/skills/agent supply chain — **CHẠY TRONG DISPOSABLE CONTAINER** (nó thực thi config); cài `npm i -g snyk/agent-scan` | khai báo manifest, chạy tay |
| 26 | [potpie-ai/potpie](https://github.com/potpie-ai/potpie) | living context graph + `potpie doctor` (skill drift) — chỉ khi repo lớn/sống lâu | Apache-2.0 |

## Research / chưa production

- [CodeBoarding](https://github.com/CodeBoarding/CodeBoarding) +
  [Pyan3](https://github.com/Technologicat/pyan) +
  [cargo-modules](https://github.com/regexident/cargo-modules) phục vụ LOGIC ATLAS,
  source checkout pin SHA trong manifest. Bản đồ local dùng Pyan3 và
  dependency-cruiser hiện có; CodeBoarding cần model provider được owner chọn,
  cargo-modules cần Rust toolchain. Xem `docs/LOGIC_ATLAS.md`.

- [UCSB-AI/HarnessAudit](https://github.com/UCSB-AI/HarnessAudit) — trajectory-level audit
  (tool-scope adherence, protected-resource access...). Đúng bài "mất kiểm soát" nhưng 53★ mới —
  R&D layer, không foundation.
- [abhigyanpatwari/GitNexus](https://github.com/abhigyanpatwari/GitNexus) — technically S-tier
  (impact/taint/PDG analysis) nhưng **PolyForm Noncommercial** → KHÔNG mặc định cho workflow
  nội bộ thương mại; cần legal review. Dùng Potpie trước.
- [shadcn/improve](https://github.com/shadcn/improve) — rescue-brain tham khảo:
  "advisor viết spec machine-checkable, executor bị khóa scope, review lại" — chính là
  nguồn cho PLAN/REPAIR của harness này. **Verified 2026-08-28** qua
  `npx skills add shadcn/improve -l` (1 skill "improve": read-only, lập plan cho agent
  khác thực thi, không tự sửa). Đã nắm nội dung — không cài vào máy, chỉ tham chiếu.
- [aider](https://github.com/Aider-AI/aider) — executor thay thế nếu cần, NHƯNG executor hiện
  (claude/codex) đủ nếu có plan pin SHA + allowlist + worktree + STOP conditions.
  Đổi agent mà không có rào = thay người gây hỗn loạn.

## Không first responder (bài học, đừng lặp)

- KHÔNG bắt đầu bằng agent tự trị (OpenHands/SWE-agent) rồi bảo "fix repo này".
- KHÔNG bắt đầu bằng rewrite framework.
- KHÔNG một agent vừa audit vừa plan vừa sửa vừa tự review.
- KHÔNG coi generated docs (DeepWiki/GitDiagram) là ground truth.
- KHÔNG import hàng trăm skills marketplace.
- KHÔNG bật toàn bộ scanner blocking ngay ngày đầu.
- KHÔNG cho agent sửa tests để hợp thức hóa implementation.
- KHÔNG dùng một CLAUDE.md dài hàng nghìn dòng làm governance.
- Cẩn thận: "source available trên GitHub" ≠ "OSS dùng tự do trong công ty" (GitNexus!).

## Pin & verify

- Phiên bản pin ở `tools/manifest.toml` (single source of truth — scan.py/fanout.py ĐỌC
  file này, không nhân bản; đổi tool = sửa manifest, không sửa code).
- v0.1/v0.2 chạy qua `uvx`/`npx` (no global install, cache máy). Binaries (trivy/gitleaks/
  osv-scanner/lychee/vale/ast-grep) tải vào `tools/bin/` bằng
  `scripts/install_binaries.py [--only trivy,gitleaks]` (gitignored, ghi `.VERSION` + sha256).
- Rule pack semgrep mặc định: `tools/rules/` (PII VN, exec/eval, pickle, archive-extract,
  secret hardcode) — có test integration bắt đủ 7 class vi phạm trên fixture.
