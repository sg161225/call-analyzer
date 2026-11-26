"""Soft skills and fatal calls section for the Overview."""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from callanalyzer.calltypes import CALL_TYPES
from callanalyzer.quality import SHORT_FATAL, SOFT_SKILLS

GOOD, WARN, BAD = "#0ca30c", "#fab219", "#d03b3b"


def _card(title: str, value: str, color: str, note: str, width: float | None) -> str:
    bar = "" if width is None else (
        f'<div style="height:8px;border-radius:4px;background:rgba(128,128,128,.18);overflow:hidden;margin:4px 0 6px">'
        f'<div style="width:{max(2, width):.0f}%;height:100%;background:{color};border-radius:4px"></div></div>')
    return (f'<div style="border:1px solid rgba(128,128,128,.28);border-radius:10px;padding:12px 14px;">'
            f'<div style="font-size:.85rem;opacity:.75">{title}</div>'
            f'<div style="font-size:1.9rem;font-weight:600;line-height:1.3;color:{color if title.startswith("⛔") else "inherit"}">{value}</div>'
            f'{bar}<div style="font-size:.8rem;opacity:.8">{note}</div></div>')


def render(view: pd.DataFrame) -> None:
    st.subheader("🧭 Soft skills & ⛔ fatal calls")
    a = view[view["Assessed"]]
    if a.empty:
        st.caption("No calls checked for soft skills yet (reviews made before this check existed). "
                   "New uploads are checked automatically.")
        return
    n = len(a)
    fatal = a[a["Fatal"] == True]  # noqa: E712
    st.caption(f"Based on {n} call(s). A call is **fatal** when the executive made any blunder (rude or arrogant, "
               "disrespectful, no empathy at a critical moment, fumbled badly, talked over the customer, or false "
               "information / promises), even once.")

    cards = [_card("⛔ Fatal calls", f"{len(fatal)}", BAD if len(fatal) else GOOD,
                   f"{len(fatal) / n:.0%} of calls" if len(fatal) else "None 🎉", None)]
    for key, col in (("empathy", "Empathy"), ("humility", "Humility"), ("fluency", "Fluency")):
        rated = a[col].dropna()
        good = (rated == "Good").mean() if len(rated) else None
        color = GOOD if (good or 0) >= 0.8 else WARN if (good or 0) >= 0.5 else BAD
        weak = int((rated == "Weak").sum())
        cards.append(_card(SOFT_SKILLS[key][0], "—" if good is None else f"{good:.0%}", color,
                           f"rated Good · {weak} weak call(s)", None if good is None else good * 100))
    st.markdown(f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;'
                f'margin:6px 0 16px">{"".join(cards)}</div>', unsafe_allow_html=True)

    if not fatal.empty:
        rows = [{"Error": SHORT_FATAL.get(e.get("category"), e.get("category"))}
                for errs in fatal["Fatal errors"] for e in errs]
        fe = pd.DataFrame(rows).value_counts().rename("Times").reset_index()
        c1, c2 = st.columns([2, 3], gap="large")[0], st.container()
        with c1:
            st.markdown("**Fatal errors by type**")
            chart = alt.Chart(fe).mark_bar(color=BAD, cornerRadiusEnd=4).encode(
                y=alt.Y("Error:N", sort="-x", title=None, axis=alt.Axis(labelLimit=200)),
                x=alt.X("Times:Q", title=None, axis=alt.Axis(tickMinStep=1)), tooltip=["Error", "Times"])
            st.altair_chart((chart + chart.mark_text(align="left", dx=4).encode(
                text="Times:Q", color=alt.value("#52514e"))).properties(height=max(120, 38 * len(fe) + 20)),
                width="stretch")
        with c2:
            st.markdown("**Fatal calls** · open them on 📋 Call reviews (toggle *Fatal calls only*)")
            fl = pd.DataFrame({
                "Date": fatal["Date"].dt.strftime("%d %b"), "Executive": fatal["Executive"],
                "Type": fatal["Call type"].map(lambda t: f"{CALL_TYPES.get(t, {}).get('icon', '')} {t}"),
                "Customer": fatal["Customer"], "Mobile": fatal["Mobile"],
                "What went wrong": fatal["Fatal errors"].map(
                    lambda errs: "; ".join(f"{SHORT_FATAL.get(e['category'], e['category'])}: “{e.get('evidence', '')}”"
                                           for e in errs)),
            }).sort_values("Date", ascending=False)
            st.dataframe(fl, hide_index=True, width="stretch",
                         column_config={"What went wrong": st.column_config.TextColumn(width="large")})

    st.markdown("**By executive**")
    g = a.groupby("Executive")
    tbl = pd.DataFrame({
        "Calls": g.size(),
        "Fatal calls": g["Fatal"].apply(lambda s: int((s == True).sum())),  # noqa: E712
        "Empathy": g["Empathy"].apply(lambda s: (s == "Good").mean() * 100).round(),
        "Humility": g["Humility"].apply(lambda s: (s == "Good").mean() * 100).round(),
        "Fluency": g["Fluency"].apply(lambda s: (s == "Good").mean() * 100).round(),
    }).sort_values(["Fatal calls", "Empathy"], ascending=[False, True]).reset_index()
    tbl["Fatal calls"] = tbl["Fatal calls"].map(lambda v: f"⛔ {v}" if v else "0")
    pc = lambda label: st.column_config.ProgressColumn(label, min_value=0, max_value=100, format="%d%%")  # noqa: E731
    st.dataframe(tbl, hide_index=True, width="stretch", column_config={
        "Empathy": pc("Empathy (Good)"), "Humility": pc("Humility & courtesy (Good)"),
        "Fluency": pc("Fluency (Good)")})
