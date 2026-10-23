"""An intentionally small planning step; no model is called."""

from actions.tools import allowed_tool


def build_plan(intent: str) -> dict:
    return {"intent": intent, "suggestion": allowed_tool(intent)}
