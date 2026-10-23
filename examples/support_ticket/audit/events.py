"""A synthetic audit stub; storage and retention are outside this example."""


def redact_event(email: str) -> dict:
    return {"kind": "ticket", "email_present": bool(email)}
