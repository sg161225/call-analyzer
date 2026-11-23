# 📞 Call Analyzer

Upload tele-calling recordings and get a **call-review dashboard**: every call scored against
the team scorecard, with one row per call:

| Business probing | Need generation | Pitch (offer / features) | Customer queries | Problem solving (objection handling) | ACPT improvement required |
|---|---|---|---|---|---|

Each parameter is rated **✅ Good / 🟡 Partial / ❌ Weak**, with what the executive did and what to improve.

**Free to run:** by default it uses the free tier of [Groq](https://console.groq.com) for both speech-to-text
(Whisper large-v3, translated to English) and the review (open-source models). No credit card is needed.

**What you get**
- **Dashboard › Calls**: the scorecard table for every call, with filters (executive, campaign, date).
  Select a row for the full review. Export to Excel/CSV.
- **Dashboard › Compare executives**: average rating per executive per parameter, rating mix, and a summary table.
- **Dashboard › Pitch over time**: one executive's scores across dates, compared by *pitch version* or month.
- **AI insights**: a written report on what's working, what isn't, the executive comparison, pitch changes,
  process improvements, and an objection-handling playbook.

---

## Start the app

### Option A: in the browser with GitHub Codespaces (nothing to install)

1. On this repository's page, click the green **Code** button → **Codespaces** tab → **Create codespace on main**.
2. Wait 2–3 minutes the first time while it installs. The app then opens in a new browser tab.
   If it doesn't, open the **Ports** tab at the bottom and click the 🌐 globe icon next to port **8501**.
3. Next time, use **Code → Codespaces** and click your existing codespace; your reviews will still be there.

If the terminal says `streamlit: command not found`, the install didn't finish. Run these in the **Terminal** tab:

```bash
sudo apt-get update && sudo apt-get install -y ffmpeg
python -m pip install --timeout 120 -r requirements.txt
bash .devcontainer/start-app.sh
```

Open the `https://…app.github.dev` link the script prints (or **Ports** tab → 🌐 on port 8501).
Do **not** use the `10.0.x.x` "Network URL": it only works inside the codespace.

Codespaces is free for personal GitHub accounts within the monthly allowance. GitHub deletes a codespace after
30 days without use, so download the Excel sheet regularly as a backup.

### Option B: on your own computer

Needs **Python 3.11+** and **ffmpeg** (Windows: `winget install ffmpeg`, Mac: `brew install ffmpeg`).

```bash
git clone https://github.com/sg161225/call-analyzer
cd call-analyzer
python -m venv .venv
.venv\Scripts\activate          # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens at http://localhost:8501.

## First-time setup inside the app (2 minutes)

1. Go to **https://console.groq.com** and sign in (Google or email). It's free.
2. Click **API Keys** → **Create API Key** → any name → **Submit**, then copy the key (starts with `gsk_`).
3. In the app, open **Settings** (left menu), paste the key into the **Groq** box, and click **Save keys**.

## Using it

1. **Upload calls**: drop one or more recordings (wav, mp3, m4a, amr, …).
2. Check the **call details** table. The executive and campaign are pre-filled from file names like
   `Sachin9873747581DroppedOct.wav`. Set the call date, and optionally a **pitch version**
   (e.g. `v1`, `v2 new offer`) whenever the script or offer changes.
3. Click **Analyse**.
4. Open the **Dashboard** and **AI insights**.

## Free-tier limits

Groq's free tier has hourly and daily limits on audio minutes and tokens. These change from time to time; see
console.groq.com → Settings → Limits. A normal day of reviewing tens of calls should fit. If you hit a limit:
- wait (limits reset every minute, hour, or day; the error message says which), or
- set the speech-to-text engine to **Local Whisper** on the upload page (free and unlimited, but slow), or
- in `config/settings.toml`, set `analysis.groq_model = "openai/gpt-oss-20b"` (higher limits, slightly weaker reviews).

AI insights reports cover up to 20 calls at a time on the free tier. Use the filters to focus a report.

## Privacy

Recordings and their text are sent to Groq for processing, then deleted by the app. Transcripts are never
stored or shown. Only the reviews are saved, in `data/calls.db`, which is never uploaded to GitHub. Keys are
stored in a private `.env` file, which is also never uploaded. For fully offline use, choose **Local Whisper**
for speech-to-text (the review step still uses Groq).

## Customising

Edit `config/settings.toml`:
- `[company]`: your product and what a good call looks like. The AI uses this to judge the pitch.
- `[transcription]`: engine (`groq`, `local`, or paid `sarvam`/`openai`), translate vs keep original language, keywords.
- `[analysis]`: `provider` (`groq` free, or `anthropic` paid for the highest-quality reviews) and model.

The scorecard parameters and their definitions are in `callanalyzer/review.py` (`PARAMETERS`, `SYSTEM`).

## Project layout

```
app.py                  Streamlit entry point
views/                  Pages: dashboard, upload, insights, settings
callanalyzer/
  audio.py              ffmpeg conversion + splitting at pauses
  transcribe.py         Groq / local Whisper / Sarvam / OpenAI engines
  review.py             Scorecard schema + AI prompts (Groq or Claude)
  pipeline.py           upload → transcribe → review → store
  store.py              SQLite storage
config/settings.toml    Editable settings
.devcontainer/          GitHub Codespaces setup
```
