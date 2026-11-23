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

def _mask(v: str) -> str:
    return f"{v[:4]}…{v[-4:]}" if len(v) > 10 else "saved"


def _test_groq() -> tuple[bool, str]:
    try:
        import groq
        groq.Groq().models.list()
        return True, "Groq key works ✅"
    except Exception as e:  # show the real reason to the user
        return False, f"Groq rejected the key or could not be reached: {type(e).__name__}: {str(e)[:200]}"


# Message from the previous click survives the page reload.
if msg := st.session_state.pop("key_msg", None):
    (st.success if msg[0] else st.error)(msg[1])

with st.form("keys", clear_on_submit=True):
    values = {}
    for name, label in KEY_NAMES.items():
        cur = os.environ.get(name, "")
        status = f" — ✅ saved ({_mask(cur)})" if cur else ""
        values[name] = st.text_input(f"{label}{status}", type="password",
                                     placeholder="leave empty to keep the saved key" if cur else "paste key here")
    submitted = st.form_submit_button("Save keys", type="primary")

if submitted:
    entered = {n: v.strip().strip('"').strip("'").replace(" ", "") for n, v in values.items() if v.strip()}
    if not entered:
        st.session_state["key_msg"] = (False, "Nothing was pasted. Click inside the Groq box, paste (Ctrl+V), then click Save keys.")
    elif "GROQ_API_KEY" in entered and not entered["GROQ_API_KEY"].startswith("gsk_"):
        st.session_state["key_msg"] = (False, "That doesn't look like a Groq key: it should start with gsk_. "
                                              "Copy it again from console.groq.com → API Keys.")
    else:
        try:
            for n, v in entered.items():
                save_key(n, v)
            ok, text = _test_groq() if "GROQ_API_KEY" in entered else (True, "")
            st.session_state["key_msg"] = (ok, f"Saved {len(entered)} key(s). {text}")
        except OSError as e:
            st.session_state["key_msg"] = (False, f"Could not write the key file: {e}")
    st.rerun()

if os.environ.get("GROQ_API_KEY") and st.button("Test Groq key"):
    ok, text = _test_groq()
    (st.success if ok else st.error)(text)

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
