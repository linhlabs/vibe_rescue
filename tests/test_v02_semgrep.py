import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_semgrep_rules_catch_violations(tmp_path):
    """Integration: rule pack (tools/rules/) bắt đủ 7 class vi phạm; file sạch không dính.

    Lý do copy ra tmp_path: semgrep mặc định bỏ qua đường dẫn chứa 'test' (built-in ignore)
    — fixture nằm trong tests/ sẽ bị trừ; tmp_path không chứa 'test'.
    """
    src = ROOT / "tests" / "fixtures" / "semgrep"
    for f in ("bad.py", "good.py"):
        shutil.copy(src / f, tmp_path / f)
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "meta" / "scan.py"),
                        "--tool", "semgrep", "--target", str(tmp_path),
                        "--out", str(tmp_path / "out.json")],
                       capture_output=True, text=True, timeout=900, check=False)
    assert r.returncode in (0, 2), r.stdout + r.stderr
    data = json.loads((tmp_path / "out.json").read_text())
    rules = {f["rule"].split(".")[-1] for f in data["findings"]}
    expected = {"pii-vn-phone", "pii-vn-cccd", "security-command-shell-true",
                "security-eval-exec", "security-pickle-insecure",
                "security-archive-extract", "security-hardcoded-secret"}
    missing = expected - rules
    assert not missing, f"rule pack thiếu: {missing} (findings={len(data['findings'])})"
    assert all(not f["file"].endswith("good.py") for f in data["findings"]), \
        "good.py phải sạch — false positive!"
