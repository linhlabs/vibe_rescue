"""A scanner failure must not become a clean scan because partial JSON parsed."""
import json
import subprocess

import pytest

from tools.meta import scan


@pytest.mark.parametrize("exit_code,stdout,expected", [
    (9, '[{"code":"F401","filename":"x.py","location":{"row":1},"message":"unused"}]', 2),
    (1, '[]', 2),
    (1, '[{"code":"F401","filename":"x.py","location":{"row":1},"message":"unused"}]', 0),
])
def test_ruff_exit_code_requires_real_findings(tmp_path, monkeypatch, exit_code, stdout, expected):
    monkeypatch.setattr(scan, "run", lambda _cmd, cwd=None: subprocess.CompletedProcess(
        [], exit_code, stdout=stdout, stderr=""))
    out = tmp_path / "ruff.json"
    result = {"tool": "ruff", "ok": False, "skipped": None, "error": None, "findings": []}
    assert scan._run_tool("ruff", out, None, tmp_path, [], result) == expected
    saved = json.loads(out.read_text())
    assert saved["exit_code"] == exit_code
    assert saved["ok"] is (expected == 0)


def test_jscpd_missing_report_is_not_zero_findings(tmp_path, monkeypatch):
    monkeypatch.setattr(scan, "JSCPD_OUT", str(tmp_path))
    r = subprocess.CompletedProcess([], 0, stdout="", stderr="")
    findings, error = scan.collect_findings("jscpd", r, tmp_path, {})
    assert findings is None
    assert "report" in error
