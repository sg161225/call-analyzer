"""Product knowledge (answers vs FAQ) section for the Overview."""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

GOOD, WARN, BAD, NA = "#0ca30c", "#fab219", "#d03b3b", "#a9adb5"
ORDER = ["Correct", "Partly correct", "Wrong", "Not answered"]


def render(view: pd.DataFrame, ctype: str) -> None:
    st.subheader("❓ Product knowledge vs FAQ")
    rows = [{**a, "Executive": r["Executive"], "Date": r["Date"], "Customer": r["Customer"], "id": r["id"]}
            for _, r in view.iterrows() for a in r["FAQ answers"]]
    if not rows:
        st.caption(f"No product questions recorded yet for these {ctype} calls. New uploads are checked against "
                   "the FAQ automatically (see 📖 Playbook → ❓ FAQs).")
        return
    d = pd.DataFrame(rows)
    pts = d["accuracy"].map({"Correct": 1, "Partly correct": .5}).fillna(0)
    wrong = d[d["accuracy"] == "Wrong"]
    m = st.columns(4)
    m[0].metric("Product questions asked", len(d), help=f"In {d['id'].nunique()} of {len(view)} calls", border=True)
    m[1].metric("Answered correctly", f"{(d['accuracy'] == 'Correct').mean():.0%}", border=True,
                help="Matches the official FAQ answer")
    m[2].metric("Wrong answers", len(wrong), border=True, help="Contradicts the FAQ: coach on these first")
    m[3].metric("Not answered", int((d["accuracy"] == "Not answered").sum()), border=True)

    d["Topic"] = d.apply(lambda a: f"{a['faq_no']}. {a['faq_question']}" if a["faq_no"] else "Not in FAQ", axis=1)
    issues = d[d["accuracy"] != "Correct"]
    if issues.empty:
        st.success("✅ Every product question in these calls was answered correctly.")
        return
    top = issues["Topic"].value_counts().head(12)
    cnt = issues[issues["Topic"].isin(top.index)].groupby(["Topic", "accuracy"]).size().reset_index(name="Times")
    st.markdown("**Questions not answered properly** (only questions where an executive went wrong; "
                f"{(d['accuracy'] == 'Correct').sum()} correct answers not shown)")
    bars = alt.Chart(cnt).mark_bar(stroke="white", strokeWidth=2).encode(
        y=alt.Y("Topic:N", sort=top.index.tolist(), title=None, axis=alt.Axis(labelLimit=380)),
        x=alt.X("Times:Q", title="Times not answered properly", axis=alt.Axis(tickMinStep=1)),
        color=alt.Color("accuracy:N", title=None, scale=alt.Scale(domain=ORDER[1:], range=[WARN, BAD, NA]),
                        legend=alt.Legend(orient="top")),
        order=alt.Order("o:Q"), tooltip=["Topic", alt.Tooltip("accuracy:N", title="Answer"), "Times"],
    ).transform_calculate(o="indexof(['Correct','Partly correct','Wrong','Not answered'], datum.accuracy)")
    labels = alt.Chart(top.rename_axis("Topic").reset_index(name="Total")).mark_text(align="left", dx=4).encode(
        y=alt.Y("Topic:N", sort=top.index.tolist()), x="Total:Q", text="Total:Q", color=alt.value("#52514e"))
    st.altair_chart((bars + labels).properties(height=max(140, 32 * len(top) + 40)), width="stretch")

    bad = d[d["accuracy"].isin(["Wrong", "Partly correct", "Not answered"])].copy()
    if not bad.empty:
        st.markdown("**Answers to fix** · what the executive said vs the official FAQ answer (hover a cell to read it in full)")
        bad["o"] = bad["accuracy"].map({"Wrong": 0, "Not answered": 1, "Partly correct": 2})
        bad = bad.sort_values(["o", "Date"], ascending=[True, False])
        st.dataframe(pd.DataFrame({
            "Answer": bad["accuracy"].map({"Wrong": "❌ Wrong", "Partly correct": "🟡 Partly", "Not answered": "➖ None"}),
            "Executive": bad["Executive"], "Date": bad["Date"].dt.strftime("%d %b"),
            "Customer asked": bad["customer_question"], "Executive said": bad["executive_answer"],
            "Correct answer (FAQ)": bad.apply(lambda a: f"FAQ {a['faq_no']}: {a['faq_answer']}" if a["faq_no"] else "Not in FAQ", axis=1),
        }), hide_index=True, width="stretch", column_config={
            "Customer asked": st.column_config.TextColumn(width="medium"),
            "Executive said": st.column_config.TextColumn(width="medium"),
            "Correct answer (FAQ)": st.column_config.TextColumn(width="large")})
        nf = int((d["faq_no"] == 0).sum())
        if nf:
            st.caption(f"{nf} question(s) weren't covered by the FAQ. Check them; they may deserve a new FAQ entry.")

    st.markdown("**By executive**")
    g = d.assign(p=pts).groupby("Executive")
    tbl = pd.DataFrame({"Questions": g.size(), "Correct": (g["accuracy"].apply(lambda s: (s == "Correct").mean()) * 100).round(),
                        "Wrong": g["accuracy"].apply(lambda s: int((s == "Wrong").sum())),
                        "Score": (g["p"].mean() * 100).round()}).sort_values("Score").reset_index()
    st.dataframe(tbl, hide_index=True, width="stretch", column_config={
        "Correct": st.column_config.ProgressColumn("Answered correctly", min_value=0, max_value=100, format="%d%%"),
        "Score": st.column_config.ProgressColumn("Knowledge score", min_value=0, max_value=100, format="%d%%",
                                                 help="Correct = 1, partly = ½, wrong / none = 0")})
