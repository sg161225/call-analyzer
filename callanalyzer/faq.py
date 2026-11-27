"""Product FAQs per call type (config/faqs/<call type>.csv: No, Question, Answer).

For each call, only the FAQs that match what was discussed are sent to the AI (all of them would be
too big for the free tier). The AI then checks the executive's answers against them.
"""
from __future__ import annotations

import csv
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from .config import ROOT

FAQ_DIR = ROOT / "config" / "faqs"
NOT_IN_FAQ = "Not in FAQ"
ACCURACY = ["Correct", "Partly correct", "Wrong", "Not answered"]

_STOP = set("""a an the is are am was were be been do does did can could will would shall should may might i you we
they he she it my your our their me us them this that these those of in on at to for from with by as or and if not no
yes so but how what why when which who whom where there here all any some only also than then too very just about into
please sir madam ji hai hain ka ki ke ko se me mein kya kaise kab nahi haan aur bhi toh to tha thi the ho kar
mobile app application busy use using get want need like same also""".split())


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower().replace("-", " "))
    return [w[:-1] if len(w) > 4 and w.endswith("s") else w for w in words if w not in _STOP and len(w) > 2]


@lru_cache(maxsize=8)
def _load(call_type: str, mtime: float) -> tuple:
    path = FAQ_DIR / f"{call_type}.csv"
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = [{"no": int(r.get("No") or i + 1), "q": (r.get("Question") or "").strip(),
                 "a": (r.get("Answer") or "").strip()} for i, r in enumerate(csv.DictReader(f))]
    return tuple(r for r in rows if r["q"])


def faqs_for(call_type: str | None) -> list[dict]:
    path = FAQ_DIR / f"{call_type}.csv"
    if not call_type or not path.exists():
        return []
    return list(_load(call_type, path.stat().st_mtime))   # reloads when the CSV is edited


def has_faqs(call_type: str | None) -> bool:
    return bool(faqs_for(call_type))


def relevant_faqs(call_type: str | None, transcript: str, k: int = 12) -> list[dict]:
    """Up to k FAQs that match the call. Each line of the call first gets its best-matching FAQ
    (so every question asked is covered), then the rest is filled by the best match overall."""
    faqs = faqs_for(call_type)
    if not faqs:
        return []
    docs = [Counter(_tokens(f["q"]) * 3 + _tokens(f["a"])) for f in faqs]   # question words count more
    df = Counter(w for d in docs for w in d)
    n = len(docs)
    norms = [math.sqrt(sum(d.values()) or 1) for d in docs]

    def scores(text: str) -> list[float]:
        c = Counter(_tokens(text))
        return [sum(math.log(1 + n / df[w]) * min(c[w], 3) * (1 + math.log(d[w])) for w in d if w in c) / nm
                for d, nm in zip(docs, norms)]

    picked: dict[int, float] = {}
    for line in re.split(r"[\n?]+", transcript):
        if not _tokens(line):
            continue
        sc = scores(line)
        best = max(range(n), key=sc.__getitem__)
        if sc[best] >= 1.0:
            picked[best] = max(picked.get(best, 0), sc[best])
    order = sorted(picked, key=lambda i: -picked[i])[:k]
    overall = scores(transcript)
    for i in sorted(range(n), key=lambda i: -overall[i]):
        if len(order) >= k or overall[i] <= 0:
            break
        if i not in order:
            order.append(i)
    return [faqs[i] for i in sorted(order, key=lambda i: faqs[i]["no"])]


def faq_prompt(faqs: list[dict]) -> str:
    return "\n".join(f"FAQ {f['no']}. Q: {f['q']}\n   A: {f['a']}" for f in faqs)


def match_faq(call_type: str | None, text: str) -> dict | None:
    """Find the FAQ the AI referred to: by 'FAQ <no>', exact/close question, or shared words."""
    import difflib
    faqs = faqs_for(call_type)
    if not faqs or not text or text.strip().lower() == NOT_IN_FAQ.lower():
        return None
    m = re.search(r"\b(?:faq\s*#?\s*)?(\d{1,3})\b", text.lower())
    if m and text.lower().strip().startswith(("faq", m.group(1))):
        no = int(m.group(1))
        hit = next((f for f in faqs if f["no"] == no), None)
        if hit:
            return hit
    by_q = {f["q"].lower(): f for f in faqs}
    close = difflib.get_close_matches(text.lower().strip(), list(by_q), n=1, cutoff=0.75)
    if close:
        return by_q[close[0]]
    w = set(_tokens(text))
    best, score = None, 0.0
    for f in faqs:
        fw = set(_tokens(f["q"]))
        s = len(w & fw) / max(1, min(len(w), len(fw)))
        if s > score:
            best, score = f, s
    if score >= 0.6:
        return best
    # Same scoring used to pick FAQs for a call (handles rewording such as 'computer is off').
    hits = relevant_faqs(call_type, text, k=1)
    return hits[0] if hits else None
