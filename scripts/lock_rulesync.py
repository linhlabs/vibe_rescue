#!/usr/bin/env python3
"""
lock_rulesync.py — LOCK phase: single-source-of-truth (rulesync 16.17.0) cho rules/
skills/MCP của TARGET, rồi chặn drift.

Modes:
  doctor   : rulesync doctor --strict (read-only, exit 1 khi cảnh báo) — kiểm tra nhanh
  generate : rulesync generate -t <tools> -f <features> vào target (viết file per-harness)
  drift    : generate rồi `git diff --exit-code` — developer KHÔNG được sửa trực tiếp
             generated files (RULES: file sinh ra lệch source of truth = CI fail)

rulesync cần cấu hình trong TARGET (rulesync.jsonc / .rulesync/) — xem
tools/rulesync/example-rulesync.jsonc. Chạy lần đầu: `rulesync init` + `import`.

Usage:
  python3 scripts/lock_rulesync.py --target <repo> [--mode doctor|generate|drift] \
      [--tools claudecode,codexcli,cursor,copilot] [--features rules,skills,mcp,permissions]
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOOLS = "claudecode,codexcli,cursor,copilot"
DEFAULT_FEATURES = "rules,skills,mcp,permissions"


def build_cmd(mode, target, tools, features, config):
    npx = ["npx", "-y", "rulesync@16.17.0"]

    def cfg():
        return ["--config", str(config)] if config else []
    if mode == "doctor":
        return npx + ["doctor", "--strict"] + cfg()
    base = npx + ["generate", "-t", tools, "-f", features] + cfg()
    if mode == "generate":
        return base + ["--output-roots", str(target)]
    return base + ["--input-roots", str(target / ".rulesync") if
                   (target / ".rulesync").exists() else str(target), "--output-roots", str(target)]


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="LOCK: rulesync single-source + chặn drift.")
    ap.add_argument("--target", required=True)
    ap.add_argument("--mode", choices=("doctor", "generate", "drift"), default="drift")
    ap.add_argument("--tools", default=DEFAULT_TOOLS)
    ap.add_argument("--features", default=DEFAULT_FEATURES)
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    mode, tools, features = a.mode, a.tools, a.features
    config = Path(a.config) if a.config else None
    target = Path(a.target)
    if mode not in ("doctor", "generate", "drift"):
        print("[WHAT] cần --target <repo> và --mode doctor|generate|drift")
        return 2
    target = target.resolve()
    if not (target / ".git").exists():
        print(f"[WHAT] {target} không phải git repo (drift cần git)")
        return 2
    cmd = build_cmd(mode, target, tools, features, config)
    print("[RUN]", " ".join(cmd))
    if mode == "drift":
        gen = subprocess.run(cmd, cwd=target, capture_output=True, text=True, check=False)
        if gen.returncode != 0:
            print(f"[LOCK] FAIL generate: {(gen.stdout or gen.stderr)[:300]}")
            return 2
        diff = subprocess.run(["git", "diff", "--exit-code"], cwd=target,
                              capture_output=True, text=True, check=False)
        if diff.returncode != 0:
            print("[LOCK] FAIL: generated files lệch source of truth (git diff != rỗng) — "
                  "sửa .rulesync/, không sửa file generated")
            return 2
        print("[LOCK] PASS: generated files khớp source of truth, không drift")
        return 0
    r = subprocess.run(cmd, cwd=target, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        print(f"[LOCK] FAIL: {(r.stdout or r.stderr)[:300]}")
        return 2
    print(f"[LOCK] PASS ({mode}): {(r.stdout or '')[:200]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
