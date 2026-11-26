from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from views.common import inr, load_flat
from callanalyzer.calltypes import CALL_TYPES, CHECKLISTS, FUNNEL_STAGES, SALES_TYPES, STAGE_OF_OUTCOME
from callanalyzer.playbook import PLAYBOOKS
from callanalyzer.review import PARAMETERS

TYPE_COLORS = {"New Sales": "#2a78d6", "Mobile App": "#eb6834", "Renewal": "#1baf7a",
               "Upsell": "#eda100", "CLM": "#e87ba4"}
BLUE, BLUE_LIGHT, ORANGE = "#2a78d6", "#b7d3f6", "#eb6834"
RATED = ["business_probing", "need_generation", "pitch", "customer_queries", "objection_handling"]

st.title("📈 Overview")
raw, flat = load_flat()
if flat.empty:
    st.info("No reviewed calls yet. Go to **Upload calls** to add recordings.")
    st.stop()

# ---- filters: call-type switch, executive, dates -----------------------------------
present = [t for t in CALL_TYPES if t in set(flat["Call type"])]
ctype = st.segmented_control(
    "Call type", ["All", *CALL_TYPES], default="All", key="ov_type", label_visibility="collapsed",
    format_func=lambda t: "All calls" if t == "All" else f"{CALL_TYPES[t]['icon']} {t}") or "All"
c1, c2 = st.columns(2)
sel_e = c1.multiselect("Executive", sorted(flat["Executive"].unique()), placeholder="All executives", key="ov_e")
dates = flat["Date"].dropna()
rng = c2.date_input("Call date", (dates.min().date(), dates.max().date()), key="ov_d") if not dates.empty else None

view = flat if ctype == "All" else flat[flat["Call type"] == ctype]
if sel_e:
    view = view[view["Executive"].isin(sel_e)]
if rng and isinstance(rng, tuple) and len(rng) == 2:
    view = view[view["Date"].isna() | ((view["Date"].dt.date >= rng[0]) & (view["Date"].dt.date <= rng[1]))]
if view.empty:
    st.warning(f"No {ctype if ctype != 'All' else ''} calls match these filters.")
    st.stop()

is_clm = ctype == "CLM"
sales = view[view["Call type"].isin(SALES_TYPES)]
today = pd.Timestamp(date.today())
open_fu = view[(~view["Follow-up done"]) & (view["Next step"].str.strip() != "")
               & (~view["Outcome"].isin(["Payment received", "Not interested / Lost"]))]
due_soon = open_fu[open_fu["Next step date"].notna() & (open_fu["Next step date"] <= today + timedelta(days=7))]
at_risk = view[view["Risk"].isin(["Medium", "High"])]


def _delta(series_fn) -> str | None:
    """Change: last 7 days vs the 7 days before (by call date)."""
    d = view.dropna(subset=["Date"])
    if d.empty:
        return None
    end = d["Date"].max()
    cur = d[d["Date"] > end - timedelta(days=7)]
    prev = d[(d["Date"] <= end - timedelta(days=7)) & (d["Date"] > end - timedelta(days=14))]
    if cur.empty or prev.empty:
        return None
    a, b = series_fn(cur), series_fn(prev)
    return None if a is None or b is None else a - b


def _rate(df: pd.DataFrame, col: str = "Success") -> float | None:
    return float(df[col].mean()) if len(df) else None


# ---- KPI cards -------------------------------------------------------------------------
k = st.columns(5)
k[0].metric("Calls audited", len(view), border=True)
d = _delta(lambda x: x["Score"].mean())
k[1].metric("Average score", f"{view['Score'].mean():.1f} / 10", None if d is None else f"{d:+.1f}", border=True,
            help="Change: last 7 days vs the 7 days before")
if is_clm:
    r = _rate(view)
    d = _delta(_rate)
    k[2].metric("Resolved / healthy", f"{r:.0%}", None if d is None else f"{d * 100:+.0f} pts", border=True,
                help="CLM success: issue resolved, or customer ends the call satisfied with no risk signals")
    k[3].metric("At-risk customers", len(at_risk), border=True, help="Medium or high risk of losing the customer")
else:
    r = _rate(sales)
    d = _delta(lambda x: _rate(x[x["Call type"].isin(SALES_TYPES)]))
    won = sales.loc[sales["Outcome"] == "Payment received", "Deal value"].sum()
    pipe = sales.loc[sales["Outcome"] == "Payment promised", "Deal value"].sum()
    k[2].metric("Conversion", "—" if r is None else f"{r:.0%}", None if d is None else f"{d * 100:+.0f} pts", border=True,
                help="Sales calls where payment was received")
    k[3].metric("Revenue won", inr(won), border=True,
                help=f"Deal value of calls with payment received. Pipeline (payment promised): {inr(pipe)}")
k[4].metric("Follow-ups due", len(due_soon), border=True,
            help=f"Due in the next 7 days (or overdue). {len(open_fu)} open follow-ups in total: see the Follow-ups page.")

if not is_clm and len(sales):
    pipe = sales.loc[sales["Outcome"] == "Payment promised", "Deal value"].sum()
    st.caption(f"💰 Pipeline (payment promised): **{inr(pipe)}** · "
               f"⚠️ At-risk customers: **{len(at_risk)}** · Success = payment received")

# ---- row 1: funnel / outcomes + calls by type or why we lose -------------------------
left, right = st.columns(2, gap="large")
with left:
    if is_clm:
        st.markdown("**How CLM calls ended**")
        oc = view["Outcome"].value_counts().rename_axis("Outcome").reset_index(name="Calls")
        chart = alt.Chart(oc).mark_bar(color=BLUE, cornerRadiusEnd=4).encode(
            y=alt.Y("Outcome:N", sort="-x", title=None), x=alt.X("Calls:Q", title="Calls", axis=alt.Axis(tickMinStep=1)),
            tooltip=["Outcome", "Calls"])
        st.altair_chart((chart + chart.mark_text(align="left", dx=4).encode(text="Calls:Q", color=alt.value("#52514e"))
                         ).properties(height=34 * len(oc) + 30), width="stretch")
    else:
        st.markdown("**Sales funnel**" + ("" if ctype != "All" else " (all sales types)"))
        base = sales if len(sales) else view
        stage = base["Outcome"].map(STAGE_OF_OUTCOME).fillna(1)
        fun = pd.DataFrame({"Stage": FUNNEL_STAGES,
                            "Calls": [int((stage >= i + 1).sum()) if i else len(base) for i in range(len(FUNNEL_STAGES))]})
        fun["Share"] = fun["Calls"] / max(1, len(base))
        fun["Label"] = fun.apply(lambda r: f"{r.Calls}  ({r.Share:.0%})", axis=1)
        chart = alt.Chart(fun).mark_bar(color=BLUE, cornerRadiusEnd=4).encode(
            y=alt.Y("Stage:N", sort=FUNNEL_STAGES, title=None),
            x=alt.X("Calls:Q", title=None, axis=alt.Axis(tickMinStep=1)),
            tooltip=["Stage", "Calls", alt.Tooltip("Share:Q", format=".0%")])
        st.altair_chart((chart + chart.mark_text(align="left", dx=4).encode(text="Label:N", color=alt.value("#52514e"))
                         ).properties(height=40 * len(fun) + 20), width="stretch")
with right:
    if ctype == "All":
        st.markdown("**Calls and average score by call type**")
        bt = view.groupby("Call type").agg(Calls=("id", "size"), Score=("Score", "mean")).reindex(present).dropna(how="all").reset_index()
        bt["Label"] = bt.apply(lambda r: f"{int(r.Calls)} calls · {r.Score:.1f}/10", axis=1)
        chart = alt.Chart(bt).mark_bar(cornerRadiusEnd=4).encode(
            y=alt.Y("Call type:N", sort=present, title=None), x=alt.X("Calls:Q", title=None, axis=alt.Axis(tickMinStep=1)),
            color=alt.Color("Call type:N", scale=alt.Scale(domain=list(TYPE_COLORS), range=list(TYPE_COLORS.values())),
                            legend=None),
            tooltip=["Call type", "Calls", alt.Tooltip("Score:Q", format=".1f", title="Avg score")])
        st.altair_chart((chart + chart.mark_text(align="left", dx=4).encode(text="Label:N", color=alt.value("#52514e"))
                         ).properties(height=40 * len(bt) + 20), width="stretch")
    else:
        st.markdown("**Why we lose** (main reason in calls that didn't succeed)")
        lost = view[(~view["Success"]) & (view["Loss reason"] != "None")]
        if lost.empty:
            st.caption("No loss reasons recorded for these calls yet.")
        else:
            lr = lost["Loss reason"].value_counts().rename_axis("Reason").reset_index(name="Calls")
            chart = alt.Chart(lr).mark_bar(color=ORANGE, cornerRadiusEnd=4).encode(
                y=alt.Y("Reason:N", sort="-x", title=None, axis=alt.Axis(labelLimit=260)),
                x=alt.X("Calls:Q", title=None, axis=alt.Axis(tickMinStep=1)), tooltip=["Reason", "Calls"])
            st.altair_chart((chart + chart.mark_text(align="left", dx=4).encode(text="Calls:Q", color=alt.value("#52514e"))
                             ).properties(height=34 * len(lr) + 30), width="stretch")

# ---- what wins -------------------------------------------------------------------------
st.divider()
st.subheader("🏆 What wins")
measure = st.radio("Count as success", ["Strict", "Positive outcome"], horizontal=True, key="ov_measure",
                   captions=["Payment received (CLM: resolved / healthy)",
                             "Also payment promised, demo booked, follow-up agreed"])
col = "Success" if measure == "Strict" else "Positive"
rows = []
if ctype in CHECKLISTS:
    for i, item in enumerate(CHECKLISTS[ctype]):
        done = view["Checklist"].map(lambda cl: next((c["done"] for c in cl if c["item"] == item), None))
        y, n = view[done == "Yes"], view[done == "No"]
        rows.append({"Behaviour": item, "With": _rate(y, col), "Without": _rate(n, col), "n_with": len(y), "n_without": len(n)})
    st.caption(f"Success rate of {ctype} calls when the executive **did** vs **didn't** do each checklist item.")
else:
    for key in RATED:
        g = view[view[f"{key}__rating"] == "Good"]
        b = view[view[f"{key}__rating"].isin(["Partial", "Weak"])]
        rows.append({"Behaviour": f"{PARAMETERS[key]} rated Good", "With": _rate(g, col), "Without": _rate(b, col),
                     "n_with": len(g), "n_without": len(b)})
    st.caption("Success rate when each scorecard area was **Good** vs **Partial/Weak**. "
               "Pick a call type above to see its checklist.")
ww = pd.DataFrame(rows)
ww["Enough data"] = (ww["n_with"] >= 3) & (ww["n_without"] >= 3)
ww["Difference"] = ww["With"] - ww["Without"]
long = ww.melt(id_vars=["Behaviour", "n_with", "n_without", "Enough data"], value_vars=["With", "Without"],
               var_name="Did it?", value_name="Rate").dropna(subset=["Rate"])
long["Did it?"] = long["Did it?"].map({"With": "Did it", "Without": "Didn't"})
long["n"] = long.apply(lambda r: r.n_with if r["Did it?"] == "Did it" else r.n_without, axis=1)
if long.empty:
    st.info("Not enough calls yet to compare.")
else:
    order = ww.sort_values("Difference", ascending=False, na_position="last")["Behaviour"].tolist()
    long["Label"] = long.apply(lambda r: f"{r['Rate']:.0%} ({int(r['n'])})", axis=1)
    enc = dict(
        y=alt.Y("Behaviour:N", sort=order, title=None, axis=alt.Axis(labelLimit=380)),
        yOffset=alt.YOffset("Did it?:N", sort=["Did it", "Didn't"]),
        x=alt.X("Rate:Q", title="Success rate (number of calls in brackets)", axis=alt.Axis(format="%", values=[0, 0.25, 0.5, 0.75, 1]),
                scale=alt.Scale(domain=[0, 1.12])),
        tooltip=["Behaviour", "Did it?", alt.Tooltip("Rate:Q", format=".0%"), alt.Tooltip("n:Q", title="Calls")])
    bars = alt.Chart(long).mark_bar(cornerRadiusEnd=4).encode(
        **enc, color=alt.Color("Did it?:N", scale=alt.Scale(domain=["Did it", "Didn't"], range=[BLUE, BLUE_LIGHT]),
                               legend=alt.Legend(orient="top", title=None)),
        opacity=alt.condition("datum['Enough data']", alt.value(1), alt.value(0.45)))
    labels = alt.Chart(long).mark_text(align="left", dx=4, fontSize=11).encode(
        **enc, text="Label:N", color=alt.value("#52514e"))
    st.altair_chart((bars + labels).properties(height=max(180, 58 * len(ww))), width="stretch")
    top = ww[ww["Enough data"]].sort_values("Difference", ascending=False).head(1)
    if not top.empty and top.iloc[0]["Difference"] > 0:
        t = top.iloc[0]
        st.success(f"Biggest lift: **{t['Behaviour']}**: {t['With']:.0%} success when done vs "
                   f"{t['Without']:.0%} when not ({t['n_with']} vs {t['n_without']} calls).")
    st.caption("Faded bars have fewer than 3 calls on one side, so treat them as early signals, not proof.")

# ---- objection handling vs playbook -----------------------------------------------------
if ctype in PLAYBOOKS:
    st.divider()
    st.subheader("🛡️ Objection handling vs playbook")
    rows = []
    for _, r in view.iterrows():
        for o in r["Objections"]:
            rows.append({"Objection": o.get("objection"), "Followed": o.get("playbook_followed"),
                         "Executive": r["Executive"], "Success": bool(r[col]), "id": r["id"]})
    od = pd.DataFrame(rows)
    if od.empty:
        st.caption(f"No objections recorded yet for these {ctype} calls. New uploads are checked against the "
                   "playbook automatically (see the 📖 Playbook page).")
    else:
        pts = od["Followed"].map({"Yes": 1.0, "Partly": 0.5, "No": 0.0})
        fol, notf = od[od["Followed"] == "Yes"], od[od["Followed"] != "Yes"]
        m = st.columns(4)
        m[0].metric("Objections raised", len(od), help=f"In {od['id'].nunique()} of {len(view)} calls", border=True)
        m[1].metric("Playbook followed", f"{pts.mean():.0%}", border=True,
                    help="Share of objections answered with a playbook response (partly = half)")
        m[2].metric("Success when followed", "—" if fol.empty else f"{fol['Success'].mean():.0%}",
                    help=f"{len(fol)} objections", border=True)
        m[3].metric("Success when not followed", "—" if notf.empty else f"{notf['Success'].mean():.0%}",
                    help=f"{len(notf)} objections", border=True)

        st.markdown("**Most common objections and how they were handled**")
        cnt = od.groupby(["Objection", "Followed"]).size().reset_index(name="Times")
        cnt["Handled"] = cnt["Followed"].map({"Yes": "Followed", "Partly": "Partly", "No": "Not followed"})
        order = od["Objection"].value_counts().index.tolist()
        tot = od["Objection"].value_counts().rename_axis("Objection").reset_index(name="Total")
        bars = alt.Chart(cnt).mark_bar(stroke="white", strokeWidth=2).encode(
            y=alt.Y("Objection:N", sort=order, title=None, axis=alt.Axis(labelLimit=320)),
            x=alt.X("Times:Q", title="Times raised", axis=alt.Axis(tickMinStep=1)),
            color=alt.Color("Handled:N", scale=alt.Scale(domain=["Followed", "Partly", "Not followed"],
                                                         range=["#0ca30c", "#fab219", "#d03b3b"]),
                            legend=alt.Legend(orient="top", title=None)),
            order=alt.Order("o:Q"), tooltip=["Objection", "Handled", "Times"],
        ).transform_calculate(o="indexof(['Followed','Partly','Not followed'], datum.Handled)")
        labels = alt.Chart(tot).mark_text(align="left", dx=4).encode(
            y=alt.Y("Objection:N", sort=order), x="Total:Q", text="Total:Q", color=alt.value("#52514e"))
        st.altair_chart((bars + labels).properties(height=34 * len(order) + 40), width="stretch")

        c1, c2 = st.container(), st.container()
        with c1:
            st.markdown("**By objection**")
            g = od.groupby("Objection")
            tab = pd.DataFrame({
                "Raised": g.size(),
                "Followed": (g["Followed"].apply(lambda s: (s == "Yes").mean()) * 100).round(),
                "Success if followed": g.apply(lambda d: d.loc[d["Followed"] == "Yes", "Success"].mean() * 100, include_groups=False).round(),
                "Success if not": g.apply(lambda d: d.loc[d["Followed"] != "Yes", "Success"].mean() * 100, include_groups=False).round(),
            }).sort_values("Raised", ascending=False).reset_index()
            st.dataframe(tab, hide_index=True, width="stretch", column_config={
                "Followed": st.column_config.ProgressColumn("Playbook followed", min_value=0, max_value=100, format="%d%%"),
                "Success if followed": st.column_config.NumberColumn(format="%d%%"),
                "Success if not": st.column_config.NumberColumn(format="%d%%")})
        with c2:
            st.markdown("**By executive**")
            eg = od.assign(p=pts).groupby("Executive")
            et = pd.DataFrame({"Objections": eg.size(), "Playbook": (eg["p"].mean() * 100).round()}) \
                .sort_values("Playbook", ascending=False).reset_index()
            st.dataframe(et, hide_index=True, width="stretch", column_config={
                "Playbook": st.column_config.ProgressColumn("Playbook followed", min_value=0, max_value=100, format="%d%%")})
        st.caption("Open a call on the 📋 Call reviews page to see what the customer said, how the executive "
                   "answered, and the playbook line they should have used.")

# ---- checklist completion + executive table --------------------------------------------
left, right = st.columns(2, gap="large")
with left:
    if ctype in CHECKLISTS:
        st.markdown(f"**{ctype} checklist: how often each item is done**")
        comp = []
        for item in CHECKLISTS[ctype]:
            done = view["Checklist"].map(lambda cl: next((c["done"] for c in cl if c["item"] == item), None))
            app = done.isin(["Yes", "No"])
            if app.any():
                comp.append({"Item": item, "Done": (done[app] == "Yes").mean(), "Calls": int(app.sum())})
        if comp:
            cdf = pd.DataFrame(comp)
            chart = alt.Chart(cdf).mark_bar(color=BLUE, cornerRadiusEnd=4).encode(
                y=alt.Y("Item:N", sort="x", title=None, axis=alt.Axis(labelLimit=300)),
                x=alt.X("Done:Q", title=None, axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
                tooltip=["Item", alt.Tooltip("Done:Q", format=".0%"), "Calls"])
            st.altair_chart((chart + chart.mark_text(align="left", dx=4).encode(
                text=alt.Text("Done:Q", format=".0%"), color=alt.value("#52514e"))).properties(height=max(140, 32 * len(cdf))), width="stretch")
        else:
            st.caption("No checklist data yet for these calls (reviews made before call types existed).")
    else:
        st.markdown("**Average score by call type and executive**")
        hm = view.groupby(["Executive", "Call type"], as_index=False).agg(Score=("Score", "mean"), Calls=("id", "size"))
        base = alt.Chart(hm).encode(x=alt.X("Call type:N", sort=present, title=None, axis=alt.Axis(labelAngle=0)),
                                    y=alt.Y("Executive:N", title=None),
                                    tooltip=["Executive", "Call type", alt.Tooltip("Score:Q", format=".1f"), "Calls"])
        st.altair_chart((base.mark_rect(cornerRadius=4, stroke="white", strokeWidth=2).encode(
            color=alt.Color("Score:Q", scale=alt.Scale(domain=[1, 10], range=["#cde2fb", "#1c5cab"]), title="Avg score"))
            + base.mark_text(fontSize=12).encode(text=alt.Text("Score:Q", format=".1f"),
                                                  color=alt.condition("datum.Score > 6", alt.value("white"), alt.value("#0b0b0b")))
        ).properties(height=max(120, 40 * hm["Executive"].nunique())), width="stretch")
with right:
    st.markdown("**Executives**")
    ex = view.groupby("Executive").agg(Calls=("id", "size"), Score=("Score", "mean"),
                                       Success=("Success", "mean"), Checklist=("Checklist %", "mean"),
                                       Revenue=("Deal value", lambda s: s[view.loc[s.index, "Outcome"] == "Payment received"].sum()))
    ex = ex.sort_values("Score", ascending=False).reset_index()
    ex["Success"] = (ex["Success"] * 100).round()
    ex["Checklist"] = (ex["Checklist"] * 100).round()
    st.dataframe(ex, hide_index=True, width="stretch", column_config={
        "Score": st.column_config.ProgressColumn("Avg score", min_value=0, max_value=10, format="%.1f"),
        "Success": st.column_config.NumberColumn("Success", format="%d%%"),
        "Checklist": st.column_config.NumberColumn("Checklist done", format="%d%%"),
        "Revenue": st.column_config.NumberColumn("Revenue won (₹)", format="₹%d")})
