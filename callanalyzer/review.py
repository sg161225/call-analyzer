"""Claude-powered call review on the six-parameter scorecard, plus cross-call insights."""
from __future__ import annotations

import json
from typing import List, Literal

import anthropic
from pydantic import BaseModel, Field

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


class CallReview(BaseModel):
    customer_name: str = Field(description="Customer / business name if mentioned, else empty")
    call_purpose: str = Field(description="e.g. Retention of dropped customer, Renewal, Upsell, Complaint, New sale")
    outcome: Literal["Converted / Retained", "Follow-up scheduled", "Undecided", "Not interested / Lost", "Issue resolved", "Unclear"]
    outcome_note: str = Field(description="One sentence on how the call ended and why")
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

Review the call against this scorecard:
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


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def review_call(transcript: str, meta: dict, settings: dict) -> dict:
    company = settings["company"]
    context = f"{company['name']}: {company['product']}\n{company['context'].strip()}"
    user = (f"Call metadata: executive={meta.get('executive') or 'unknown'}, date={meta.get('call_date') or 'unknown'}, "
            f"campaign={meta.get('campaign') or 'unknown'}\n\n<transcript>\n{transcript}\n</transcript>")
    resp = _client().beta.messages.parse(
        model=settings["analysis"]["model"],
        max_tokens=16000,
        system=SYSTEM.format(context=context),
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
pitch version, ratings and notes). Write a concise, practical report for the sales manager in
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


def insights_report(rows: list[dict], settings: dict, focus: str = "") -> str:
    company = settings["company"]
    payload = json.dumps(rows, ensure_ascii=False)
    user = f"Company: {company['name']}: {company['product']}\n"
    if focus:
        user += f"Manager's focus for this report: {focus}\n"
    user += f"\n{len(rows)} call reviews:\n<reviews>\n{payload}\n</reviews>"
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
