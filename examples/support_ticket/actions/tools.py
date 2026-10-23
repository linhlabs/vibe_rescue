"""The name is a control candidate, not proof of authorization enforcement."""


def allowed_tool(intent: str) -> str:
    return "reply" if intent == "question" else "triage"
