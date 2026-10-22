#!/usr/bin/env python3
"""
rescue_voyage.py — MỘT LỆNH chạy autonomous (có gate): MAP → PROVE → REVIEW → PLAN → REPAIR → LOCK.

Pact (docs/OWNER_PACT.md):
- MAP/PROVE read-only: chạy tự động, kết quả báo owner (không cần đồng ý).
- PLAN/REPAIR/merge/LOCK: PHẢI có owner đồng ý — reject = dừng bước đó, KHÔNG tự quyết.
- Backup trước mọi thay đổi (git tag) + CHANGES.log/REVERT.md (revert được từng bước).
- NEVER BREAK: probe (tests/smoke) chạy TRƯỚC và SAU mỗi thay đổi; lệch = block + tự hủy branch.

Sau stage REVIEW (audit v0.3.5 → v0.4):
- H2: máy tự kiểm số LLM nêu (check_review_numbers.py) — advisory, không chặn.
- H3: EVIDENCE/ tự chứa (collect_evidence.py) — JSON đã redact, ai cũng kiểm lại được.
- H4: AI KIỂM chấm chéo bản review (mắt thứ hai) — fail-open, bỏ qua khi agent chính chạy tay.
- H1: '.rescue/' chưa bị target gitignore -> IN CẢNH BÁO, hỏi owner (không tự đụng .gitignore).

Mọi thứ của phiên nằm trong <target>/.rescue/voyage/ (evidence, KHÔNG commit).

Usage:
  python3 scripts/rescue_voyage.py --name self [--stages map,prove,review,plan,repair,lock]
      [--owner interactive|file] [--answers <dir>] [--max-rounds 3]
      [--path <repo>] [--probe "cmd1;cmd2"] [--executor-cmd ...] [--reviewer-cmd ...]
      [--adviser-cmd ...] [--review-cmd ...]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # cho phép import scripts.* khi chạy trực tiếp

# Chính sách noqa: evidence/session hỏng cục bộ phải báo và chạy tiếp, không crash (R11).
# ruff: noqa: BLE001

import argparse
import datetime
import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field

from scripts.exec_util import sh
from scripts.llm_config import build_cmd, describe, load_config

STAGES = ["map", "prove", "review", "plan", "repair", "lock"]


def now():
    return datetime.datetime.now(datetime.UTC).isoformat()


def load_registry():
    import tomllib
    with open(ROOT / "targets" / "registry.toml", "rb") as f:
        return {t["name"]: t for t in tomllib.load(f).get("targets", [])}


@dataclass
class Ctx:
    """Trạng thái dùng chung của các stage trong 1 phiên voyage."""
    target: Path
    session: Path
    stages: list
    max_rounds: int
    reg: dict = field(default_factory=dict)
    probe_cmds: list | None = None
    scan_tools: str = "all"
    executor_cmd: str = ""
    reviewer_cmd: str = ""
    adviser_cmd: str = ""
    review_cmd: str = ""
    review_cmd_custom: bool = False
    roles: dict = field(default_factory=dict)
    d: object = None            # Dialogue
    log: dict = field(default_factory=dict)
    probe_before: dict | None = None


def parse_args(argv):
    ap = argparse.ArgumentParser(description="Voyage một lệnh: MAP→PROVE→REVIEW→PLAN→REPAIR→LOCK.")
    ap.add_argument("--name", help="tên trong targets/registry.toml")
    ap.add_argument("--path", help="đường dẫn repo target (nếu không dùng --name)")
    ap.add_argument("--stages", help=f"danh sách stage, vd: {','.join(STAGES)}")
    ap.add_argument("--owner", help="interactive | file")
    ap.add_argument("--answers", help="dir chứa ANSWER-<id>.json (owner=file)")
    ap.add_argument("--max-rounds", type=int, default=3)
    ap.add_argument("--probe", action="append", help="mỗi probe một --probe; lặp lại được")
    ap.add_argument("--tools", help="scanner cho PROVE và REPAIR (mặc định: registry hoặc all)")
    ap.add_argument("--executor-cmd", help="override LLM vai write (mặc định: config.toml)")
    ap.add_argument("--reviewer-cmd", help="override LLM vai verify")
    ap.add_argument("--adviser-cmd", help="override adviser (vai write)")
    ap.add_argument("--review-cmd", help="override LLM vai audit (stage review)")
    a = ap.parse_args(argv)
    stages = [s.strip() for s in a.stages.split(",") if s.strip()] if a.stages else None
    probe = [c.strip() for c in a.probe if c.strip()] if a.probe else None
    return a, stages, probe


def _stage_map(c: Ctx):
    context = sh(sys.executable, ROOT / "tools" / "meta" / "context_pack.py",
                 "--target", c.target, "--outdir", c.session / "map")
    if context.returncode != 0:
        print(f"[MAP] BLOCK: context_pack lỗi: {(context.stderr or context.stdout)[-300:]}")
        return 2
    recon = sh(sys.executable, ROOT / "tools" / "meta" / "recon.py",
               "--target", c.target, "--out", c.session / "map" / "recon.json")
    if recon.returncode != 0 or not (c.session / "map" / "recon.json").is_file():
        print(f"[MAP] BLOCK: recon lỗi/thiếu artifact: {(recon.stderr or recon.stdout)[-300:]}")
        return 2
    print(f"[MAP] done -> {c.session / 'map'}")


def _stage_prove(c: Ctx):
    scan = sh(sys.executable, ROOT / "scripts" / "fanout.py", "--target", c.target,
              "--tools", c.scan_tools, "--outdir", c.session / "prove", "--parallel", "3")
    if scan.returncode != 0:
        print(f"[PROVE] BLOCK: scanner lỗi; không tạo baseline: {(scan.stderr or scan.stdout)[-300:]}")
        return 2
    merge = sh(sys.executable, ROOT / "scripts" / "merge_findings.py",
               "--rundir", c.session / "prove", "--sarif", c.session / "prove" / "findings.sarif")
    if merge.returncode != 0:
        print(f"[PROVE] BLOCK: không gộp được evidence: {(merge.stderr or merge.stdout)[-300:]}")
        return 2
    base_p = c.session / "baseline" / "findings.json"
    if base_p.exists():
        from scripts.fanout import ALL
        from scripts.rescue_loop import _coverage_problems
        expected = ALL if c.scan_tools == "all" else [t.strip() for t in c.scan_tools.split(",") if t.strip()]
        old_meta = json.loads(base_p.read_text()).get("meta", {})
        new_meta = json.loads((c.session / "prove" / "findings.json").read_text()).get("meta", {})
        problems = _coverage_problems(old_meta, new_meta, expected)
        if problems:
            print(f"[PROVE] BLOCK: scanner coverage đổi: {'; '.join(problems)[:300]}")
            return 2
        g = sh(sys.executable, ROOT / "scripts" / "delta_gate.py",
               "--baseline", base_p, "--current", c.session / "prove" / "findings.json")
        print(f"[PROVE] delta exit={g.returncode} (xem {c.session / 'prove' / 'findings.md'})")
        if g.returncode != 0:
            return 2
    else:
        (c.session / "baseline").mkdir(parents=True, exist_ok=True)
        (c.session / "baseline" / "findings.json").write_text(
            (c.session / "prove" / "findings.json").read_text())
        print("[PROVE] baseline đầu tiên đã lưu (nợ hiện tại)")
    print(f"[PROVE] done -> {c.session / 'prove'}")


def _crosscheck(c: Ctx, rdir: Path):
    """H4 — AI KIỂM chấm chéo bản review. Fail-open: chỉ phụ trợ, không bao giờ chặn."""
    if c.review_cmd_custom:
        return  # agent chính chạy tay/template — không có bản review chuẩn để chấm
    cli = (c.roles.get("verify") or {}).get("cli", "codex")
    if cli.lower() != "openai" and not shutil.which(cli):
        print(f"[CROSSCHECK] bỏ qua (CLI verify '{cli}' chưa cài)")
        return
    env = {**os.environ,
           "PROMPT_AGENT": (ROOT / "agents" / "crosscheck.md").read_text(encoding="utf-8"),
           "TARGET_DIR": str(c.target), "REVIEW_DIR": str(rdir),
           "EVIDENCE_DIR": str(c.session), "VIBE_AGENT_TASK": "crosscheck"}
    r = sh("bash", "-c", f"{build_cmd('verify', c.roles)} > {rdir / 'EVIDENCE' / 'cross-check-raw.txt'}"
                         f" 2> {rdir / 'EVIDENCE' / 'cross-check-cmd.err'}",
           cwd=str(ROOT), env=env)
    if r.returncode == 0:
        print("[CROSSCHECK] mắt thứ hai đã chấm -> EVIDENCE/cross-check.md")
    else:
        err = (rdir / "EVIDENCE" / "cross-check-cmd.err").read_text(errors="ignore")[:200]
        print(f"[CROSSCHECK] không chạy được (fail-open, review vẫn hợp lệ): {err.strip()}")


def _stage_review(c: Ctx):
    rdir = c.session / "review"
    (rdir / "EVIDENCE").mkdir(parents=True, exist_ok=True)
    env = {**os.environ,
           "PROMPT_AGENT": (ROOT / "agents" / "auditor_architecture.md").read_text(encoding="utf-8"),
           "TARGET_DIR": str(c.target), "EVIDENCE_DIR": str(c.session),
           "REVIEW_DIR": str(rdir), "VIBE_AGENT_TASK": "review"}
    ran_at = datetime.datetime.now(datetime.UTC).timestamp()
    sh("bash", "-c", f"{c.review_cmd} > {rdir / 'raw-review.txt'}"
                     f" 2> {rdir / 'EVIDENCE' / 'review-cmd.err'}",
       cwd=str(ROOT), env=env)
    # agent_wrote: README.md hoặc REVIEW.md + PROPOSALS.md được GHI MỚI (mtime)
    def _new(p):
        return p.exists() and p.stat().st_mtime >= ran_at
    wrote_md = ((_new(rdir / "README.md") or _new(rdir / "REVIEW.md"))
                and _new(rdir / "PROPOSALS.md"))
    if wrote_md:
        # alias: README.md (canonical) <-> REVIEW.md (tương thích code cũ)
        if _new(rdir / "README.md") and not _new(rdir / "REVIEW.md"):
            shutil.copy(rdir / "README.md", rdir / "REVIEW.md")
        elif _new(rdir / "REVIEW.md") and not _new(rdir / "README.md"):
            shutil.copy(rdir / "REVIEW.md", rdir / "README.md")
    else:
        _review_templates(rdir, c.session, c.target)
        err = (rdir / "EVIDENCE" / "review-cmd.err").read_text(errors="ignore")[:200]
        notice = ("# REVIEW — " + c.target.name
                  + "\n> Lưu ý: LLM auditor (claude) chưa chạy được lần này — "
                  + (err.strip() or "xem review-cmd.err")
                  + ". Harness dùng template + số liệu thật;"
                  + "\n> chạy lại sau khi `claude /login` để sinh bản đầy đủ.\n\n")
        body = (rdir / "README.md").read_text(encoding="utf-8")
        (rdir / "README.md").write_text(notice + body, encoding="utf-8")
        shutil.copy(rdir / "README.md", rdir / "REVIEW.md")
    print(f"[REVIEW] done -> {rdir} (agent_wrote={wrote_md}) — xem docs/OUTPUT_PROTOCOL.md")

    # H2: máy tự kiểm số LLM nêu — advisory, không chặn
    nc = sh(sys.executable, ROOT / "scripts" / "check_review_numbers.py",
            "--review-dir", rdir, cwd=str(ROOT))
    print((nc.stdout or "").strip()
          or f"[NUMCHECK] lỗi: {(nc.stderr or '')[:200]}")
    # H3: EVIDENCE tự chứa (JSON đã redact + summary)
    ev = sh(sys.executable, ROOT / "scripts" / "collect_evidence.py",
            "--session", c.session, cwd=str(ROOT))
    print((ev.stdout or "").strip() or f"[EVIDENCE] lỗi: {(ev.stderr or '')[:200]}")
    if ev.returncode != 0:
        print("[REVIEW] BLOCK: evidence package không tạo được")
        return 2
    # H4: mắt thứ hai chấm chéo
    _crosscheck(c, rdir)
    # H1: advisory — không tự đụng .gitignore của target (PACT)
    gi = sh("git", "-C", c.target, "check-ignore", "-q", ".rescue/")
    if gi.returncode != 0:
        print("[PACT] '.rescue/' CHƯA nằm trong .gitignore của target — evidence đã redact "
              "khóa nhưng vẫn nên ignore. HỎI OWNER trước khi sửa (không tự đụng .gitignore).")


def _stage_plan(c: Ctx):
    """Fail-closed plan gate: proceed only when plan_check passes AND the owner
    explicitly accepts. Reject stops; edit retries; anything else stops after
    3 attempts instead of silently continuing into REPAIR."""
    plan_p = c.session / "PLAN-001.md"
    env = {**os.environ,
           "PROMPT_AGENT": (ROOT / "agents" / "advisor.md").read_text(encoding="utf-8"),
           "EVIDENCE_DIR": str(c.session), "TARGET_DIR": str(c.target),
           "VIBE_AGENT_TASK": "plan"}
    r = sh("bash", "-c", f"{c.adviser_cmd} > {plan_p}", cwd=str(ROOT), env=env)
    if r.returncode != 0 or not plan_p.exists():
        plan_p.write_text(_plan_template(c.session), encoding="utf-8")
        print("[PLAN] adviser did not run (claude CLI required) — wrote template, owner edits by hand")

    for attempt in range(1, 4):
        chk = sh(sys.executable, ROOT / "scripts" / "plan_check.py",
                 "--plan", plan_p, "--target", c.target)
        if chk.returncode != 0:
            print(f"[PLAN] plan_check FAIL (attempt {attempt}): {chk.stdout[:300]} — fix before accept")
        proposed_hash = hashlib.sha256(plan_p.read_bytes()).hexdigest()
        proposed_head = _guards_snapshot_sha(c.target)
        choice, note = c.d.ask("plan", f"Approve plan {plan_p.name}? (owner verdict)",
                               ["accept", "edit", "reject"],
                               context={"plan_check": chk.returncode,
                                        "plan_sha256": proposed_hash, "target_head": proposed_head})
        c.log["decisions"].append({"phase": "plan", "choice": choice, "note": note})
        if choice == "reject":
            print("[PLAN] owner rejected — stop, no changes made")
            c.log["state"] = "stopped_plan_rejected"
            (c.session / "voyage.json").write_text(json.dumps(c.log, ensure_ascii=False, indent=1))
            return 2
        if choice == "accept" and chk.returncode == 0:
            if (hashlib.sha256(plan_p.read_bytes()).hexdigest() != proposed_hash
                    or _guards_snapshot_sha(c.target) != proposed_head):
                print("[PLAN] plan hoặc target đổi khi chờ owner — phải duyệt lại")
                continue
            recheck = sh(sys.executable, ROOT / "scripts" / "plan_check.py",
                         "--plan", plan_p, "--target", c.target)
            if recheck.returncode != 0:
                print("[PLAN] plan_check đổi trạng thái khi chờ owner — phải duyệt lại")
                continue
            approval_dir = c.session / "approvals"
            approval_dir.mkdir(exist_ok=True)
            (approval_dir / f"{plan_p.stem}.json").write_text(json.dumps({
                "plan_sha256": proposed_hash,
                "target_head": proposed_head,
                "accepted_at": now(),
            }, ensure_ascii=False, indent=1))
            return None
        if choice == "accept":
            print("[PLAN] cannot accept: plan_check is failing — edit the plan first")
        else:
            print("[PLAN] owner chose edit — update the plan and answer again")

    print("[PLAN] no approved plan after 3 attempts — stop (fail-closed)")
    c.log["state"] = "stopped_plan_not_approved"
    (c.session / "voyage.json").write_text(json.dumps(c.log, ensure_ascii=False, indent=1))
    return 2


def _stage_repair(c: Ctx):
    reg_probe = c.probe_cmds or (c.reg or {}).get("probe") or None
    baseline = c.session / "prove" / "findings.json"
    if not reg_probe or not baseline.is_file():
        print("[REPAIR] BLOCK: cần probe và PROVE hiện tại trước khi sửa candidate")
        return 2
    plans = sorted(c.session.glob("PLAN-*.md"))
    if not plans:
        print("[REPAIR] BLOCK: không có PLAN-*.md đã duyệt")
        return 2
    for plan_p in plans:
        plan_id = plan_p.stem
        approval_file = c.session / "approvals" / f"{plan_id}.json"
        try:
            approval = json.loads(approval_file.read_text())
        except (OSError, json.JSONDecodeError):
            approval = {}
        if (approval.get("plan_sha256") != hashlib.sha256(plan_p.read_bytes()).hexdigest()
                or approval.get("target_head") != _guards_snapshot_sha(c.target)):
            print(f"[REPAIR] BLOCK: {plan_p.name} chưa được duyệt hoặc đã đổi sau khi duyệt")
            return 2
        choice, note = c.d.ask("repair", f"Cho phép THI HÀNH {plan_p.name} trong worktree rời?",
                               ["accept", "reject"],
                               context={"plan": plan_p.name,
                                        "plan_sha256": approval["plan_sha256"],
                                        "target_head": approval["target_head"]})
        c.log["decisions"].append({"phase": "repair-run", "plan": plan_p.name,
                                   "choice": choice, "note": note})
        if choice != "accept":
            print(f"[REPAIR] owner từ chối {plan_p.name} — bỏ qua")
            continue
        if (hashlib.sha256(plan_p.read_bytes()).hexdigest() != approval["plan_sha256"]
                or _guards_snapshot_sha(c.target) != approval["target_head"]):
            print("[REPAIR] BLOCK: plan/HEAD đổi khi chờ owner thi hành")
            return 2
        tag = _guards_backup_tag(c.target, f"backup-prep-{plan_id}")
        before_sha = _guards_snapshot_sha(c.target)
        loop_state = c.session / "logs" / f"{plan_id}.loop.json"
        loop_state.unlink(missing_ok=True)
        loop = sh(sys.executable, ROOT / "scripts" / "rescue_loop.py",
                  "--target", c.target, "--plan", plan_p,
                  "--baseline", baseline, "--tools", c.scan_tools,
                  "--workdir", c.session / "worktrees",
                  "--logdir", c.session / "logs",
                  "--max-rounds", str(c.max_rounds),
                  "--executor-cmd", c.executor_cmd, "--reviewer-cmd", c.reviewer_cmd,
                  *(arg for cmd in reg_probe for arg in ("--probe", cmd)))
        try:
            state = json.loads(loop_state.read_text())
        except Exception:
            print(f"[REPAIR] BLOCK: không đọc được loop state: {(loop.stderr or loop.stdout)[:300]}")
            state = {"result": None}
        if loop.returncode != 0 or state.get("result") != "APPROVE":
            c.log["changes"].append({"ts": now(), "action": "repair-not-approved",
                                     "plan": plan_id, "state": state["result"],
                                     "revert_cmd": f"git branch -D rescue/{plan_id}"})
            _guards_track_change(c.session, c.log["changes"][-1])
            print(f"[REPAIR] {plan_id}: {state['result']} — KHÔNG merge; kiểm tra branch/state")
            return 2
        branch = f"rescue/{plan_id}"
        branch_sha = sh("git", "-C", c.target, "rev-parse", branch)
        if (branch_sha.returncode != 0 or branch_sha.stdout.strip() != state.get("candidate_sha")
                or _guards_snapshot_sha(c.target) != before_sha):
            print("[REPAIR] BLOCK: candidate/target HEAD đổi sau khi reviewer duyệt")
            return 2
        c3, note = c.d.ask("repair", f"Merge {plan_p.name} vào nhánh hiện tại?",
                           ["accept", "reject"],
                           context={"plan": plan_p.name,
                                    "plan_sha256": approval["plan_sha256"],
                                    "target_head": before_sha,
                                    "candidate_sha": state["candidate_sha"]})
        c.log["decisions"].append({"phase": "merge", "plan": plan_p.name,
                                   "choice": c3, "note": note})
        if c3 != "accept":
            print(f"[REPAIR] owner chưa đồng ý merge {plan_p.name} — giữ branch")
            continue
        if (_guards_snapshot_sha(c.target) != before_sha
                or hashlib.sha256(plan_p.read_bytes()).hexdigest() != approval["plan_sha256"]
                or sh("git", "-C", c.target, "rev-parse", branch).stdout.strip()
                != state["candidate_sha"]):
            print("[REPAIR] BLOCK: target/plan/candidate đổi trong khi chờ owner merge")
            return 2
        m = sh("git", "-C", c.target, "merge", "--no-ff", branch)
        if m.returncode != 0:
            sh("git", "-C", c.target, "merge", "--abort")
            print(f"[REPAIR] BLOCK: merge lỗi, đã abort: {(m.stderr or m.stdout)[:200]}")
            return 2
        after_sha = _guards_snapshot_sha(c.target)
        from scripts import guards
        after_probe = guards.run_probe(c.target, reg_probe)
        if not guards.probes_equal(state.get("probe_before", []), after_probe):
            # Auto-revert only when the merge commit is still HEAD and no tracked
            # file changed after it. Never reset away concurrent work.
            clean = sh("git", "-C", c.target, "diff", "--quiet", "HEAD", "--")
            if _guards_snapshot_sha(c.target) == after_sha and clean.returncode == 0:
                undo = sh("git", "-C", c.target, "revert", "--no-edit", "-m", "1", after_sha)
                action = "auto-revert" if undo.returncode == 0 else "rollback-failed"
            else:
                action = "rollback-needs-owner"
            entry = {"ts": now(), "action": action, "branch": branch,
                     "before_sha": before_sha, "after_sha": after_sha, "tag": tag,
                     "revert_cmd": f"git revert -m 1 {after_sha}",
                     "note": "probe sau merge lệch baseline; kiểm tra target và side effect ngoài Git"}
            c.log["changes"].append(entry)
            _guards_track_change(c.session, entry)
            print(f"[REPAIR] BLOCK: probe sau merge lệch; {action}")
            return 2
        entry = {"ts": now(), "action": "merge", "branch": f"rescue/{plan_id}",
                 "before_sha": before_sha, "after_sha": after_sha, "tag": tag,
                 "revert_cmd": f"git revert -m 1 {after_sha}",
                 "note": (m.stdout or m.stderr)[:200]}
        c.log["changes"].append(entry)
        _guards_track_change(c.session, entry)
        print(f"[REPAIR] merged {plan_id} ({before_sha[:8]} -> {after_sha[:8]}) "
              f"— revert: `{entry['revert_cmd']}`")
    return None


def _stage_lock(c: Ctx):
    choice, note = c.d.ask("lock", "Chạy LOCK rulesync cho target (ghi file rules)?" if (
        (c.target / "rulesync.jsonc").exists() or (c.target / ".rulesync").exists())
        else "Không thấy config rulesync — bỏ qua LOCK, đồng ý?",
        ["accept", "reject"], context={"note": "LOCK ghi file vào target"})
    c.log["decisions"].append({"phase": "lock", "choice": choice, "note": note})
    if choice == "accept" and ((c.target / "rulesync.jsonc").exists()
                               or (c.target / ".rulesync").exists()):
        g = sh(sys.executable, ROOT / "scripts" / "lock_rulesync.py",
               "--target", c.target, "--mode", "drift")
        print(f"[LOCK] drift exit={g.returncode}")
        if g.returncode != 0:
            return 2


# guards import muộn để giữ module gọn (tests mock qua subprocess không bị ảnh hưởng)
def _guards_run_probe(target, cmds):
    from scripts import guards
    return guards.run_probe(target, cmds)


def _guards_backup_tag(target, name):
    from scripts import guards
    return guards.backup_tag(target, name)


def _guards_snapshot_sha(target):
    from scripts import guards
    return guards.snapshot_sha(target)


def _guards_probes_equal(a, b):
    from scripts import guards
    return guards.probes_equal(a, b)


def _guards_track_change(session, entry):
    from scripts import guards
    return guards.track_change(session, entry)


STAGE_FUNCS = {"map": _stage_map, "prove": _stage_prove, "review": _stage_review,
               "plan": _stage_plan, "repair": _stage_repair, "lock": _stage_lock}


def main():
    a, stages, probe = parse_args(sys.argv[1:])
    reg = load_registry().get(a.name or "")
    path = Path(a.path) if a.path else (ROOT / reg["path"] if a.name and reg else None)
    if not path:
        print("[WHAT] cần --name (registry) hoặc --path")
        return 2
    target = path.resolve()
    if not (target / ".git").exists():
        print(f"[WHAT] {target} không phải git repo — voyage yêu cầu git (backup/revert)")
        return 2
    stages = stages or STAGES
    for s in stages:
        if s not in STAGES:
            print(f"[WHAT] stage '{s}' không hợp lệ ({STAGES})")
            return 2

    session = target / ".rescue" / "voyage"
    (session / "logs").mkdir(parents=True, exist_ok=True)
    (session / "dialogue").mkdir(parents=True, exist_ok=True)
    roles = load_config()
    c = Ctx(target=target, session=session, stages=stages, max_rounds=a.max_rounds,
            reg=reg or {}, probe_cmds=probe,
            scan_tools=a.tools or ",".join((reg or {}).get("tools") or []) or "all",
            executor_cmd=a.executor_cmd or build_cmd("write", roles),
            reviewer_cmd=a.reviewer_cmd or build_cmd("verify", roles),
            adviser_cmd=a.adviser_cmd or build_cmd("write", roles),
            review_cmd=a.review_cmd or build_cmd("audit", roles),
            review_cmd_custom=a.review_cmd is not None,
            roles=roles)
    from scripts.dialogue import Dialogue
    c.d = Dialogue(mode=a.owner or (reg or {}).get("owner", "interactive"),
                   directory=str(Path(a.answers) if a.answers else session / "dialogue"))
    c.log = {"target": str(target), "started": now(), "stages": stages,
             "owner": c.d.mode, "llm": describe(roles), "decisions": [], "changes": [],
             "state": "running"}
    (session / "voyage.json").write_text(json.dumps(c.log, ensure_ascii=False, indent=1))

    for s in STAGES:
        if s in stages:
            try:
                rc = STAGE_FUNCS[s](c)
            except Exception as exc:
                c.log["state"] = f"error_{s}"
                c.log["error"] = str(exc)[:300]
                c.log["finished"] = now()
                (session / "voyage.json").write_text(json.dumps(c.log, ensure_ascii=False, indent=1))
                print(f"[{s.upper()}] BLOCK: exception: {exc}")
                return 2
            if rc:
                if c.log.get("state") == "running":
                    c.log["state"] = f"blocked_{s}"
                c.log["finished"] = now()
                (session / "voyage.json").write_text(json.dumps(c.log, ensure_ascii=False, indent=1))
                return rc

    c.log["state"] = "done"
    (session / "voyage.json").write_text(json.dumps(c.log, ensure_ascii=False, indent=1))
    print(f"\n[DONE] voyage phiên tại {session} — REVERT: {session / 'REVERT.md'}")
    return 0


def _review_templates(rdir, session, target):
    """Template team-readable khi agent không chạy được — vẫn có số liệu thật từ evidence."""
    (rdir / "README.md").write_text(_review_template_body(rdir, session, target), encoding="utf-8")
    (rdir / "REVIEW.md").write_text(_review_template_body(rdir, session, target), encoding="utf-8")
    (rdir / "PROPOSALS.md").write_text(_proposals_template(session), encoding="utf-8")


def _review_template_body(rdir, session, target):
    counts = {}
    findings = None
    fp = session / "prove" / "findings.json"
    if fp.exists():
        try:
            data = json.loads(fp.read_text())
            findings = data.get("findings", [])
            counts = dict(data.get("meta", {}).get("counts", {}))
        except Exception:
            findings = None
    top = {}
    if findings:
        from collections import Counter
        top = dict(Counter(f["file"] for f in findings).most_common(8))
    (rdir / "EVIDENCE" / "README.md").write_text(
        f"# EVIDENCE\n- findings.json: {session / 'prove' / 'findings.json'}\n"
        f"- sarif: {session / 'prove' / 'findings.sarif'}\n"
        f"- archgraph: {session / 'review' / 'archgraph.json' if (session / 'review' / 'archgraph.json').exists() else '(chạy prove để có)'}\n",
        encoding="utf-8")
    return "\n".join([
        f"# REVIEW — {target.name}", "",
        "> Template tự sinh (agent review chưa chạy được). Điền tiếp.", "",
        f"- Evidence: findings {sum(counts.values())} ({counts})",
        "- Đọc máy đầy đủ: EVIDENCE/", "",
        "## Điều tốt", "- (điền: import-graph sạch / gate compliance / test-rich...)", "",
        "## Điều cần sửa (top — xem PROPOSALS.md)",
        f"- File nóng nhất: {', '.join(list(top)[:5])}", "",
        "## Mức ưu tiên", "- P1 ngay · P2 tuần này · P3 backlog", ""])


def _proposals_template(session):
    findings = None
    fp = session / "prove" / "findings.json"
    if fp.exists():
        try:
            findings = json.loads(fp.read_text()).get("findings", [])
        except Exception:
            findings = None
    rows = []
    if findings:
        seen = set()
        for f in findings:
            key = (f["tool"], f["file"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                f"| {f['tool']} | {f['file']} | {f['severity']} | |  | (evidence máy) |")
            if len(rows) >= 12:
                break
    return "\n".join(["# PROPOSALS — đọc là hiểu, hiểu là fix", "",
                      ("> Format: ID | Vấn đề (lời thường) | Bằng chứng · file:line | Sửa sao | "
                       "Rủi ro | Verify | Ưu tiên. TL;DR (EN) mỗi thẻ 1 dòng."), "",
                      "| ID | Vấn đề | Bằng chứng | Sửa sao | Rủi ro | Verify | Ưu tiên |",
                      "|---|---|---|---|---|---|---|"] + rows)


def _plan_template(session):
    return """# PLAN-001: (điền outcome duy nhất — adviser chưa chạy được hoặc owner tự soạn)
Plan SHA: (git rev-parse HEAD của target)
Scope: [path/to/existing.file, +path/to/new.file]
Out-of-scope: [tests/, dependencies, public API]
Baseline evidence: []
Steps:
  1. — Verification: `true`
STOP conditions: test fail | diff > 5 file
Rollback: `git reset --hard backup-prep-PLAN-001`
Done criteria: `true`
"""


if __name__ == "__main__":
    sys.exit(main())
