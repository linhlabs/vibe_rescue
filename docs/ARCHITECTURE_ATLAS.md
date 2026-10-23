# Architecture Atlas — contract, evidence, limits

<!-- markdownlint-disable MD013 -->

Architecture Atlas is the first screen for a new engineer. It connects an approved repository's **documented purpose → functional blocks → documented steps → source functions**, then shows control questions for an agent harness or sensitive application. It runs locally without a model or target-code execution. It is an investigation aid, not an automatic architecture or production-readiness certificate.

## Generate and read

```bash
python scripts/repo_explorer.py --generic \
  --root /path/to/project --sources src tests \
  --profile agent --profile pii \
  --out /path/to/project/VIBE_RESCUE/source-explorer.html
```

Choose only directories approved for inspection; replace `src tests` with actual paths. The command writes four files together:

| File | Use |
| --- | --- |
| `architecture.html` | Offline entry: purpose, blocks, connections, journeys, control leads, coverage. Select a block to draw/download its SVG. |
| `architecture.json` | Same model for tools; includes `file:line` examples and evidence state. |
| `source-explorer.html` | Python definition detail, parameters, locals, guards, raises, static caller/callee SVG. |
| `source-explorer.json` | Complete Python syntax ledger, including unresolved calls. |

The root README and named `README.md`, `DESIGN.md`, `ARCHITECTURE.md`, `PIPELINE.md` files under approved source directories are read with a 96 KB per-document and 100-document limit. `--docs relative/path.md` adds another approved Markdown file; unsafe/out-of-root or missing paths fail. Excluded data, audit archives, attachments, logs and `test_e2e` are not indexed. These restrictions apply to both the Python and architecture layers. The JSON contains documentation prose, docstrings and source identifiers; keep a private target's output in its controlled workspace.

## How the layers are derived

1. **Purpose.** The root README supplies a labelled *documentation claim*. A block takes its own README purpose, then a local Python module docstring, then inherited directory documentation. Every description has an evidence state and source anchor. A docstring or README can be stale; neither is runtime proof.
2. **Blocks.** Approved code files are grouped by directory, splitting large areas when needed. Each block lists member files, indexed Python functions and config/prompt/policy/workflow *paths*. A short function list prioritizes entry-like names and cross-block callers only as navigation hints; the Source Explorer retains every function. The path inventory does not claim that a config or prompt is loaded. Other supported code extensions remain file-level inventory; Python alone gets parameters and calls in this view.
3. **Connections.** Python AST calls and imports connect blocks when both endpoints resolve to indexed files. Edges from test files are labelled `test_call` or `test_import`, separate from runtime-source `static_call` and `import`. Examples carry callsite/import line and `exact_lexical` or `unique_module_suffix`. A suffix binding is accepted only when one indexed module has that suffix; dynamic `sys.path`, reflection and dependency injection can change actual runtime dispatch.
4. **Journeys.** Numbered steps under headings such as architecture/pipeline/workflow are copied from the bounded docs. Only exact backtick function/file anchors bind automatically. An unbound step is `unknown`, not absent or implemented by assumption. The first screen intentionally reports the unbound count; a human should trace such steps and maintain a current journey test.
5. **Control leads.** Agent, swarm, PII, medical and billing profiles expose concrete questions. Function names, test names and docs are *candidates*. No static candidate becomes `runtime_verified`, `safe` or `production_ready`. `not_located_in_scope` means this scope did not locate a candidate, not that a control is absent from the product.

## Review the sensitive path

For an agent or PHI-bearing application, use the Atlas as a checklist while following **intake → identity/subject → plan → search/tools → provider egress → writer → final audit → response → storage/telemetry**. At each boundary, record the function/callsite, a synthetic fault or adversarial case, the expected fail-closed result, and a redacted trace from the exact release snapshot. Examples: masker returns failure before provider egress; a worker times out after sibling fan-out; a source is absent or contradicts another; memory is requested for a different person; a payment is replayed. A green unit test proves only its case. A name match proves even less.

For a release review, promote a control only through an external evidence record with: `control ID | source anchors | commit/config fingerprint | probe/trace/test command | observed result | unknowns | reviewer | decision`. Keep raw PHI out of the Atlas. The static generator deliberately does not issue the promotion itself.

## Read a diagram without overclaiming

The HTML's block SVG shows up to seven inbound and seven outbound relations. The list below it shows up to 30; all edges and examples remain in `architecture.json`. Click a block or function to drill down. The separate [public Vibe Rescue workflow diagram](assets/vibe-rescue-v1-architecture.html) is an overview of this toolkit's workflow; it does not replace a target-specific Atlas.

`architecture.json` has a fingerprint over indexed Python files and bounded documents. It describes the **working tree**, which may contain uncommitted changes. It does not hash every non-Python asset or establish a deployed build identity. Regenerate on the release candidate and record Git revision, dirty state, config identity, and focused trace/test receipts outside the public repo.

## Known gaps and next work

| Gap | Implication | Next proof or extension |
| --- | --- | --- |
| Cross-language calls and UI → HTTP → backend not connected here | A browser path can be missing despite all Python blocks appearing. | Join the existing JS/TS function atlas to route/endpoint contracts; verify one browser trace. |
| Docs step without exact anchor remains unbound | An old journey can look plausible but be stale. | Owner-curated source binding plus a test/trace for each step; preserve documented vs observed provenance. |
| Config/prompt files are path leads only | Active setting/prompt and precedence remain unknown. | Parse known loaders and record config/prompt read sites with safe path-only evidence. |
| Candidate control search can include unrelated names | A card may lead to the wrong module. | Require reviewer triage, then source-to-egress graph and fault test; do not count candidates as coverage. |
| Static call resolution cannot prove dynamic dispatch | Runtime may choose another function or package. | Redacted trace on the exact snapshot, including timeout/cancel/error branches. |
| Dirty tree and partial parsing | A report may not match the deployed build. | Compare manifest and build identity; reject stale receipts at release gate. |

## Verification for maintainers

```bash
python -m pytest -q tests/test_architecture_atlas.py tests/test_repo_explorer.py
python -m pytest -q
ruff check scripts/repo_explorer.py scripts/architecture_atlas.py scripts/module_resolution.py tests/test_architecture_atlas.py
git diff --check
```

The focused fixtures cover an exact doc anchor, an unbound step, a cross-block call, a uniquely shortened import, an ambiguous import that remains unresolved, excluded Python scope, HTML escaping and a masker name that must **not** become a safety verdict. Browser inspection should check the overview, one block SVG, source links and the controls/coverage cards at desktop width.
