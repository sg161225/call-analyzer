import os

import streamlit as st

from views.common import load_flat  # noqa: F401  (sets import path)
from callanalyzer import store
from callanalyzer.config import KEY_NAMES, SETTINGS_PATH, load_settings, missing_keys, save_key

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

with st.expander("Optional: add a free Cerebras key for more reviews per day"):
    st.markdown(
        "Groq's free tier reviews roughly 20-30 calls a day. With a Cerebras key, reviews continue on Cerebras "
        "when Groq's limit is reached (transcription still uses Groq).\n\n"
        "1. Go to **https://cloud.cerebras.ai** and sign up (free, no card).\n"
        "2. Open **API Keys** and copy your key (it starts with `csk-`).\n"
        "3. Paste it in the **Cerebras** box below and click **Save keys**"
        + (" (online version: add `CEREBRAS_API_KEY = \"csk-...\"` in Streamlit Secrets)." if os.environ.get("CALL_ANALYZER_FROM_SECRETS") == "1" else "."))


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

HOSTED = os.environ.get("CALL_ANALYZER_FROM_SECRETS") == "1"
if HOSTED:
    st.info("This online version reads its keys from **Streamlit Secrets** (app ⋮ menu → Settings → Secrets "
            "on share.streamlit.io). Change them there; the app restarts with the new values.")
else:
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
        elif "CEREBRAS_API_KEY" in entered and not entered["CEREBRAS_API_KEY"].startswith("csk"):
            st.session_state["key_msg"] = (False, "That doesn't look like a Cerebras key: it should start with csk-. "
                                                  "Copy it again from cloud.cerebras.ai → API Keys.")
        elif "GROQ_API_KEY" in entered and not entered["GROQ_API_KEY"].startswith("gsk_"):
            st.session_state["key_msg"] = (False, "That doesn't look like a Groq key: it should start with gsk_. "
                                                  "Copy it again from console.groq.com → API Keys.")
        else:
            try:
                for n, v in entered.items():
                    save_key(n, v)
                ok, text = _test_groq() if "GROQ_API_KEY" in entered else (True, "")
                if "CEREBRAS_API_KEY" in entered:
                    from callanalyzer.cerebras import test_key
                    ok2, text2 = test_key()
                    ok, text = ok and ok2, f"{text} {text2}".strip()
                st.session_state["key_msg"] = (ok, f"Saved {len(entered)} key(s). {text}")
            except OSError as e:
                st.session_state["key_msg"] = (False, f"Could not write the key file: {e}")
        st.rerun()

tc1, tc2, _ = st.columns([1, 1, 3])
if os.environ.get("GROQ_API_KEY") and tc1.button("Test Groq key"):
    ok, text = _test_groq()
    (st.success if ok else st.error)(text)
if os.environ.get("CEREBRAS_API_KEY") and tc2.button("Test Cerebras key"):
    from callanalyzer.cerebras import test_key
    ok, text = test_key()
    (st.success if ok else st.error)(text)

if not HOSTED:
    st.caption("Keys are saved in a private `.env` file in this app's folder (never uploaded to GitHub).")

st.subheader("Current setup")
t, a = settings["transcription"], settings["analysis"]
st.markdown(f"- Speech-to-text: **{t['engine']}**" + (f" ({t.get('groq_task', 'translate')})" if t["engine"] == "groq" else "") +
            f"\n- Call review: **{a.get('provider', 'groq')}** · model `{a['groq_model'] if a.get('provider', 'groq') == 'groq' else a['model']}`")
st.caption(f"To change these, or your company description, edit `config/{SETTINGS_PATH.name}`"
           + (" in the GitHub repository; the online app updates itself within a minute." if HOSTED else "."))
with st.expander("All settings"):
    st.json(settings)

st.subheader("Data")
st.caption(f"Reviews are stored in the {store.storage_label()}. "
           "Download the Excel sheet from the Dashboard regularly as a backup.")

from views.common import export_frame, flatten  # noqa: E402
from callanalyzer import store  # noqa: E402

raw = store.load_calls()
n_calls, n_reports = len(raw), len(store.load_reports())
st.write(f"Stored now: **{n_calls} call(s)** and **{n_reports} AI insights report(s)**.")

n_rec, mb = store.recordings_size_mb()
keep = settings.get("storage", {}).get("keep_recordings", True)
st.write(f"Stored recordings: **{n_rec}** ({mb} MB). Keeping new recordings: **{'on' if keep else 'off'}** "
         "(change `keep_recordings` in config/settings.toml).")
if store.is_online_db() and mb > 300:
    st.warning("Recordings are taking a lot of space in the online database (the free Neon plan has 0.5 GB). "
               "Consider deleting older recordings below.")
with st.expander("🎧 Delete stored recordings (keep the reviews)", expanded=False):
    st.caption("Removes every stored recording and transcript. Reviews, scores and dashboards stay.")
    sure_rec = st.text_input("Type DELETE to confirm", key="del_rec_confirm")
    if st.button("Delete recordings", disabled=sure_rec.strip().upper() != "DELETE" or n_rec == 0):
        store.delete_all_recordings()
        st.success("Recordings deleted.")
        st.rerun()

with st.expander("🗑️ Delete all data", expanded=False):
    st.warning("This permanently deletes every call review" + (" and AI insights report" if n_reports else "")
               + ". It can't be undone. Your API keys and settings are kept.")
    flat = flatten(raw)
    if not flat.empty:
        from io import BytesIO  # noqa: E402
        buf = BytesIO()
        export_frame(flat).to_excel(buf, index=False, sheet_name="Call reviews")
        st.download_button("⬇️ Download a backup first (Excel)", buf.getvalue(), "call_reviews_backup.xlsx")
    also_reports = st.checkbox("Also delete AI insights reports", value=True)
    sure = st.text_input('Type DELETE to confirm', key="del_all_confirm")
    if st.button("Delete all data", type="primary", disabled=sure.strip().upper() != "DELETE" or n_calls + n_reports == 0):
        store.delete_all(include_reports=also_reports)
        st.session_state.clear()
        st.success("All data deleted.")
        st.rerun()
