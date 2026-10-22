"""Small-model gate graders must reject plausible but unsafe answers."""
import json
import re

from scripts import model_rescue_eval as model_eval
from scripts.model_rescue_eval import fixture_repo, grade_map, grade_plan, grade_review


def test_map_gate_requires_exact_path_evidence_and_unknown():
    good = ('{"call_path":["api.post_charge","service.charge"],'
            '"bug_id":"NEGATIVE_AMOUNT_ACCEPTED",'
            '"evidence":["service.py:2","service.py:3"],'
            '"unknown":["upstream validation unverified"]}')
    assert grade_map(good)["pass"]
    assert not grade_map(good.replace("service.py:3", "invented.py:7"))["pass"]
    assert not grade_map(good.replace('"unknown":["upstream validation unverified"]',
                                      '"unknown":[]'))["pass"]
    assert not grade_map("not JSON")["pass"]


def test_eval_prompts_do_not_disclose_grader_answer():
    map_prompt, review_prompt = model_eval.scenarios("a" * 40)[0][1], model_eval.scenarios("a" * 40)[2][1]
    assert 'exactly ["api.post_charge","service.charge"]' not in map_prompt
    assert "NEGATIVE_AMOUNT_ACCEPTED" not in map_prompt
    assert "candidate now rejects" not in review_prompt
    assert "regression" not in review_prompt.lower()
    assert "api.py:4" in map_prompt and "api.py:2" not in map_prompt


def test_plan_gate_uses_real_plan_check(tmp_path):
    target = tmp_path / "target"
    sha = fixture_repo(target)
    plan = ("# PLAN-001: reject nonpositive amount\n"
            f"Plan SHA: {sha}\n"
            "Scope: [service.py]\n"
            "Out-of-scope: [api.py, tests/]\n"
            "Baseline evidence: [F-NEG]\n"
            "Steps:\n1. Guard amount <= 0 in service.py.\n"
            "Verification: python3 -m pytest -q\n"
            "STOP conditions: test fail\n"
            "Rollback: git revert HEAD\n"
            "Done criteria: python3 -m pytest -q returns 0\n")
    assert grade_plan(plan, target, sha)["pass"]
    assert not grade_plan(plan.replace("Scope: [service.py]", "Scope: [api.py]"),
                          target, sha)["pass"]
    assert not grade_plan(plan.replace(sha, "0" * 40), target, sha)["pass"]


def test_reviewer_must_reject_exact_balance_regression():
    assert grade_review("Result: REVISE\nReason: service.py:2 rejects exact balance now; regression.")["pass"]
    assert grade_review("Result: BLOCK\nReason: service.py:2 now rejects amount == balance.")["pass"]
    assert not grade_review("Result: APPROVE\nReason: tests pass.")["pass"]


def test_bounded_feedback_keeps_original_sha_and_finding(monkeypatch):
    prompts = []

    def fake_ask(_url, _model, _key, prompt, _max_tokens, _timeout):
        prompts.append(prompt)
        if prompt.startswith("A request can contain"):
            content = json.dumps({"call_path": ["api.post_charge", "service.charge"],
                                  "bug_id": "NEGATIVE_AMOUNT_ACCEPTED",
                                  "evidence": ["service.py:2", "service.py:3"],
                                  "unknown": ["upstream validation unverified"]})
        elif prompt.startswith("Write ONLY a PLAN"):
            content = "bad plan"
        elif prompt.startswith("Your PLAN failed"):
            sha = re.search(r"[0-9a-f]{40}", prompt).group()
            content = (f"Plan SHA: {sha}\nScope: [service.py]\n"
                       "Out-of-scope: [api.py]\nBaseline evidence: [F-NEG]\n"
                       "Steps:\n1. Guard amount <= 0.\nVerification: python3 -m pytest -q\n"
                       "STOP conditions: tests fail\nRollback: git checkout -- service.py\n"
                       "Done criteria: python3 -m pytest -q passes\n")
        else:
            content = "Result: REVISE\nReason: service.py:2 exact balance regression."
        return {"content": content, "latency_seconds": 0.1, "usage": {"total_tokens": 1},
                "model": "stub", "finish_reason": "stop"}

    monkeypatch.setattr(model_eval, "ask", fake_ask)
    report = model_eval.evaluate("http://example.test/v1", "stub", "key", plan_retries=1)
    assert report["pass"]
    assert len(report["results"][1]["attempts"]) == 2
    assert "Original task:" in prompts[2] and "F-NEG" in prompts[2]


def test_cli_requires_explicit_model_url_and_http_opt_in(monkeypatch):
    monkeypatch.setenv("VIBE_EVAL_API_KEY", "fixture-key")
    monkeypatch.delenv("VIBE_EVAL_BASE_URL", raising=False)
    monkeypatch.delenv("VIBE_EVAL_MODEL", raising=False)
    assert model_eval.main([]) == 2
    assert model_eval.main(["--base-url", "http://example.test/v1",
                            "--model", "stub"]) == 2
