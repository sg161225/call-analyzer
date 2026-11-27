import pandas as pd
import streamlit as st

from views.common import load_flat
from callanalyzer.calltypes import CALL_TYPES
from callanalyzer.faq import FAQ_DIR, faqs_for, is_active
from callanalyzer.playbook import OTHER, PLAYBOOKS

st.title("📖 Playbook")
st.caption("What executives should say: objection-handling responses and product FAQs. Calls of these types are "
           "checked against them. To change them, edit `callanalyzer/playbook.py` (objections) or the CSV files in "
           "`config/faqs/` (FAQs, opens in Excel).")

raw, flat = load_flat()
types = [t for t in CALL_TYPES if t in PLAYBOOKS or faqs_for(t)]
ctype = st.segmented_control("Call type", types, default=types[0], label_visibility="collapsed",
                             format_func=lambda t: f"{CALL_TYPES.get(t, {}).get('icon', '')} {t}") or types[0]
calls = flat[flat["Call type"] == ctype] if not flat.empty else flat
faqs = faqs_for(ctype)

show_all = st.toggle("Show the full playbook (all objections and FAQs)", value=False, key="pb_all",
                     help="Off: only what customers raised on calls and executives didn't handle properly.")
tabs = st.tabs(["🛡️ Objections"] + ([f"❓ FAQs ({len(faqs)})"] if faqs else []))

# ---- objections -------------------------------------------------------------------------------
with tabs[0]:
    items = PLAYBOOKS.get(ctype, [])
    if not items:
        st.info(f"There's no objection playbook for {ctype} yet. Send the objections and responses you use and "
                "they'll be added here.")
    else:
        stats, bad = {}, {}
        rows = [o for objs in calls["Objections"] for o in objs] if not calls.empty else []
        if rows:
            od = pd.DataFrame(rows)
            for name, g in od.groupby("objection"):
                stats[name] = (len(g), (g["playbook_followed"] == "Yes").mean())
                bad[name] = int((g["playbook_followed"] != "Yes").sum())
        if not show_all:
            items = sorted([o for o in items if bad.get(o["objection"])], key=lambda o: -bad[o["objection"]])
            if items:
                st.caption(f"{len(items)} objection(s) raised on calls that executives didn't handle the playbook way, "
                           "most frequent first. Turn on *Show the full playbook* to see all.")
            else:
                st.success("✅ No objections mishandled on reviewed calls. Turn on *Show the full playbook* to see all.")
        q = st.text_input("🔎 Find an objection", placeholder="e.g. expensive, CA, partner, discount", key="pb_q")
        for i, o in enumerate(items, 1):
            text = (o["objection"] + " " + " ".join(o["responses"])).lower()
            if q.strip() and q.strip().lower() not in text:
                continue
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"**{i}. {o['objection']}**")
                if o["objection"] in stats:
                    n, rate = stats[o["objection"]]
                    c2.markdown(f"<div style='text-align:right;opacity:.8'>❌ mishandled {bad.get(o['objection'], 0)} of {n}</div>",
                                unsafe_allow_html=True)
                for resp in o["responses"]:
                    st.markdown(f"💬 {resp}")
        if OTHER in stats:
            st.info(f"Customers raised **{stats[OTHER][0]}** objection(s) not in this playbook (shown as *Other* in call "
                    "reviews). They may deserve a playbook entry.")

# ---- FAQs -------------------------------------------------------------------------------------
if faqs:
    with tabs[1]:
        asked, badf = {}, {}
        rows = [a for ans in calls["FAQ answers"] for a in ans] if not calls.empty else []
        if rows:
            ad = pd.DataFrame(rows)
            for no, g in ad[ad["faq_no"] > 0].groupby("faq_no"):
                asked[int(no)] = (len(g), (g["accuracy"] == "Correct").mean())
                badf[int(no)] = int((g["accuracy"] != "Correct").sum())
        c1, c2 = st.columns([3, 1])
        q = c1.text_input("🔎 Search the FAQs", placeholder="e.g. price, GST, sync, offline, device, salesman",
                          key="faq_q")
        sort = c2.selectbox("Order", ["FAQ number", "Most asked", "Most often answered wrong"], key="faq_sort")
        base = faqs if show_all else [f for f in faqs if badf.get(f["no"])]
        if not show_all and not base:
            st.success("✅ No product questions answered wrongly on reviewed calls. Turn on *Show the full playbook* "
                       "to browse all FAQs.")
        if not show_all and sort == "FAQ number":
            base = sorted(base, key=lambda f: -badf.get(f["no"], 0))
        shown = [f for f in base if not q.strip() or q.strip().lower() in (f["q"] + " " + f["a"]).lower()]
        if sort == "Most asked":
            shown.sort(key=lambda f: -asked.get(f["no"], (0, 0))[0])
        elif sort == "Most often answered wrong":
            shown.sort(key=lambda f: (asked.get(f["no"], (0, 1))[1], -asked.get(f["no"], (0, 0))[0]))
        st.caption((f"{len(shown)} FAQ(s) that executives answered wrongly, partly or not at all on calls, "
                    "most frequent first" if not show_all else f"{len(shown)} of {len(faqs)} FAQs")
                   + (f" · matching “{q.strip()}”" if q.strip() else ""))
        for f in shown:
            tag = ""
            if f["no"] in asked:
                n, rate = asked[f["no"]]
                tag = f"  ·  ❌ not answered properly {badf.get(f['no'], 0)} of {n}" if badf.get(f["no"]) else f"  ·  ✅ asked {n}×, always correct"
            if f.get("till"):
                tag += (f"  ·  ⏳ offer valid till {f['till']:%d %b %Y}" if is_active(f)
                        else f"  ·  ⌛ offer ended {f['till']:%d %b %Y} (not checked on newer calls)")
            with st.expander(f"**{f['no']}.** {f['q']}{tag}"):
                st.markdown(f["a"])
        path = FAQ_DIR / f"{ctype}.csv"
        st.download_button("⬇️ Download FAQs (CSV, opens in Excel)", path.read_bytes(), path.name)
