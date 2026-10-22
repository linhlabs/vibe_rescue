#!/usr/bin/env python3
"""
run_target.py — chạy MAP+PROVE cho một target theo targets/registry.toml (hoặc --path).

  MAP  : context_pack + recon -> <target-artdir>/
  PROVE: fanout (--tools all) + merge (+ --sarif) -> reports/targets/<name>/run/
  DELTA: so với baseline trong registry nếu có; không có baseline -> lưu baseline đầu.

Usage:
  python3 scripts/run_target.py --name self
  python3 scripts/run_target.py --path /path/to/repo --name demo [--tools all]
"""
import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_registry(path: Path = ROOT / "targets" / "registry.toml"):
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return {t["name"]: t for t in data.get("targets", [])}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="MAP+PROVE cho 1 target theo registry.toml.")
    ap.add_argument("--name", help="tên trong targets/registry.toml")
    ap.add_argument("--path", help="đường dẫn repo (nếu không dùng --name)")
    ap.add_argument("--tools", default="all", help="'all' hoặc danh sách cách nhau bằng ','")
    ap.add_argument("--sarif", help="ghi findings.sarif ra đường dẫn này")
    a = ap.parse_args(argv)
    name, path, tools, sarif = a.name, Path(a.path) if a.path else None, a.tools, a.sarif
    if name and not path:
        reg = load_registry().get(name)
        if not reg:
            print(f"[WHAT] target '{name}' không có trong targets/registry.toml")
            return 2
        path = ROOT / reg["path"]
        if reg.get("tools"):
            tools = reg["tools"]  # registry giới hạn tool (vd bỏ mutmut cho self-run)
    if not path:
        print("[WHAT] thiếu --name (registry) hoặc --path")
        return 2
    path = path.resolve()
    out = ROOT / "reports" / "targets" / (name or path.name)
    p = lambda *xs: str(out.joinpath(*xs))

    context_file = out / ".rescue" / "context.json"
    recon_file = out / "recon.json"
    cur = out / "run" / "findings.json"
    for stale in (context_file, recon_file, cur):
        stale.unlink(missing_ok=True)
    for label, command, artifact in (
        ("MAP", [sys.executable, str(ROOT / "tools" / "meta" / "context_pack.py"),
                 "--target", str(path), "--outdir", p(".rescue")], context_file),
        ("RECON", [sys.executable, str(ROOT / "tools" / "meta" / "recon.py"),
                   "--target", str(path), "--out", p("recon.json")], recon_file),
    ):
        r = subprocess.run(command, check=False)
        if r.returncode != 0 or not artifact.is_file():
            print(f"[{label}] BLOCK: exit={r.returncode}, missing={not artifact.is_file()}")
            return 2
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "fanout.py"),
                        "--target", str(path), "--tools", ",".join(tools) if isinstance(tools, list) else tools,
                        "--outdir", p("run"), "--parallel", "3"], check=False)
    if r.returncode != 0:
        print("[PROVE] BLOCK: scanner fanout failed; baseline không được tạo")
        return 2
    try:
        summary = json.loads((out / "run" / "run.summary.json").read_text())
    except (OSError, ValueError):
        summary = {}
    if summary.get("failed") != 0 or not summary.get("ok"):
        print("[PROVE] BLOCK: run summary thiếu/failed/không scanner nào chạy")
        return 2
    merged = subprocess.run([sys.executable, str(ROOT / "scripts" / "merge_findings.py"),
                    "--rundir", p("run")] + (["--sarif", p("findings.sarif")] if sarif else []),
                   check=False)
    if merged.returncode != 0 or not cur.is_file():
        print(f"[PROVE] BLOCK: merge exit={merged.returncode}, fresh findings={cur.is_file()}")
        return 2
    baseline = ROOT / "reports" / "targets" / (name or path.name) / "baseline"
    baseline_file = baseline / "findings.json"
    if baseline_file.exists() and cur.exists():
        g = subprocess.run([sys.executable, str(ROOT / "scripts" / "delta_gate.py"),
                            "--baseline", str(baseline_file),
                            "--current", str(cur)], check=False)
        return g.returncode
    if cur.exists():
        baseline.mkdir(parents=True, exist_ok=True)
        baseline_file.write_text(cur.read_text())
        print(f"[BASELINE] saved first baseline for {name or path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
