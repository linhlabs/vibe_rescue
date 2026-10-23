"""A placeholder classifier, not a production intent model."""


def classify_intent(message: str) -> str:
    return "question" if "?" in message else "support"
