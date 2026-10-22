#!/usr/bin/env python3
# Chính sách noqa: verdict file lỗi/không có = trả None cho state machine xử lý, không crash.
# ruff: noqa: BLE001
"""
rescue_loop.py — REPAIR phase tự động: executor bị khóa trong worktree rời,
re-check scope, re-run gates, reviewer (codex) verdict — loop tới APPROVE.

State machine (mỗi round):
  plan_check (máy, exit 2 = plan hỏng -> dừng)
  -> git worktree add (disposable)
  -> executor cmd (mặc định: claude -p ... với agents/executor.md) + env
     PLAN / TARGET_WT / VERDICT_FILE / REVISE_REASON (nếu vòng trước REVISE)
  -> plan_check --worktree (diff ⊆ Scope; vi phạm = REVISE)
  -> [nếu có --baseline] fanout(ruff) + merge + delta_gate (finding mới = REVISE)
  -> reviewer cmd (mặc định: codex exec ... với agents/reviewer.md)
  -> parse verdict file -> APPROVE | REVISE(loop) | BLOCK(dừng)
  -> dọn worktree (finally)

Executor/reviewer cmd chèn được qua --executor-cmd/--reviewer-cmd (test dùng stub).

Usage:
  python3 scripts/rescue_loop.py --target <repo> --plan <plan.md> \
      [--baseline findings.json] [--logdir logs_audit] [--max-rounds 3]
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # cho phép import scripts.* khi chạy trực tiếp

from scripts.exec_util import sh_expand as sh


def parse_verdict(path: Path):
    """logs_audit/PLAN-<id>.md -> APPROVE | REVISE | BLOCK | None (unit-testable)."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    m = re.search(r"^Result:\s*(APPROVE|REVISE|BLOCK)", text, re.MULTILINE)
    return m.group(1) if m else None


def _git_head(path):
    r = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                       capture_output=True, text=True, check=False)
    return r.stdout.strip() if r.returncode == 0 else None


def _tracked_clean(path):
    return subprocess.run(["git", "-C", str(path), "diff", "--quiet", "HEAD", "--"],
                          capture_output=True, check=False).returncode == 0


def _coverage_problems(baseline_meta, current_meta, expected):
    problems = []
    if baseline_meta.get("tools") != expected or current_meta.get("tools") != expected:
        problems.append("scanner list khác baseline/current")
    before = baseline_meta.get("tool_status", {})
    after = current_meta.get("tool_status", {})
    for tool in expected:
        if before.get(tool) not in {"ok", "skipped"}:
            problems.append(f"baseline thiếu scanner {tool}")
        if after.get(tool) not in {"ok", "skipped"}:
            problems.append(f"candidate thiếu scanner {tool}")
        if before.get(tool) == "ok" and after.get(tool) != "ok":
            problems.append(f"mất coverage của scanner {tool}")
    return problems


def main():
    import argparse
    ap = argparse.ArgumentParser(description="REPAIR: executor trong worktree rời + reviewer 4 mắt.")
    ap.add_argument("--target", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--baseline", help="findings.json — gate finding mới = REVISE")
    ap.add_argument("--tools", default="all", help="cùng danh sách scanner đã dùng cho baseline")
    ap.add_argument("--probe", action="append", default=[],
                    help="lệnh probe ổn định phải xanh trên base và candidate; lặp lại được")
    ap.add_argument("--workdir", default=str(ROOT.parent / "worktrees"))
    ap.add_argument("--logdir", default=str(ROOT / "logs_audit"))
    ap.add_argument("--max-rounds", type=int, default=3)
    ap.add_argument("--executor-cmd", help="override LLM vai write (mặc định: config.toml)")
    ap.add_argument("--reviewer-cmd", help="override LLM vai verify")
    a = ap.parse_args()
    target = Path(a.target)
    plan = Path(a.plan)
    baseline = Path(a.baseline) if a.baseline else None
    workdir = Path(a.workdir)
    logdir = Path(a.logdir)
    max_rounds = a.max_rounds
    executor_cmd = a.executor_cmd
    reviewer_cmd = a.reviewer_cmd

    from scripts.llm_config import build_cmd as _bc
    from scripts.llm_config import load_config as _lc
    _roles = _lc()
    executor_cmd = executor_cmd or _bc("write", _roles)
    reviewer_cmd = reviewer_cmd or _bc("verify", _roles)

    target, plan = target.resolve(), plan.resolve()
    logdir.mkdir(parents=True, exist_ok=True)
    plan_id = re.sub(r"\W+", "-", plan.stem)
    wt = (workdir / plan_id).resolve()
    verdict_file = logdir / f"{plan_id}.md"
    state = {"plan": str(plan), "worktree": str(wt), "rounds": [], "result": None}

    if not baseline or not baseline.is_file() or not a.probe:
        state["result"] = "BLOCK"
        state["rounds"].append({"round": 0, "step": "preflight", "result": "BLOCK",
                                "detail": "cần --baseline findings.json và ít nhất một --probe"})
        (logdir / f"{plan_id}.loop.json").write_text(json.dumps(state, ensure_ascii=False, indent=1))
        return 2
    base_head = _git_head(target)
    if not base_head or not _tracked_clean(target):
        state["result"] = "BLOCK"
        state["rounds"].append({"round": 0, "step": "target_clean", "result": "BLOCK",
                                "detail": "target có thay đổi tracked; candidate không thể chứng minh từ HEAD"})
        (logdir / f"{plan_id}.loop.json").write_text(json.dumps(state, ensure_ascii=False, indent=1))
        return 2
    from scripts.fanout import ALL
    expected = ALL if a.tools == "all" else [t.strip() for t in a.tools.split(",") if t.strip()]
    try:
        base_meta = json.loads(baseline.read_text()).get("meta", {})
    except (OSError, ValueError):
        base_meta = {}
    if (base_meta.get("sha") != base_head or
            _coverage_problems(base_meta, base_meta, expected)):
        state["result"] = "BLOCK"
        state["rounds"].append({"round": 0, "step": "baseline_coverage", "result": "BLOCK",
                                "detail": "baseline phải quét đúng HEAD và scanner list/coverage"})
        (logdir / f"{plan_id}.loop.json").write_text(json.dumps(state, ensure_ascii=False, indent=1))
        return 2
    from scripts.guards import probes_equal, run_probe
    probe_before = run_probe(target, a.probe)
    state["probe_before"] = [{k: p[k] for k in ("cmd", "rc", "out_hash")}
                             for p in probe_before]
    if any(p["rc"] != 0 for p in probe_before):
        state["result"] = "BLOCK"
        state["rounds"].append({"round": 0, "step": "probe_before", "result": "BLOCK",
                                "detail": "probe baseline không xanh"})
        (logdir / f"{plan_id}.loop.json").write_text(json.dumps(state, ensure_ascii=False, indent=1))
        return 2

    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "plan_check.py"),
                        "--plan", str(plan), "--target", str(target)],
                       capture_output=True, text=True, check=False)
    if r.returncode != 0:
        state["result"] = "BLOCK"
        state["rounds"].append({"round": 0, "step": "plan_check", "result": "FAIL",
                                "detail": (r.stdout or r.stderr)[:400]})
        (logdir / f"{plan_id}.loop.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=1))
        print(json.dumps(state, ensure_ascii=False, indent=1))
        return 2

    wt_add = sh(f'git -C "{target}" worktree add "{wt}" -b "rescue/{plan_id}"')
    if wt_add.returncode != 0:
        state["rounds"].append({"round": 0, "step": "worktree_add", "result": "FAIL",
                                "detail": (wt_add.stdout or wt_add.stderr)[:400]})
        (logdir / f"{plan_id}.loop.json").write_text(json.dumps(state, ensure_ascii=False, indent=1))
        print(json.dumps(state, ensure_ascii=False, indent=1))
        return 2
    reason = ""
    try:
        for round_no in range(1, max_rounds + 1):
            env = {**os.environ, "PLAN": str(plan), "TARGET_WT": str(wt),
                   "VERDICT_FILE": str(verdict_file), "PLAN_ID": plan_id,
                   "REVISE_REASON": reason,
                   "PROMPT_AGENT": (ROOT / "agents" / "executor.md").read_text(encoding="utf-8"),
                   "VIBE_AGENT_TASK": "execute"}

            # 1) executor
            try:
                ex = sh(executor_cmd, cwd=wt, env=env)
            except FileNotFoundError as e:
                reason = f"executor command unavailable: {e}"
                state["rounds"].append({"round": round_no, "step": "executor",
                                        "result": "REVISE", "detail": reason})
                verdict_file.write_text(f"# Verdict {plan_id}\nResult: REVISE\n"
                                        f"REVISE reason: {reason}\n", encoding="utf-8")
                continue
            if _git_head(target) != base_head or not _tracked_clean(target):
                state["rounds"].append({"round": round_no, "step": "target_integrity",
                                        "result": "BLOCK",
                                        "detail": "executor đã đổi target gốc; giữ nguyên để owner kiểm tra"})
                state["result"] = "BLOCK"
                break
            if ex.returncode != 0:
                reason = f"executor exit={ex.returncode}: {(ex.stderr or ex.stdout)[:200]}"
                state["rounds"].append({"round": round_no, "step": "executor",
                                        "result": "REVISE", "detail": reason})
                continue

            # 2) scope: diff ⊆ plan Scope
            scope_r = subprocess.run([sys.executable, str(ROOT / "scripts" / "plan_check.py"),
                                      "--plan", str(plan), "--worktree", str(wt)],
                                     capture_output=True, text=True, check=False)
            if scope_r.returncode != 0:
                reason = (scope_r.stdout or scope_r.stderr)[:400]
                state["rounds"].append({"round": round_no, "step": "scope_check",
                                        "result": "REVISE", "detail": reason})
                verdict_file.write_text(f"# Verdict {plan_id}\nResult: REVISE\n"
                                        f"REVISE reason: diff ngoài scope — {reason}\n",
                                        encoding="utf-8")
                continue

            # 2.5) COMMIT executor changes lên branch rescue/<plan> — nếu không:
            #      branch cứng-trống, merge "Already up to date", revert vô nghĩa
            # (tin nhắn phải quote — sh() split theo shlex KHÔNG qua shell)
            add = sh("git add -A", cwd=wt)
            if add.returncode != 0:
                state["rounds"].append({"round": round_no, "step": "git_add",
                                        "result": "BLOCK", "detail": (add.stderr or add.stdout)[:200]})
                state["result"] = "BLOCK"
                break
            cc = sh(f"git commit -q -m \"rescue({plan_id}): thuc thi plan\"", cwd=wt,
                    env={**os.environ, "GIT_AUTHOR_NAME": "rescue_loop", "GIT_AUTHOR_EMAIL": "rescue@vibe",
                         "GIT_COMMITTER_NAME": "rescue_loop", "GIT_COMMITTER_EMAIL": "rescue@vibe"})
            if cc.returncode != 0:
                reason = (f"executor không tạo ra thay đổi nào hoặc commit lỗi: "
                          f"{(cc.stderr or cc.stdout)[:200]}")
                state["rounds"].append({"round": round_no, "step": "commit_change",
                                        "result": "REVISE", "detail": reason})
                verdict_file.write_text(f"# Verdict {plan_id}\nResult: REVISE\n"
                                        f"REVISE reason: {reason}\n", encoding="utf-8")
                continue

            probe_after = run_probe(wt, a.probe)
            if not probes_equal(probe_before, probe_after):
                reason = "probe candidate khác baseline; reviewer không được chạy"
                state["rounds"].append({"round": round_no, "step": "candidate_probe",
                                        "result": "REVISE", "detail": reason})
                continue

            # 3) gates: finding mới so baseline = REVISE
            if baseline:
                gdir = logdir / plan_id / f"r{round_no}"
                gdir.mkdir(parents=True, exist_ok=True)
                scan = subprocess.run([sys.executable, str(ROOT / "scripts" / "fanout.py"),
                                       "--target", str(wt), "--tools", a.tools,
                                       "--outdir", str(gdir)],
                                      capture_output=True, text=True, check=False)
                merge = subprocess.run([sys.executable, str(ROOT / "scripts" / "merge_findings.py"),
                                        "--rundir", str(gdir)],
                                       capture_output=True, text=True, check=False)
                if scan.returncode != 0 or merge.returncode != 0:
                    reason = f"scanner lỗi: fanout={scan.returncode}, merge={merge.returncode}"
                    state["rounds"].append({"round": round_no, "step": "scanner",
                                            "result": "REVISE", "detail": reason})
                    continue
                try:
                    current_meta = json.loads((gdir / "findings.json").read_text()).get("meta", {})
                except (OSError, ValueError):
                    current_meta = {}
                coverage = _coverage_problems(base_meta, current_meta, expected)
                if coverage:
                    state["rounds"].append({"round": round_no, "step": "scanner_coverage",
                                            "result": "REVISE", "detail": "; ".join(coverage)[:400]})
                    continue
                g = subprocess.run([sys.executable, str(ROOT / "scripts" / "delta_gate.py"),
                                    "--baseline", str(baseline),
                                    "--current", str(gdir / "findings.json")],
                                   capture_output=True, text=True, check=False)
                if g.returncode != 0:
                    reason = (g.stdout or g.stderr)[:400]
                    state["rounds"].append({"round": round_no, "step": "delta_gate",
                                            "result": "REVISE", "detail": reason})
                    verdict_file.write_text(f"# Verdict {plan_id}\nResult: REVISE\n"
                                            f"REVISE reason: finding mới — {reason}\n",
                                            encoding="utf-8")
                    continue

            # 4) reviewer (codex) — writes verdict into VERDICT_FILE
            env["PROMPT_AGENT"] = (ROOT / "agents" / "reviewer.md").read_text(encoding="utf-8")
            env["VIBE_AGENT_TASK"] = "verdict"
            # receipts of what the harness already ran, for reviewers that cannot run commands
            env["VIBE_RECEIPTS"] = (
                "Already verified by the harness before you were called: (1) the diff only touches files "
                "listed in the plan Scope; (2) probe command(s) [" + "; ".join(a.probe) + "] gave the same "
                "exit code and output on the original and on this candidate"
                + ("; (3) scanners re-run on the candidate found no finding that is not in the baseline."
                   if baseline else "."))
            before_review_head = _git_head(wt)
            before_review_status = subprocess.run(
                ["git", "-C", str(wt), "status", "--porcelain"],
                capture_output=True, text=True, check=False)
            if before_review_status.returncode != 0 or before_review_status.stdout.strip():
                state["rounds"].append({"round": round_no, "step": "reviewer_preflight",
                                        "result": "REVISE", "detail": "candidate không sạch sau probe/scanner"})
                continue
            verdict_file.unlink(missing_ok=True)  # verdict cũ không được tái dùng
            try:
                ex = sh(reviewer_cmd, cwd=wt, env=env)
            except FileNotFoundError as e:
                state["rounds"].append({"round": round_no, "step": "reviewer",
                                        "result": "UNKNOWN", "detail": f"reviewer unavailable: {e}"})
                continue
            after_review_status = subprocess.run(
                ["git", "-C", str(wt), "status", "--porcelain"],
                capture_output=True, text=True, check=False)
            if (_git_head(wt) != before_review_head or after_review_status.returncode != 0
                    or after_review_status.stdout.strip() or _git_head(target) != base_head
                    or not _tracked_clean(target)):
                state["rounds"].append({"round": round_no, "step": "reviewer_integrity",
                                        "result": "BLOCK", "detail": "reviewer/target đã bị thay đổi"})
                state["result"] = "BLOCK"
                break
            verdict = parse_verdict(verdict_file) if ex.returncode == 0 else None
            if verdict == "APPROVE":
                final_scope = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "plan_check.py"),
                     "--plan", str(plan), "--worktree", str(wt)],
                    capture_output=True, text=True, check=False)
                if final_scope.returncode != 0:
                    verdict = "REVISE"
                    reason = f"scope sau reviewer lỗi: {(final_scope.stdout or final_scope.stderr)[:200]}"
            state["rounds"].append({"round": round_no, "step": "reviewer",
                                    "result": verdict or "UNKNOWN",
                                    "detail": (ex.stdout or ex.stderr)[:200]})
            if verdict == "APPROVE":
                state["result"] = "APPROVE"
                state["candidate_sha"] = subprocess.run(
                    ["git", "-C", str(wt), "rev-parse", "HEAD"], capture_output=True,
                    text=True, check=False).stdout.strip()
                break
            if verdict == "BLOCK":
                state["result"] = "BLOCK"
                break
            reason = "reviewer REVISE — sửa theo verdict rồi chạy lại"
        else:
            state["result"] = "REVISE_LIMIT"
    finally:
        sh(f'git -C "{target}" worktree remove --force "{wt}"')
    if state["result"] != "APPROVE":
        sh(f'git -C "{target}" branch -D "rescue/{plan_id}"')

    (logdir / f"{plan_id}.loop.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=1))
    print(json.dumps(state, ensure_ascii=False, indent=1))
    return 0 if state["result"] == "APPROVE" else 2


if __name__ == "__main__":
    sys.exit(main())
