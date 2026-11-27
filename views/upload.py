from datetime import date

import pandas as pd
import streamlit as st

from views.common import load_flat  # noqa: F401  (sets import path)
from callanalyzer.config import load_settings, missing_keys
from callanalyzer.review import DailyLimit
from callanalyzer.pipeline import guess_meta, process_call
from callanalyzer.calltypes import CALL_TYPES
from callanalyzer.transcribe import ENGINES

st.title("⬆️ Upload calls")
_keep = load_settings().get("storage", {}).get("keep_recordings", True)
st.caption("Each recording is stored (compressed) with its timed transcript, so you can play it on the call page."
           if _keep else "Recordings are processed and then discarded. Only the review is saved.")

settings = load_settings()

files = st.file_uploader("Call recordings", accept_multiple_files=True,
                         type=["wav", "mp3", "m4a", "aac", "amr", "ogg", "opus", "flac", "3gp", "mp4", "webm"])
if not files:
    st.info("Drop one or more recordings above. You'll then fill in the executive, date and campaign for each.")
    st.stop()

st.markdown("**Call details**: check and correct these before processing. "
            "Use *Pitch version* to tag a script/offer change (e.g. `v1`, `v2 new offer`) so you can compare before vs after.")
AUTO = "Auto-detect"


def _type_from_campaign(text: str) -> str:
    t = (text or "").lower()
    for words, ctype in ((("renew", "tss"), "Renewal"), (("upsell", "upgrade", "addon", "add-on"), "Upsell"),
                         (("mobile", "app"), "Mobile App"), (("new sale", "newsale", "lead", "enquiry", "inquiry"), "New Sales"),
                         (("onboard", "welcome", "setup", "activation", "new licen"), "CLM Onboarding"),
                         (("drop", "clm", "complaint", "reactiv", "retention", "check-in", "checkin"), "CLM Existing")):
        if any(w in t for w in words):
            return ctype
    return AUTO


seed = []
for f in files:
    g = guess_meta(f.name)
    seed.append({"File": f.name, "Executive": g["executive"], "Mobile": g["mobile"],
                 "Call type": _type_from_campaign(g["campaign"] + " " + f.name), "Call date": date.today(),
                 "Campaign": g["campaign"], "Pitch version": ""})
meta = st.data_editor(
    pd.DataFrame(seed), hide_index=True, width="stretch", num_rows="fixed", key=f"meta_{len(files)}",
    column_config={"File": st.column_config.TextColumn(disabled=True),
                   "Call date": st.column_config.DateColumn(format="DD MMM YYYY", required=True),
                   "Executive": st.column_config.TextColumn(required=True),
                   "Mobile": st.column_config.TextColumn(help="Customer's mobile number, read from the file name"),
                   "Call type": st.column_config.SelectboxColumn(
                       options=[AUTO, *CALL_TYPES], required=True,
                       help="Auto-detect lets the AI decide from the conversation")})

c1, c2 = st.columns([2, 3])
default = list(ENGINES).index(settings["transcription"]["engine"])
engine = c1.selectbox("Speech-to-text engine", list(ENGINES), index=default, format_func=ENGINES.get)

missing = missing_keys(settings, engine)
def _t(v) -> str:
    """Text from a table cell; empty cells can come back as None or NaN (a number)."""
    return "" if v is None or (isinstance(v, float) and v != v) else str(v).strip()


blank = [r["File"] for r in meta.to_dict("records") if not str(r.get("Executive") or "").strip()]
if blank:
    st.warning(f"Fill in the **Executive** for: {', '.join(blank)}. (Double-click the cell to type.)")
if missing:
    st.error(f"Missing key: {', '.join(missing)}. Add it on the **Settings** page (left menu).")
    st.page_link("views/settings.py", label="Open Settings", icon="⚙️")
if engine == "local":
    st.caption("Local Whisper is free but slow: expect a few minutes per call. The model downloads on first use.")

if st.button(f"Analyse {len(files)} call(s)", type="primary", disabled=bool(missing) or bool(blank)):
    ok, limit_hit, waiting = 0, None, 0
    progress = st.progress(0.0)
    for i, (f, m) in enumerate(zip(files, meta.to_dict("records"))):
        label = "transcribing (AI review later: daily limit reached)" if limit_hit else "transcribing and reviewing"
        with st.status(f"{f.name}: {label}…", expanded=False) as s:
            try:
                d = m["Call date"]
                process_call(f.getvalue(), {
                    "file_name": f.name, "executive": _t(m["Executive"]),
                    "mobile": "".join(ch for ch in str(m.get("Mobile") or "") if ch.isdigit())[-10:],
                    "call_date": d.isoformat() if hasattr(d, "isoformat") and not pd.isna(d) else _t(d),
                    "campaign": _t(m["Campaign"]), "pitch_version": _t(m["Pitch version"]),
                    "call_type": None if m.get("Call type") in (None, AUTO) else m["Call type"],
                }, settings, engine, review=not limit_hit)
                if limit_hit:
                    waiting += 1
                    s.update(label=f"{f.name}: transcribed, waiting for review ⏳", state="complete")
                else:
                    s.update(label=f"{f.name}: done ✅", state="complete")
                    ok += 1
            except DailyLimit as e:
                limit_hit = getattr(e, "wait", "") or "later"
                waiting += 1
                s.update(label=f"{f.name}: transcribed, waiting for review ⏳ (daily AI limit reached)", state="error")
                st.write(str(e).split(" Details:")[0])
            except Exception as e:
                s.update(label=f"{f.name}: failed ❌", state="error")
                st.write(f"{type(e).__name__}: {e}")
        progress.progress((i + 1) / len(files))
    st.success(f"{ok} of {len(files)} call(s) reviewed.")
    if limit_hit:
        st.warning(f"⏳ {waiting} call(s) were transcribed and saved but not reviewed, because the free AI's daily "
                   f"limit is used up. It frees up again in about **{limit_hit}**. Then open **Call reviews** "
                   "and click **🔁 Retry all**. No need to upload them again.")
    st.page_link("views/overview.py", label="Open the overview →", icon="📈")
