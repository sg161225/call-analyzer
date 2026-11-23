import os

import streamlit as st

from views.common import load_flat  # noqa: F401  (sets import path)
from callanalyzer.config import DB_PATH, KEY_NAMES, SETTINGS_PATH, load_settings, missing_keys, save_key

st.title("⚙️ Settings")
settings = load_settings()

st.subheader("API keys")
need = missing_keys(settings)
if need:
    st.warning(f"Needed for your current setup: **{', '.join(need)}**")
else:
    st.success("All keys needed for your current setup are in place.")

with st.expander("How to get a free Groq key (2 minutes, no card)", expanded="GROQ_API_KEY" in need):
    st.markdown(
        "1. Go to **https://console.groq.com** and sign in (Google or email).\n"
        "2. Click **API Keys** → **Create API Key** → give it any name → **Submit**.\n"
        "3. Copy the key (it starts with `gsk_`) and paste it below.")

with st.form("keys"):
    values = {}
    for name, label in KEY_NAMES.items():
        have = bool(os.environ.get(name))
        values[name] = st.text_input(f"{label} {'✅' if have else ''}", type="password", key=name,
                                     placeholder="saved, leave empty to keep" if have else "paste key here")
    if st.form_submit_button("Save keys", type="primary"):
        saved = [n for n, v in values.items() if v.strip()]
        for n in saved:
            save_key(n, values[n])
        st.success(f"Saved {len(saved)} key(s)." if saved else "Nothing to save.")
        st.rerun()
st.caption("Keys are saved in a private `.env` file in this app's folder (never uploaded to GitHub). "
           "In Codespaces they stay with your codespace.")

st.subheader("Current setup")
t, a = settings["transcription"], settings["analysis"]
st.markdown(f"- Speech-to-text: **{t['engine']}**" + (f" ({t.get('groq_task', 'translate')})" if t["engine"] == "groq" else "") +
            f"\n- Call review: **{a.get('provider', 'groq')}** · model `{a['groq_model'] if a.get('provider', 'groq') == 'groq' else a['model']}`")
st.caption(f"To change these, or your company description, edit `{SETTINGS_PATH.name}` in the `config` folder.")
with st.expander("All settings"):
    st.json(settings)

st.subheader("Data")
st.caption(f"Reviews are stored in `{DB_PATH}`. Download the Excel sheet from the Dashboard regularly as a backup.")
