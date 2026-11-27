"""AI insights report that fits the free tier for any number of calls.

The app calculates the numbers itself (exact, and small to send), turns each call into one short line,
and, when there are many calls, has the AI summarise them in batches before writing the final report.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from .calltypes import canonical_type, is_success
from .faq import faqs_for
from .quality import SHORT_FATAL

BATCH_CHARS = 7000      # ~1,750 tokens of call lines per request
FINAL_OBS_CHARS = 9000  # cap on combined batch observations sent to the final request


def clean(rows: list[dict]) -> list[dict]:
    """Empty spreadsheet-style values (None / NaN) become empty text so sorting and grouping work."""
    out = []
    for r in rows:
        r = dict(r)
        for k in ("executive", "date", "campaign", "pitch_version", "call_type"):
            v = r.get(k)
            r[k] = v.strip() if isinstance(v, str) else ""
        out.append(r)
    return out


def _pct(a: int, b: int) -> str:
    return f"{a / b:.0%}" if b else "n/a"


def _type(r: dict) -> str:
    return canonical_type(r.get("call_type")) or "Unknown"


def stats_text(rows: list[dict]) -> str:
    """Exact figures for the report, worked out by the app."""
    rows = clean(rows)
    n = len(rows)
    lines = [f"Calls: {n}. Dates: {min((r.get('date') or '') for r in rows) or '?'} to "
             f"{max((r.get('date') or '') for r in rows) or '?'}."]

    def ok(r):
        ss = r.get("risk_level", "None")
        return is_success(_type(r), r.get("outcome", ""), ss)

    # by call type
    by_t = defaultdict(list)
    for r in rows:
        by_t[_type(r)].append(r)
    lines.append("\nBy call type (calls | avg score | success | fatal calls):")
    for t, rs in sorted(by_t.items(), key=lambda x: -len(x[1])):
        sc = [r.get("overall_score") or 0 for r in rs]
        lines.append(f"- {t}: {len(rs)} | {sum(sc) / len(sc):.1f} | {_pct(sum(ok(r) for r in rs), len(rs))} | "
                     f"{sum(bool(r.get('fatal_errors')) for r in rs)}")

    # by executive
    by_e = defaultdict(list)
    for r in rows:
        by_e[r.get("executive") or "Unknown"].append(r)
    lines.append("\nBy executive (calls | avg score | success | fatal | empathy/humility/fluency Good | checklist done):")
    for e, rs in sorted(by_e.items(), key=lambda x: -len(x[1])):
        sc = [r.get("overall_score") or 0 for r in rs]
        good = lambda k: _pct(sum(((r.get("soft_skills") or {}).get(k) or {}).get("rating") == "Good" for r in rs),  # noqa: E731
                              sum(bool((r.get("soft_skills") or {}).get(k)) for r in rs))
        cl = [c for r in rs for c in r.get("checklist") or [] if c.get("done") in ("Yes", "No")]
        types = ", ".join(f"{t} {c}" for t, c in Counter(_type(r) for r in rs).most_common())
        lines.append(f"- {e}: {len(rs)} ({types}) | {sum(sc) / len(sc):.1f} | {_pct(sum(ok(r) for r in rs), len(rs))} | "
                     f"{sum(bool(r.get('fatal_errors')) for r in rs)} | {good('empathy')}/{good('humility')}/{good('fluency')} | "
                     f"{_pct(sum(c['done'] == 'Yes' for c in cl), len(cl))}")

    # scorecard areas
    areas = {"business_probing": "Business probing", "need_generation": "Need generation", "pitch": "Pitch",
             "customer_queries": "Customer queries", "objection_handling": "Objection handling"}
    lines.append("\nScorecard areas rated Weak (share of calls):")
    lines.append("- " + "; ".join(f"{label} {_pct(sum((r.get(k) or {}).get('rating') == 'Weak' for r in rows), n)}"
                                  for k, label in areas.items()))

    # checklist misses per type
    lines.append("\nMost missed checklist points (by call type):")
    for t, rs in by_t.items():
        miss, tot = Counter(), Counter()
        for r in rs:
            for c in r.get("checklist") or []:
                if c.get("done") in ("Yes", "No"):
                    tot[c["item"]] += 1
                    miss[c["item"]] += c["done"] == "No"
        top = [f"{i} ({miss[i]}/{tot[i]})" for i, _ in miss.most_common(4) if miss[i]]
        if top:
            lines.append(f"- {t}: " + "; ".join(top))

    # fatal errors
    fe = Counter(SHORT_FATAL.get(f.get("category"), f.get("category")) for r in rows for f in r.get("fatal_errors") or [])
    if fe:
        lines.append("\nFatal errors: " + "; ".join(f"{k} {v}" for k, v in fe.most_common()))

    # outcomes and loss reasons
    lines.append("\nOutcomes: " + "; ".join(f"{k} {v}" for k, v in Counter(r.get("outcome") for r in rows).most_common()))
    lr = Counter(r.get("loss_reason") for r in rows if r.get("loss_reason") not in (None, "", "None"))
    if lr:
        lines.append("Loss reasons: " + "; ".join(f"{k} {v}" for k, v in lr.most_common()))

    # objections
    ob = defaultdict(Counter)
    for r in rows:
        for o in r.get("objections") or []:
            ob[o.get("objection")][o.get("playbook_followed")] += 1
    if ob:
        lines.append("\nObjections (times raised | playbook followed):")
        for k, c in sorted(ob.items(), key=lambda x: -sum(x[1].values()))[:10]:
            tot = sum(c.values())
            lines.append(f"- {k}: {tot} | {_pct(c['Yes'], tot)}")

    # product questions vs FAQ
    fq = defaultdict(Counter)
    for r in rows:
        for a in r.get("faq_answers") or []:
            fq[a.get("faq_question") or a.get("customer_question")][a.get("accuracy")] += 1
    if fq:
        allc = Counter()
        for c in fq.values():
            allc.update(c)
        tot = sum(allc.values())
        lines.append(f"\nProduct questions vs FAQ: {tot} asked, {_pct(allc['Correct'], tot)} correct, "
                     f"{allc['Wrong']} wrong, {allc['Not answered']} not answered. Most often answered wrong or not at all:")
        bad = sorted(fq.items(), key=lambda x: -(x[1]["Wrong"] + x[1]["Not answered"]))[:6]
        lines += [f"- {q}: wrong {c['Wrong']}, not answered {c['Not answered']}, of {sum(c.values())}"
                  for q, c in bad if c["Wrong"] + c["Not answered"]]

    # pitch versions
    pv = defaultdict(list)
    for r in rows:
        if r.get("pitch_version"):
            pv[(r.get("executive") or "Unknown", r["pitch_version"])].append(r)
    if len({v for _, v in pv}) > 1:
        lines.append("\nBy executive and pitch version (calls | avg score | success):")
        for (e, v), rs in sorted(pv.items()):
            sc = [r.get("overall_score") or 0 for r in rs]
            lines.append(f"- {e} / {v}: {len(rs)} | {sum(sc) / len(sc):.1f} | {_pct(sum(ok(r) for r in rs), len(rs))}")
    return "\n".join(lines)


def call_line(r: dict) -> str:
    """One short line per call."""
    cut = lambda t, k: " ".join(str(t or "").split())[:k]  # noqa: E731
    missed = [c["item"][:40] for c in r.get("checklist") or [] if c.get("done") == "No"][:3]
    fatal = [SHORT_FATAL.get(f.get("category"), f.get("category")) for f in r.get("fatal_errors") or []]
    obj = [f"{o.get('objection')}={o.get('playbook_followed')}" for o in r.get("objections") or []][:3]
    wrong = [cut(a.get("customer_question"), 40) for a in r.get("faq_answers") or [] if a.get("accuracy") == "Wrong"][:2]
    parts = [r.get("date") or "", r.get("executive") or "", _type(r), r.get("outcome") or "", f"score {r.get('overall_score')}",
             cut(r.get("one_line_summary"), 140)]
    if fatal:
        parts.append("FATAL: " + ", ".join(fatal))
    if missed:
        parts.append("missed: " + "; ".join(missed))
    if obj:
        parts.append("objections: " + ", ".join(obj))
    if wrong:
        parts.append("wrong answers: " + "; ".join(wrong))
    tips = r.get("acpt_improvement") or []
    if tips:
        parts.append("coach: " + cut(tips[0], 90))
    return " | ".join(p for p in parts if p)


BATCH_SYSTEM = """You are helping the head of quality of an Indian software company's tele-calling team.
You get one line per call (date | executive | call type | outcome | score | summary | fatal errors | missed checklist
points | objections | wrong product answers | top coaching point). Write 6-12 short bullet observations about
patterns in THESE calls: what works, what doesn't, recurring misses, objections, product-knowledge gaps, and
executive-specific issues. Name executives and dates as evidence. No introduction, bullets only."""

FINAL_INSTRUCTIONS = """
You get (1) EXACT FIGURES calculated by the app — use these numbers as given, never recalculate or invent numbers —
and (2) per-call lines or batch observations as evidence. Return ONLY a JSON object with exactly these keys:

{
 "headline": [{"title": "<6-10 words>", "detail": "<1-2 sentences with numbers from EXACT FIGURES>",
               "tone": "good" | "bad" | "neutral"}],                       // exactly 3
 "working": [{"point": "<behaviour linked to good outcomes>", "evidence": "<executive + date / numbers>"}],   // 2-5
 "not_working": [{"point": "<recurring weakness, fatal error, loss reason or unresolved query>",
                  "evidence": "<executive + date / numbers>"}],          // 2-6
 "executives": [{"name": "<executive exactly as in EXACT FIGURES>", "strength": "<one line>",
                 "coaching": "<the single most important coaching point>"}],   // every executive
 "product_and_objections": [{"point": "<FAQ answer to fix or objection where the playbook isn't followed>",
                             "evidence": "<numbers / examples>"}],       // 0-5
 "pitch_changes": "<pitch versions or changes over dates; say clearly when there is too little data>",
 "improvements": [{"action": "<concrete change to script, preparation, offers, escalation or follow-up>",
                   "why": "<the finding it fixes>", "priority": "High" | "Medium" | "Low"}]   // 3-7
}

Say which call type a finding applies to. Keep every string short and practical. Mention sample sizes and
don't overstate patterns from 1-2 calls."""

KEYS = ("headline", "working", "not_working", "executives", "product_and_objections", "pitch_changes", "improvements")


def parse_json(text: str) -> dict | None:
    import json
    import re
    text = (text or "").strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    if not isinstance(d, dict) or not any(k in d for k in KEYS):
        return None
    lst = lambda v: [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []  # noqa: E731
    out = {k: lst(d.get(k)) for k in KEYS if k != "pitch_changes"}
    out["pitch_changes"] = str(d.get("pitch_changes") or "")
    for h in out["headline"]:
        h["tone"] = h.get("tone") if h.get("tone") in ("good", "bad", "neutral") else "neutral"
    for i in out["improvements"]:
        i["priority"] = str(i.get("priority") or "Medium").title()
        if i["priority"] not in ("High", "Medium", "Low"):
            i["priority"] = "Medium"
    return out


def to_markdown(d: dict, rows: list[dict]) -> str:
    """Readable report (for the PDF / Markdown download) from the structured one plus the app's exact figures."""
    rows = clean(rows)
    cut = lambda t: " ".join(str(t or "").split()).replace("|", "/")  # noqa: E731
    md = ["## Headline"] + [f"- **{cut(h.get('title'))}**: {cut(h.get('detail'))}" for h in d["headline"]]
    md += ["", "## What is working"] + [f"- **{cut(w.get('point'))}** ({cut(w.get('evidence'))})" for w in d["working"]]
    md += ["", "## What is not working"] + [f"- **{cut(w.get('point'))}** ({cut(w.get('evidence'))})" for w in d["not_working"]]
    by_e = defaultdict(list)
    for r in rows:
        by_e[r.get("executive") or "Unknown"].append(r)
    coach = {str(e.get("name", "")).strip().lower(): e for e in d["executives"]}
    md += ["", "## Executive comparison", "| Executive | Calls | Avg score | Success | Fatal calls | Key coaching point |",
           "|---|---|---|---|---|---|"]
    for e, rs in sorted(by_e.items(), key=lambda x: -len(x[1])):
        sc = [r.get("overall_score") or 0 for r in rs]
        ok = sum(is_success(_type(r), r.get("outcome", ""), r.get("risk_level", "None")) for r in rs)
        md.append(f"| {e} | {len(rs)} | {sum(sc) / len(sc):.1f} | {_pct(ok, len(rs))} | "
                  f"{sum(bool(r.get('fatal_errors')) for r in rs)} | {cut(coach.get(e.lower(), {}).get('coaching'))} |")
    for e in d["executives"]:
        if e.get("strength"):
            md.append(f"\n**{cut(e.get('name'))}**: strength: {cut(e.get('strength'))}. Coach: {cut(e.get('coaching'))}")
    if d["product_and_objections"]:
        md += ["", "## Product knowledge & objections"] + [f"- **{cut(w.get('point'))}** ({cut(w.get('evidence'))})"
                                                           for w in d["product_and_objections"]]
    if d["pitch_changes"]:
        md += ["", "## Pitch changes over time", cut(d["pitch_changes"])]
    order = {"High": 0, "Medium": 1, "Low": 2}
    md += ["", "## Process improvements"] + [f"{i}. **[{x['priority']}] {cut(x.get('action'))}**: {cut(x.get('why'))}"
                                            for i, x in enumerate(sorted(d["improvements"], key=lambda x: order[x["priority"]]), 1)]
    return "\n".join(md)


def build_report(rows: list[dict], settings: dict, focus: str = "", progress=None) -> dict:
    from .review import INSIGHTS_SYSTEM, _client, _groq_chat, _provider

    company = settings["company"]
    head = f"Company: {company['name']}: {company['product']}\n" + (f"Manager's focus for this report: {focus}\n" if focus else "")
    rows = clean(rows)
    stats = stats_text(rows)
    lines = [call_line(r) for r in sorted(rows, key=lambda r: (r.get("date") or "", r.get("executive") or ""))]
    system = INSIGHTS_SYSTEM.split("Write a concise")[0] + FINAL_INSTRUCTIONS

    if _provider(settings) != "groq":
        user = f"{head}\nEXACT FIGURES\n{stats}\n\nCALLS (one line each)\n" + "\n".join(lines)
        with _client().beta.messages.stream(
            model=settings["analysis"]["model"], max_tokens=32000, system=system,
            messages=[{"role": "user", "content": user}], output_config={"effort": "high"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        ) as stream:
            msg = stream.get_final_message()
        if msg.stop_reason == "refusal":
            raise RuntimeError("The AI declined to write this report.")
        data = parse_json("".join(b.text for b in msg.content if b.type == "text"))
        if data is None:
            raise RuntimeError("The AI's report came back in the wrong format. Please click Generate report again.")
        return {"md": to_markdown(data, rows), "data": data}

    joined = "\n".join(lines)
    if len(joined) <= BATCH_CHARS:
        evidence = "CALLS (one line each)\n" + joined
    else:
        batches, cur = [], []
        for ln in lines:
            if cur and len("\n".join(cur + [ln])) > BATCH_CHARS:
                batches.append(cur)
                cur = []
            cur.append(ln)
        if cur:
            batches.append(cur)
        obs = []
        for i, b in enumerate(batches, 1):
            if progress:
                progress(f"Reading calls: batch {i} of {len(batches)}…")
            obs.append(f"Batch {i} ({len(b)} calls):\n" + _groq_chat(BATCH_SYSTEM, "\n".join(b), settings, json_mode=False,
                                                                     max_out=1500, what="summarise these calls"))
        evidence = "BATCH OBSERVATIONS\n" + "\n\n".join(obs)[:FINAL_OBS_CHARS]
    if progress:
        progress("Writing the report…")
    user = f"{head}\nEXACT FIGURES\n{stats}\n\n{evidence}"
    text = _groq_chat(system, user, settings, json_mode=True, max_out=4000, what="write this report")
    data = parse_json(text)
    if data is None:
        raise RuntimeError("The AI's report came back in the wrong format. Please click Generate report again.")
    return {"md": to_markdown(data, rows), "data": data}
