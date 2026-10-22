#!/usr/bin/env python3
# Chính sách noqa: git status của worktree lỗi phải báo REVISE, không crash (RULES R11).
# ruff: noqa: BLE001
"""
plan_check.py — kiểm tra plan máy đọc được (RULES R8) + diff ⊆ scope (phase 4).

Kiểm tra cấu trúc:
  - Các section bắt buộc: Plan SHA / Scope / Out-of-scope / Steps / STOP conditions /
    Rollback / Done criteria
  - Mỗi step phải có dòng "Verification:"
  - Scope: file liệt kê phải tồn tại trong target (nếu có --target)
  - --worktree <dir>: git status --porcelain phải ⊆ Scope (actual diff ⊆ intended scope)

Exit: 0 = hợp lệ; 2 = vi phạm (advisor/executor phải sửa).

Usage:
  python3 scripts/plan_check.py --plan .rescue/PLAN-001.md --target ../repo
  python3 scripts/plan_check.py --plan .rescue/PLAN-001.md --worktree ../worktrees/plan-001
"""
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

HEADERS = ["Plan SHA:", "Scope:", "Out-of-scope:", "Baseline evidence:", "Steps:",
           "STOP conditions", "Rollback:", "Done criteria:"]
REQUIRED = ["Plan SHA:", "Scope:", "Out-of-scope:", "Steps:", "STOP conditions",
            "Rollback:", "Done criteria:"]


def parse_plan(text):
    lines = text.splitlines()
    sections = {}
    cur = None
    for ln in lines:
        s = ln.strip()
        matched = None
        for h in HEADERS:
            if s.startswith(h):
                matched = h
                break
        if matched:
            cur = matched
            sections[cur] = sections.get(cur, []) + [s[len(matched):].strip()]
        elif cur and s:
            sections[cur].append(s)
    return sections


def scope_entries(sections):
    """Scope: [path, +new/path] or bullet lines; any extension is allowed."""
    entries, invalid = [], []
    for line in sections.get("Scope:", []):
        value = line.strip()
        if value.startswith("[") and value.endswith("]"):
            value = value[1:-1]
        elif value.startswith("- "):
            value = value[2:]
        for token in value.split(","):
            token = token.strip().strip("'\"")
            if not token:
                continue
            is_new = token.startswith("+")
            name = token[1:] if is_new else token
            p = PurePosixPath(name)
            if (not name or p.is_absolute() or any(part in {"..", "."} for part in p.parts)
                    or "\\" in name or any(ch in name for ch in "*?[]")
                    or name.startswith("-") or name.endswith("/")):
                invalid.append(token)
            else:
                entries.append((str(p), is_new))
    return entries, invalid


def scope_files(sections):
    entries, _invalid = scope_entries(sections)
    return [name for name, _is_new in entries]


def check_plan(sections, target=None):
    problems = []
    for h in REQUIRED:
        if h not in sections or not any(x for x in sections.get(h, [])):
            problems.append(f"thiếu section '{h}'")
    steps = sections.get("Steps:", [])
    step_idx = []
    for i, ln in enumerate(steps):
        if re.match(r"^\s*\d+\.\s", ln):
            step_idx.append(i)
    if not step_idx:
        problems.append("không có step nào (Steps: phải có danh sách đánh số)")
    else:
        for k, i0 in enumerate(step_idx):
            i1 = step_idx[k + 1] if k + 1 < len(step_idx) else len(steps)
            block = "\n".join(steps[i0:i1])
            if "Verification:" not in block:
                problems.append(f"step {k + 1} thiếu 'Verification:'")
    if not sections.get("STOP conditions") and "STOP conditions" in sections:
        problems.append("STOP conditions rỗng")
    entries, invalid = scope_entries(sections)
    files = [name for name, _is_new in entries]
    if invalid:
        problems.append(f"Scope có đường dẫn không an toàn/không rõ: {invalid[:10]}")
    if len(files) != len(set(files)):
        problems.append("Scope có file trùng")
    if not files:
        problems.append("Scope phải có ít nhất một file cụ thể")
    missing = []
    if target:
        sha = (sections.get("Plan SHA:") or [""])[0].strip()
        head = subprocess.run(["git", "-C", str(target), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=False)
        if head.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", sha) \
                or head.stdout.strip() != sha:
            problems.append("Plan SHA không khớp HEAD của target; lập lại plan trên commit hiện tại")
        root = Path(target).resolve()
        for f, is_new in entries:
            path = root / f
            if not path.resolve().is_relative_to(root) or path.is_symlink():
                problems.append(f"Scope thoát target hoặc symlink: {f}")
            elif is_new and path.exists():
                problems.append(f"Scope đánh dấu file mới nhưng đã tồn tại: {f}")
            elif not is_new and not path.is_file():
                missing.append(f)
    return problems, files, missing


def check_worktree(worktree, files, base_sha=None):
    problems = []
    try:
        r = subprocess.run(["git", "-C", str(worktree), "status", "--porcelain", "-z"],
                           capture_output=True, timeout=60, check=False)
        if r.returncode != 0:
            return [f"git status lỗi: {r.stderr[:200].decode(errors='replace')}"]
        records = r.stdout.split(b"\0")
        modified = []
        i = 0
        while i < len(records):
            rec = records[i]
            i += 1
            if len(rec) < 4:
                continue
            code = rec[:2].decode(errors="replace")
            modified.append(rec[3:].decode("utf-8", errors="replace"))
            if "R" in code or "C" in code:
                i += 1  # porcelain -z adds old path after rename/copy
        if base_sha:
            diff = subprocess.run(["git", "-C", str(worktree), "diff", "--name-only", "-z",
                                   base_sha, "HEAD"], capture_output=True, text=True,
                                  timeout=60, check=False)
            if diff.returncode != 0:
                return [f"git diff base..HEAD lỗi: {diff.stderr[:200]}"]
            modified.extend(p for p in diff.stdout.split("\0") if p)
    except Exception as e:
        return [f"không đọc được git status: {e}"]
    allow = set(files)
    outside = [m for m in modified if m and m not in allow]
    if outside:
        problems.append(f"diff ngoài scope: {outside[:20]}")
    root = Path(worktree).resolve()
    unsafe = [m for m in modified if m and ((root / m).is_symlink() or
              not (root / m).resolve().is_relative_to(root))]
    if unsafe:
        problems.append(f"diff chứa symlink/path ngoài worktree: {unsafe[:20]}")
    return problems


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Kiểm plan máy đọc được + diff ⊆ scope.")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--target", help="root target (kiểm Scope file tồn tại)")
    ap.add_argument("--worktree", help="dir worktree (kiểm git status ⊆ Scope)")
    a = ap.parse_args(argv)
    plan_p = a.plan
    target = Path(a.target) if a.target else None
    worktree = Path(a.worktree) if a.worktree else None
    text = Path(plan_p).read_text(encoding="utf-8")
    sections = parse_plan(text)
    problems, files, missing = check_plan(sections, target)
    for f in missing:
        problems.append(f"Scope file không tồn tại trong target: {f}")
    if worktree:
        sha = (sections.get("Plan SHA:") or [""])[0].strip()
        problems += check_worktree(worktree, files, sha if re.fullmatch(r"[0-9a-f]{40}", sha) else None)
    report = {"plan": str(plan_p), "scope_files": files, "problems": problems}
    print(json.dumps(report, ensure_ascii=False, indent=1))
    if problems:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
