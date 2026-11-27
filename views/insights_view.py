"""Visual dashboard for an AI insights report: the app's exact figures as tiles and charts, with the AI's
findings as cards. Old reports (text only) are shown as text."""
from __future__ import annotations

import html
from collections import Counter

import altair as alt
import pandas as pd
import streamlit as st

from callanalyzer.review import PARAMETERS

GOOD, WARN, BAD, BLUE, NA = "#0ca30c", "#e0a100", "#d03b3b", "#2a78d6", "#a9adb5"
TONE = {"good": (GOOD, "✅"), "bad": (BAD, "⚠️"), "neutral": (BLUE, "💡")}
PRIO = {"High": BAD, "Medium": WARN, "Low": BLUE}
AREAS = {k: v.split(" (")[0] for k, v in PARAMETERS.items() if k != "acpt_improvement"}
AREAS["objection_handling"] = "Objection handling"


def esc(s) -> str:
    return html.escape(str(s or ""))


def card(title: str, body: str, color: str, icon: str = "", foot: str = "") -> str:
    return (f"<div style='border:1px solid color-mix(in srgb,{color} 35%,transparent);border-left:5px solid {color};"
            f"border-radius:10px;padding:10px 14px;margin:0 0 10px;background:color-mix(in srgb,{color} 7%,transparent)'>"
            f"<div style='font-weight:700;margin-bottom:3px'>{icon} {esc(title)}</div>"
            f"<div style='font-size:.9rem;opacity:.85'>{esc(body)}</div>"
            + (f"<div style='font-size:.8rem;opacity:.65;margin-top:4px'>{foot}</div>" if foot else "") + "</div>")


def kpis(v: pd.DataFrame) -> list[tuple[str, str, str]]:
    """(label, value, colour) tiles, worked out by the app."""
    fatal = int(v["Fatal"].fillna(False).astype(bool).sum())
    score = v["Score"].astype(float).mean()
    succ = v["Success"].mean()
    pb = v["Playbook %"].dropna()
    fq = v["FAQ %"].dropna()
    col = lambda x, g, w: GOOD if x >= g else WARN if x >= w else BAD  # noqa: E731
    out = [("Calls reviewed", f"{len(v)}", BLUE),
           ("Average score", f"{score:.1f}/10", col(score, 7, 5)),
           ("Success rate", f"{succ:.0%}", col(succ, .5, .25)),
           ("Fatal calls", f"{fatal}" + (f" ({fatal / len(v):.0%})" if len(v) else ""), BAD if fatal else GOOD)]
    if len(pb):
        out.append(("Objections handled right", f"{pb.mean():.0%}", col(pb.mean(), .75, .5)))
    if len(fq):
        out.append(("Product answers correct", f"{fq.mean():.0%}", col(fq.mean(), .8, .6)))
    return out


def exec_table(v: pd.DataFrame, data: dict) -> pd.DataFrame:
    g = v.groupby("Executive")
    t = pd.DataFrame({"Calls": g.size(), "Avg score": g["Score"].mean().round(1),
                      "Success": (g["Success"].mean() * 100).round(),
                      "Checklist": (g["Checklist %"].mean() * 100).round(),
                      "Fatal calls": g["Fatal"].apply(lambda s: int(s.fillna(False).astype(bool).sum()))})
    coach = {str(e.get("name", "")).strip().lower(): e for e in data.get("executives", [])}
    t["Strength"] = [coach.get(e.lower(), {}).get("strength", "") for e in t.index]
    t["Coaching point"] = [coach.get(e.lower(), {}).get("coaching", "") for e in t.index]
    return t.sort_values("Avg score", ascending=False).reset_index()


def top_issues(v: pd.DataFrame) -> dict[str, Counter]:
    miss = Counter(c["item"] for cl in v["Checklist"] for c in cl or [] if c.get("done") == "No")
    obj = Counter(o["objection"] for os_ in v["Objections"] for o in os_ if o.get("playbook_followed") != "Yes")
    faq = Counter((a.get("faq_question") or a.get("customer_question") or "")[:80]
                  for fa in v["FAQ answers"] for a in fa if a.get("accuracy") != "Correct")
    return {"Checklist points missed": miss, "Objections not handled properly": obj,
            "Product questions not answered properly": faq}


def _bar(counter: Counter, color: str, title: str, n: int = 8):
    d = pd.DataFrame(counter.most_common(n), columns=["What", "Times"])
    base = alt.Chart(d).encode(y=alt.Y("What:N", sort="-x", title=None, axis=alt.Axis(labelLimit=330)))
    bars = base.mark_bar(color=color, cornerRadiusEnd=3).encode(
        x=alt.X("Times:Q", title=title, axis=alt.Axis(tickMinStep=1)), tooltip=["What", "Times"])
    text = base.mark_text(align="left", dx=4, color="#52514e").encode(x="Times:Q", text="Times:Q")
    return (bars + text).properties(height=max(110, 30 * len(d) + 30))


def render(rep: dict, flat: pd.DataFrame) -> None:
    data = rep.get("data")
    if not data:
        st.markdown(rep["content_md"])
        return
    v = flat[flat["id"].isin(rep.get("ids") or [])] if not flat.empty else flat
    if len(v):
        tiles = kpis(v)
        cols = st.columns(len(tiles))
        for c, (label, value, color) in zip(cols, tiles):
            c.markdown(f"<div style='border:1px solid color-mix(in srgb,{color} 30%,transparent);border-top:4px solid {color};"
                       f"border-radius:10px;padding:10px 12px;text-align:center'><div style='font-size:.78rem;opacity:.7'>{label}</div>"
                       f"<div style='font-size:1.55rem;font-weight:700;color:{color}'>{value}</div></div>", unsafe_allow_html=True)
        missing = len(rep.get("ids") or []) - len(v)
        if missing > 0:
            st.caption(f"{missing} call(s) in this report have since been deleted; figures cover the {len(v)} still saved.")
    elif rep.get("ids"):
        st.caption("The calls in this report have been deleted, so only the AI's findings are shown.")

    # headline
    st.markdown("#### 📰 Headline")
    hc = st.columns(max(1, len(data["headline"])))
    for c, h in zip(hc, data["headline"]):
        color, icon = TONE[h["tone"]]
        c.markdown(card(h.get("title"), h.get("detail"), color, icon), unsafe_allow_html=True)

    # working vs not
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.markdown("#### ✅ What is working")
        st.markdown("".join(card(w.get("point"), w.get("evidence"), GOOD) for w in data["working"]) or "—",
                    unsafe_allow_html=True)
    with c2:
        st.markdown("#### ⚠️ What is not working")
        st.markdown("".join(card(w.get("point"), w.get("evidence"), BAD) for w in data["not_working"]) or "—",
                    unsafe_allow_html=True)

    if len(v):
        # executives
        st.markdown("#### 👥 Executive comparison")
        t = exec_table(v, data)
        e1, e2 = st.columns([2, 3], gap="medium")
        with e1:
            d = t.assign(Status=t["Avg score"].map(lambda s: "Good (7+)" if s >= 7 else "OK (5-7)" if s >= 5 else "Weak (<5)"))
            base = alt.Chart(d).encode(y=alt.Y("Executive:N", sort=d["Executive"].tolist(), title=None,
                                               axis=alt.Axis(labelOverlap=False, labelLimit=160)))
            bars = base.mark_bar(cornerRadiusEnd=3).encode(
                x=alt.X("Avg score:Q", scale=alt.Scale(domain=[0, 10]), title="Average score (out of 10)"),
                color=alt.Color("Status:N", scale=alt.Scale(domain=["Good (7+)", "OK (5-7)", "Weak (<5)"], range=[GOOD, WARN, BAD]),
                                legend=alt.Legend(orient="top", title=None)),
                tooltip=["Executive", "Calls", "Avg score", alt.Tooltip("Success:Q", title="Success %"), "Fatal calls"])
            text = base.mark_text(align="left", dx=4, color="#52514e").encode(
                x="Avg score:Q", text=alt.Text("label:N")).transform_calculate(
                label="format(datum['Avg score'], '.1f') + (datum['Fatal calls'] > 0 ? '  ⛔' + datum['Fatal calls'] : '')")
            st.altair_chart((bars + text).properties(height=max(170, 46 * len(d) + 40)), width="stretch")
        with e2:
            st.dataframe(t[["Executive", "Calls", "Avg score", "Success", "Fatal calls", "Coaching point"]], hide_index=True,
                         width="stretch", column_config={
                             "Avg score": st.column_config.ProgressColumn("Avg score", min_value=0, max_value=10, format="%.1f"),
                             "Success": st.column_config.ProgressColumn("Success", min_value=0, max_value=100, format="%d%%"),
                             "Coaching point": st.column_config.TextColumn(width="large")})

        # scorecard heatmap
        rows = []
        for e, g in v.groupby("Executive"):
            for k, label in AREAS.items():
                r = g[f"{k}__rating"].dropna()
                r = r[r != "Not applicable"]
                if len(r):
                    rows.append({"Executive": e, "Area": label, "Good": (r == "Good").mean() * 100, "n": len(r)})
        if rows:
            st.markdown("#### 🧭 Scorecard by executive · share of calls rated Good")
            hm = pd.DataFrame(rows)
            base = alt.Chart(hm).encode(x=alt.X("Area:N", sort=list(AREAS.values()), title=None, axis=alt.Axis(labelAngle=0, labelLimit=140)),
                                        y=alt.Y("Executive:N", title=None))
            rect = base.mark_rect(cornerRadius=4, stroke="white", strokeWidth=2).encode(
                color=alt.Color("Good:Q", scale=alt.Scale(domain=[0, 50, 100], range=[BAD, "#f3d27a", GOOD]), legend=None),
                tooltip=["Executive", "Area", alt.Tooltip("Good:Q", format=".0f", title="% Good"), alt.Tooltip("n:Q", title="Calls")])
            txt = base.mark_text(fontWeight="bold", color="#1d1d1b").encode(text=alt.Text("Good:Q", format=".0f"))
            st.altair_chart((rect + txt).properties(height=max(120, 40 * hm["Executive"].nunique() + 40)), width="stretch")

        # trend
        dated = v.dropna(subset=["Date"])
        if len(dated):
            wk = dated.assign(Week=dated["Date"].dt.to_period("W").dt.start_time)
            tr = wk.groupby("Week").agg(Score=("Score", "mean"), Success=("Success", "mean"), Calls=("id", "size")).reset_index()
            if len(tr) >= 2:
                st.markdown("#### 📈 Trend by week")
                tr["Success %"] = tr["Success"] * 100
                base = alt.Chart(tr).encode(x=alt.X("Week:T", title=None, axis=alt.Axis(format="%d %b")))
                s1 = base.mark_line(point=True, color=BLUE).encode(
                    y=alt.Y("Score:Q", title="Avg score", scale=alt.Scale(domain=[0, 10])),
                    tooltip=[alt.Tooltip("Week:T", format="%d %b"), alt.Tooltip("Score:Q", format=".1f"), "Calls"])
                s2 = base.mark_line(point=True, color=GOOD, strokeDash=[5, 3]).encode(
                    y=alt.Y("Success %:Q", title="Success %", scale=alt.Scale(domain=[0, 100])),
                    tooltip=[alt.Tooltip("Week:T", format="%d %b"), alt.Tooltip("Success %:Q", format=".0f"), "Calls"])
                st.altair_chart(alt.layer(s1, s2).resolve_scale(y="independent").properties(height=230), width="stretch")
                st.caption("Blue: average score (left axis) · green dashed: success rate (right axis)")

        # top issues
        issues = {k: c for k, c in top_issues(v).items() if c}
        if issues:
            st.markdown("#### 🎯 Where calls go wrong most often")
            tabs = st.tabs(list(issues))
            colors = [WARN, BAD, "#8e44ad"]
            for tab, (name, cnt), color in zip(tabs, issues.items(), colors):
                with tab:
                    st.altair_chart(_bar(cnt, color, "Times"), width="stretch")

    if data["product_and_objections"]:
        st.markdown("#### ❓ Product knowledge & objections")
        st.markdown("".join(card(w.get("point"), w.get("evidence"), "#8e44ad", "📘") for w in data["product_and_objections"]),
                    unsafe_allow_html=True)
    if data["pitch_changes"]:
        st.markdown("#### 🔁 Pitch changes over time")
        st.markdown(card("What changed", data["pitch_changes"], BLUE, "🗓️"), unsafe_allow_html=True)

    if data["improvements"]:
        st.markdown("#### 🛠️ Action plan")
        order = {"High": 0, "Medium": 1, "Low": 2}
        imps = sorted(data["improvements"], key=lambda x: order.get(x["priority"], 1))
        cols = st.columns(min(3, len(imps)))
        for i, x in enumerate(imps):
            color = PRIO.get(x["priority"], BLUE)
            chip = (f"<span style='background:{color};color:white;border-radius:999px;padding:1px 9px;font-size:.72rem;"
                    f"font-weight:700'>{x['priority']} priority</span>")
            cols[i % len(cols)].markdown(card(f"{i + 1}. {x.get('action', '')}", x.get("why", ""), color, "", chip),
                                         unsafe_allow_html=True)


def pdf_extras(rep: dict, flat: pd.DataFrame) -> tuple[list, list]:
    """KPI tiles and bar charts for the PDF."""
    v = flat[flat["id"].isin(rep.get("ids") or [])] if not flat.empty and rep.get("data") else flat.iloc[0:0]
    if not len(v):
        return [], []
    tiles = kpis(v)
    t = exec_table(v, rep["data"])
    charts = [("Average score by executive (out of 10)",
               [(e, s, f"{s:.1f}" + (f"  · {f} fatal" if f else ""), GOOD if s >= 7 else WARN if s >= 5 else BAD)
                for e, s, f in zip(t["Executive"], t["Avg score"], t["Fatal calls"])], 10)]
    for (name, cnt), color in zip(top_issues(v).items(), [WARN, BAD, "#8e44ad"]):
        if cnt:
            top = cnt.most_common(6)
            charts.append((name, [(k, n, str(n), color) for k, n in top], max(n for _, n in top)))
    return tiles, charts
