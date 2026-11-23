from datetime import date

import pandas as pd
import streamlit as st

from views.common import load_flat  # noqa: F401  (sets import path)
from callanalyzer.config import load_settings, missing_keys
from callanalyzer.pipeline import guess_meta, process_call
from callanalyzer.transcribe import ENGINES

st.title("⬆️ Upload calls")
st.caption("Recordings are processed and then discarded. Only the review is saved, not the audio or the transcript.")

settings = load_settings()

files = st.file_uploader("Call recordings", accept_multiple_files=True,
                         type=["wav", "mp3", "m4a", "aac", "amr", "ogg", "opus", "flac", "3gp", "mp4", "webm"])
if not files:
    st.info("Drop one or more recordings above. You'll then fill in the executive, date and campaign for each.")
    st.stop()

st.markdown("**Call details**: check and correct these before processing. "
            "Use *Pitch version* to tag a script/offer change (e.g. `v1`, `v2 new offer`) so you can compare before vs after.")
seed = []
for f in files:
    g = guess_meta(f.name)
    seed.append({"File": f.name, "Executive": g["executive"], "Call date": date.today(),
                 "Campaign": g["campaign"], "Pitch version": ""})
meta = st.data_editor(
    pd.DataFrame(seed), hide_index=True, width="stretch", num_rows="fixed", key=f"meta_{len(files)}",
    column_config={"File": st.column_config.TextColumn(disabled=True),
                   "Call date": st.column_config.DateColumn(format="DD MMM YYYY", required=True),
                   "Executive": st.column_config.TextColumn(required=True)})

c1, c2 = st.columns([2, 3])
default = list(ENGINES).index(settings["transcription"]["engine"])
engine = c1.selectbox("Speech-to-text engine", list(ENGINES), index=default, format_func=ENGINES.get)

missing = missing_keys(settings, engine)
if missing:
    st.error(f"Missing key: {', '.join(missing)}. Add it on the **Settings** page (left menu).")
    st.page_link("views/settings.py", label="Open Settings", icon="⚙️")
if engine == "local":
    st.caption("Local Whisper is free but slow: expect a few minutes per call. The model downloads on first use.")

if st.button(f"Analyse {len(files)} call(s)", type="primary", disabled=bool(missing)):
    ok = 0
    progress = st.progress(0.0)
    for i, (f, m) in enumerate(zip(files, meta.to_dict("records"))):
        with st.status(f"{f.name}: transcribing and reviewing…", expanded=False) as s:
            try:
                d = m["Call date"]
                process_call(f.getvalue(), {
                    "file_name": f.name, "executive": (m["Executive"] or "").strip(),
                    "call_date": d.isoformat() if hasattr(d, "isoformat") else str(d),
                    "campaign": (m["Campaign"] or "").strip(), "pitch_version": (m["Pitch version"] or "").strip(),
                }, settings, engine)
                s.update(label=f"{f.name}: done ✅", state="complete")
                ok += 1
            except Exception as e:
                s.update(label=f"{f.name}: failed ❌", state="error")
                st.write(f"{type(e).__name__}: {e}")
        progress.progress((i + 1) / len(files))
    st.success(f"{ok} of {len(files)} call(s) reviewed.")
    st.page_link("views/dashboard.py", label="Open the dashboard →", icon="📊")
