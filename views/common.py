"""Shared helpers: flatten reviews into one row per call, filters, rating badges."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from callanalyzer import store  # noqa: E402
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
    c1, c2, c3 = st.columns([2, 2, 2])
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
            "Customer": flat["Customer"], "Outcome": flat["Outcome"], "Score (1-10)": flat["Score"]}
    for key, label in PARAMETERS.items():
        text = flat[f"{key}__text"]
        if key in RATED:
            cols[label] = flat[f"{key}__rating"].fillna("") + " – " + text
        else:
            cols[label] = text
    return pd.DataFrame(cols)


def load_flat() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = store.load_calls()
    return raw, flatten(raw)
