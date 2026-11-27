"""Claude-powered call review on the six-parameter scorecard, plus cross-call insights."""
from __future__ import annotations

import json
from typing import List, Literal

from pydantic import BaseModel, Field

from .calltypes import CALL_TYPES, CHECKLISTS, LOSS_REASONS, OUTCOMES, RISK_LEVELS, canonical_type, checklist_prompt
from .faq import ACCURACY, NOT_IN_FAQ, faq_prompt, faqs_for, match_faq, relevant_faqs
from .quality import match_fatal, quality_prompt
from .playbook import OTHER, PLAYBOOKS, objection_names, playbook_prompt, responses_for

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


class ObjectionHandled(BaseModel):
    objection: str = Field(description="Objection name copied exactly from the playbook, or 'Other' if it is not in the playbook")
    customer_said: str = Field(description="What the customer said, short, in English")
    executive_response: str = Field(description="How the executive responded, short, in English. 'No response' if ignored")
    playbook_followed: Literal["Yes", "Partly", "No"] = Field(
        description="Yes = used a recommended response (or an equally strong one); Partly = weak or incomplete; No = ignored or wrong")
    recommended_response: str = Field(description="The best playbook response for this moment, in the playbook's Hinglish, adapted to this customer")


class SkillRating(BaseModel):
    rating: Literal["Good", "Partial", "Weak"]
    evidence: str = Field(description="Short evidence from the call (quote or description)")


class SoftSkills(BaseModel):
    empathy: SkillRating
    humility: SkillRating = Field(description="Humility & courtesy")
    fluency: SkillRating = Field(description="Fluency & confidence (no fumbling)")


class FatalError(BaseModel):
    category: str = Field(description="Fatal error category, copied exactly from the list")
    evidence: str = Field(description="Short quote or description of what the executive said or did")
    time_sec: int = Field(default=0, description="When it happened, in seconds from the start (from the [line | mm:ss] stamps). 0 if unknown")


class Moment(BaseModel):
    time_sec: int = Field(description="Seconds from the start of the call, from the [line | mm:ss] stamps")
    kind: Literal["Checklist done", "Objection", "Missed", "Fatal", "Outcome", "Positive", "Other"]
    text: str = Field(description="Very short description, e.g. 'Objection: will pay later', 'Recovery mobile captured'")


class MoodSpan(BaseModel):
    start_sec: int
    end_sec: int
    mood: Literal["Positive", "Neutral", "Negative"]


class FaqAnswer(BaseModel):
    customer_question: str = Field(description="The product question the customer asked, short, in English")
    faq_no: int = Field(default=0, description="Number of the matching FAQ, 0 if none of the given FAQs covers it")
    executive_answer: str = Field(description="What the executive answered, short. 'No answer' if none")
    accuracy: Literal[tuple(ACCURACY)] = Field(
        description="Correct = matches the FAQ; Partly correct = incomplete or vague; Wrong = contradicts the FAQ; "
                    "Not answered = no real answer")


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
    faq_answers: List[FaqAnswer] = Field(default_factory=list, description="Each product question the customer asked, "
                                         "checked against the company's FAQ answers. Empty if no FAQs were given")
    objections: List[ObjectionHandled] = Field(
        description="Every objection the customer raised, checked against the playbook. Empty list if none, or if no playbook applies")
    soft_skills: SoftSkills
    moments: List[Moment] = Field(default_factory=list, description="5-12 key moments of the call in time order: checklist points done or missed, "
                                              "objections, fatal errors, the outcome")
    mood_timeline: List[MoodSpan] = Field(default_factory=list, description="The customer's mood through the call as 1-4 consecutive time spans")
    executive_lines: List[int] = Field(default_factory=list, description="Line numbers (from [line | mm:ss]) spoken by the executive; all other lines are the customer")
    fatal_errors: List[FatalError] = Field(description="Every fatal error (blunder) the executive committed. Empty list if none")
    acpt_improvement: List[str] = Field(description="Top 3-6 prioritised improvements for the executive, most important first, each actionable")
    overall_score: int = Field(description="Overall call quality from 1 (very poor) to 10 (excellent)")
    one_line_summary: str = Field(description="One-line summary of the call for a manager")


SYSTEM = """You are a senior call-quality coach for an Indian software company's tele-calling team.
Calls are usually in Hindi, English or Hinglish and the transcript comes from automatic speech
recognition, so expect misheard words and no speaker labels: infer who is the executive (the
company's caller) and who is the customer from context. Write all output in clear, simple English.

Company context:
{context}

First decide the call type (one of: {types}). 'CLM Onboarding' is a welcome / setup
call to a customer who has just bought a licence; 'CLM Existing' is any other service call to an existing
customer (check-in, complaint follow-up, reactivating a dropped customer). If the call metadata gives a
call type, use it. Then fill in the checklist for THAT type, copying each item exactly, marking
Yes / No / Not applicable:
{checklists}

Outcome rules: 'Payment received' only when the customer confirms payment is made during the call;
a promise to pay is 'Payment promised'. Capture any rupee amount quoted or agreed as deal_value_inr.

The transcript is split into numbered, time-stamped lines: [line | mm:ss] text. Use these numbers and times for
moments, the customer's mood timeline, fatal error times and which lines the executive spoke.

Then review the call against this scorecard:
- Business probing: did the executive understand the customer's business (type, size, volume,
  current process/software, users, decision maker) before pitching?
- Need generation: did they uncover or build a need/pain and link it to the product?
- Pitch (offer / features): which features and offers were pitched, and were they relevant to
  this customer's situation? A pitch with no concrete offer or next step is at best Partial.
- Customer queries: list every question/complaint the customer raised; were they answered?
- Problem solving (objection handling): did they acknowledge, empathise, resolve or escalate,
  and commit to a timeline? For call types with a playbook, rate this mainly on how well the
  executive used the playbook responses below.

Objections: {playbook}

Product questions: {faq}
- ACPT improvement required: the prioritised coaching points for the executive.

{quality}

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


# Free Groq models that work for reviews, in order of preference (used when available on the account).
PREFERRED_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile",
                    "meta-llama/llama-4-scout-17b-16e-instruct", "moonshotai/kimi-k2-instruct",
                    "meta-llama/llama-4-maverick-17b-128e-instruct", "qwen/qwen3-32b", "llama-3.1-8b-instant"]
_NOT_CHAT = ("whisper", "guard", "tts", "playai", "orpheus", "distil", "compound", "safeguard", "allam")
_AVAILABLE: dict = {"at": 0.0, "ids": None}
MAX_MODELS = 5


def _available_models(client) -> list[str] | None:
    """Chat models this Groq account can use right now (cached for an hour); None if unknown."""
    import time
    if _AVAILABLE["ids"] is not None and time.time() - _AVAILABLE["at"] < 3600:
        return _AVAILABLE["ids"]
    try:
        ids = [m.id for m in client.models.list().data if not any(x in m.id.lower() for x in _NOT_CHAT)
               and getattr(m, "active", True) is not False]
    except Exception:
        return None
    _AVAILABLE.update(at=time.time(), ids=ids)
    return ids


def _groq_models(settings: dict, client=None) -> list[str]:
    a = settings["analysis"]
    chain = [a.get("groq_model", "openai/gpt-oss-120b"), *a.get("groq_fallback_models", []), *PREFERRED_MODELS]
    chain = list(dict.fromkeys(m for m in chain if m))
    avail = _available_models(client) if client is not None else None
    if avail:
        chain = [m for m in chain if m in avail] + sorted(m for m in avail if m not in chain)
    return chain[:MAX_MODELS]


def _err_text(e) -> str:
    try:
        body = e.body if isinstance(e.body, dict) else {}
        msg = (body.get("error") or {}).get("message") or str(e)
    except Exception:
        msg = str(e)
    import re
    msg = re.sub(r"\s*in organization \S+ service tier \S+", "", " ".join(str(msg).split()))
    msg = re.sub(r"\s*(Need more tokens\?|Visit https?://\S+).*$", "", msg)
    return msg[:260]


def _groq_chat(system: str, user: str, settings: dict, json_mode: bool, lite: tuple[str, str] | None = None,
               on_wait=None, max_out: int = 8000, what: str = "review this call") -> str:
    """Call Groq. Per model: try the full request; if it's too big, try the lighter one (if given); if a
    per-minute limit is hit, wait as long as Groq asks (up to ~1 minute) and try again. Then move on to
    the next available model. The error lists Groq's own reason for every model tried."""
    import time

    import groq

    client = groq.Groq()
    problems = []
    for model in _groq_models(settings, client):
        attempts = [("full", system, user, max_out)] + ([("lighter", lite[0], lite[1], min(max_out, 4500))] if lite else [])
        i, waited = 0, False
        while i < len(attempts):
            label, sys_msg, user_msg, max_out = attempts[i]
            kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
            if model.startswith("openai/gpt-oss"):
                kwargs["reasoning_effort"] = "low" if label == "lighter" else settings["analysis"].get("effort", "medium")
            try:
                resp = client.chat.completions.create(
                    model=model, temperature=0.2, max_completion_tokens=max_out,
                    messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}], **kwargs)
                return resp.choices[0].message.content or ""
            except groq.RateLimitError as e:
                try:
                    wait = float(e.response.headers.get("retry-after") or 0)
                except (TypeError, ValueError, AttributeError):
                    wait = 0
                if not waited and 0 < wait <= 65:
                    waited = True
                    if on_wait:
                        on_wait(model, wait)
                    time.sleep(wait + 1)
                    continue
                problems.append(f"{model}: limit reached ({_err_text(e)})")
                break
            except groq.APIStatusError as e:
                code = e.status_code
                if code == 413 or (code == 400 and "reduce the length" in _err_text(e).lower()):
                    if i + 1 < len(attempts):
                        i += 1
                        continue
                    problems.append(f"{model}: too long ({_err_text(e)})")
                    break
                if code in (400, 403, 404):
                    problems.append(f"{model}: {_err_text(e)}")
                    break
                raise
    hint = (" You can retry it later from the failed-calls list (🔁 Retry)." if what == "review this call"
            else " Try again in a minute, or with fewer calls selected.")
    raise RuntimeError(f"Groq couldn't {what} on the free tier: " + " | ".join(problems) + "." + hint
                       + " Free-tier limits reset every minute and every day.")


def _compact_schema() -> str:
    """The answer format without descriptions (the instructions already explain the fields)."""
    def strip(o):
        if isinstance(o, dict):
            return {k: strip(v) for k, v in o.items() if k not in ("description", "title", "default")}
        if isinstance(o, list):
            return [strip(v) for v in o]
        return o
    return json.dumps(strip(CallReview.model_json_schema()), separators=(",", ":"))


FIELD_NOTES = """Field notes: call_purpose = short purpose; checklist = every item of the call type's checklist in order;
outcome 'Payment received' only if payment is confirmed on the call; next_step_date = YYYY-MM-DD or "";
deal_value_inr = rupee amount quoted/agreed, 0 if none; loss_reason 'None' if not lost; risk_level = risk of losing
the customer; ratings are Good/Partial/Weak with short 'observed' and 'improvement'; objections = each objection with
the playbook name, customer_said, executive_response, playbook_followed, recommended_response (playbook line);
fatal_errors = blunders with category, evidence, time_sec; moments = 5-12 key moments (time_sec, kind, text);
mood_timeline = 1-4 spans of the customer's mood; executive_lines = line numbers spoken by the executive;
acpt_improvement = 3-6 coaching points; overall_score 1-10; one_line_summary = one line for a manager; faq_answers = each product question with faq_no, executive_answer,
accuracy (Correct / Partly correct / Wrong / Not answered)."""


_ENUM_FALLBACKS = ("Other", "None", "Neutral", "Unclear", "Partial", "No", "Not applicable")


def _coerce(value, schema: dict, defs: dict):
    """Repair small slips in the AI's JSON so one odd value can't fail a whole review:
    unknown choices -> closest allowed value (or a safe default such as 'Other'), numbers sent as
    text -> numbers, missing fields -> empty values."""
    import difflib
    if "$ref" in schema:
        schema = defs.get(schema["$ref"].split("/")[-1], {})
    if "anyOf" in schema:
        schema = next((x for x in schema["anyOf"] if x.get("type") != "null"), schema["anyOf"][0])
    if "enum" in schema:
        allowed = [str(a) for a in schema["enum"]]
        v = str(value or "").strip()
        if v in allowed:
            return v
        low = {a.lower(): a for a in allowed}
        if v.lower() in low:
            return low[v.lower()]
        close = difflib.get_close_matches(v.lower(), list(low), n=1, cutoff=0.6)
        if close:
            return low[close[0]]
        for fb in _ENUM_FALLBACKS:
            if fb in allowed:
                return fb
        return allowed[0]
    t = schema.get("type")
    if t == "object":
        value = value if isinstance(value, dict) else {}
        props = schema.get("properties", {})
        out = dict(value)
        for name, sub in props.items():
            if name in value:
                out[name] = _coerce(value[name], sub, defs)
            elif name in schema.get("required", []):
                out[name] = _coerce(None, sub, defs)
        return out
    if t == "array":
        items = value if isinstance(value, list) else ([] if value in (None, "") else [value])
        return [_coerce(v, schema.get("items", {}), defs) for v in items]
    if t == "integer":
        try:
            return int(float(str(value).strip())) if value not in (None, "") else 0
        except ValueError:
            return 0
    if t == "string":
        return "" if value is None else value if isinstance(value, str) else str(value)
    if t == "boolean":
        return bool(value)
    return value


def _parse_review(raw: str) -> dict:
    schema = CallReview.model_json_schema()
    data = _coerce(json.loads(raw), schema, schema.get("$defs", {}))
    return CallReview.model_validate(data).model_dump()


def _with_format(system: str) -> str:
    return (system + "\n\n" + FIELD_NOTES + "\n\nReply with ONE JSON object only, no prose, matching this JSON "
            "Schema exactly (all fields required; enums must use the exact listed values):\n" + _compact_schema())


def _review_groq(system: str, user: str, settings: dict, lite: tuple[str, str] | None = None) -> dict:
    """JSON mode + schema in the prompt; small slips repaired, then validated; one corrective retry."""
    system = _with_format(system)
    lite = (_with_format(lite[0]), lite[1]) if lite else None
    raw = _groq_chat(system, user, settings, json_mode=True, lite=lite)
    try:
        return _parse_review(raw)
    except Exception as err:  # bad JSON, or a problem the repair step can't fix
        fix = (user + "\n\nYour previous reply did not match the schema. Error:\n" + str(err)[:1500]
               + "\nReturn the corrected JSON object only.")
        raw = _groq_chat(system, fix, settings, json_mode=True, lite=lite)
        return _parse_review(raw)


def lighter_transcript(transcript: str, block_sec: int = 30) -> str:
    """Merge numbered lines into ~30-second blocks with one time stamp each (smaller request)."""
    import re
    out, cur, start = [], [], None
    for line in transcript.splitlines():
        m = re.match(r"^\[(\d+) \| (\d+):(\d+)\]\s*(.*)$", line)
        if not m:
            return transcript
        t = int(m.group(2)) * 60 + int(m.group(3))
        if start is None:
            start = t
        if t - start >= block_sec and cur:
            out.append(f"[{start // 60:02d}:{start % 60:02d}] " + " ".join(cur))
            cur, start = [], t
        cur.append(m.group(4))
    if cur:
        out.append(f"[{start // 60:02d}:{start % 60:02d}] " + " ".join(cur))
    return "\n".join(out)


def _words(t: str) -> set[str]:
    import re
    return {w for w in re.findall(r"[a-z]+", t.lower().replace("'", "")) if len(w) > 2}


def _match_objection(name: str, names: list[str], call_type: str = "New Sales") -> str:
    """Map the AI's objection label to the playbook name: exact, close spelling, keyword rules,
    then shared key words; otherwise 'Other'."""
    import difflib
    from .playbook import KEYWORDS
    import re
    if name in names:
        return name
    lower = {n.lower(): n for n in names}
    if name.lower() in lower:
        return lower[name.lower()]
    text = name.lower().replace("'", "")
    for words, target in KEYWORDS.get(call_type, []):
        if target in names and any(re.search(r"\b" + re.escape(k.strip().replace("'", "")) + r"\b", text) for k in words):
            return target
    close = difflib.get_close_matches(name.lower(), list(lower), n=1, cutoff=0.75)
    if close:
        return lower[close[0]]
    w = _words(name)
    best, score = OTHER, 0.0
    for n in names:
        nw = _words(n)
        overlap = len(w & nw) / max(1, min(len(w), len(nw)))
        if overlap > score:
            best, score = n, overlap
    return best if score >= 0.6 else OTHER


def normalize(rv: dict, forced_type: str | None = None) -> dict:
    """Make AI output consistent: chosen call type wins, checklist matches the official items
    in order, date and amount are valid."""
    import difflib
    from datetime import date

    if forced_type in CALL_TYPES:
        rv["call_type"] = forced_type
    rv["call_type"] = canonical_type(rv.get("call_type"))
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
    names = objection_names(rv.get("call_type"))
    objs = []
    for o in rv.get("objections") or []:
        if not names:
            break
        name = _match_objection((o.get("objection") or "").strip(), names, rv.get("call_type"))
        rec = o.get("recommended_response") or " / ".join(responses_for(rv.get("call_type"), name)[:2])
        objs.append({**o, "objection": name, "recommended_response": rec,
                     "playbook_followed": o.get("playbook_followed") if o.get("playbook_followed") in ("Yes", "Partly", "No") else "No"})
    rv["objections"] = objs
    answers = []
    for a in (rv.get("faq_answers") or []) if faqs_for(rv.get("call_type")) else []:
        if not (a.get("customer_question") or "").strip():
            continue
        hit = None
        no = int(a.get("faq_no") or 0)
        if no:
            hit = next((f for f in faqs_for(rv.get("call_type")) if f["no"] == no), None)
        if hit is None:
            hit = match_faq(rv.get("call_type"), a.get("customer_question", ""))
        answers.append({"customer_question": a["customer_question"], "executive_answer": a.get("executive_answer", ""),
                        "accuracy": a.get("accuracy") if a.get("accuracy") in ACCURACY else "Not answered",
                        "faq_no": hit["no"] if hit else 0, "faq_question": hit["q"] if hit else NOT_IN_FAQ,
                        "faq_answer": hit["a"] if hit else ""})
    rv["faq_answers"] = answers
    fatal = []
    for f in rv.get("fatal_errors") or []:
        if (f.get("category") or f.get("evidence") or "").strip():
            fatal.append({"category": match_fatal((f.get("category") or "").strip()), "evidence": f.get("evidence", ""),
                          "time_sec": max(0, int(f.get("time_sec") or 0))})
    rv["fatal_errors"] = fatal
    rv["fatal"] = bool(fatal)
    rv["moments"] = sorted(({"time_sec": max(0, int(m.get("time_sec") or 0)), "kind": m.get("kind", "Other"),
                             "text": m.get("text", "")} for m in rv.get("moments") or []), key=lambda m: m["time_sec"])
    rv["mood_timeline"] = sorted(({"start_sec": max(0, int(m.get("start_sec") or 0)),
                                   "end_sec": max(0, int(m.get("end_sec") or 0)),
                                   "mood": m.get("mood", "Neutral")} for m in rv.get("mood_timeline") or []),
                                 key=lambda m: m["start_sec"])
    rv["executive_lines"] = sorted({int(i) for i in rv.get("executive_lines") or [] if str(i).lstrip("-").isdigit()})
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


def classify_call(transcript: str, settings: dict) -> str | None:
    """Cheap first step for Auto-detect: decide the call type from the start of the call, so the
    full review only needs that type's checklist and playbook."""
    types = "\n".join(f"- {t}: {v['about']}" for t, v in CALL_TYPES.items())
    system = ("Classify this sales/service phone call of an Indian accounting-software company into exactly one "
              f"call type:\n{types}\nReply with JSON only: {{\"call_type\": \"<one of the names above>\"}}")
    try:
        raw = _groq_chat(system, transcript[:4000], {**settings, "analysis": {**settings["analysis"], "effort": "low"}},
                         json_mode=True)
        t = json.loads(raw).get("call_type")
    except Exception:
        return None
    return t if t in CALL_TYPES else None


def timed_transcript(segments: list[dict]) -> str:
    """Numbered, time-stamped lines for the AI: [line | mm:ss] text."""
    def mmss(t: float) -> str:
        t = int(t or 0)
        return f"{t // 60:02d}:{t % 60:02d}"
    return "\n".join(f"[{i} | {mmss(s.get('start'))}] {s.get('text', '')}" for i, s in enumerate(segments))


def review_call(transcript: str, meta: dict, settings: dict) -> dict:
    if meta.get("call_type") not in CALL_TYPES and _provider(settings) == "groq":
        guessed = classify_call(transcript, settings)
        if guessed:
            meta = {**meta, "call_type": guessed}
            rv = _review_call(transcript, meta, settings)
            rv["call_type"] = rv.get("call_type") or guessed
            return normalize(rv)
    return normalize(_review_call(transcript, meta, settings), meta.get("call_type"))


def _review_call(transcript: str, meta: dict, settings: dict) -> dict:
    company = settings["company"]
    context = f"{company['name']}: {company['product']}\n{company['context'].strip()}"
    hint = meta.get("call_type") if meta.get("call_type") in CALL_TYPES else "not given (decide from the call)"
    dur = int(meta.get("duration_sec") or 0)
    forced = meta.get("call_type") if meta.get("call_type") in CALL_TYPES else None
    # Send only what this call needs when the type is known (keeps requests inside free-tier limits).
    if forced and forced not in PLAYBOOKS:
        pb = "no objection playbook applies to this call type; return an empty objections list."
    else:
        pb = ("for calls of the types below, list every objection the customer raised, using the exact "
              "objection name from THAT type's playbook (or 'Other'), and judge whether the executive used the "
              "recommended responses. For any other call type return an empty objections list.\n"
              + playbook_prompt(forced))

    def build(text: str, faq_k: int, note: str = "") -> tuple[str, str]:
        faqs = relevant_faqs(forced, text, k=faq_k) if forced else []
        if faqs:
            faq = ("below are the company's official answers to product questions likely raised in this call. For EVERY "
                   "product question the customer asked, give faq_no (0 if none of these covers it), the executive's "
                   "answer and its accuracy against the official answer. A Wrong answer about price, offers, policy or "
                   "a feature that doesn't exist is also a fatal error 'False information or a promise they can't make'.\n"
                   + faq_prompt(faqs))
        else:
            faq = "no FAQ list applies to this call; return an empty faq_answers list."
        system = SYSTEM.format(context=context, types=", ".join(CALL_TYPES), quality=quality_prompt(),
                               checklists=checklist_prompt(forced), playbook=pb, faq=faq) + note
        user = (f"Call metadata: executive={meta.get('executive') or 'unknown'}, date={meta.get('call_date') or 'unknown'}, "
                f"length={dur // 60}:{dur % 60:02d}, "
                f"campaign={meta.get('campaign') or 'unknown'}, call type={hint}\n\n<transcript>\n{text}\n</transcript>")
        return system, user

    system, user = build(transcript, 12)
    light = lighter_transcript(transcript)
    lite = build(light, 6, "\n\nIn this version the transcript is in ~30-second blocks without line numbers: use the "
                           "[mm:ss] stamps for times and return an empty executive_lines list.") if light != transcript else None
    if _provider(settings) == "groq":
        return _review_groq(system, user, settings, lite=lite)
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
pitch version, call type, checklist, outcome, deal value, soft skills, fatal errors, ratings and notes).
A call with any fatal error (a blunder such as rudeness, no empathy at a critical moment or bad fumbling) is a
FATAL call: always report fatal calls by executive and the most common fatal errors. Call types are New Sales,
Mobile App, Renewal, Upsell, CLM Onboarding (welcome/setup calls to new customers) and CLM Existing
(service calls to existing customers). Success means payment received for sales types, onboarding completed
for CLM Onboarding, and an issue resolved / healthy customer for CLM Existing. Compare like with like: always say
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


def insights_report(rows: list[dict], settings: dict, focus: str = "", progress=None) -> str:
    from .insights import build_report
    return build_report(rows, settings, focus, progress)
