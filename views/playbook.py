import pandas as pd
import streamlit as st

from views.common import load_flat
from callanalyzer.calltypes import CALL_TYPES
from callanalyzer.playbook import OTHER, PLAYBOOKS

st.title("📖 Objection playbook")
st.caption("The responses executives should use for common customer objections. Every call of these types is "
           "checked against this playbook. To change it, edit `callanalyzer/playbook.py`.")

raw, flat = load_flat()
types = list(PLAYBOOKS)
ctype = st.segmented_control("Call type", types, default=types[0], label_visibility="collapsed",
                             format_func=lambda t: f"{CALL_TYPES.get(t, {}).get('icon', '')} {t}") or types[0]

# How the team handles each objection in reviewed calls.
stats = {}
if not flat.empty:
    rows = [o for objs in flat.loc[flat["Call type"] == ctype, "Objections"] for o in objs]
    if rows:
        od = pd.DataFrame(rows)
        for name, g in od.groupby("objection"):
            stats[name] = (len(g), (g["playbook_followed"] == "Yes").mean())

q = st.text_input("🔎 Find an objection", placeholder="e.g. expensive, CA, partner, discount")
for i, o in enumerate(PLAYBOOKS[ctype], 1):
    text = (o["objection"] + " " + " ".join(o["responses"])).lower()
    if q.strip() and q.strip().lower() not in text:
        continue
    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"**{i}. {o['objection']}**")
        if o["objection"] in stats:
            n, rate = stats[o["objection"]]
            c2.markdown(f"<div style='text-align:right;opacity:.8'>Raised {n}× · followed {rate:.0%}</div>",
                        unsafe_allow_html=True)
        for resp in o["responses"]:
            st.markdown(f"💬 {resp}")

if OTHER in stats:
    n, _ = stats[OTHER]
    st.info(f"Customers raised **{n}** objection(s) not in this playbook (shown as *Other* in call reviews). "
            "Check them on the 📋 Call reviews page; they may deserve a playbook entry.")
