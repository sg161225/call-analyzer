import streamlit as st

st.set_page_config(page_title="Call Analyzer", page_icon="📞", layout="wide")

pages = [
    st.Page("views/dashboard.py", title="Dashboard", icon="📊", default=True),
    st.Page("views/upload.py", title="Upload calls", icon="⬆️"),
    st.Page("views/insights.py", title="AI insights", icon="💡"),
    st.Page("views/settings.py", title="Settings", icon="⚙️"),
]
st.navigation(pages).run()
