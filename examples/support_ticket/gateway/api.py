"""Synthetic API boundary for the public handoff example."""

from audit.events import redact_event
from domain.policy import classify_intent
from orchestrator.agent import build_plan


def submit(message: str, email: str) -> dict:
    intent = classify_intent(message)
    plan = build_plan(intent)
    event = redact_event(email)
    return respond({"plan": plan, "audit": event})


def respond(payload: dict) -> dict:
    return {"ticket": "demo", "result": payload}
