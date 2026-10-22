"""Behavioral gates: a failed candidate may never reach reviewer or merge."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = 'python3 -B -c "import src.a; assert src.a.x == 1"'


def _fixture(tmp_path):
    target = tmp_path / "repo"
    (target / "src").mkdir(parents=True)
    (target / "src" / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    subprocess.run(["git", "add", "-A"], cwd=target, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                    "-qm", "base"], cwd=target, check=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=target,
                         capture_output=True, text=True, check=True).stdout.strip()
    plan = tmp_path / "PLAN-001.md"
    plan.write_text(f"""# PLAN-001: safety probe
Plan SHA: {sha}
Scope: [src/a.py]
Out-of-scope: [other files]
Baseline evidence: [none]
Steps:
  1. Change src/a.py — Verification: `true`
STOP conditions: candidate probe or scanner fails
Rollback: `git reset --hard {sha}`
Done criteria: candidate probe and reviewer approve
""")
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"meta": {"sha": sha, "tools": ["ruff"],
                                            "tool_status": {"ruff": "ok"}},
                                    "findings": []}))
    return target, plan, baseline, sha


def _run(tmp_path, target, plan, baseline, executor, reviewer="true", probe=PROBE):
    logdir = tmp_path / "logs"
    args = [sys.executable, str(ROOT / "scripts" / "rescue_loop.py"),
            "--target", str(target), "--plan", str(plan),
            "--workdir", str(tmp_path / "worktrees"), "--logdir", str(logdir),
            "--max-rounds", "1", "--executor-cmd", executor,
            "--reviewer-cmd", reviewer, "--tools", "ruff"]
    if baseline is not None:
        args += ["--baseline", str(baseline)]
    if probe is not None:
        args += ["--probe", probe]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                            check=False, timeout=120)
    state = json.loads((logdir / "PLAN-001.loop.json").read_text())
    return result, state


def test_broken_candidate_probe_blocks_reviewer_and_removes_branch(tmp_path):
    target, plan, baseline, sha = _fixture(tmp_path)
    result, state = _run(tmp_path, target, plan, baseline,
                         "sh -c 'printf \"x = 2\\n\" > src/a.py'",
                         "sh -c 'printf \"Result: APPROVE\\n\" > \"$VERDICT_FILE\"'")
    assert result.returncode == 2
    assert state["result"] == "REVISE_LIMIT"
    assert [r["step"] for r in state["rounds"]] == ["candidate_probe"]
    assert subprocess.run(["git", "rev-parse", "HEAD"], cwd=target,
                          capture_output=True, text=True, check=True).stdout.strip() == sha
    assert subprocess.run(["git", "branch", "--list", "rescue/PLAN-001"], cwd=target,
                          capture_output=True, text=True, check=True).stdout.strip() == ""


def test_stale_approve_verdict_cannot_approve_new_round(tmp_path):
    target, plan, baseline, _ = _fixture(tmp_path)
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "PLAN-001.md").write_text("Result: APPROVE\n")
    result, state = _run(tmp_path, target, plan, baseline,
                         "sh -c 'printf \"y = 2\\n\" >> src/a.py'")
    assert result.returncode == 2
    assert state["result"] == "REVISE_LIMIT"
    assert state["rounds"][-1]["step"] == "reviewer"
    assert state["rounds"][-1]["result"] == "UNKNOWN"


def test_new_static_finding_blocks_approve(tmp_path):
    target, plan, baseline, _ = _fixture(tmp_path)
    result, state = _run(tmp_path, target, plan, baseline,
                         "sh -c 'printf \"import os\\n\" >> src/a.py'",
                         "sh -c 'printf \"Result: APPROVE\\n\" > \"$VERDICT_FILE\"'")
    assert result.returncode == 2
    assert state["result"] == "REVISE_LIMIT"
    assert state["rounds"][-1]["step"] == "delta_gate"


def test_missing_probe_or_baseline_fails_before_executor(tmp_path):
    target, plan, baseline, sha = _fixture(tmp_path)
    for missing_baseline, missing_probe in ((True, False), (False, True)):
        result, state = _run(tmp_path, target, plan,
                             None if missing_baseline else baseline,
                             "sh -c 'printf \"x = 2\\n\" > src/a.py'",
                             probe=None if missing_probe else PROBE)
        assert result.returncode == 2
        assert state["result"] == "BLOCK"
        assert state["rounds"][0]["step"] == "preflight"
        assert subprocess.run(["git", "rev-parse", "HEAD"], cwd=target,
                              capture_output=True, text=True, check=True).stdout.strip() == sha


def test_reviewer_cannot_change_candidate_and_approve_it(tmp_path):
    target, plan, baseline, _ = _fixture(tmp_path)
    reviewer = ("sh -c 'printf \"z = 3\\n\" >> src/a.py; git add -A; "
                "git -c user.name=t -c user.email=t@t commit -qm reviewer; "
                "printf \"Result: APPROVE\\n\" > \"$VERDICT_FILE\"'")
    result, state = _run(tmp_path, target, plan, baseline,
                         "sh -c 'printf \"y = 2\\n\" >> src/a.py'", reviewer)
    assert result.returncode == 2
    assert state["result"] == "BLOCK"
    assert state["rounds"][-1]["step"] == "reviewer_integrity"


def test_executor_modifying_target_outside_worktree_is_blocked(tmp_path):
    target, plan, baseline, _ = _fixture(tmp_path)
    executor = (f"sh -c 'printf \"x = 9\\n\" > {target / 'src' / 'a.py'}; "
                "printf \"y = 2\\n\" >> src/a.py'")
    result, state = _run(tmp_path, target, plan, baseline, executor)
    assert result.returncode == 2
    assert state["result"] == "BLOCK"
    assert state["rounds"][-1]["step"] == "target_integrity"
    assert (target / "src" / "a.py").read_text() == "x = 9\n"


def test_scanner_coverage_mismatch_blocks_before_executor(tmp_path):
    target, plan, baseline, sha = _fixture(tmp_path)
    data = json.loads(baseline.read_text())
    data["meta"]["tools"] = ["bandit"]
    baseline.write_text(json.dumps(data))
    result, state = _run(tmp_path, target, plan, baseline,
                         "sh -c 'printf \"x = 2\\n\" > src/a.py'")
    assert result.returncode == 2
    assert state["result"] == "BLOCK"
    assert state["rounds"][0]["step"] == "baseline_coverage"
    assert (target / "src" / "a.py").read_text() == "x = 1\n"
    assert subprocess.run(["git", "rev-parse", "HEAD"], cwd=target,
                          capture_output=True, text=True, check=True).stdout.strip() == sha
