import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from scripts import dialogue, guards
from scripts.dialogue import Dialogue, DialogueTimeout

ROOT = Path(__file__).resolve().parents[1]


def _git_init(dirpath: Path):
    subprocess.run(["git", "init", "-q"], cwd=dirpath, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=dirpath, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=dirpath, check=True)
    (dirpath / ".gitkeep").write_text("1")


def _commit(dirpath: Path, msg="init"):
    subprocess.run(["git", "add", "-A"], cwd=dirpath, check=True)
    subprocess.run(["git", "commit", "-qm", msg], cwd=dirpath, check=True)


def test_parse_answer_valid_and_invalid():
    q = {"id": "Q-random", "nonce": "fresh", "binding": "pinned"}
    assert dialogue.parse_answer({**q, "choice": "accept"}, ["accept", "reject"], q) == ("accept", "")
    assert dialogue.parse_answer({**q, "choice": "edit", "note": "x"}, ["accept", "edit"], q) == ("edit", "x")
    with pytest.raises(ValueError):
        dialogue.parse_answer({**q, "choice": "maybe"}, ["accept", "reject"], q)
    with pytest.raises(ValueError):
        dialogue.parse_answer({}, ["accept"], q)
    with pytest.raises(ValueError):
        dialogue.parse_answer({**q, "id": "old", "choice": "accept"}, ["accept"], q)
    with pytest.raises(ValueError):
        dialogue.parse_answer({**q, "nonce": "old", "choice": "accept"}, ["accept"], q)


def _answer_when_asked(dirpath, choices):
    """Test owner writes only after reading the unique current question."""
    def worker():
        seen = {p.name for p in dirpath.glob("QUESTION-*.json")}
        for choice in choices:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                questions = sorted(dirpath.glob("QUESTION-*.json"), key=lambda p: p.stat().st_mtime_ns)
                pending = [p for p in questions if p.name not in seen]
                if pending:
                    qpath = pending[0]
                    q = json.loads(qpath.read_text())
                    seen.add(qpath.name)
                    answer = {k: q[k] for k in ("id", "nonce", "binding")}
                    answer.update({"choice": choice, "note": "test"})
                    tmp = dirpath / (q["answer_file"] + ".tmp")
                    tmp.write_text(json.dumps(answer))
                    os.replace(tmp, dirpath / q["answer_file"])
                    break
                time.sleep(0.02)
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread


def test_dialogue_file_mode(tmp_path):
    _answer_when_asked(tmp_path, ["accept"])
    d = Dialogue(mode="file", directory=str(tmp_path))
    choice, note = d.ask("plan", "OK?", ["accept", "reject"], timeout=3)
    assert choice == "accept" and note == "test"
    assert len(list(tmp_path.glob("QUESTION-Q000-*.json"))) == 1
    assert not list(tmp_path.glob("ANSWER-*.json"))


def test_dialogue_reject_and_timeout(tmp_path):
    d = Dialogue(mode="file", directory=str(tmp_path))
    with pytest.raises(DialogueTimeout):
        d.ask("plan", "OK?", ["accept"], timeout=0.2)
    d2dir = tmp_path / "r2"
    d2dir.mkdir()
    (d2dir / "ANSWER-Q000.json").write_text(json.dumps({"choice": "reject"}))
    d2 = Dialogue(mode="file", directory=str(d2dir))
    with pytest.raises(DialogueTimeout):
        d2.ask("plan", "OK?", ["accept", "reject"], timeout=0.2)
    _answer_when_asked(d2dir, ["reject"])
    d3 = Dialogue(mode="file", directory=str(d2dir))
    choice, _ = d3.ask("plan", "OK?", ["accept", "reject"], timeout=3)
    assert choice == "reject"


def test_dialogue_bad_answer_is_discarded(tmp_path):
    _answer_when_asked(tmp_path, ["nonsense"])
    d = Dialogue(mode="file", directory=str(tmp_path))
    with pytest.raises(DialogueTimeout):
        d.ask("p", "q", ["accept"], timeout=0.3)


def test_guards_backup_and_revert(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _git_init(repo)
    (repo / "a.txt").write_text("1")
    _commit(repo)
    tag1 = guards.backup_tag(repo, "backup-pre")
    tag2 = guards.backup_tag(repo, "backup-pre")
    assert tag1 == "backup-pre" and tag2 == "backup-pre-1"
    # revert tracking
    before = guards.snapshot_sha(repo)
    (repo / "a.txt").write_text("2")
    _commit(repo, "change")
    after = guards.snapshot_sha(repo)
    guards.track_change(tmp_path, {"ts": "T", "action": "merge", "branch": "b",
                                   "before_sha": before, "after_sha": after,
                                   "revert_cmd": f"git revert -m 1 {after}", "note": ""})
    log = (tmp_path / "CHANGES.log").read_text()
    revert = (tmp_path / "REVERT.md").read_text()
    assert "merge" in log and f"git revert -m 1 {after}" in revert


def test_probe_never_break(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _git_init(repo)
    _commit(repo)
    before = guards.run_probe(repo, ["git rev-parse HEAD"])
    assert guards.probes_equal(before, before)
    (repo / "x.txt").write_text("x")
    _commit(repo, "change")
    after = guards.run_probe(repo, ["git rev-parse HEAD"])
    assert not guards.probes_equal(before, after)
    # lệnh khác nhau -> không bằng
    assert not guards.probes_equal(before, guards.run_probe(repo, ["true"]))


def _make_target(tmp_path):
    target = tmp_path / "target"
    (target / "src").mkdir(parents=True)
    (target / "src" / "a.py").write_text("x = 1\n")
    _git_init(target)
    _commit(target)
    return target


def test_voyage_repair_merge_with_owner(tmp_path):
    """Full: owner (file) đồng ý chạy repair + merge; probe never-break giữ nguyên."""
    target = _make_target(tmp_path)
    session = target / ".rescue" / "voyage"
    plan = session / "PLAN-001.md"
    plan.parent.mkdir(parents=True)
    (session / "prove").mkdir()
    (session / "prove" / "findings.json").write_text(json.dumps({
        "meta": {"sha": guards.snapshot_sha(target), "tools": ["ruff"],
                 "tool_status": {"ruff": "ok"}}, "findings": []}))
    plan.write_text(f"""# PLAN-001: demo
Plan SHA: {guards.snapshot_sha(target)}
Scope: [src/a.py]
Out-of-scope: [src/b.py]
Baseline evidence: []
Steps:
  1. Đổi biến — Verification: `true`
STOP conditions: diff > 1 file
Rollback: `git checkout .`
Done criteria: `true`
""")
    (session / "approvals").mkdir()
    (session / "approvals" / "PLAN-001.json").write_text(json.dumps({
        "plan_sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
        "target_head": guards.snapshot_sha(target),
    }))
    answers = tmp_path / "answers"
    answers.mkdir()
    _answer_when_asked(answers, ["accept", "accept"])
    executor = 'sh -c \'echo "y = 2" >> src/a.py\''
    reviewer = 'sh -c \'printf "Result: APPROVE\\n" > "$VERDICT_FILE"\''
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "rescue_voyage.py"),
                        "--path", str(target), "--stages", "repair",
                        "--owner", "file", "--answers", str(answers),
                        "--probe", "python3 -B -c \"import src.a; assert src.a.x == 1\"",
                        "--tools", "ruff",
                        "--executor-cmd", executor, "--reviewer-cmd", reviewer],
                       capture_output=True, text=True, cwd=str(ROOT), check=False, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
    # merge thành công: branch chính giữ thay đổi
    head = subprocess.run(["git", "-C", str(target), "log", "--oneline", "-2"],
                          capture_output=True, text=True, check=False).stdout
    assert "demo" in head or "PLAN-001" in head
    log = (session / "CHANGES.log").read_text()
    assert "merge" in log and 'git revert -m 1' in log
    assert (session / "REVERT.md").exists()


def test_voyage_post_merge_probe_failure_auto_reverts(tmp_path):
    target = _make_target(tmp_path)
    session = target / ".rescue" / "voyage"
    session.mkdir(parents=True)
    plan = session / "PLAN-001.md"
    sha = guards.snapshot_sha(target)
    plan.write_text(f"""# PLAN-001: add field
Plan SHA: {sha}
Scope: [src/a.py]
Out-of-scope: [other files]
Baseline evidence: [none]
Steps:
  1. Add field — Verification: `true`
STOP conditions: probe fails
Rollback: `git revert HEAD`
Done criteria: probe and reviewer pass
""")
    (session / "prove").mkdir()
    (session / "prove" / "findings.json").write_text(json.dumps({
        "meta": {"sha": sha, "tools": ["ruff"], "tool_status": {"ruff": "ok"}},
        "findings": []}))
    (session / "approvals").mkdir()
    (session / "approvals" / "PLAN-001.json").write_text(json.dumps({
        "plan_sha256": hashlib.sha256(plan.read_bytes()).hexdigest(), "target_head": sha}))
    answers = tmp_path / "answers"
    answers.mkdir()
    _answer_when_asked(answers, ["accept", "accept"])
    probe = ("python3 -B -c \"import subprocess; assert len(subprocess.check_output("
             "['git','rev-list','--parents','-n1','HEAD']).split()) <= 2\"")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "rescue_voyage.py"),
                        "--path", str(target), "--stages", "repair", "--owner", "file",
                        "--answers", str(answers), "--probe", probe, "--tools", "ruff",
                        "--executor-cmd", 'sh -c \'echo "y = 2" >> src/a.py\'',
                        "--reviewer-cmd", 'sh -c \'printf "Result: APPROVE\\n" > "$VERDICT_FILE"\''],
                       capture_output=True, text=True, cwd=ROOT, check=False, timeout=120)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "auto-revert" in r.stdout
    assert (target / "src" / "a.py").read_text() == "x = 1\n"
    assert json.loads((session / "voyage.json").read_text())["state"] == "blocked_repair"


def test_voyage_plan_reject_stops(tmp_path):
    target = _make_target(tmp_path)
    answers = tmp_path / "answers"
    answers.mkdir()
    _answer_when_asked(answers, ["reject"])
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "rescue_voyage.py"),
                        "--path", str(target), "--stages", "plan",
                        "--owner", "file", "--answers", str(answers),
                        "--adviser-cmd", "false"],  # adviser fail -> template + owner quyết
                       capture_output=True, text=True, cwd=str(ROOT), check=False, timeout=300)
    assert r.returncode == 2
    state = json.loads((target / ".rescue" / "voyage" / "voyage.json").read_text())
    assert state["state"] == "stopped_plan_rejected"
    # không có thay đổi nào trong git
    status = subprocess.run(["git", "-C", str(target), "status", "--porcelain"],
                            capture_output=True, text=True, check=False).stdout
    assert "a.py" not in status


def test_plan_approval_is_bound_to_plan_contents(tmp_path):
    target = _make_target(tmp_path)
    session = target / ".rescue" / "voyage"
    session.mkdir(parents=True)
    source = tmp_path / "proposed.md"
    source.write_text(f"""# PLAN-001: add field
Plan SHA: {guards.snapshot_sha(target)}
Scope: [src/a.py]
Out-of-scope: [other files]
Baseline evidence: [none]
Steps:
  1. Add field — Verification: `true`
STOP conditions: probe fails
Rollback: `git revert HEAD`
Done criteria: probe and reviewer pass
""")
    answers = tmp_path / "answers"
    answers.mkdir()
    _answer_when_asked(answers, ["accept"])
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "rescue_voyage.py"),
                        "--path", str(target), "--stages", "plan",
                        "--owner", "file", "--answers", str(answers),
                        "--adviser-cmd", f"cat {source}"], cwd=ROOT,
                       capture_output=True, text=True, check=False, timeout=30)
    assert r.returncode == 0, r.stdout + r.stderr
    approval = json.loads((session / "approvals" / "PLAN-001.json").read_text())
    plan = session / "PLAN-001.md"
    assert approval["plan_sha256"] == hashlib.sha256(plan.read_bytes()).hexdigest()
    (session / "prove").mkdir()
    (session / "prove" / "findings.json").write_text(json.dumps({
        "meta": {"sha": guards.snapshot_sha(target), "tools": ["ruff"],
                 "tool_status": {"ruff": "ok"}}, "findings": []}))
    plan.write_text(plan.read_text() + "\nExtra unchecked step.\n")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "rescue_voyage.py"),
                        "--path", str(target), "--stages", "repair",
                        "--owner", "file", "--answers", str(answers),
                        "--probe", "true", "--tools", "ruff"], cwd=ROOT,
                       capture_output=True, text=True, check=False, timeout=30)
    assert r.returncode == 2
    assert "đã đổi sau khi duyệt" in r.stdout
    assert guards.snapshot_sha(target) == approval["target_head"]


def test_archgraph_cycles_and_hub(tmp_path):
    """Integration: archgraph phát hiện cycle + hub module trên repo fixture nhỏ."""
    repo = tmp_path / "repo"
    (repo / "pkg" / "a").mkdir(parents=True)
    (repo / "pkg" / "b").mkdir(parents=True)
    (repo / "pkg" / "a" / "__init__.py").write_text("")
    (repo / "pkg" / "b" / "__init__.py").write_text("")
    (repo / "pkg" / "a" / "x.py").write_text("from pkg.b import y\nfrom pkg.c import z\n")
    (repo / "pkg" / "b" / "y.py").write_text("from pkg.a import x\nfrom pkg.c import z\n")
    (repo / "pkg" / "c.py").write_text("z = 1\n")
    for name in ("u1", "u2", "u3", "u4", "u5"):
        (repo / "pkg" / f"{name}.py").write_text("from pkg.c import z\n")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "meta" / "archgraph.py"),
                        str(repo)], capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    cyc = [c for c in d["cycles"] if set(c) == {"pkg.a.x", "pkg.b.y"}]
    assert cyc, d["cycles"]
    assert d["fan_in"]["pkg.c"] >= 5
    assert "pkg.c" in [h["module"] for h in d["summary"]["hub_modules"]]


def test_voyage_review_stage_template(tmp_path):
    """Stage 'review': agent không chạy được -> template team-readable vẫn ra đủ bộ."""
    target = _make_target(tmp_path)
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "rescue_voyage.py"),
                        "--path", str(target), "--stages", "review",
                        "--review-cmd", "false"],
                       capture_output=True, text=True, cwd=str(ROOT), check=False, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    rdir = target / ".rescue" / "voyage" / "review"
    assert (rdir / "REVIEW.md").exists() and (rdir / "PROPOSALS.md").exists()
    assert (rdir / "EVIDENCE" / "README.md").exists()
    props = (rdir / "PROPOSALS.md").read_text()
    assert "| ID | Vấn đề" in props  # format team-readable
