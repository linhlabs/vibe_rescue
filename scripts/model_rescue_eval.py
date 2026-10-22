#!/usr/bin/env python3
# Direct execution needs the repository root on sys.path.
"""Smoke-evaluate an OpenAI-compatible model on synthetic rescue contracts.

No target repository or secret is sent. The key is read from one env variable and
never written to the report. This is a capability probe, not a production safety
certification or a substitute for a full candidate/merge evaluation.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.plan_check import check_plan, parse_plan, scope_files

SOURCE = ('api.py:1 from service import charge\n'
          'api.py:3 def post_charge(req, balance):\n'
          'api.py:4     return charge(req["amount"], balance)\n'
          'service.py:1 def charge(amount, balance):\n'
          'service.py:2     if amount > balance: return {"error":"insufficient"}\n'
          'service.py:3     return {"charged":amount,"balance":balance-amount}')
EVIDENCE = {"api.py:1", "api.py:3", "api.py:4", "service.py:1", "service.py:2", "service.py:3"}


def fixture_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    (path / "api.py").write_text(
        'from service import charge\n\ndef post_charge(req, balance):\n'
        '    return charge(req["amount"], balance)\n', encoding="utf-8")
    (path / "service.py").write_text(
        'def charge(amount, balance):\n'
        '    if amount > balance: return {"error":"insufficient"}\n'
        '    return {"charged":amount,"balance":balance-amount}\n', encoding="utf-8")
    commands = [["git", "init", "-q"], ["git", "add", "."],
                ["git", "-c", "user.name=Eval", "-c", "user.email=eval@example.test",
                 "commit", "-qm", "fixture"]]
    for command in commands:
        subprocess.run(command, cwd=path, check=True, capture_output=True)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, check=True,
                          capture_output=True, text=True).stdout.strip()


def scenarios(sha):
    return [
        ("map", "A request can contain a negative amount. From the source below, "
         "trace the call path and identify the resulting bug. Return ONLY a JSON "
         "object, no markdown. Required keys/types: call_path: array of qualified "
         "function names in order; bug_id: short descriptive string; evidence: "
         "array of actual file:line anchors; unknown: nonempty array of runtime "
         "facts not proven by the shown source. Do not invent edges.\n" + SOURCE),
        ("plan", "Write ONLY a PLAN Markdown document accepted by plan_check.py. "
         "Use these exact headers: Plan SHA:, Scope:, Out-of-scope:, Baseline evidence:, "
         "Steps:, STOP conditions:, Rollback:, Done criteria:. Number at least one "
         "step and include Verification: under it. One outcome: reject amount <= 0. "
         "Pin Plan SHA exactly " + sha + ". Scope ONLY [service.py]. "
         "Baseline evidence [F-NEG] points to service.py:2-3. "
         "Do not change api.py or tests. Verification command: python3 -m pytest -q. "
         "Use a concrete rollback command. No invented file or finding."),
        ("review", ("You are an independent reviewer. Return ONLY two lines: "
         "Result: APPROVE|REVISE|BLOCK and Reason: ... . Source before: "
         "service.py:2 if amount > balance: return insufficient. Candidate diff: "
         "- if amount > balance: return insufficient\n"
         "+ if amount >= balance: return insufficient\n"
         "A weak test suite still passes. Decide whether this diff is safe; "
         "cite the relevant source line in Reason.")),
    ]


def grade_map(content):
    try:
        data = json.loads(content)
    except ValueError:
        return {"pass": False, "problems": ["not valid JSON"]}
    if not isinstance(data, dict):
        return {"pass": False, "problems": ["not an object"]}
    problems = []
    if data.get("call_path") != ["api.post_charge", "service.charge"]:
        problems.append("call_path mismatch or wrong type")
    bug = data.get("bug_id")
    if not isinstance(bug, str) or not re.search(r"(?i)(negative|nonpositive).*amount|amount.*(negative|nonpositive)", bug):
        problems.append("bug_id must identify negative amount behavior")
    evidence = data.get("evidence")
    if not isinstance(evidence, list) or not {"service.py:2", "service.py:3"}.issubset(evidence):
        problems.append("missing source anchors")
    elif not set(evidence).issubset(EVIDENCE):
        problems.append("invented source anchor")
    if not isinstance(data.get("unknown"), list) or not data["unknown"]:
        problems.append("unknown runtime edges not marked")
    return {"pass": not problems, "problems": problems}


def grade_plan(content, fixture, sha):
    sections = parse_plan(content)
    problems, _files, missing = check_plan(sections, fixture)
    if missing:
        problems.append("scope file missing")
    if scope_files(sections) != ["service.py"]:
        problems.append("scope must be exactly service.py")
    if sha not in content:
        problems.append("plan SHA missing")
    if "F-NEG" not in content:
        problems.append("finding ID missing")
    if re.search(r"(?i)api\.py|tests/", "\n".join(sections.get("Scope:", []))):
        problems.append("extra file in scope")
    return {"pass": not problems, "problems": problems}


def grade_review(content):
    verdict = re.search(r"^Result:\s*(APPROVE|REVISE|BLOCK)\s*$", content, re.MULTILINE)
    problems = []
    if not verdict or verdict.group(1) not in {"REVISE", "BLOCK"}:
        problems.append("unsafe or missing verdict")
    if "service.py:2" not in content:
        problems.append("missing source anchor")
    if not re.search(r"(?i)exact.balance|equal|regression|bằng|bằng nhau|amount\s*==\s*balance", content):
        problems.append("no exact-balance regression reason")
    return {"pass": not problems, "problems": problems}


def ask(base_url, model, key, prompt, max_tokens, timeout):
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps({"model": model, "temperature": 0, "max_tokens": max_tokens,
                         "messages": [{"role": "system", "content": "Follow the output schema exactly. Be concise."},
                                      {"role": "user", "content": prompt}]}).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.load(response)
    choice = data["choices"][0]
    return {"content": choice["message"].get("content") or "",
            "model": data.get("model"), "usage": data.get("usage"),
            "finish_reason": choice.get("finish_reason"),
            "latency_seconds": round(time.monotonic() - started, 2)}


def evaluate(base_url, model, key, max_tokens=1800, timeout=90, plan_retries=1):
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp) / "target"
        sha = fixture_repo(fixture)
        results = []
        for name, prompt in scenarios(sha):
            try:
                response = ask(base_url, model, key, prompt, max_tokens, timeout)
                content = response.pop("content")
                if name == "map":
                    grade = grade_map(content)
                elif name == "plan":
                    grade = grade_plan(content, fixture, sha)
                else:
                    grade = grade_review(content)
                first_pass = grade["pass"]
                attempts = [{"pass": grade["pass"], "problems": grade["problems"],
                             "usage": response.get("usage"), "latency_seconds": response["latency_seconds"]}]
                if name == "plan":
                    for _ in range(plan_retries):
                        if grade["pass"]:
                            break
                        correction = ("Your PLAN failed the deterministic plan_check gate. "
                                      "Repair only these errors and return the COMPLETE corrected PLAN "
                                      "Markdown, no explanation. Preserve the exact SHA, Scope and "
                                      "finding ID from the original task.\nOriginal task:\n" + prompt
                                      + "\nChecker errors:\n" + "\n".join(grade["problems"][:8])
                                      + "\nPrevious PLAN:\n" + content)
                        response = ask(base_url, model, key, correction, max_tokens, timeout)
                        content = response.pop("content")
                        grade = grade_plan(content, fixture, sha)
                        attempts.append({"pass": grade["pass"], "problems": grade["problems"],
                                         "usage": response.get("usage"),
                                         "latency_seconds": response["latency_seconds"]})
                results.append({"scenario": name, **response, **grade, "first_pass": first_pass,
                                "attempts": attempts, "output": content})
            except (OSError, ValueError, KeyError, IndexError, urllib.error.URLError) as exc:
                results.append({"scenario": name, "pass": False,
                                "problems": [f"request/response error: {type(exc).__name__}"]})
        return {"base_url": base_url, "requested_model": model,
                "fixture": "synthetic-charge-v1", "max_tokens": max_tokens,
                "plan_retries": plan_retries,
                "pass": all(row["pass"] for row in results), "results": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Synthetic small-model rescue gate")
    parser.add_argument("--base-url", default=os.environ.get("VIBE_EVAL_BASE_URL"))
    parser.add_argument("--model", default=os.environ.get("VIBE_EVAL_MODEL"))
    parser.add_argument("--api-key-env", default="VIBE_EVAL_API_KEY")
    parser.add_argument("--max-tokens", type=int, default=1800)
    parser.add_argument("--plan-retries", type=int, choices=range(3), default=1)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--allow-http", action="store_true",
                        help="allow HTTP only for a trusted private gateway")
    parser.add_argument("--out", type=Path, default=ROOT / "reports/model-eval/last.json")
    args = parser.parse_args(argv)
    if not args.base_url or not args.model:
        print("[EVAL] set --base-url and --model (or VIBE_EVAL_BASE_URL/VIBE_EVAL_MODEL)")
        return 2
    parsed = urllib.parse.urlparse(args.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        print("[EVAL] invalid base URL")
        return 2
    if parsed.scheme == "http" and not args.allow_http:
        print("[EVAL] HTTP gateway requires explicit --allow-http")
        return 2
    key = os.environ.get(args.api_key_env, "")
    if not key:
        print(f"[EVAL] missing key env: {args.api_key_env}")
        return 2
    report = evaluate(args.base_url, args.model, key, args.max_tokens,
                      args.timeout, args.plan_retries)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for row in report["results"]:
        print(f"[EVAL] {row['scenario']}: {'PASS' if row['pass'] else 'FAIL'} "
              f"{', '.join(row['problems']) or 'contract met'}; "
              f"attempts={len(row.get('attempts', []))} "
              f"{row.get('latency_seconds', '?')}s final")
    print(f"[EVAL] report: {args.out}")
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
