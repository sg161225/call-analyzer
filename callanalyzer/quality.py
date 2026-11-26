"""Soft skills and fatal errors.

Soft skills are rated Good / Partial / Weak on every call. A call is FATAL when the executive makes
any blunder in FATAL_ERRORS, even once. Edit these lists to change the rules.
"""
from __future__ import annotations

SOFT_SKILLS = {
    "empathy": ("Empathy", "Acknowledges the customer's problem and feelings, apologises where the company is at "
                           "fault, never dismisses a complaint"),
    "humility": ("Humility & courtesy", "Polite and respectful (Sir/Ma'am), patient, never arrogant, "
                                        "argumentative or blaming the customer"),
    "fluency": ("Fluency & confidence", "Answers clearly and confidently, no fumbling, no contradictions, "
                                        "knows basic product answers"),
}

FATAL_ERRORS = [
    "Rude, arrogant or argumentative with the customer",
    "Disrespectful or abusive language, or mocked the customer",
    "No empathy at a critical moment (dismissed a complaint, an angry customer or a loss)",
    "Fumbled badly (couldn't answer basic product questions, contradicted self, confused information)",
    "Repeatedly interrupted or talked over the customer",
    "False information or a promise they can't make (e.g. refund, free items)",
]
OTHER_FATAL = "Other blunder"

SHORT_FATAL = {
    FATAL_ERRORS[0]: "Rude / arrogant",
    FATAL_ERRORS[1]: "Disrespectful language",
    FATAL_ERRORS[2]: "No empathy",
    FATAL_ERRORS[3]: "Fumbled badly",
    FATAL_ERRORS[4]: "Talked over customer",
    FATAL_ERRORS[5]: "False info / promise",
    OTHER_FATAL: "Other blunder",
}

# Keyword fallback when the AI words a fatal category differently (whole words, in order).
FATAL_KEYWORDS = [
    (("abusive", "disrespect", "mock", "insult", "swear"), FATAL_ERRORS[1]),
    (("rude", "arrogant", "argument", "argumentative", "shout", "blame"), FATAL_ERRORS[0]),
    (("empathy", "dismiss", "ignored", "insensitive"), FATAL_ERRORS[2]),
    (("fumble", "fumbled", "fumbling", "contradict", "confused", "didn't know", "wrong answer"), FATAL_ERRORS[3]),
    (("interrupt", "interrupted", "talked over", "cut off"), FATAL_ERRORS[4]),
    (("false", "misleading", "promise", "promised", "refund", "wrong information"), FATAL_ERRORS[5]),
]


def quality_prompt() -> str:
    skills = "\n".join(f"- {name}: {desc}" for name, desc in SOFT_SKILLS.values())
    fatal = "\n".join(f"- {f}" for f in FATAL_ERRORS)
    return (f"Soft skills (rate each Good / Partial / Weak, with short evidence):\n{skills}\n\n"
            "FATAL errors: list every one the executive committed, even once, copying the category name exactly, "
            "with a short quote or description from the call as evidence. Only flag clear blunders that the "
            "transcript actually shows; do not flag ordinary small hesitations or ASR noise. Leave the list "
            f"empty if there were none.\n{fatal}")


def match_fatal(category: str) -> str:
    import difflib
    import re
    if category in FATAL_ERRORS:
        return category
    low = (category or "").lower().replace("'", "")
    for words, target in FATAL_KEYWORDS:
        if any(re.search(r"\b" + re.escape(w.replace("'", "")), low) for w in words):  # word starts
            return target
    close = difflib.get_close_matches(low, [f.lower() for f in FATAL_ERRORS], n=1, cutoff=0.6)
    return next((f for f in FATAL_ERRORS if close and f.lower() == close[0]), OTHER_FATAL)
