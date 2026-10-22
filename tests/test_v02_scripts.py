import json
import subprocess
import sys
from pathlib import Path

from scripts import lock_rulesync, rescue_loop, run_target
from scripts.merge_findings import to_sarif

ROOT = Path(__file__).resolve().parents[1]


def test_sarif():
    findings = [{"tool": "semgrep", "rule": "pii-vn-phone", "severity": "high",
                 "file": "src/x.py", "line": 5, "message": "PII", "evidence": "ev"}]
    sarif = to_sarif(findings, {"target": "t"})
    assert sarif["version"] == "2.1.0"
    res = sarif["runs"][0]["results"][0]
    assert res["level"] == "error"
    assert res["locations"][0]["physicalLocation"]["region"]["startLine"] == 5


def test_parse_verdict(tmp_path):
    ok = tmp_path / "a.md"
    ok.write_text("# Verdict PLAN-001\nResult: APPROVE\nScope: OK\n")
    assert rescue_loop.parse_verdict(ok) == "APPROVE"
    bad = tmp_path / "b.md"
    bad.write_text("blabla")
    assert rescue_loop.parse_verdict(bad) is None


def test_rescue_loop_approve(tmp_path):
    """Loop thật với stub: executor modify file trong scope, reviewer APPROVE."""
    target = tmp_path / "repo"
    (target / "src").mkdir(parents=True)
    (target / "src" / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=target, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=target, check=True)
    subprocess.run(["git", "add", "-A"], cwd=target, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=target, check=True)

    plan = tmp_path / "PLAN-001.md"
    sha = subprocess.run(["git", "-C", str(target), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()
    plan.write_text(f"""# PLAN-001: demo
Plan SHA: {sha}
Scope: [src/a.py]
Out-of-scope: [src/b.py]
Baseline evidence: [X]
Steps:
  1. Đổi biến — Verification: `true`
STOP conditions: diff > 1 file
Rollback: `git checkout .`
Done criteria: `true`
""")
    executor = ('sh -c \'echo "y = 2" >> src/a.py\'')
    reviewer = ('sh -c \'printf "# Verdict $PLAN_ID\\nResult: APPROVE\\n" > "$VERDICT_FILE"\'')
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"meta": {"sha": sha, "tools": ["ruff"],
                                            "tool_status": {"ruff": "ok"}},
                                    "findings": []}))
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "rescue_loop.py"),
                        "--target", str(target), "--plan", str(plan),
                        "--baseline", str(baseline), "--tools", "ruff",
                        "--probe", "python3 -B -c \"import src.a; assert src.a.x == 1\"",
                        "--workdir", str(tmp_path / "wt"),
                        "--logdir", str(tmp_path / "logs"),
                        "--executor-cmd", executor,
                        "--reviewer-cmd", reviewer],
                       capture_output=True, text=True, cwd=ROOT, check=False, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    state = json.loads((tmp_path / "logs" / "PLAN-001.loop.json").read_text())
    assert state["result"] == "APPROVE"
    assert state["rounds"][0]["step"] == "reviewer"


def test_rescue_loop_scope_violation(tmp_path):
    """Executor sửa file NGOÀI scope -> REVISE, không bao giờ APPROVE."""
    target = tmp_path / "repo"
    (target / "src").mkdir(parents=True)
    (target / "src" / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=target, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=target, check=True)
    subprocess.run(["git", "add", "-A"], cwd=target, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=target, check=True)
    plan = tmp_path / "PLAN-002.md"
    sha = subprocess.run(["git", "-C", str(target), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()
    plan.write_text(f"""# PLAN-002: demo
Plan SHA: {sha}
Scope: [src/a.py]
Out-of-scope: [src/b.py]
Baseline evidence: [X]
Steps:
  1. Đổi biến — Verification: `true`
STOP conditions: diff > 1 file
Rollback: `git checkout .`
Done criteria: `true`
""")
    executor = 'sh -c \'echo "y" > src/b.py\''
    reviewer = 'sh -c \'printf "Result: APPROVE\\n" > "$VERDICT_FILE"\''
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"meta": {"sha": sha, "tools": ["ruff"],
                                            "tool_status": {"ruff": "ok"}},
                                    "findings": []}))
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "rescue_loop.py"),
                        "--target", str(target), "--plan", str(plan),
                        "--baseline", str(baseline), "--tools", "ruff",
                        "--probe", "python3 -B -c \"import src.a; assert src.a.x == 1\"",
                        "--workdir", str(tmp_path / "wt2"),
                        "--logdir", str(tmp_path / "logs2"),
                        "--executor-cmd", executor, "--reviewer-cmd", reviewer],
                       capture_output=True, text=True, cwd=ROOT, check=False, timeout=300)
    assert r.returncode != 0
    state = json.loads((tmp_path / "logs2" / "PLAN-002.loop.json").read_text())
    assert state["result"] == "REVISE_LIMIT"  # 3 vòng REVISE scope -> hết budget
    assert any(x["result"] == "REVISE" and x["step"] == "scope_check" for x in state["rounds"])


def test_registry_load():
    reg = run_target.load_registry()
    assert "self" in reg and reg["self"]["path"] == "."


def test_lock_rulesync_build_cmd(tmp_path):
    t = tmp_path / "repo"
    t.mkdir()
    (t / ".git").mkdir()
    cmd = lock_rulesync.build_cmd("doctor", t, "claudecode", "rules", None)
    assert "doctor" in cmd and "--strict" in cmd
    cmd = lock_rulesync.build_cmd("drift", t, "claudecode", "rules", None)
    assert "generate" in cmd and "--output-roots" in cmd
