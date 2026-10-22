#!/usr/bin/env python3
# Chính sách noqa: 1 file raw hỏng không được làm hỏng cả đợt evidence (RULES R11).
# ruff: noqa: BLE001
"""
merge_findings.py — gộp raw/<tool>.json thành findings chuẩn + digest markdown.

Dedupe key: (tool|rule|file|line). Giữ finding nghiêm trọng nhất nếu trùng.

Usage:
  python3 scripts/merge_findings.py --rundir reports/run-<ts>
"""
import json
import posixpath
import sys
from collections import Counter
from pathlib import Path

try:
    from tools.meta import redact  # dùng như package (pytest/ROOT đã có trong sys.path)
except ImportError:                 # standalone — load theo ĐÚNG ĐƯỜNG DẪN FILE.
    # KHÔNG fallback insert-ROOT-rồi-import-lại: nếu môi trường người dùng có package
    # tên 'tools' ở site-packages (rất phổ biến), nó đã bị cache vào sys.modules từ lần
    # thử đầu và import lại vẫn trỏ nhầm (audit v0.4 round-2 — bug thật trên máy dev).
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "vibe_rescue_redact", Path(__file__).resolve().parents[1] / "tools" / "meta" / "redact.py")
    redact = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(redact)

# Rank used when two findings collide on the dedupe key: keep the more severe one.
# "critical" (trivy CRITICAL) is ranked above high; unknown severities still fall
# back to "low" in load_raw(), so a critical CVE is never silently downgraded.
SEV_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}
REQUIRED = ("rule", "severity", "file", "line", "message", "evidence")


def load_raw(raw_dir: Path):
    items = []
    errors = []
    for f in sorted(raw_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except Exception as e:
            errors.append(f"{f.name}: {e}")
            continue
        if not isinstance(data, dict):
            continue
        for x in data.get("findings", []):
            if not isinstance(x, dict):
                continue
            rec = {k: x.get(k) for k in REQUIRED}
            rec["tool"] = data.get("tool", f.stem)
            # H1 (audit v0.3.5): lớp 2 — raw từ nguồn ngoài (tay, CI khác) cũng được che
            # trước khi vào findings.json / SARIF.
            rec["message"] = redact.mask_text(str(rec.get("message") or ""))
            rec["evidence"] = redact.mask_text(str(rec.get("evidence") or ""))
            rec["file"] = posixpath.normpath(str(rec["file"] or "").replace("\\", "/")).lstrip("./")
            sev = str(rec.get("severity") or "low").lower()
            rec["severity"] = sev if sev in SEV_RANK else "low"
            if not rec["file"]:
                continue
            items.append(rec)
    return items, errors


def merge(items):
    """Dedupe by (tool, rule, file, line).

    Tools that never emit a line number (lychee broken links, dependency-cruiser
    violations, trivy misconfigs) would otherwise collapse distinct findings in
    the same file, so their message is appended to the key when line is None.
    """
    best = {}
    for rec in items:
        line = rec.get("line")
        key = (rec["tool"], rec["rule"], rec["file"], line) if line is not None \
            else (rec["tool"], rec["rule"], rec["file"], line, rec.get("message"))
        cur = best.get(key)
        if cur is None or SEV_RANK.get(rec["severity"], 0) > SEV_RANK.get(cur["severity"], 0):
            best[key] = rec
    return sorted(best.values(), key=lambda r: (-SEV_RANK.get(r["severity"], 0), r["file"], r["rule"]))


def digest(findings, meta):
    counts = Counter(f["severity"] for f in findings)
    by_tool = Counter(f["tool"] for f in findings)
    lines = [f"# Findings digest — {meta.get('rundir')}", ""]
    lines.append(f"- target: {meta.get('target')}  sha: {meta.get('sha')}")
    lines.append(f"- total: {len(findings)}  " + "  ".join(f"{k}={v}" for k, v in counts.items()), )
    lines.append("")
    lines.append("## Theo tool")
    for t, n in by_tool.most_common():
        lines.append(f"- {t}: {n}")
    lines.append("")
    lines.append("## Findings")
    for f in findings:
        loc = f"{f['file']}:{f['line']}" if f.get("line") else f["file"]
        lines.append(f"- [{f['severity']}] `{f['tool']}` {loc} `{f['rule']}` — {f['message'][:140]}")
    return "\n".join(lines) + "\n"


def to_sarif(findings, meta):
    """SARIF 2.1.0 — xuất để CI/GitHub consume (tối thiểu: results + ruleId + locations)."""
    sev_map = {"critical": "error", "high": "error", "medium": "warning", "low": "note"}
    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "vibe_rescue", "informationUri": "https://github.com/thusinh1969/vibe_rescue"}},
            "results": [{
                "ruleId": f"{f['tool']}|{f['rule']}",
                "level": sev_map.get(f.get("severity"), "warning"),
                "message": {"text": f"{f.get('message', '')} [{f.get('evidence', '')}]"[:400]},
                "locations": [{"physicalLocation": {"artifactLocation": {"uri": f.get("file", "")},
                                                   "region": {"startLine": f.get("line")} if f.get("line") else {}}}],
            } for f in findings],
        }],
    }


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Gộp raw/<tool>.json -> findings.json + SARIF.")
    ap.add_argument("--rundir", required=True, help="dir evidence chứa raw/")
    ap.add_argument("--sarif", help="ghi thêm findings.sarif ra đường dẫn này")
    a = ap.parse_args(argv)
    rundir, sarif_out = Path(a.rundir), a.sarif
    raw_dir = rundir / "raw"
    if not raw_dir.exists():
        print(f"[WHAT] không có {raw_dir}")
        return 2
    conf = {}
    if (rundir / "run.conf.json").exists():
        conf = json.loads((rundir / "run.conf.json").read_text())
    items, errors = load_raw(raw_dir)
    findings = merge(items)
    tool_status = {}
    for tool in conf.get("tools", []):
        raw = raw_dir / f"{tool}.json"
        try:
            data = json.loads(raw.read_text())
            tool_status[tool] = ("ok" if data.get("ok") else
                                 "skipped" if data.get("skipped") else "failed")
        except (OSError, ValueError):
            tool_status[tool] = "failed"
            errors.append(f"{tool}: missing or invalid raw evidence")
    meta = {"rundir": str(rundir), "target": conf.get("target"), "sha": conf.get("sha"),
            "tools": conf.get("tools", []), "tool_status": tool_status,
            "counts": dict(Counter(f["severity"] for f in findings)),
            "raw_errors": errors}
    (rundir / "findings.json").write_text(
        json.dumps({"meta": meta, "findings": findings}, ensure_ascii=False, indent=1))
    (rundir / "findings.md").write_text(digest(findings, meta), encoding="utf-8")
    if sarif_out:
        Path(sarif_out).parent.mkdir(parents=True, exist_ok=True)
        Path(sarif_out).write_text(json.dumps(to_sarif(findings, meta), ensure_ascii=False, indent=1))
    print(f"[DONE] findings={len(findings)} high={meta['counts'].get('high', 0)} "
          f"medium={meta['counts'].get('medium', 0)} low={meta['counts'].get('low', 0)} -> {rundir/'findings.json'}")
    if errors:
        print(f"[WARN] raw errors: {errors}")
    return 2 if errors or "failed" in tool_status.values() else 0


if __name__ == "__main__":
    sys.exit(main())
