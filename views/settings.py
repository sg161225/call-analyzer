import streamlit as st

from views.common import load_flat  # noqa: F401  (sets import path)
from callanalyzer.config import DB_PATH, ROOT, SETTINGS_PATH, key_status, load_settings

st.title("⚙️ Settings")

st.subheader("API keys")
for name, ok in key_status().items():
    st.write(("✅ " if ok else "❌ ") + name)
st.caption(f"Keys are read from `{ROOT / '.env'}`. Copy `.env.example` to `.env`, fill in your keys, then restart the app.")

st.subheader("Configuration")
st.caption(f"Company context, transcription engine and AI model are set in `{SETTINGS_PATH}`. "
           "Edit that file in any text editor; changes apply on the next upload.")
st.json(load_settings(), expanded=False)

st.subheader("Data")
st.caption(f"All reviews are stored locally in `{DB_PATH}`. Back up or delete this file as needed.")
