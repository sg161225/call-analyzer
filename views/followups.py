from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st

from views.common import inr, load_flat
from callanalyzer import store
from callanalyzer.calltypes import CALL_TYPES

st.title("📅 Follow-ups")
st.caption("Customers to call back: payment promises, demos, callbacks and escalated issues, "
           "plus customers at risk of leaving. Tick **Done** when a follow-up is completed.")

raw, flat = load_flat()
if flat.empty:
    st.info("No reviewed calls yet.")
    st.stop()

c1, c2, c3 = st.columns(3)
types = [t for t in CALL_TYPES if t in set(flat["Call type"])]
sel_t = c1.multiselect("Call type", types, placeholder="All call types",
                       format_func=lambda t: f"{CALL_TYPES[t]['icon']} {t}", key="fu_t")
sel_e = c2.multiselect("Executive", sorted(flat["Executive"].unique()), placeholder="All executives", key="fu_e")
q = c3.text_input("🔎 Search", placeholder="Mobile number or customer", key="fu_q")
view = flat
if sel_t:
    view = view[view["Call type"].isin(sel_t)]
if sel_e:
    view = view[view["Executive"].isin(sel_e)]
if q.strip():
    needle, digits = q.strip().lower(), "".join(ch for ch in q if ch.isdigit())
    hit = (view["Mobile"].fillna("") + " " + view["Customer"].fillna("")).str.lower().str.contains(needle, regex=False)
    if len(digits) >= 4:
        hit |= view["Mobile"].fillna("").str.contains(digits[-10:], regex=False)
    view = view[hit]


def _xlsx(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


tab_fu, tab_risk = st.tabs(["📅 Follow-ups", "⚠️ At-risk customers"])

with tab_fu:
    fu = view[(view["Next step"].str.strip() != "")
              & (~view["Outcome"].isin(["Payment received", "Not interested / Lost"]))].copy()
    show_done = st.toggle("Show completed follow-ups", value=False)
    if not show_done:
        fu = fu[~fu["Follow-up done"]]
    if fu.empty:
        st.success("No open follow-ups. 🎉")
    else:
        today = pd.Timestamp(date.today())

        def status(r) -> str:
            if r["Follow-up done"]:
                return "✅ Done"
            d = r["Next step date"]
            if pd.isna(d):
                return "⚪ No date"
            return "🔴 Overdue" if d < today else ("🟠 Today" if d == today else "🟢 Upcoming")

        fu["Status"] = fu.apply(status, axis=1)
        fu["_order"] = fu["Status"].map({"🔴 Overdue": 0, "🟠 Today": 1, "🟢 Upcoming": 2, "⚪ No date": 3, "✅ Done": 4})
        fu = fu.sort_values(["_order", "Next step date"])
        counts = fu["Status"].value_counts()
        m = st.columns(4)
        for col, label in zip(m, ["🔴 Overdue", "🟠 Today", "🟢 Upcoming", "⚪ No date"]):
            col.metric(label, int(counts.get(label, 0)), border=True)
        table = pd.DataFrame({
            "id": fu["id"].values, "Done": fu["Follow-up done"].values, "Status": fu["Status"].values,
            "Due": fu["Next step date"].dt.date.values, "Next step": fu["Next step"].values,
            "Customer": fu["Customer"].values, "Mobile": fu["Mobile"].values,
            "Type": fu["Call type"].map(lambda t: f"{CALL_TYPES.get(t, {}).get('icon', '')} {t}").values,
            "Executive": fu["Executive"].values, "Deal value": fu["Deal value"].map(lambda v: inr(v) if v else "").values,
            "Outcome": fu["Outcome"].values, "Call date": fu["Date"].dt.date.values,
        })
        edited = st.data_editor(
            table, hide_index=True, width="stretch", key="fu_editor",
            disabled=[c for c in table.columns if c != "Done"],
            column_config={"id": None, "Done": st.column_config.CheckboxColumn("Done", help="Tick when completed"),
                           "Due": st.column_config.DateColumn(format="DD MMM YYYY"),
                           "Call date": st.column_config.DateColumn(format="DD MMM YYYY"),
                           "Mobile": st.column_config.TextColumn(width="medium"),
                           "Next step": st.column_config.TextColumn(width="large")})
        changed = edited[edited["Done"] != table["Done"]]
        if not changed.empty:
            for _, r in changed.iterrows():
                store.update_meta(int(r["id"]), followup_done=1 if r["Done"] else 0)
            # Forget the table's pending edits: rows move after saving, so old edits would hit other rows.
            st.session_state.pop("fu_editor", None)
            st.rerun()
        st.download_button("⬇️ Download follow-up list (Excel)", _xlsx(table.drop(columns=["id"])),
                           "follow_ups.xlsx")

with tab_risk:
    risk = view[view["Risk"].isin(["High", "Medium"])].copy()
    if risk.empty:
        st.success("No customers flagged as at risk. 🎉")
    else:
        risk["_o"] = risk["Risk"].map({"High": 0, "Medium": 1})
        risk = risk.sort_values(["_o", "Date"], ascending=[True, False])
        m = st.columns(2)
        m[0].metric("🔴 High risk", int((risk["Risk"] == "High").sum()), border=True)
        m[1].metric("🟠 Medium risk", int((risk["Risk"] == "Medium").sum()), border=True)
        rt = pd.DataFrame({
            "Risk": risk["Risk"].map({"High": "🔴 High", "Medium": "🟠 Medium"}).values,
            "Customer": risk["Customer"].values, "Mobile": risk["Mobile"].values,
            "Why": risk["Risk reason"].values,
            "Type": risk["Call type"].map(lambda t: f"{CALL_TYPES.get(t, {}).get('icon', '')} {t}").values,
            "Executive": risk["Executive"].values, "Outcome": risk["Outcome"].values,
            "Next step": risk["Next step"].values, "Call date": risk["Date"].dt.date.values,
        })
        st.dataframe(rt, hide_index=True, width="stretch", column_config={
            "Call date": st.column_config.DateColumn(format="DD MMM YYYY"),
            "Mobile": st.column_config.TextColumn(width="medium"), "Why": st.column_config.TextColumn(width="large")})
        st.caption("Flagged by the AI when a customer sounds unhappy, isn't using the software, or mentions "
                   "switching or not renewing. Call them before their renewal date.")
        st.download_button("⬇️ Download at-risk list (Excel)", _xlsx(rt), "at_risk_customers.xlsx")
