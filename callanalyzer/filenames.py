"""Read the executive name, customer mobile number and campaign from a recording's file name.

Handles names such as:
    Sachin9873747581DroppedOct.wav          -> Sachin, 9873747581, DroppedOct
    Sachin_+91 98737 47581_Dropped Oct.mp3  -> Sachin, 9873747581, Dropped Oct
    9873747581_Sachin_Renewal.m4a           -> Sachin, 9873747581, Renewal
    Call recording Sachin_919873747581_20261123_103015.m4a -> Sachin, 9873747581
    Rahul Sharma - 09811122233 - Upsell.wav -> Rahul Sharma, 9811122233, Upsell
"""
from __future__ import annotations

import re
from pathlib import Path

# Indian mobile: optional +91 / 91 / 0 prefix, then 10 digits starting 6-9 (spaces/dashes allowed).
_MOBILE = re.compile(r"(?<!\d)(?:\+?91[\s-]?|0)?([6-9]\d{4}[\s-]?\d{5})(?!\d)")
# Words recorders add that are not a person's name.
_NOISE = {
    "call", "calls", "recording", "recordings", "record", "rec", "audio", "voice", "phone",
    "incoming", "outgoing", "missed", "in", "out", "callrecording", "whatsapp", "sim", "sim1",
    "sim2", "mobile", "mob", "number", "no", "cust", "customer", "agent", "exec", "executive",
}


def _split_camel(text: str) -> str:
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)


def _words(text: str) -> list[str]:
    """Letter-only words, with digits/dates/times and recorder noise removed."""
    text = re.sub(r"\d+", " ", text)
    return [w for w in re.split(r"[^A-Za-z]+", text) if w and w.lower() not in _NOISE]


def parse_file_name(file_name: str) -> dict:
    stem = Path(str(file_name)).stem
    mobile, before, after = "", stem, ""
    m = _MOBILE.search(stem)
    if m:
        mobile = re.sub(r"\D", "", m.group(1))
        before, after = stem[:m.start()], stem[m.end():]

    before_words = _words(before)
    after_words = _words(after)
    if not m and not re.search(r"[\s_.\-]", stem):
        # Single run like "PriyaRenewalNov": first CamelCase word is the name.
        words = _words(_split_camel(stem))
        return {"executive": " ".join(words[:1]).title(), "mobile": "", "campaign": " ".join(words[1:])}
    if before_words:
        # "Name <number> Campaign": keep the name's own spacing, split CamelCase only for campaign.
        executive_words = before_words
        campaign_words = after_words
    else:
        # "<number> Name Campaign" or no number: first word is the name.
        parts = re.split(r"[\s_.\-]+", _split_camel(after if m else stem).strip(" _-."))
        parts = [w for p in parts for w in _words(p)]
        executive_words, campaign_words = parts[:1], parts[1:]

    return {
        "executive": " ".join(executive_words).title(),
        "mobile": mobile,
        "campaign": " ".join(campaign_words),
    }
