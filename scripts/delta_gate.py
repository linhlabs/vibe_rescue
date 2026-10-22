#!/usr/bin/env python3
"""
delta_gate.py — so baseline vs current findings.

Đơn vị so sánh là (tool|file|rule) — KHÔNG có line, vì dòng chảy khi sửa sẽ tạo
finding giả. "Fixed" = rule không còn bắn trong file đó; "New" = rule mới xuất hiện
trong file (hoặc file mới). Nợ cũ (trong baseline) không bao giờ block (RULES R7).

Quy tắc (RULES R7/R10):
- Block CHỈ finding MỚI (key tool|file|rule có trong current nhưng không trong baseline).
- --allow <pattern> cho phép theo pattern: "ruff" (cả tool), "src/gen/" (prefix file),
  "src/gen/*" (prefix file + wildcard), "bandit|src/" (key-prefix tool|file).

Exit codes: 0 = không có finding mới (hoặc đều được allow); 2 = có finding mới (CI fail).

Usage:
  python3 scripts/delta_gate.py --baseline a/findings.json --current b/findings.json
"""
import json
import sys
from pathlib import Path


def keys_of(findings):
    out = set()
    for f in findings:
        f_ = str(f.get("file") or "").replace("\\", "/").lstrip("./")
        out.add(f"{f.get('tool')}|{f_}|{f.get('rule')}")
    return out


def compute(baseline_path, current_path):
    base = json.loads(Path(baseline_path).read_text()).get("findings", [])
    cur = json.loads(Path(current_path).read_text()).get("findings", [])
    bkeys, ckeys = keys_of(base), keys_of(cur)
    new = sorted(ckeys - bkeys)
    fixed = sorted(bkeys - ckeys)
    remain = sorted(bkeys & ckeys)
    return {"baseline": len(bkeys), "current": len(ckeys),
            "new": new, "fixed": fixed, "remain": remain}


def allowed(k, allow):
    """Kiểm tra key 'tool|file|rule' có nằm trong pattern list không (xem docstring)."""
    tool, f, _rule = k.split("|", 2)
    for p in allow:
        if "|" in p:
            if k.startswith(p.rstrip("*")):
                return True
        elif p.endswith("*"):
            if f.startswith(p.rstrip("*")) or tool == p.rstrip("*"):
                return True
        elif f.startswith(p) or tool == p:
            return True
    return False


def gate(baseline, current, allow):
    """Trả về (exit_code, kết quả chi tiết). Gộp logic để unit-test được."""
    r = compute(baseline, current)
    new_allowed = [k for k in r["new"] if allowed(k, allow)]
    new_blocking = [k for k in r["new"] if not allowed(k, allow)]
    lines = [("baseline={} current={} new={} fixed={} remain={}".format(
        r['baseline'], r['current'], len(r['new']), len(r['fixed']), len(r['remain'])))]
    for k in r["new"]:
        lines.append(f"  NEW   {k}" + (" [allowed]" if k in new_allowed else " [BLOCK]"))
    for k in r["fixed"]:
        lines.append(f"  FIXED {k}")
    if new_blocking:
        lines.append(f"[GATE] FAIL: {len(new_blocking)} finding mới "
                     f"(baseline giữ {len(r['remain'])} nợ cũ)")
        return 2, "\n".join(lines)
    lines.append("[GATE] PASS: không có finding mới")
    return 0, "\n".join(lines)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Gate: chỉ chặn finding MỚI so baseline (RULES R7).")
    ap.add_argument("--baseline", required=True, help="findings.json của baseline")
    ap.add_argument("--current", required=True, help="findings.json hiện tại")
    ap.add_argument("--allow", default="", help="pattern cho phép, cách nhau bằng ','")
    a = ap.parse_args(argv)
    allow = [x.strip() for x in a.allow.split(",") if x.strip()]
    code, report = gate(a.baseline, a.current, allow)
    print(report)
    return code


if __name__ == "__main__":
    sys.exit(main())
