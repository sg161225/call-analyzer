from datetime import datetime

import streamlit as st

from views.common import filters, load_flat
from callanalyzer import store
from callanalyzer.config import load_settings, missing_keys
from callanalyzer.review import GROQ_MAX_CALLS, insights_report

st.title("💡 AI insights")
st.caption("Claude reads all the call reviews in the selection and writes a report: what's working, what isn't, "
           "how the executives compare, how pitches changed over time, and how to improve the process.")

raw, flat = load_flat()
if flat.empty:
    st.info("No reviewed calls yet.")
    st.stop()

view = filters(flat, "ins")
st.write(f"**{len(view)} call(s)** selected.")
focus = st.text_input("Anything to focus on? (optional)",
                      placeholder="e.g. why dropped customers are not renewing; compare Sachin's October vs November pitch")

settings = load_settings()
need = [k for k in missing_keys(settings, engine="none")]
has_key = not need
if need:
    st.error(f"Missing key: {', '.join(need)}. Add it on the **Settings** page (left menu).")
if settings["analysis"].get("provider", "groq") == "groq" and len(view) > GROQ_MAX_CALLS:
    st.warning(f"On the free tier a report covers up to {GROQ_MAX_CALLS} calls; the {GROQ_MAX_CALLS} most recent "
               "in your selection will be used. Narrow the filters (e.g. one executive or campaign) to focus it.")
if st.button("Generate report", type="primary", disabled=view.empty or not has_key):
    reviews = raw.set_index("id").loc[view["id"]]
    rows = [{"executive": r["executive"], "date": r["call_date"], "campaign": r["campaign"],
             "pitch_version": r["pitch_version"], **r["review"]} for _, r in reviews.iterrows()]
    with st.spinner(f"Analysing {len(rows)} call reviews… this can take a minute or two."):
        try:
            md = insights_report(rows, settings, focus)
        except Exception as e:
            st.error(f"{type(e).__name__}: {e}")
            st.stop()
    scope = f"{len(rows)} calls" + (f"; focus: {focus}" if focus else "")
    store.save_report(scope, md)
    st.rerun()

reports = store.load_reports()
if reports:
    latest, older = reports[0], reports[1:]
    st.divider()
    st.subheader(f"Latest report · {latest['created_at'].replace('T', ' ')}")
    st.caption(latest["scope"])
    st.markdown(latest["content_md"])
    st.download_button("⬇️ Download report (.md)", latest["content_md"].encode(),
                       f"call_insights_{datetime.now():%Y%m%d}.md")
    for r in older:
        with st.expander(f"{r['created_at'].replace('T', ' ')} · {r['scope']}"):
            st.markdown(r["content_md"])
