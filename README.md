# 📞 Call Analyzer

Upload tele-calling recordings and get a **call-review dashboard**: every call scored against
the team scorecard, with one row per call:

| Business probing | Need generation | Pitch (offer / features) | Customer queries | Problem solving (objection handling) | ACPT improvement required |
|---|---|---|---|---|---|

Each parameter is rated **✅ Good / 🟡 Partial / ❌ Weak**, with what the executive did and what to improve.

**What you get**
- **Dashboard › Calls**: the scorecard table for every uploaded call, with filters (executive, campaign,
  date). Select a row for the full review. Export to Excel/CSV.
- **Dashboard › Compare executives**: average rating per executive per parameter (heatmap), rating mix,
  and a summary table.
- **Dashboard › Pitch over time**: one executive's scores across dates, compared by *pitch version* or
  month, to see whether a pitch change worked.
- **AI insights**: a written report across the selected calls covering what's working, what isn't, the executive
  comparison, pitch changes, process improvements, and an objection-handling playbook.

**Privacy:** the app runs on your own computer. Recordings are sent to the speech-to-text service and
deleted right after. Transcripts are not stored or shown. Only the review is saved, in a
local SQLite file (`data/calls.db`), which is never committed to git.

---

## Option A: run in the browser with GitHub Codespaces (no installation)

1. **Add your keys once:** GitHub → your profile → **Settings → Codespaces → Secrets → New secret**.
   Add `ANTHROPIC_API_KEY` and `SARVAM_API_KEY`, and give each access to this repository.
2. Open this repository on GitHub → green **Code** button → **Codespaces** tab → **Create codespace on main**.
3. Wait 2–3 minutes the first time. The app starts automatically. Open the **Ports** tab and
   click the globe icon next to **Call Analyzer (8501)** if it doesn't open by itself.
4. Next time, use **Code → Codespaces** and pick your existing codespace. Your reviews are still there.

Notes: each person gets their own codespace and their own reviews. GitHub deletes a codespace after
30 days of no use, so download the Excel sheet regularly as a backup. Codespaces is free for
personal accounts up to a monthly limit (about 60 hours); organisations are billed.

## Option B: setup on your own computer (once per computer)

Needs **Python 3.11+** and **ffmpeg**.

```bash
# 1. Get the code
git clone <your-repo-url> call-analyzer
cd call-analyzer

# 2. Install ffmpeg (if you don't have it)
#    Windows: winget install ffmpeg     macOS: brew install ffmpeg     Ubuntu: sudo apt install ffmpeg

# 3. Create a virtual environment and install
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# 4. Add your API keys
cp .env.example .env        # Windows: copy .env.example .env
# then edit .env and fill in ANTHROPIC_API_KEY and SARVAM_API_KEY
```

API keys:
- **Anthropic** (call review + insights): https://console.anthropic.com → API keys
- **Sarvam AI** (speech-to-text, best for Hindi/Hinglish): https://dashboard.sarvam.ai
- or **OpenAI** (alternative speech-to-text): https://platform.openai.com/api-keys
- or the **local** engine: free, no key, `pip install faster-whisper` (slow on CPU; downloads the model on first use)

## Run

```bash
streamlit run app.py
```

The app opens at http://localhost:8501.

## Using it

1. **Upload calls**: drop one or many recordings (wav, mp3, m4a, amr, …).
2. Check the **call details** table. The executive and campaign are pre-filled from file names like
   `Sachin9873747581DroppedOct.wav`. Set the call date, and optionally a **pitch version** (e.g.
   `v1`, `v2 new offer`) whenever the script or offer changes.
3. Click **Analyse**. Each call takes about 30–90 seconds.
4. Open the **Dashboard** and **AI insights**.

## Customising

Edit `config/settings.toml`:
- `[company]`: your product and what a good call looks like. The AI uses this to judge the pitch.
- `[transcription]`: the default engine, language, and product keywords to help recognition.
- `[analysis]`: the Claude model and effort (`low` / `medium` / `high`).

The scorecard parameters and their definitions are in `callanalyzer/review.py` (`PARAMETERS`, `SYSTEM`).

## Approximate cost per call (5-minute call, rough estimate)

| Step | Cost |
|---|---|
| Sarvam speech-to-text | ~₹2–3 |
| Claude review (Opus 5.5, medium effort) | ~₹5–10 |
| AI insights report (per report, not per call) | ~₹10–40, depending on how many calls |

## Project layout

```
app.py                  Streamlit entry point
views/                  Pages: dashboard, upload, insights, settings
callanalyzer/
  audio.py              ffmpeg conversion + splitting at pauses
  transcribe.py         Sarvam / OpenAI / local Whisper engines
  review.py             Scorecard schema + Claude prompts
  pipeline.py           upload → transcribe → review → store
  store.py              SQLite storage
config/settings.toml    Editable settings
```
