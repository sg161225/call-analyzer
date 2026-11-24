"""Claude-powered call review on the six-parameter scorecard, plus cross-call insights."""
from __future__ import annotations

import json
from typing import List, Literal

from pydantic import BaseModel, Field

from .calltypes import CALL_TYPES, CHECKLISTS, LOSS_REASONS, OUTCOMES, RISK_LEVELS, checklist_prompt

Rating = Literal["Good", "Partial", "Weak", "Not applicable"]
RATING_SCORE = {"Good": 3, "Partial": 2, "Weak": 1}

# Column order used everywhere in the UI and exports.
PARAMETERS = {
    "business_probing": "Business probing",
    "need_generation": "Need generation",
    "pitch": "Pitch (offer / features)",
    "customer_queries": "Customer queries",
    "objection_handling": "Problem solving (objection handling)",
    "acpt_improvement": "ACPT improvement required",
}


class Assessment(BaseModel):
    rating: Rating = Field(description="Good / Partial / Weak, or 'Not applicable' if the call gave no opportunity")
    observed: str = Field(description="What the executive actually did on this parameter, 1-3 short sentences, with specifics from the call")
    improvement: str = Field(description="The specific thing the executive should do differently next time, ideally with an example line to say")


class Pitch(Assessment):
    features_mentioned: List[str] = Field(description="Product features the executive pitched")
    offers_made: List[str] = Field(description="Commercial offers made (discount, extension, free demo/training...). Empty if none")


class Queries(BaseModel):
    rating: Rating = Field(description="How well the customer's queries were answered overall")
    queries: List[str] = Field(description="Each distinct question/complaint the customer raised, one per item")
    unresolved: List[str] = Field(description="Queries that were left unanswered or unresolved")


class ChecklistItem(BaseModel):
    item: str = Field(description="Checklist item, copied exactly from the list for this call type")
    done: Literal["Yes", "No", "Not applicable"]
    evidence: str = Field(description="Very short evidence from the call (or why it was missed)")


class CallReview(BaseModel):
    call_type: Literal[tuple(CALL_TYPES)] = Field(description="Which of the five call types this call is")
    customer_name: str = Field(description="Customer / business name if mentioned, else empty")
    call_purpose: str = Field(description="Short purpose, e.g. 'Renewal of yearly licence', 'Reactivating dropped customer'")
    checklist: List[ChecklistItem] = Field(description="Every checklist item for this call type, in order")
    outcome: Literal[tuple(OUTCOMES)] = Field(description="How the call ended. 'Payment received' only if the customer confirms the payment is done")
    outcome_note: str = Field(description="One sentence on how the call ended and why")
    next_step: str = Field(description="Agreed next step, e.g. 'Customer will pay via payment link', 'Demo on Friday 4pm'. Empty if none")
    next_step_date: str = Field(description="Date of the next step as YYYY-MM-DD, worked out from the call date if said relatively ('tomorrow', 'Monday'). Empty if none")
    deal_value_inr: int = Field(description="Price/amount in rupees discussed for this deal (final quoted or agreed amount). 0 if no amount was mentioned")
    deal_value_note: str = Field(description="What the amount is for, e.g. '1-year renewal, 2 users'. Empty if none")
    loss_reason: Literal[tuple(LOSS_REASONS)] = Field(description="Main reason the customer did not buy / is unhappy; 'None' if not applicable")
    risk_level: Literal[tuple(RISK_LEVELS)] = Field(description="Risk of losing this customer (unhappy, not using, mentions switching or not renewing)")
    risk_reason: str = Field(description="Why, in one line. Empty if risk is None")
    customer_sentiment_start: Literal["Positive", "Neutral", "Negative"]
    customer_sentiment_end: Literal["Positive", "Neutral", "Negative"]
    business_probing: Assessment
    need_generation: Assessment
    pitch: Pitch
    customer_queries: Queries
    objection_handling: Assessment
    acpt_improvement: List[str] = Field(description="Top 3-6 prioritised improvements for the executive, most important first, each actionable")
    overall_score: int = Field(description="Overall call quality from 1 (very poor) to 10 (excellent)")
    one_line_summary: str = Field(description="One-line summary of the call for a manager")


SYSTEM = """You are a senior call-quality coach for an Indian software company's tele-calling team.
Calls are usually in Hindi, English or Hinglish and the transcript comes from automatic speech
recognition, so expect misheard words and no speaker labels: infer who is the executive (the
company's caller) and who is the customer from context. Write all output in clear, simple English.

Company context:
{context}

First decide the call type (one of: New Sales, Mobile App, Renewal, Upsell, CLM). If the call
metadata gives a call type, use it. Then fill in the checklist for THAT type, copying each item
exactly, marking Yes / No / Not applicable:
{checklists}

Outcome rules: 'Payment received' only when the customer confirms payment is made during the call;
a promise to pay is 'Payment promised'. Capture any rupee amount quoted or agreed as deal_value_inr.

Then review the call against this scorecard:
- Business probing: did the executive understand the customer's business (type, size, volume,
  current process/software, users, decision maker) before pitching?
- Need generation: did they uncover or build a need/pain and link it to the product?
- Pitch (offer / features): which features and offers were pitched, and were they relevant to
  this customer's situation? A pitch with no concrete offer or next step is at best Partial.
- Customer queries: list every question/complaint the customer raised; were they answered?
- Problem solving (objection handling): did they acknowledge, empathise, resolve or escalate,
  and commit to a timeline?
- ACPT improvement required: the prioritised coaching points for the executive.

Rate each parameter Good / Partial / Weak strictly and consistently, so that ratings are
comparable across executives and dates. Base every judgement on evidence in the transcript;
do not invent facts. Keep 'observed' and 'improvement' short and specific."""


def _client():
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("The paid Anthropic option needs: pip install -r requirements-paid.txt") from e
    return anthropic.Anthropic()


def _provider(settings: dict) -> str:
    return settings["analysis"].get("provider", "groq")


def _groq_chat(system: str, user: str, settings: dict, json_mode: bool) -> str:
    import groq

    client = groq.Groq()
    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    model = settings["analysis"].get("groq_model", "openai/gpt-oss-120b")
    if model.startswith("openai/gpt-oss"):
        kwargs["reasoning_effort"] = settings["analysis"].get("effort", "medium")
    try:
        resp = client.chat.completions.create(
            model=model, temperature=0.2, max_completion_tokens=8000,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], **kwargs)
    except groq.RateLimitError as e:
        raise RuntimeError("Groq free-tier limit reached for now. Wait a minute and retry; if it keeps happening, "
                           "the daily limit is used up (it resets the next day), or set analysis.groq_model to "
                           "'openai/gpt-oss-20b' in config/settings.toml.") from e
    except groq.APIStatusError as e:
        if e.status_code == 413:
            raise RuntimeError("This call is too long for the Groq free tier in one request. "
                               "Try a smaller model with a bigger limit (llama-3.3-70b-versatile).") from e
        raise
    return resp.choices[0].message.content or ""


def _review_groq(system: str, user: str, settings: dict) -> dict:
    """JSON mode + schema in the prompt, validated with Pydantic; one corrective retry."""
    schema = json.dumps(CallReview.model_json_schema())
    system = (system + "\n\nReply with ONE JSON object only, no prose, matching this JSON Schema exactly "
              "(all fields required; enums must use the exact listed values):\n" + schema)
    raw = _groq_chat(system, user, settings, json_mode=True)
    try:
        return CallReview.model_validate_json(raw).model_dump()
    except Exception as err:  # pydantic ValidationError or bad JSON
        fix = (user + "\n\nYour previous reply did not match the schema. Error:\n" + str(err)[:1500]
               + "\nReturn the corrected JSON object only.")
        raw = _groq_chat(system, fix, settings, json_mode=True)
        return CallReview.model_validate_json(raw).model_dump()


def normalize(rv: dict, forced_type: str | None = None) -> dict:
    """Make AI output consistent: chosen call type wins, checklist matches the official items
    in order, date and amount are valid."""
    import difflib
    from datetime import date

    if forced_type in CALL_TYPES:
        rv["call_type"] = forced_type
    official = CHECKLISTS.get(rv.get("call_type"), [])
    given = {(c.get("item") or "").strip().lower(): c for c in rv.get("checklist") or []}
    fixed = []
    for item in official:
        key = item.lower()
        match = given.get(key)
        if match is None:
            close = difflib.get_close_matches(key, list(given), n=1, cutoff=0.8)
            match = given.get(close[0]) if close else None
        fixed.append({"item": item, "done": (match or {}).get("done", "No"),
                      "evidence": (match or {}).get("evidence", "Not covered in the call")})
    rv["checklist"] = fixed
    d = (rv.get("next_step_date") or "").strip()
    try:
        rv["next_step_date"] = date.fromisoformat(d).isoformat() if d else ""
    except ValueError:
        rv["next_step_date"] = ""
    try:
        rv["deal_value_inr"] = max(0, int(rv.get("deal_value_inr") or 0))
    except (TypeError, ValueError):
        rv["deal_value_inr"] = 0
    return rv


def review_call(transcript: str, meta: dict, settings: dict) -> dict:
    return normalize(_review_call(transcript, meta, settings), meta.get("call_type"))


def _review_call(transcript: str, meta: dict, settings: dict) -> dict:
    company = settings["company"]
    context = f"{company['name']}: {company['product']}\n{company['context'].strip()}"
    hint = meta.get("call_type") if meta.get("call_type") in CALL_TYPES else "not given (decide from the call)"
    user = (f"Call metadata: executive={meta.get('executive') or 'unknown'}, date={meta.get('call_date') or 'unknown'}, "
            f"campaign={meta.get('campaign') or 'unknown'}, call type={hint}\n\n<transcript>\n{transcript}\n</transcript>")
    system = SYSTEM.format(context=context, checklists=checklist_prompt())
    if _provider(settings) == "groq":
        return _review_groq(system, user, settings)
    resp = _client().beta.messages.parse(
        model=settings["analysis"]["model"],
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=CallReview,
        output_config={"effort": settings["analysis"].get("effort", "medium")},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("The AI declined to review this call.")
    if resp.stop_reason == "max_tokens" or resp.parsed_output is None:
        raise RuntimeError("The AI response was cut off; try again.")
    return resp.parsed_output.model_dump()


INSIGHTS_SYSTEM = """You are the head of quality for an Indian software company's tele-calling team.
You get structured reviews of many calls (one JSON object per call, with executive, date, campaign,
pitch version, call type, checklist, outcome, deal value, ratings and notes). Call types are New Sales,
Mobile App, Renewal, Upsell and CLM (customer life cycle management). Success means payment received
for sales types, and an issue resolved / healthy customer for CLM. Compare like with like: always say
which call type a finding applies to. Write a concise, practical report for the sales manager in
Markdown with these sections:

1. **Headline**: 3 bullets with the most important findings.
2. **What is working**: behaviours/pitch lines linked to good outcomes, with call examples (executive + date).
3. **What is not working**: recurring weaknesses, lost-call reasons, common unresolved queries.
4. **Executive comparison**: a table (executive, calls, avg score, strongest parameter, weakest parameter,
   key coaching point), then 1-2 lines per executive.
5. **Pitch changes over time**: for executives with calls on different dates or pitch versions, what
   changed in their approach and whether results improved. Say clearly when there is too little data.
6. **Process improvements**: concrete changes to the calling process, script, pre-call preparation,
   offers, escalation, and follow-up.
7. **Objection playbook**: the top recurring customer objections with a recommended response for each.

Only use evidence present in the data. Mention sample size, and do not overstate patterns seen in 1-2 calls."""


GROQ_MAX_CALLS = 20  # keeps one report inside the free tier's per-request token limit


def compact(row: dict) -> dict:
    """Shorter version of a review for the free tier."""
    cut = lambda t, n=160: (t or "")[:n]
    out = {k: row.get(k) for k in ("executive", "date", "campaign", "pitch_version", "call_type", "call_purpose",
                                   "outcome", "loss_reason", "deal_value_inr", "risk_level", "overall_score",
                                   "customer_sentiment_start", "customer_sentiment_end")}
    out["checklist_missed"] = [c["item"][:60] for c in row.get("checklist") or [] if c.get("done") == "No"][:5]
    for k in ("business_probing", "need_generation", "objection_handling"):
        a = row.get(k) or {}
        out[k] = {"rating": a.get("rating"), "observed": cut(a.get("observed"))}
    p = row.get("pitch") or {}
    out["pitch"] = {"rating": p.get("rating"), "features": p.get("features_mentioned", [])[:5], "offers": p.get("offers_made", [])}
    q = row.get("customer_queries") or {}
    out["queries"] = [cut(x, 90) for x in q.get("queries", [])[:5]]
    out["unresolved"] = [cut(x, 90) for x in q.get("unresolved", [])[:3]]
    out["improvements"] = [cut(x, 120) for x in row.get("acpt_improvement", [])[:3]]
    return out


def insights_report(rows: list[dict], settings: dict, focus: str = "") -> str:
    company = settings["company"]
    groq_mode = _provider(settings) == "groq"
    if groq_mode:
        rows = [compact(r) for r in rows[:GROQ_MAX_CALLS]]
    payload = json.dumps(rows, ensure_ascii=False)
    user = f"Company: {company['name']}: {company['product']}\n"
    if focus:
        user += f"Manager's focus for this report: {focus}\n"
    user += f"\n{len(rows)} call reviews:\n<reviews>\n{payload}\n</reviews>"
    if groq_mode:
        return _groq_chat(INSIGHTS_SYSTEM, user, settings, json_mode=False)
    with _client().beta.messages.stream(
        model=settings["analysis"]["model"],
        max_tokens=32000,
        system=INSIGHTS_SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": "high"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("The AI declined to write this report.")
    return "".join(b.text for b in msg.content if b.type == "text")
