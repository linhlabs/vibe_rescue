#!/usr/bin/env python3
# Chính sách noqa: fanout phải thu evidence tới cùng dù 1 tool hỏng — except rộng là chủ đích
# (RULES R11: fail-loud trong báo cáo, không crash cả đợt). BLE001/S110 kiểm điểm ở self-run.
# ruff: noqa: BLE001
"""
fanout.py — phase PROVE wave 1: chạy các scanner deterministic SONG SONG.

Mỗi tool chạy độc lập qua `tools/meta/scan.py`, kết quả ghi:
  <outdir>/raw/<tool>.json   (chuẩn hóa)
  <outdir>/run.conf.json     (target, sha, thời gian, danh sách tool)

Usage:
  python3 scripts/fanout.py --target <repo> --tools all --outdir reports/run-<ts>
  python3 scripts/fanout.py --target <repo> --tools ruff,vulture --outdir ... --parallel 4
"""
import datetime
import json
import subprocess
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

with open(ROOT / "tools" / "manifest.toml", "rb") as _f:
    _MAN = tomllib.load(_f)
# single source of truth — không nhân bản ở đây
CORE = _MAN["core"]["order"]["tools"]
_T3 = [t for t in list(_MAN["tier3"]["python"]) + list(_MAN["tier3"]["js"])
       if isinstance(_MAN["tier3"]["python"].get(t) or _MAN["tier3"]["js"].get(t), str)]
ALL = CORE + _T3 + list(_MAN["binaries"]) + ["mcp-conformance"]


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(
        description="PROVE: chạy scanner song song qua tools/meta/scan.py (pin từ manifest).")
    ap.add_argument("--target", required=True, help="repo mục tiêu")
    ap.add_argument("--outdir", required=True, help="dir evidence, vd reports/run-<ts>")
    ap.add_argument("--tools", default="all", help="'all' hoặc danh sách cách nhau bằng ','")
    ap.add_argument("--parallel", type=int, default=4)
    a = ap.parse_args(argv)
    target, outdir, tools, parallel = Path(a.target), Path(a.outdir), a.tools, a.parallel
    target = target.resolve()
    tool_list = ALL if tools in (None, "all") else [t.strip() for t in tools.split(",") if t.strip()]
    outdir.mkdir(parents=True, exist_ok=True)
    raw = outdir / "raw"
    raw.mkdir(exist_ok=True)

    sha = None
    try:
        sha = subprocess.run(["git", "-C", str(target), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=30, check=False).stdout.strip() or None
    except Exception as e:
        print(f"[WARN] không đọc được git sha: {e}", file=sys.stderr)

    conf = {"target": str(target), "sha": sha, "tools": tool_list,
            "parallel_workers": parallel,
            "started_at": datetime.datetime.now(datetime.UTC).isoformat()}
    (outdir / "run.conf.json").write_text(json.dumps(conf, ensure_ascii=False, indent=1))

    def one(tool):
        out = raw / f"{tool}.json"
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "meta" / "scan.py"),
                            "--tool", tool, "--target", str(target), "--out", str(out)],
                           capture_output=True, text=True, timeout=1800, check=False)
        try:
            data = json.loads(out.read_text())
        except Exception as e:
            data = {"tool": tool, "ok": False,
                    "error": f"không đọc được output ({e}): {r.stderr[:300]}"}
        return tool, data

    results = {}
    with ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
        futs = {ex.submit(one, t): t for t in tool_list}
        for idx, f in enumerate(as_completed(futs), 1):
            tool, data = f.result()
            results[tool] = data
            print(f"  [{idx}/{len(tool_list)}] {tool}: "
                  f"{'skipped: ' + data.get('skipped') if data.get('skipped') else str(len(data.get('findings', []))) + ' findings' if data.get('ok') else 'FAILED'}",
                  flush=True)

    summary = {"ok": sum(1 for r in results.values() if r.get("ok")),
               "skipped": sum(1 for r in results.values() if r.get("skipped")),
               "failed": sum(1 for r in results.values() if not r.get("ok") and not r.get("skipped"))}
    (outdir / "run.summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"[DONE] ok={summary['ok']} skipped={summary['skipped']} failed={summary['failed']} out={outdir}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
