from io import BytesIO

import altair as alt
import pandas as pd
import streamlit as st

from views import call_view
from views.common import BADGE, PARAMETERS, RATED, badge, checklist_summary, export_frame, filters, inr, load_flat
from callanalyzer.calltypes import CALL_TYPES
from callanalyzer.quality import SHORT_FATAL, SOFT_SKILLS
from callanalyzer import store
from callanalyzer.config import load_settings
from callanalyzer.review import DailyLimit
from callanalyzer.pipeline import can_retry, retry_review

# Status colours (good / warning / critical), always shown with a label.
STATUS_DOMAIN = ["Good", "Partial", "Weak"]
STATUS_RANGE = ["#0ca30c", "#fab219", "#d03b3b"]
SEQ_RANGE = ["#cde2fb", "#1c5cab"]  # single-hue blue ramp for magnitude
POSITIVE = {"Converted / Retained", "Issue resolved", "Follow-up scheduled"}

@st.dialog("Delete calls?")
def confirm_delete(ids: list[int]) -> None:
    st.write(f"This permanently deletes **{len(ids)} call review(s)**. It can't be undone.")
    st.caption("Tip: download the Excel sheet first if you may need these reviews later.")
    c1, c2 = st.columns(2)
    if c1.button("Yes, delete", type="primary", width="stretch"):
        store.delete_calls(ids)
        st.session_state.pop("calls_table", None)
        st.rerun()
    if c2.button("Cancel", width="stretch"):
        st.rerun()


st.title("📋 Call reviews")
raw, flat = load_flat()

failed = raw[raw["status"] == "error"]
if msg := st.session_state.pop("retry_msg", None):
    (st.success if msg[0] else st.error)(msg[1])
if not failed.empty:
    retryable = [int(r["id"]) for _, r in failed.iterrows() if can_retry(r)]
    with st.expander(f"⚠️ {len(failed)} call(s) failed to process", expanded=True):
        st.caption("🔁 Retry runs only the AI review again from the saved transcript (no new transcription). "
                   "Free-tier limits reset every minute and every day.")

        def _retry(ids: list[int]) -> None:
            ok, errs = 0, []
            with st.spinner(f"Reviewing {len(ids)} call(s) again… this can take a minute per call."):
                for cid in ids:
                    try:
                        retry_review(cid, load_settings())
                        ok += 1
                    except DailyLimit as e:      # no point trying the rest today
                        errs.insert(0, str(e).split(" The transcript")[0])
                        break
                    except Exception as e:  # noqa: BLE001 - shown to the user
                        errs.append(str(e)[:200])
            st.session_state["retry_msg"] = (not errs, f"{ok} of {len(ids)} call(s) reviewed."
                                             + (f" Still failing: {errs[0]}" if errs else ""))

        if len(retryable) > 1:
            st.button(f"🔁 Retry all {len(retryable)}", on_click=_retry, args=(retryable,), key="retry_all")
        for _, r in failed.iterrows():
            c1, c2, c3 = st.columns([7, 1, 1])
            c1.markdown(f"**{r['file_name']}**  \n<span style='opacity:.8;font-size:.88em'>{r['error']}</span>",
                        unsafe_allow_html=True)
            if int(r["id"]) in retryable:
                c2.button("🔁 Retry", key=f"rt_{r['id']}", on_click=_retry, args=([int(r["id"])],), width="stretch")
            else:
                c2.caption("Upload again")
            if c3.button("Remove", key=f"rm_{r['id']}", width="stretch"):
                store.delete_call(int(r["id"]))
                st.rerun()

if flat.empty:
    st.info("No reviewed calls yet. Go to **Upload calls** to add recordings.")
    st.stop()

view = filters(flat, "dash")
if st.toggle("⛔ Fatal calls only", key="dash_fatal", help="Calls where the executive made a blunder (see Overview)"):
    view = view[view["Fatal"] == True]  # noqa: E712
if view.empty:
    st.warning("No calls match these filters.")
    st.stop()

# ---- headline tiles ---------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Calls reviewed", len(view))
k2.metric("Average score", f"{view['Score'].mean():.1f} / 10")
k3.metric("Positive outcome", f"{view['Positive'].mean():.0%}",
          help="Payment received or promised, demo booked, follow-up agreed, or issue resolved")
weakest = min(RATED, key=lambda k: view[f"{k}__score"].mean(skipna=True) if view[f"{k}__score"].notna().any() else 9)
SHORT = {"business_probing": "Probing", "need_generation": "Need gen.", "pitch": "Pitch",
         "customer_queries": "Queries", "objection_handling": "Objections"}
k4.metric("Weakest area", SHORT[weakest], help=PARAMETERS[weakest])

tab_calls, tab_agents, tab_time = st.tabs(["📋 Calls", "👥 Compare executives", "📈 Pitch over time"])

# ---- calls table ----------------------------------------------------------------
with tab_calls:
    show_notes = st.toggle("Show notes in table", value=False,
                           help="Off: ratings only. Tick a row to see its full review below.")
    table = pd.DataFrame({
        "⛔": view["Fatal"].map({True: "⛔ FATAL", False: "", None: ""}),
        "Date": view["Date"].dt.strftime("%d %b %Y"),
        "Type": view["Call type"].map(lambda t: f"{CALL_TYPES.get(t, {}).get('icon', '')} {t}"),
        "Executive": view["Executive"], "Mobile": view["Mobile"], "Customer": view["Customer"], "Outcome": view["Outcome"], "Score": view["Score"],
    })
    for key, label in PARAMETERS.items():
        if key in RATED:
            table[label] = view[f"{key}__rating"].map(badge)
            if show_notes:
                table[label] = table[label] + " · " + view[f"{key}__text"]
        else:
            table[label] = view[f"{key}__text"]
    cfg = {"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=10, format="%d"),
           "Mobile": st.column_config.TextColumn("Mobile", width="medium")}
    sel = st.dataframe(table, hide_index=True, width="stretch", column_config=cfg,
                       on_select="rerun", selection_mode="multi-row", key="calls_table")

    exp = export_frame(view)
    c1, c2, _ = st.columns([1, 1, 4])
    buf = BytesIO()
    exp.to_excel(buf, index=False, sheet_name="Call reviews")
    c1.download_button("⬇️ Excel", buf.getvalue(), "call_reviews.xlsx", width="stretch")
    c2.download_button("⬇️ CSV", exp.to_csv(index=False).encode("utf-8-sig"), "call_reviews.csv",
                       width="stretch")

    rows = sel.selection.rows if sel and sel.selection else []
    ids = [int(view.iloc[i]["id"]) for i in rows]
    if ids:
        st.divider()
        st.markdown(f"**{len(ids)} call(s) ticked**")
        with st.form("bulk_edit", border=True):
            st.caption("Fix call details for the ticked calls. Leave a box empty to keep what's there.")
            one = len(ids) == 1
            cols = st.columns(6 if one else 5)
            c1, c2, c3, c4, c5 = cols[:5]
            ct = c5.selectbox("Call type", ["(keep)", *CALL_TYPES])
            mob = cols[5].text_input("Mobile") if one else ""
            ex = c1.text_input("Executive")
            dt = c2.date_input("Call date", value=None, format="DD/MM/YYYY")
            cp = c3.text_input("Campaign")
            pv = c4.text_input("Pitch version")
            if st.form_submit_button(f"✏️ Apply to {len(ids)} call(s)"):
                fields = {k: v for k, v in {"executive": ex.strip(), "campaign": cp.strip(), "mobile": mob.strip(),
                                            "pitch_version": pv.strip(),
                                            "call_type": "" if ct == "(keep)" else ct,
                                            "call_date": dt.isoformat() if dt else ""}.items() if v}
                for i in ids:
                    store.update_meta(i, **fields)
                st.session_state.pop("calls_table", None)
                st.rerun()
        if st.button(f"🗑️ Delete {len(ids)} ticked call(s)", type="secondary"):
            confirm_delete(ids)
    # Which call to show in full: the most recently ticked row, or the one reached with Previous / Next.
    ticked = [int(view.iloc[i]["id"]) for i in rows]
    newly = [i for i in ticked if i not in st.session_state.get("prev_ticked", [])]
    st.session_state["prev_ticked"] = ticked
    if newly:
        st.session_state["detail_id"] = newly[-1]
    nav_ids = [int(i) for i in view["id"]]
    detail_id = st.session_state.get("detail_id")
    if ticked and detail_id in nav_ids:
        r = view[view["id"] == detail_id].iloc[0]
        raw_row = raw[raw["id"] == detail_id].iloc[0]
        st.divider()
        call_view.render(r, raw_row["review"], raw_row, nav_ids)
    elif not rows:
        st.caption("Tick a row to see its full review. Tick several to fix their details or delete them together.")

# ---- executive comparison --------------------------------------------------------
with tab_agents:
    long = view.melt(id_vars=["Executive"], value_vars=[f"{k}__rating" for k in RATED],
                     var_name="param", value_name="Rating").dropna()
    long = long[long["Rating"].isin(STATUS_DOMAIN)]
    long["Parameter"] = long["param"].str.replace("__rating", "").map(PARAMETERS)
    order = [PARAMETERS[k] for k in RATED]

    st.markdown("**Average rating by executive and parameter** (1 = Weak, 2 = Partial, 3 = Good)")
    heat = long.assign(s=long["Rating"].map({"Good": 3, "Partial": 2, "Weak": 1})) \
        .groupby(["Executive", "Parameter"], as_index=False).agg(avg=("s", "mean"), calls=("s", "size"))
    base = alt.Chart(heat).encode(
        x=alt.X("Parameter:N", sort=order, title=None, axis=alt.Axis(labelAngle=0, labelLimit=160)),
        y=alt.Y("Executive:N", title=None),
        tooltip=["Executive", "Parameter", alt.Tooltip("avg:Q", format=".2f", title="Avg rating"), "calls"])
    rect = base.mark_rect(cornerRadius=4, stroke="white", strokeWidth=2).encode(
        color=alt.Color("avg:Q", scale=alt.Scale(domain=[1, 3], range=SEQ_RANGE), title="Avg rating"))
    text = base.mark_text(fontSize=13).encode(
        text=alt.Text("avg:Q", format=".1f"),
        color=alt.condition("datum.avg > 2.2", alt.value("white"), alt.value("#0b0b0b")))
    st.altair_chart((rect + text).properties(height=max(120, 48 * heat["Executive"].nunique())),
                    width="stretch")

    st.markdown("**Rating mix per parameter, by executive**")
    mix = long.groupby(["Executive", "Parameter", "Rating"], as_index=False).size()
    bars = alt.Chart(mix).mark_bar(cornerRadiusEnd=4, stroke="white", strokeWidth=2).encode(
        y=alt.Y("Executive:N", title=None),
        x=alt.X("size:Q", stack="normalize", title="Share of calls", axis=alt.Axis(format="%")),
        color=alt.Color("Rating:N", scale=alt.Scale(domain=STATUS_DOMAIN, range=STATUS_RANGE),
                        legend=alt.Legend(orient="top", title=None)),
        order=alt.Order("rating_order:Q"),
        tooltip=["Executive", "Parameter", "Rating", alt.Tooltip("size:Q", title="Calls")],
    ).transform_calculate(rating_order="indexof(['Good','Partial','Weak'], datum.Rating)") \
     .properties(height=max(60, 28 * mix["Executive"].nunique()))
    st.altair_chart(bars.facet(row=alt.Row("Parameter:N", sort=order, title=None,
                                           header=alt.Header(labelAngle=0, labelAlign="left", labelFontWeight="bold"))),
                    width="stretch")

    summary = view.groupby("Executive").agg(
        Calls=("id", "size"), **{"Avg score": ("Score", "mean")},
        **{"Positive outcome": ("Outcome", lambda s: s.isin(POSITIVE).mean())}).reset_index()
    for k in RATED:
        summary[PARAMETERS[k]] = view.groupby("Executive")[f"{k}__score"].mean().values
    st.markdown("**Summary table**")
    st.dataframe(summary, hide_index=True, width="stretch", column_config={
        "Avg score": st.column_config.NumberColumn(format="%.1f"),
        "Positive outcome": st.column_config.NumberColumn(format="percent"),
        **{PARAMETERS[k]: st.column_config.NumberColumn(format="%.1f") for k in RATED}})

# ---- pitch over time --------------------------------------------------------------
with tab_time:
    execs = view["Executive"].value_counts().index.tolist()  # most calls first
    who = st.selectbox("Executive", execs, key="time_exec")
    ev = view[view["Executive"] == who].dropna(subset=["Date"]).sort_values("Date")
    if len(ev) < 2:
        st.info("Upload at least 2 calls on different dates for this executive to see how their pitch changes.")
    else:
        st.markdown(f"**Call score over time for {who}**")
        pts = ev.assign(DateStr=ev["Date"].dt.strftime("%d %b %Y"))
        hover = alt.selection_point(fields=["Date"], nearest=True, on="pointerover", empty=False)
        line = alt.Chart(pts).mark_line(strokeWidth=2, color="#2a78d6").encode(
            x=alt.X("Date:T", title=None), y=alt.Y("Score:Q", scale=alt.Scale(domain=[0, 10]), title="Score"))
        dots = line.mark_point(size=140, filled=True, color="#2a78d6", stroke="white", strokeWidth=2).encode(
            tooltip=["DateStr", "Customer", "Outcome", "Score", "Pitch version"]).add_params(hover)
        st.altair_chart(line + dots, width="stretch")

        group_by = st.radio("Compare by", ["Pitch version", "Month"], horizontal=True,
                            help="Tag calls with a pitch version on upload (e.g. 'v1 old script', 'v2 new offer') to measure a pitch change.")
        key = ev["Pitch version"].replace("", "(untagged)") if group_by == "Pitch version" else ev["Date"].dt.strftime("%Y-%m")
        g = ev.assign(Group=key).groupby("Group")
        comp = g.agg(Calls=("id", "size"), **{"Avg score": ("Score", "mean")},
                     **{"Positive outcome": ("Outcome", lambda s: s.isin(POSITIVE).mean())})
        for k in RATED:
            comp[PARAMETERS[k]] = g[f"{k}__score"].mean()
        comp = comp.reset_index()
        st.dataframe(comp, hide_index=True, width="stretch", column_config={
            "Avg score": st.column_config.NumberColumn(format="%.1f"),
            "Positive outcome": st.column_config.NumberColumn(format="percent"),
            **{PARAMETERS[k]: st.column_config.NumberColumn(format="%.1f") for k in RATED}})
        if len(comp) >= 2:
            first, last = comp.iloc[0], comp.iloc[-1]
            st.markdown(f"**Change from {first['Group']} → {last['Group']}**")
            cols = st.columns(len(RATED) + 1)
            cols[0].metric("Avg score", f"{last['Avg score']:.1f}", f"{last['Avg score'] - first['Avg score']:+.1f}")
            for c, k in zip(cols[1:], RATED):
                lab = PARAMETERS[k]
                if pd.notna(last[lab]) and pd.notna(first[lab]):
                    c.metric(lab, f"{last[lab]:.1f}", f"{last[lab] - first[lab]:+.1f}")
            st.caption("Ratings are 1–3. Small samples (a few calls) can swing a lot, so treat early numbers as a signal, not proof. "
                       "Use **AI insights** for a written comparison of what changed in the pitch.")
