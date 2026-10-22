#!/usr/bin/env python3
# Chính sách noqa: fallback builtin khi repomix hỏng là chủ đích — evidence phải chạy tiếp.
# ruff: noqa: BLE001
"""
context_pack.py — phase MAP: bóc tách blackbox của repo mục tiêu thành artifact đọc được.

Ưu tiên: npx repomix (đầy đủ config/whitelist riêng của repomix).
Fallback: packer tích hợp (stdlib) — bộ loc nhạy, sort ổn định, giới hạn kích thước,
không đụng .git/node_modules/.venv.

Usage:
  python3 tools/meta/context_pack.py --target <repo> --outdir .rescue
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from tools.meta import redact  # import package (test / dùng như module)
except ImportError:                  # chạy trực tiếp: python3 tools/meta/context_pack.py
    import redact

IGNORE_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".tox",
               ".pytest_cache", ".mypy_cache", ".ipynb_checkpoints", "dist", "build",
               ".next", "target", ".idea", ".vscode", ".auditor_g6_sweep", "logs_audit",
               "bin", ".rescue", "reports"}
# "bin" = tools/bin binaries; ".rescue" and "reports" are harness evidence, not
# target source — packing them only bloats context.txt with stale prior runs.
BIN_EXT = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".pyc", ".so",
           ".exe", ".dll", ".woff", ".woff2", ".ttf", ".ico", ".lock"}
MAX_FILE_LINES = 3000
MAX_TOTAL = 4 * 1024 * 1024  # 4MB cap artifact
MAX_FILE_BYTES = 10 * 1024 * 1024  # skip file > 10MB (binary không extension)


def is_binary(p: Path):
    """Sniff 8KB đầu — file nhị phân (null byte) không đưa vào context."""
    try:
        with open(p, "rb") as f:
            head = f.read(8192)
        return b"\x00" in head
    except Exception:
        return True


def collect(path: Path, root: Path, out: list, stats: dict, budget: dict):
    for p in sorted(path.iterdir()):
        if p.is_dir():
            if p.name in IGNORE_DIRS or p.name.startswith("."):
                continue
            collect(p, root, out, stats, budget)
            continue
        try:
            rel = str(p.relative_to(root))
        except ValueError:
            continue
        rel_l = rel.lower()
        if any(rel_l.endswith(e) for e in BIN_EXT):
            stats["binaries"] += 1
            continue
        size = p.stat().st_size
        if size > MAX_FILE_BYTES or is_binary(p):
            stats["binaries"] += 1
            continue
        if size > 512 * 1024:
            stats["big_files"] += 1
        n_lines = sum(1 for _ in p.open(errors="ignore"))
        stats["files"] += 1
        stats["lines"] += n_lines
        if size > budget["remain"] or budget["remain"] <= 0:
            stats["truncated"] += 1
            continue
        out.append((rel, n_lines, p))
        budget["remain"] -= p.stat().st_size


def write_pack(target: Path, outfile: Path, stats: dict):
    out = []
    budget = {"remain": MAX_TOTAL}
    files = []
    collect(target, target, files, stats, budget)
    for rel, n_lines, p in files:
        out.append(f"### FILE: {rel}  ({n_lines} lines)\n")
        try:
            lines = p.read_text(errors="ignore").splitlines()
            show = lines[:MAX_FILE_LINES]
            out.extend(show)
            if len(lines) > MAX_FILE_LINES:
                out.append(f"### [truncated: {len(lines) - MAX_FILE_LINES} lines]\n")
        except Exception as e:
            out.append(f"### [read error: {e}]\n")
        out.append("")
    outfile.write_text("\n".join(out))
    stats["packed_files"] = len(files)
    stats["packed_bytes"] = outfile.stat().st_size


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="MAP: bóc tách repo mục tiêu thành context.txt.")
    ap.add_argument("--target", default=".")
    ap.add_argument("--outdir", default=".rescue")
    a = ap.parse_args(argv)
    target, outdir = Path(a.target), Path(a.outdir)
    target = target.resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    stats = {"files": 0, "lines": 0, "binaries": 0, "big_files": 0, "truncated": 0,
             "packed_files": 0, "packed_bytes": 0, "engine": "builtin"}

    repomix_exe = shutil.which("repomix") or shutil.which("npx")
    ctx = outdir / "context.txt"
    used_repomix = False
    if repomix_exe:
        try:
            r = subprocess.run(["npx", "-y", "repomix@1.18.0", "-t", str(target), "-o", str(ctx)],
                               capture_output=True, text=True, timeout=600, check=False)
            if r.returncode == 0 and ctx.exists():
                stats["engine"] = "repomix"
                used_repomix = True
        except Exception as e:
            print(f"[WARN] repomix không chạy được ({e}); dùng builtin packer", file=sys.stderr)
    if not used_repomix:
        write_pack(target, ctx, stats)

    # H1 (audit v0.3.5): context.txt gom nội dung target — có thể chứa khóa thật
    # (file .env bị skip vì là dotfile, nhưng model_inventory.json / script dán key thì không).
    redact.mask_file(ctx)
    stats["redacted"] = True

    meta = {"target": str(target), "engine": stats["engine"], "stats": stats,
            "artifact": str(ctx), "generated_at": __import__("datetime").datetime.now().isoformat()}
    (outdir / "context.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(json.dumps(meta, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
