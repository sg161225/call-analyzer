import hmac
import os

import streamlit as st

st.set_page_config(page_title="Call Analyzer", page_icon="📞", layout="wide")

# Hosted version: keys, database address and password come from Streamlit "Secrets".
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, (str, int, float)):
            os.environ[_k] = str(_v)  # Secrets win over any local .env value
            os.environ["CALL_ANALYZER_FROM_SECRETS"] = "1"
except Exception:  # no secrets file when running locally
    pass

# Optional password screen (set APP_PASSWORD in Secrets for the online version).
_pw = os.environ.get("APP_PASSWORD", "")
if _pw and not st.session_state.get("authed"):
    st.title("📞 Call Analyzer")
    with st.form("login"):
        entered = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in", type="primary"):
            if hmac.compare_digest(entered.encode(), _pw.encode()):
                st.session_state["authed"] = True
                st.rerun()
            st.error("Wrong password.")
    st.stop()

pages = [
    st.Page("views/overview.py", title="Overview", icon="📈", default=True),
    st.Page("views/dashboard.py", title="Call reviews", icon="📋"),
    st.Page("views/followups.py", title="Follow-ups", icon="📅"),
    st.Page("views/upload.py", title="Upload calls", icon="⬆️"),
    st.Page("views/insights.py", title="AI insights", icon="💡"),
    st.Page("views/settings.py", title="Settings", icon="⚙️"),
]
st.navigation(pages).run()
