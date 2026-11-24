"""Shared helpers: flatten reviews into one row per call, filters, rating badges."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from callanalyzer import store  # noqa: E402
from callanalyzer.calltypes import CALL_TYPES, guess_type_from_purpose, is_positive, is_success  # noqa: E402
from callanalyzer.filenames import parse_file_name  # noqa: E402
from callanalyzer.review import PARAMETERS, RATING_SCORE  # noqa: E402

BADGE = {"Good": "✅ Good", "Partial": "🟡 Partial", "Weak": "❌ Weak", "Not applicable": "➖ N/A"}
RATED = ["business_probing", "need_generation", "pitch", "customer_queries", "objection_handling"]


def badge(rating: str | None) -> str:
    return BADGE.get(rating or "", "")


def flatten(df: pd.DataFrame) -> pd.DataFrame:
    """One row per reviewed call with the scorecard columns."""
    rows = []
    for _, r in df[df["status"] == "done"].iterrows():
        rv = r["review"]
        g = parse_file_name(r["file_name"])
        row = {
            "id": r["id"], "Date": r["call_date"],
            "Executive": _s(r.get("executive")) or g["executive"] or "Unknown",
            "Mobile": _s(r.get("mobile")) or g["mobile"],
            "Campaign": _s(r["campaign"]), "Pitch version": _s(r["pitch_version"]),
            "File": r["file_name"], "Customer": rv.get("customer_name", ""),
            "Purpose": rv.get("call_purpose", ""), "Outcome": rv.get("outcome", ""),
            "Score": rv.get("overall_score"), "Summary": rv.get("one_line_summary", ""),
            "Minutes": round((r["duration_sec"] or 0) / 60, 1),
        }
        ctype = _s(r.get("call_type")) or rv.get("call_type") or guess_type_from_purpose(rv.get("call_purpose", ""))
        checklist = rv.get("checklist") or []
        applicable = [c for c in checklist if c.get("done") in ("Yes", "No")]
        risk = rv.get("risk_level", "None")
        due = pd.to_datetime(rv.get("next_step_date") or None, errors="coerce")
        row.update({
            "Call type": ctype, "Checklist": checklist,
            "Checklist %": (sum(c["done"] == "Yes" for c in applicable) / len(applicable)) if applicable else None,
            "Next step": rv.get("next_step", ""), "Next step date": due,
            "Deal value": int(rv.get("deal_value_inr") or 0), "Deal note": rv.get("deal_value_note", ""),
            "Loss reason": rv.get("loss_reason", "None"), "Risk": risk, "Risk reason": rv.get("risk_reason", ""),
            "Sentiment end": rv.get("customer_sentiment_end", ""),
            "Success": is_success(ctype, row["Outcome"], risk), "Positive": is_positive(row["Outcome"]),
            "Follow-up done": _flag(r.get("followup_done")),
        })
        for key in RATED:
            a = rv.get(key, {})
            row[f"{key}__rating"] = a.get("rating")
            row[f"{key}__score"] = RATING_SCORE.get(a.get("rating"))
        q = rv.get("customer_queries", {})
        p = rv.get("pitch", {})
        row["business_probing__text"] = _txt(rv.get("business_probing"))
        row["need_generation__text"] = _txt(rv.get("need_generation"))
        row["pitch__text"] = "Features: " + (", ".join(p.get("features_mentioned", [])) or "none") + \
            " | Offers: " + (", ".join(p.get("offers_made", [])) or "none") + " | " + _txt(p)
        row["customer_queries__text"] = "; ".join(q.get("queries", [])) + \
            (f" | Unresolved: {'; '.join(q['unresolved'])}" if q.get("unresolved") else "")
        row["objection_handling__text"] = _txt(rv.get("objection_handling"))
        row["acpt_improvement__text"] = " • ".join(rv.get("acpt_improvement", []))
        rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty:
        out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    return out


def _flag(v) -> bool:
    """1/0 database flag; None and NaN (empty cells) count as not set."""
    try:
        return bool(pd.notna(v) and int(v) == 1)
    except (TypeError, ValueError):
        return False


def _s(v) -> str:
    """Text value from a DataFrame cell; empty for None/NaN."""
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


def _txt(a: dict | None) -> str:
    if not a:
        return ""
    return f"{a.get('observed', '')} → Improve: {a.get('improvement', '')}"


def filters(flat: pd.DataFrame, key: str) -> pd.DataFrame:
    """One row of filters above the content."""
    if flat.empty:
        return flat
    q = st.text_input("🔎 Search", key=f"{key}_q", placeholder="Mobile number, customer, executive or file name")
    c0, c1, c2, c3 = st.columns([2, 2, 2, 2])
    types = [t for t in CALL_TYPES if t in set(flat["Call type"])]
    sel_t = c0.multiselect("Call type", types, key=f"{key}_t", placeholder="All call types",
                           format_func=lambda t: f"{CALL_TYPES[t]['icon']} {t}")
    execs = sorted(flat["Executive"].dropna().unique())
    camps = sorted(c for c in flat["Campaign"].dropna().unique() if c)
    sel_e = c1.multiselect("Executive", execs, key=f"{key}_e", placeholder="All executives")
    sel_c = c2.multiselect("Campaign", camps, key=f"{key}_c", placeholder="All campaigns")
    dates = flat["Date"].dropna()
    rng = None
    if not dates.empty:
        rng = c3.date_input("Call date", (dates.min().date(), dates.max().date()), key=f"{key}_d")
    out = flat
    if q.strip():
        needle = q.strip().lower()
        digits = "".join(ch for ch in needle if ch.isdigit())
        hay = (out["Mobile"].fillna("") + " " + out["Customer"].fillna("") + " " + out["Executive"].fillna("")
               + " " + out["File"].fillna("")).str.lower()
        hit = hay.str.contains(needle, regex=False)
        if len(digits) >= 4:  # match numbers typed with spaces / +91
            hit |= out["Mobile"].fillna("").str.contains(digits[-10:], regex=False)
        out = out[hit]
    if sel_t:
        out = out[out["Call type"].isin(sel_t)]
    if sel_e:
        out = out[out["Executive"].isin(sel_e)]
    if sel_c:
        out = out[out["Campaign"].isin(sel_c)]
    if rng and isinstance(rng, tuple) and len(rng) == 2:
        d = out["Date"]
        out = out[d.isna() | ((d.dt.date >= rng[0]) & (d.dt.date <= rng[1]))]
    return out


def export_frame(flat: pd.DataFrame) -> pd.DataFrame:
    """Spreadsheet layout: your six columns against each call."""
    cols = {"Date": flat["Date"].dt.strftime("%Y-%m-%d"), "Executive": flat["Executive"],
            "Mobile": flat["Mobile"],
            "Campaign": flat["Campaign"], "Pitch version": flat["Pitch version"], "File": flat["File"],
            "Call type": flat["Call type"], "Customer": flat["Customer"], "Outcome": flat["Outcome"],
            "Next step": flat["Next step"], "Next step date": flat["Next step date"].dt.strftime("%Y-%m-%d").fillna(""),
            "Deal value (₹)": flat["Deal value"], "Loss reason": flat["Loss reason"].replace("None", ""),
            "Risk": flat["Risk"].replace("None", ""), "Checklist": flat["Checklist"].map(checklist_summary),
            "Score (1-10)": flat["Score"]}
    for key, label in PARAMETERS.items():
        text = flat[f"{key}__text"]
        if key in RATED:
            cols[label] = flat[f"{key}__rating"].fillna("") + " – " + text
        else:
            cols[label] = text
    return pd.DataFrame(cols)


def checklist_summary(items: list) -> str:
    app = [c for c in items or [] if c.get("done") in ("Yes", "No")]
    if not app:
        return ""
    missed = [c["item"] for c in app if c["done"] == "No"]
    return f"{len(app) - len(missed)}/{len(app)} done" + (f" · Missed: {'; '.join(missed)}" if missed else "")


def inr(v: float) -> str:
    """₹ amount in Indian style: ₹1,25,000 / ₹2.4 L / ₹1.2 Cr."""
    v = float(v or 0)
    if v >= 1e7:
        return f"₹{v / 1e7:.2f}".rstrip("0").rstrip(".") + " Cr"
    if v >= 1e5:
        return f"₹{v / 1e5:.2f}".rstrip("0").rstrip(".") + " L"
    s = f"{int(round(v)):d}"
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
        s = f"{head},{tail}"
    return f"₹{s}"


def load_flat() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = store.load_calls()
    return raw, flatten(raw)
