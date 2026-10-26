# vibe_rescue: agent contract

For every LLM or agent that opens this repository (Claude, Codex, ChatGPT, any other). `CLAUDE.md` and `GEMINI.md` are one-line pointers to this file; do not copy content into them.

Product goal and plan: [docs/PRODUCT_NORTH_STAR.md](docs/PRODUCT_NORTH_STAR.md), [PLAN.md](PLAN.md). EXPLORE must connect architecture, documented journeys and functions with evidence. A function name or a scanner hit never certifies a harness, a swarm, or PII/PHI/billing safety.

## Map: where is what

| path | what it is |
|---|---|
| `vr`, `scripts/vr.py` | the one command: `./vr doctor`, `explore`, `check`, `report`, `fix`, `ai`. Starts its own `.venv` |
| `scripts/` | the engines: `logic_atlas.py` (maps), `repo_explorer.py` (generic handoff), `rescue_voyage.py` (MAP, PROVE, REVIEW, PLAN, REPAIR, LOCK), `rescue_loop.py`, `openai_agent.py` (any OpenAI-style server), `fanout.py`, `merge_findings.py`, `delta_gate.py`, `plan_check.py`, `po_report.py` (PO slides and detailed page from Markdown, RULES R13) |
| `tools/` | pinned checker list (`manifest.toml`), parsers, custom rules |
| `agents/` | one prompt per AI role |
| `config.toml` | which AI plays which role; local override `config.local.toml` (ignored by Git, never holds a key) |
| `docs/` | documents; the index with languages is [docs/README.md](docs/README.md) |
| `examples/support_ticket/` | a synthetic example with its generated output committed |
| `tests/` | pytest suite |
| `STATUS.md` | the current state only. The dated story is `docs/HISTORY.md` |

## Commands

```bash
./vr doctor                       # what is missing
./vr explore PROJECT              # map and team handoff, no AI
./vr check PROJECT                # findings, no AI
.venv/bin/python -m pytest -q     # tests (run ./vr doctor once to create .venv)
.venv/bin/python -m ruff check .  # lint (pip install ruff==0.16.5 into .venv first)
```

## Read in this order

1. `README.md`, then `STATUS.md`.
2. `docs/RULES.md` (binding), `docs/OWNER_PACT.md`, `docs/VOYAGE.md`, `docs/PIPELINE.md`.
3. Your role in `agents/<role>.md`.

Most files in `docs/` are in Vietnamese; [docs/README.md](docs/README.md) says which are English.

## Do not read these (large, generated)

`docs/assets/*` (HTML with embedded fonts, images), `examples/**/VIBE_RESCUE/*.json`, `llms-full.txt`, any `*.html`. Regenerate them, do not edit them by hand. `scripts/build_llms_full.py` rebuilds `llms-full.txt`.

## Allowed and not allowed

- Allowed: read any file; run read-only checkers; run `scripts/*` to collect evidence; write under `VIBE_RESCUE/`, `reports/`, `logs_audit/` and `.rescue/` of a run; propose changes to the harness as a diff and update `STATUS.md`.
- Not allowed: change files of a target project during MAP, PROVE or PLAN; change target code except as the executor, in a separate worktree, with an approved plan; declare "done" (only the gates or the reviewer decide); write sensitive data (PII/PHI, keys) outside `.rescue/`, `VIBE_RESCUE/`, `reports/`, `logs_audit/`; conclude about legal text with a regex (`docs/RULES.md` R6).

## Conventions

- No emoji in code or files.
- Keep `STATUS.md` to the current state; put the dated story in `docs/HISTORY.md`. State only what you read in a file, a log or a test result, and say when it was checked.
- Errors are loud and fail closed: say what, why, how to fix.
- A finding has evidence (file and line); a plan has stop conditions; ask before committing to a change.
- README and the full guide exist in English and Vietnamese and must say the same thing.
