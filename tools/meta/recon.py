#!/usr/bin/env python3
# Chính sách noqa: recon phải chạy được trên repo hỏng — git/log lỗi thì bỏ trống, không crash.
# ruff: noqa: BLE001, S112
"""
recon.py — phase MAP: nhận diện cấu trúc repo (không cần LLM).

- ngôn ngữ (đếm extension)
- entrypoints: pyproject.toml / package.json / setup.py / Makefile / docker-compose* / Dockerfile
- test discovery, coverage config
- file quá lớn (top 10), dấu hiệu generated/vendored
- rules files: CLAUDE.md / AGENTS.md / GEMINI.md / .cursorrules / .github/copilot-* / hermes/
- git: HEAD sha, số commit, top commit churn (theo inserted lines) — dấu vết "vibe coding"
- assets: skills/, tools/ đếm + skills không có test (kiểm tra bằng string)

Usage:
  python3 tools/meta/recon.py --target <dir> --out <json>
"""
import json
import re
import subprocess
import sys
from pathlib import Path

if __package__:
    from tools.meta import context_pack
else:
    import context_pack

IGNORE_DIRS = context_pack.IGNORE_DIRS

LANG_EXT = {
    "python": {".py", ".pyi"}, "js": {".js", ".jsx", ".mjs", ".cjs"},
    "ts": {".ts", ".tsx"}, "go": {".go"}, "rust": {".rs"}, "java": {".java"},
    "c": {".c", ".h"}, "cpp": {".cpp", ".hpp", ".cc"}, "sql": {".sql"},
    "yaml": {".yaml", ".yml"}, "json": {".json"}, "markdown": {".md"},
    "shell": {".sh", ".bash"}, "html": {".html"}, "css": {".css"},
}
RULES_FILES = ["CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules", "CODEX.md",
               ".github/copilot-instructions.md"]
TEST_MARKERS = ["tests", "test_", "_test", "spec.ts", "spec.js", "test.py"]


def _skipped(p: Path):
    # .rescue = evidence của chính harness (không phải code target)
    return any(part in IGNORE_DIRS for part in p.parts) or p.name.startswith(".")


def count_exts(root):
    counts = {}
    for p in root.rglob("*"):
        if p.is_file() and not _skipped(p):
            e = p.suffix.lower()
            counts[e] = counts.get(e, 0) + 1
    return counts


def langs(counts):
    lc = {}
    total = sum(counts.values()) or 1
    for lang, exts in LANG_EXT.items():
        n = sum(counts.get(e, 0) for e in exts)
        if n:
            lc[lang] = {"files": n, "pct": round(100 * n / total)}
    return lc


def big_files(root, top=10):
    out = []
    for p in root.rglob("*"):
        if p.is_file() and not _skipped(p) and p.suffix.lower() not in {".png", ".jpg", ".pdf", ".zip"}:
            try:
                n = sum(1 for _ in p.open(errors="ignore"))
            except Exception:
                continue
            if n > 800:
                out.append({"file": str(p.relative_to(root)), "lines": n})
    return sorted(out, key=lambda x: -x["lines"])[:top]


def git_info(root):
    out = {"branch": None, "head": None, "commits": None}
    def g(*args):
        try:
            r = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                               text=True, timeout=60, check=False)
        except Exception as e:
            print(f"[WARN] git {args[0]} lỗi: {e}", file=sys.stderr)
            return ""
        return r.stdout.strip()
    out["branch"] = g("rev-parse", "--abbrev-ref", "HEAD") or None
    out["head"] = g("rev-parse", "HEAD") or None
    try:
        out["commits"] = int(g("rev-list", "--count", "HEAD") or "0")
    except ValueError:
        out["commits"] = None
    # top churn commits (tổng dòng inserted) — dấu hiệu commit "vibe"
    churn = []
    try:
        r = subprocess.run(["git", "-C", str(root), "log", "--shortstat", "--pretty=format:%h|%s|%an"],
                           capture_output=True, text=True, timeout=120, check=False)
        cur = None
        for line in r.stdout.splitlines():
            if "|" in line and line.count("|") >= 2:
                cur = {"sha": line.split("|")[0], "subject": line.split("|")[1][:70],
                       "author": line.split("|")[2], "ins": 0}
                churn.append(cur)
            elif cur and line.strip():
                m = re.search(r"(\d+) insertions", line)
                if m:
                    cur["ins"] += int(m.group(1))
    except Exception as e:
        print(f"[WARN] git log lỗi: {e}", file=sys.stderr)
    out["top_churn_commits"] = sorted(churn[:400], key=lambda x: -x["ins"])[:5]
    return out


def assets(root):
    out = {"skills_dirs": [], "skills_count": 0, "tools_dirs": [], "rules_files": []}
    for name in RULES_FILES + [".github/copilot-instructions.md"]:
        for p in [root / name, root / ".github" / name]:
            if p.exists():
                out["rules_files"].append({"path": str(p.relative_to(root)),
                                           "bytes": p.stat().st_size})
    for rel in ["skills", "hermes/skills", ".hermes/skills", "tools", "hermes/tools", "plugins"]:
        d = root / rel
        if d.is_dir():
            entries = [e.name for e in d.iterdir()]
            if rel.endswith("skills"):
                out["skills_dirs"].append(rel)
                out["skills_count"] += len(entries)
            else:
                out["tools_dirs"].append(rel)
    return out


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="RECON: thống kê ngôn ngữ/entrypoint/test của repo.")
    ap.add_argument("--target", default=".")
    ap.add_argument("--out", help="ghi JSON ra file (mặc định: in stdout)")
    a = ap.parse_args(argv)
    target = Path(a.target)
    outp = a.out
    target = target.resolve()
    counts = count_exts(target)
    tests_found = sum(1 for p in target.rglob("*") if p.is_file() and any(
        m in str(p.relative_to(target)) for m in TEST_MARKERS))
    info = {
        "target": str(target),
        "ext_counts": counts,
        "langs": langs(counts),
        "entrypoints": [str(p.relative_to(target)) for p in [
            target / "pyproject.toml", target / "setup.py", target / "package.json",
            target / "Makefile", target / "docker-compose.yml", target / "docker-compose.yaml",
            target / "Dockerfile", target / "pytest.ini", target / "tox.ini"] if p.exists()],
        "test_files": tests_found,
        "big_files": big_files(target),
        "git": git_info(target),
        "assets": assets(target),
    }
    if outp:
        Path(outp).parent.mkdir(parents=True, exist_ok=True)
        Path(outp).write_text(json.dumps(info, ensure_ascii=False, indent=1))
    else:
        print(json.dumps(info, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
