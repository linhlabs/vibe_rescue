# STATUS — vibe_rescue

> The current state only, updated when the state changes. The dated story is in [docs/HISTORY.md](docs/HISTORY.md). Every number here names where it came from; if it has no date, do not trust it.

## Version and distribution

- `0.8.0-preview` (`pyproject.toml`). Distribution is a source checkout: `git clone`, then `./vr` (see [README.md](README.md)). There is no wheel and no `pip install` claim; a wheel build fails on ambiguous flat-layout package discovery.

## What was checked, and when

- **Quick start** (2026-10-24): in a clean clone, `./vr doctor`, `./vr explore` and `./vr check` on a two-file toy project took 10 s in total and left the project's Git status empty. The CI job `one-minute` repeats this on every push (green on `21d737c`).
- **Tests** (2026-10-27): 186 passed locally on macOS with Python 3.14, 12 of them for the PO renderer. On 2026-10-24 the CI job `tests` ran the whole suite and was green on `21d737c`.
- **Handoff and atlas:** `./vr explore` writes the architecture atlas and the English/Vietnamese team handoff for **Python** projects and a file-level map for Python, JavaScript/TypeScript, Rust, Go, Java, PHP and C#. It runs offline and does not execute target code. The public synthetic example (`examples/support_ticket/`) yields 6 blocks, 8 source relations and 5 of 5 exact journey bindings.
- **Checkers:** `./vr check` runs `ruff`, `vulture`, `radon`, `bandit` for Python and saves a baseline on the first run. Found and fixed 2026-10-24: `vulture` exits 3 when it finds dead code, which the exit-code policy rejected, so the stage was blocked on most real projects.
- **AI steps** (`report`, `fix`): through Claude Code and Codex, or any OpenAI-style server via `scripts/openai_agent.py`. The adapter was tested with a scripted fake server and with one full run (report, plan, approvals, fix, second check, merge, undo file) on a two-file toy project with one hosted model. **Not tested:** Gemma or Qwen on a real server, and any real project. One run is an observation, not a statistic.
- **PO output** (2026-10-27): `scripts/po_report.py` builds the slide deck and the detailed page of RULES R13 from `PO_SUMMARY.md` and `PO_DETAIL.md`, offline, stdlib only. It refuses to write HTML when a section is missing, a slide holds too many lines, a [Pn] code has no appendix row, or the Markdown has an emoji. Rendered locally from one real review converted to this format (not committed): 11 slides, 0 overflowing in headless Chrome at 1024, 1440 and 1920 px wide, 11 PDF pages, 40 of 40 P codes open their appendix row. Overflow is measured in a browser only (`<body data-overflow>`), not by the script.
- **Secrets:** Gitleaks 8.30.1 scanned the source tree and the Git history with no finding (2026-10-23). This is a pattern scan, not a privacy review.

<a id="current-preview-gaps"></a>
<a id="public-release-blockers"></a>

## Open gaps (do not advertise unattended auto-repair or universal production readiness)

- **Repair safety** (register R1 to R6 in [docs/REPO_RUNTIME_ATLAS.md](docs/REPO_RUNTIME_ATLAS.md), last reviewed 2026-10-23, **not re-verified in this pass**): owner answers in file mode prove that a process with write access answered, not who the owner is (R1); partial scanner coverage can pass (R2 to R4); executor and scanner commands are not sandboxed, a Git worktree is not isolation (R5, see [SECURITY.md](SECURITY.md)); the AI review can fall back to a template (R6).
- **Not connected by the generic handoff:** UI-to-API and other cross-language edges; stale-documentation detection beyond exact anchors; runtime or fault proof for sensitive controls. A generated handoff is not an independent human audit; a function name or a green unit test does not prove safety.
- **Binaries:** the optional downloaded checking tools are pinned by release metadata, with no independent attestation, for Linux x86-64 only.
- **Unverified:** whether other checkers (for example `lychee`) use an exit status for "found something" that the exit-code policy rejects, the same class of bug as `vulture`.

## Where things are

See [AGENTS.md](AGENTS.md) for the map of the repository and [docs/README.md](docs/README.md) for the documents and their languages.

---

**Tóm tắt (tiếng Việt).** Phiên bản `0.8.0-preview`, cài bằng `git clone` rồi `./vr`, không có `pip install`. Đã kiểm ngày 2026-10-24: từ bản clone sạch đến khi explore và check xong mất 10 giây, CI trên GitHub xanh cho cả "một phút" và toàn bộ test. Ngày 2026-10-27: 186 test đạt trên macOS. Bước AI mới thử với một model host sẵn trên dự án mẫu 2 file, chưa thử Gemma hay Qwen trên server thật. Còn mở: an toàn khi sửa (R1 đến R6, chưa kiểm lại lượt này), chưa cô lập lệnh agent, bản bàn giao chung chưa nối các cạnh giữa ngôn ngữ. Output cho PO (R13): `scripts/po_report.py` dựng slide và trang chi tiết từ 2 file Markdown, đã thử trên một báo cáo thật (11 slide, không slide nào tràn chữ); tràn chữ chỉ đo được trong trình duyệt. Không quảng bá tự sửa không giám sát. Nhật ký theo ngày nằm ở [docs/HISTORY.md](docs/HISTORY.md).
