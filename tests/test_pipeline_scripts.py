import json
import subprocess
import sys
from pathlib import Path

from scripts import merge_findings
from scripts.delta_gate import compute


def _raw(dirpath, name, tool, findings):
    (dirpath / "raw").mkdir(parents=True, exist_ok=True)
    (dirpath / "raw" / f"{name}.json").write_text(json.dumps(
        {"tool": tool, "ok": True, "findings": findings}))


def test_merge_dedupe(tmp_path):
    _raw(tmp_path, "ruff", "ruff", [
        {"rule": "F401", "severity": "high", "file": "src/a.py", "line": 1,
         "message": "m1", "evidence": "F401"},
        {"rule": "F401", "severity": "high", "file": "src/a.py", "line": 1,
         "message": "dup", "evidence": "F401"},
    ])
    _raw(tmp_path, "bandit", "bandit", [
        {"rule": "B301", "severity": "medium", "file": "src/b.py", "line": 3,
         "message": "pickle", "evidence": ""},
    ])
    items, errors = merge_findings.load_raw(tmp_path / "raw")
    assert not errors
    assert len(items) == 3
    merged = merge_findings.merge(items)
    assert len(merged) == 2  # dedupe (tool|rule|file|line)
    assert merged[0]["message"] == "m1"


def test_merge_normalizes_severity_and_path(tmp_path):
    _raw(tmp_path, "x", "x", [
        {"rule": "R", "severity": "WEIRD", "file": "./src/./a.py", "line": None,
         "message": "", "evidence": ""},
    ])
    items, _ = merge_findings.load_raw(tmp_path / "raw")
    assert items[0]["severity"] == "low"  # unknown severity falls back to low
    assert items[0]["file"] == "src/a.py"


def test_merge_keeps_trivy_critical(tmp_path):
    """Regression F1: trivy CRITICAL must survive merge as 'critical', not 'low'."""
    _raw(tmp_path, "trivy", "trivy", [
        {"rule": "CVE-2026-1", "severity": "CRITICAL", "file": "app:1.0", "line": None,
         "message": "boom", "evidence": "1.0"},
    ])
    items, _ = merge_findings.load_raw(tmp_path / "raw")
    assert items[0]["severity"] == "critical"
    assert merge_findings.SEV_RANK["critical"] > merge_findings.SEV_RANK["high"]


def test_merge_keeps_distinct_lineless_findings(tmp_path):
    """Regression F5: two different line-less findings in one file stay distinct."""
    items = [
        {"tool": "lychee", "rule": "LINK-broken", "severity": "low",
         "file": "docs/README.md", "line": None, "message": "https://a.com -> 404",
         "evidence": "code=404"},
        {"tool": "lychee", "rule": "LINK-broken", "severity": "low",
         "file": "docs/README.md", "line": None, "message": "https://b.com -> 500",
         "evidence": "code=500"},
    ]
    merged = merge_findings.merge(items)
    assert len(merged) == 2


def test_delta_new_and_fixed(tmp_path):
    base = tmp_path / "base.json"
    cur = tmp_path / "cur.json"
    mk = lambda path, files: path.write_text(json.dumps({
        "findings": [{"tool": t, "file": f, "rule": r} for t, f, r in files]}))
    mk(base, [("ruff", "a.py", "F401"), ("bandit", "b.py", "B301")])
    mk(cur, [("ruff", "a.py", "F401"), ("ruff", "c.py", "E501")])
    r = compute(str(base), str(cur))
    assert r["new"] == ["ruff|c.py|E501"]
    assert r["fixed"] == ["bandit|b.py|B301"]
    assert r["remain"] == ["ruff|a.py|F401"]


def test_delta_gate_cli_blocks_new(tmp_path):
    """Regression: gate phải chạy qua CLI thật, block finding mới (exit 2)."""
    base = tmp_path / "b.json"
    cur = tmp_path / "c.json"
    base.write_text(json.dumps({"findings": [{"tool": "ruff", "file": "a.py", "rule": "F401"}]}))
    cur.write_text(json.dumps({"findings": [
        {"tool": "ruff", "file": "a.py", "rule": "F401"},
        {"tool": "ruff", "file": "b.py", "rule": "E501"}]}))
    root = Path(__file__).resolve().parents[1]
    r = subprocess.run([sys.executable, "scripts/delta_gate.py",
                        "--baseline", str(base), "--current", str(cur)],
                       capture_output=True, text=True, cwd=root, check=False)
    assert r.returncode == 2 and "BLOCK" in r.stdout and "ruff|b.py|E501" in r.stdout
