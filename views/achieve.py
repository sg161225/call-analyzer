"""Achieve / miss view of a call type's checklist: section scorecards, top misses,
a call-by-call grid and executive x section achievement."""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from callanalyzer.calltypes import sections_for, short_label

GOOD, WARN, BAD, NA = "#0ca30c", "#fab219", "#d03b3b", "#c3c2b7"


def _status(rate: float | None) -> tuple[str, str, str]:
    """(colour, icon, label) for an achievement rate."""
    if rate is None:
        return NA, "➖", "No data"
    if rate >= 0.8:
        return GOOD, "✅", "On track"
    if rate >= 0.5:
        return WARN, "⚠️", "Needs work"
    return BAD, "❌", "Mostly missed"


def checklist_long(view: pd.DataFrame, ctype: str) -> pd.DataFrame:
    """One row per (call, checklist item) with Achieved / Missed / N/A."""
    order = {item: (si, ii) for si, (_, items) in enumerate(sections_for(ctype)) for ii, item in enumerate(items)}
    section_of = {item: name for name, items in sections_for(ctype) for item in items}
    rows = []
    for _, r in view.iterrows():
        given = {c["item"]: c for c in r["Checklist"] or []}
        if not given:
            continue
        label = f"{r['Executive']} · {r['Customer'] or r['Mobile'] or r['File']}"
        if pd.notna(r["Date"]):
            label += f" · {r['Date']:%d %b}"
        for item in order:
            c = given.get(item, {})
            done = c.get("done")
            rows.append({
                "id": r["id"], "Call": label, "Date": r["Date"], "Executive": r["Executive"],
                "Section": section_of[item], "Item": item, "Short": short_label(item),
                "Status": {"Yes": "Achieved", "No": "Missed"}.get(done, "N/A"),
                "Evidence": c.get("evidence", ""), "_s": order[item][0], "_i": order[item][1],
            })
    return pd.DataFrame(rows)


def render(view: pd.DataFrame, ctype: str) -> None:
    st.subheader("✅ Achieved vs ❌ missed")
    long = checklist_long(view, ctype)
    if long.empty:
        st.caption("No checklist data for these calls yet (reviews made before checklists existed). "
                   "New uploads fill this in automatically.")
        return
    calls = long["id"].nunique()
    app = long[long["Status"] != "N/A"]
    st.caption(f"Based on {calls} call(s). Each checklist point is **achieved** when the executive did it on the "
               "call, **missed** when they didn't; points that didn't apply to a call are left out.")

    # ---- section scorecards ----------------------------------------------------------
    sec_order = [name for name, _ in sections_for(ctype)]
    cards = []
    for name in sec_order:
        s = app[app["Section"] == name]
        ach, tot = int((s["Status"] == "Achieved").sum()), len(s)
        rate = ach / tot if tot else None
        color, icon, label = _status(rate)
        pct = "—" if rate is None else f"{rate:.0%}"
        width = 0 if rate is None else max(2, rate * 100)
        cards.append(f"""
<div style="border:1px solid rgba(128,128,128,.28);border-radius:10px;padding:12px 14px;">
  <div style="font-size:.85rem;opacity:.75">{name}</div>
  <div style="font-size:1.9rem;font-weight:600;line-height:1.3">{pct}</div>
  <div style="height:8px;border-radius:4px;background:rgba(128,128,128,.18);overflow:hidden;margin:4px 0 6px">
    <div style="width:{width:.0f}%;height:100%;background:{color};border-radius:4px"></div></div>
  <div style="font-size:.8rem">{icon} {label} <span style="opacity:.65">· {ach} of {tot} checks</span></div>
</div>""")
    st.markdown(f"""<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:12px;
margin:6px 0 18px">{''.join(cards)}</div>""", unsafe_allow_html=True)

    # ---- top misses / best achieved ----------------------------------------------------
    per_item = app.groupby(["Item", "Short", "Section", "_s", "_i"]).agg(
        Achieved=("Status", lambda x: int((x == "Achieved").sum())),
        Missed=("Status", lambda x: int((x == "Missed").sum()))).reset_index()
    per_item["Total"] = per_item["Achieved"] + per_item["Missed"]
    per_item["Rate"] = per_item["Achieved"] / per_item["Total"]
    c1, c2 = st.columns(2, gap="large")
    with c1:
        with st.container(border=True):
            st.markdown("**❌ Most missed**")
            miss = per_item[per_item["Missed"] > 0].sort_values(["Rate", "Missed"], ascending=[True, False]).head(6)
            if miss.empty:
                st.markdown("Nothing missed. 🎉")
            for _, m in miss.iterrows():
                st.markdown(f"- **{m['Short']}** <span style='opacity:.7'>({m['Section']})</span>: missed in "
                            f"**{m['Missed']} of {m['Total']}** calls", unsafe_allow_html=True)
    with c2:
        with st.container(border=True):
            st.markdown("**✅ Done best**")
            best = per_item[per_item["Achieved"] > 0].sort_values(["Rate", "Achieved"], ascending=[False, False]).head(6)
            if best.empty:
                st.markdown("Nothing achieved yet.")
            for _, b in best.iterrows():
                st.markdown(f"- **{b['Short']}** <span style='opacity:.7'>({b['Section']})</span>: done in "
                            f"**{b['Achieved']} of {b['Total']}** calls", unsafe_allow_html=True)

    # ---- call-by-call grid ---------------------------------------------------------------
    st.markdown("**Call by call** · hover a square to see what happened")
    recent_ids = (long.drop_duplicates("id").sort_values("Date", ascending=False)["id"].head(30).tolist())
    grid = long[long["id"].isin(recent_ids)].copy()
    if calls > 30:
        st.caption(f"Showing the 30 most recent of {calls} calls. Use the filters above to narrow down.")
    grid["Mark"] = grid["Status"].map({"Achieved": "✓", "Missed": "✗", "N/A": "–"})
    grid["Col"] = grid.apply(lambda r: f"{r['Executive']} · {r['Date']:%d %b}" if pd.notna(r["Date"]) else r["Executive"], axis=1)
    # Two calls by the same executive on the same day need distinct column names.
    grid["Col"] = grid["Col"] + grid.groupby("Col")["id"].transform(
        lambda ids: ids.rank(method="dense").astype(int).map(lambda k: "" if k == 1 else f" ({k})"))
    col_order = grid.drop_duplicates("id").sort_values("Date", ascending=False)["Col"].tolist()
    base = alt.Chart().encode(
        x=alt.X("Col:N", sort=col_order, title=None,
                axis=alt.Axis(labelAngle=-60, labelLimit=150, labelFontSize=11, labelOverlap=False, orient="top")),
        y=alt.Y("Short:N", sort=alt.EncodingSortField("_i"), title=None, axis=alt.Axis(labelLimit=160)),
        tooltip=[alt.Tooltip("Call:N"), alt.Tooltip("Item:N", title="Checklist point"),
                 alt.Tooltip("Status:N"), alt.Tooltip("Evidence:N", title="What happened")])
    cells = base.mark_rect(cornerRadius=4, stroke="white", strokeWidth=2).encode(
        color=alt.Color("Status:N", scale=alt.Scale(domain=["Achieved", "Missed", "N/A"], range=[GOOD, BAD, NA]),
                        legend=alt.Legend(orient="top", title=None)))
    marks = base.mark_text(fontSize=12, fontWeight="bold").encode(text="Mark:N", color=alt.value("white"))
    chart = alt.layer(cells, marks, data=grid).properties(width=alt.Step(34), height=alt.Step(26)).facet(
        row=alt.Row("Section:N", sort=sec_order, title=None,
                    header=alt.Header(labelAngle=0, labelAlign="left", labelAnchor="start", labelOrient="top",
                                      labelFontWeight="bold", labelFontSize=12, labelPadding=4)),
        spacing=6).resolve_scale(y="independent")
    st.altair_chart(chart, width="content")

    # ---- executive x section ------------------------------------------------------------
    st.markdown("**By executive** · share of checklist points achieved")
    ex = app.assign(a=(app["Status"] == "Achieved").astype(float))
    tbl = ex.pivot_table(index="Executive", columns="Section", values="a", aggfunc="mean")
    tbl = (tbl.reindex(columns=[s for s in sec_order if s in tbl.columns]) * 100).round()
    tbl.insert(0, "Overall", (ex.groupby("Executive")["a"].mean() * 100).round())
    tbl.insert(0, "Calls", long.groupby("Executive")["id"].nunique())
    tbl = tbl.sort_values("Overall", ascending=False).reset_index()
    cfg = {c: st.column_config.ProgressColumn(c, min_value=0, max_value=100, format="%d%%", width="small")
           for c in tbl.columns if c not in ("Executive", "Calls")}
    cfg["Calls"] = st.column_config.NumberColumn("Calls", width="small")
    st.dataframe(tbl, hide_index=True, width="stretch", column_config=cfg)
