# VOYAGE — chạy autonomous một lệnh, có owner gate

> `python3 scripts/rescue_voyage.py --name <target> [--stages map,prove,plan,repair,lock]`
> Toàn bộ phiên: `<target>/.rescue/voyage/` (evidence, CHANGES.log, REVERT.md,
> dialogue/, worktrees/, voyage.json).

## Vòng đời một phiên

| Stage | Việc | Cần owner đồng ý? | Output |
|---|---|---|---|
| map | context_pack + recon | KHÔNG (read-only) | `map/` (đã redact khóa) |
| prove | fanout + merge + SARIF (+ delta vs baseline phiên trước) | KHÔNG (read-only) | `prove/` (raw đã redact ở nguồn), baseline tự lưu lần đầu |
| review | auditor (vai audit) viết README/PROPOSALS → máy kiểm số (number-check) → EVIDENCE tự chứa → verify chấm chéo (fail-open) | KHÔNG (read-only) | `review/` (+ EVIDENCE/number-check.md, cross-check.md) |
| plan | adviser viết plan → plan_check SHA/Scope → **owner phán quyết**; approval gắn nội dung plan + target HEAD | **CÓ** | `PLAN-*.md`, `approvals/` |
| repair | kiểm approval/baseline/probe → owner cho chạy → worktree → probe + scanner trên candidate → reviewer → owner cho merge → merge + revert record | **CÓ (2 lần)** | `logs/`, worktrees/, CHANGES.log |
| lock | rulesync generate/drift (nếu target có config) | **CÓ** | — |

## Các cơ chế bảo vệ (chi tiết ở docs/OWNER_PACT.md)

1. Không change chưa đồng ý — dialogue file/stdin, timeout = dừng.
2. Backup tag trước mọi thay đổi; REVERT.md tái sinh sau mỗi event (revert từng bước).
3. Probe base/candidate (rc+hash) — lệch = không gọi reviewer, auto-drop branch.
4. REPAIR dùng worktree rời; lệnh executor/reviewer vẫn chạy với quyền của host.
   Dùng môi trường cô lập nếu target hoặc agent chưa tin cậy.
5. Mỗi quyết định owner được ghi vào `voyage.json` (decisions[]).

## Ví dụ chạy thật

```bash
# người có mặt (interactive):
python3 scripts/rescue_voyage.py --name self --stages map,prove,plan

# trình tự chuẩn một phiên đầy đủ (owner trả lời qua stdin):
python3 scripts/rescue_voyage.py --name self

# kênh file chỉ dành cho owner/người được ủy quyền (đọc docs/OWNER_PACT.md P4):
mkdir -p answers
python3 scripts/rescue_voyage.py --name self --owner file --answers answers
# Owner đọc QUESTION mới rồi trả ANSWER có id/nonce/binding khớp; không pre-seed.
```

## Agent đọc repo này để "take over" — đọc theo thứ tự

1. `README.md` (pipeline + nguyên tắc sắt)
2. `STATUS.md` (đang làm gì, cái gì pending)
3. `docs/RULES.md` (luật binding) → `docs/OWNER_PACT.md` (pact với owner) →
   `docs/PIPELINE.md` + `docs/VOYAGE.md` (protocol vận hành)
4. `tools/manifest.toml` (toolchain — single source of truth)
5. `agents/` (12 contract prompt — role để đọc/khi được giao)
6. `targets/registry.toml` (danh bạ target + probe + tools)
