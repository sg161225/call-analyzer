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

## Start the app on Windows (recommended)

**One-time download**
1. On this page, click the green **`<> Code`** button → **Download ZIP**.
2. Open your **Downloads** folder, right-click **call-analyzer-main.zip** → **Extract All…** → **Extract**.
   Move the extracted folder somewhere easy, e.g. **Documents**.

**Every time you want to use it**
1. Open the **call-analyzer-main** folder and double-click **`Start Call Analyzer`** (or `Start Call Analyzer.bat`).
   - If Windows shows *"Windows protected your PC"*, click **More info** → **Run anyway**.
   - **First time only:** it installs everything it needs (Python if missing, and the app's packages).
     This takes 5–10 minutes. If it says *"Python is installed, close this window and run again"*, do that.
2. Your browser opens the app at **http://localhost:8501**.
   If it doesn't, open that address yourself.
3. Keep the black window open while you use the app. Close it to stop the app.

Your reviews are saved in the `data` folder inside the app folder. Keep that folder when you update the app.

**Updating to a newer version:** download the ZIP again, extract it, and copy your old `data` folder and
`.env` file (your saved key) into the new folder.

### Mac / Linux

Download and extract the ZIP as above, open Terminal in the folder, and run `bash start-mac-linux.sh`.

### GitHub Codespaces (alternative, runs in the browser)

**Code** → **Codespaces** → **Create codespace on main**, then open the `https://…app.github.dev` link the
terminal prints. This needs a network that allows `*.app.github.dev`; many office networks block it.
If you see `streamlit: command not found`, run `bash .devcontainer/ensure-deps.sh` and then
`bash .devcontainer/start-app.sh` in the Terminal.

## Host it online (free): one link for the whole team

The app can run on **Streamlit Community Cloud** (free), straight from this GitHub repository, with reviews
kept in a free **Neon** online database. Everyone opens the same link, signs in with a team password, and
sees the same data. Each push to GitHub updates the online app automatically.

**Step 1: free database (Neon), 3 minutes**
1. Go to **https://neon.tech** → **Sign up** (you can use your GitHub account). No card needed.
2. Create a project: any name (e.g. `call-analyzer`), region **AWS Asia Pacific (Singapore)** (closest to India).
3. On the project dashboard click **Connect**, then copy the **connection string**. It looks like
   `postgresql://user:password@ep-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`.

**Step 2: deploy the app (Streamlit Community Cloud), 5 minutes**
1. Go to **https://share.streamlit.io** → **Continue with GitHub** → allow access.
2. Click **Create app** → **Deploy a public app from GitHub**, and fill in:
   - Repository: `sg161225/call-analyzer` · Branch: `main` · Main file path: `app.py`
   - App URL: pick a name, e.g. `busy-call-analyzer`
3. Open **Advanced settings**, choose Python **3.12**, and paste this into **Secrets** with your own values:
   ```toml
   GROQ_API_KEY = "gsk_your_groq_key"
   DATABASE_URL = "postgresql://...your Neon connection string..."
   APP_PASSWORD = "choose-a-team-password"
   ```
4. Click **Deploy**. The first start takes 3–5 minutes. You get a link like `https://busy-call-analyzer.streamlit.app`.

Share the link and the password with your team. Without the password, people only see the sign-in box.

**Good to know**
- Change keys or the password later in share.streamlit.io → your app's **⋮** menu → **Settings → Secrets**.
- On the free plan the app sleeps after a few days without visitors; opening the link shows a
  "wake up" button and it starts again in about a minute. Your reviews are safe in Neon.
- Recordings are processed in memory and never stored; only the reviews go into the database.
- If your office network blocks `*.streamlit.app`, ask IT to allow it, or keep using the Windows version.
- The online and Windows versions keep separate data unless you also put the same `DATABASE_URL`
  in the Windows version's `.env` file.

## First-time setup inside the app (2 minutes)

1. Go to **https://console.groq.com** and sign in (Google or email). It's free and needs no card.
2. Click **API Keys** → **Create API Key** → any name → **Submit**, then copy the key (starts with `gsk_`).
3. In the app, click **⚙️ Settings** in the left menu, paste the key into the **Groq** box, and click
   **Save keys**. A green message confirms it was saved and that Groq accepted it.

## Using it

1. **Upload calls**: drop one or more recordings (wav, mp3, m4a, amr, …).
2. Check the **call details** table. The executive, mobile number and campaign are filled in from the file name.
   Pick the **Call type** (or leave *Auto-detect* and the AI decides), set the call date, and optionally a
   **pitch version** (e.g. `v1`, `v2 new offer`) whenever the script or offer changes.
3. Click **Analyse**.

**Call types:** 🆕 New Sales · 📱 Mobile App · 🔄 Renewal · ⬆️ Upsell · 🤝 CLM (customer life cycle management).
Each type has its own checklist (edit them in `callanalyzer/calltypes.py`). For every call the AI records the
outcome, next step and date, the deal value in ₹ mentioned on the call, the loss reason, and the risk of losing
the customer. Success = payment received for sales types; issue resolved / healthy customer for CLM.

**Pages**
- **📈 Overview**: switch between call types; KPI cards (conversion, revenue won, pipeline, follow-ups due),
  sales funnel, *why we lose*, *what wins* (success rate when each checklist item was done vs not), checklist
  completion and an executive table.
- **📋 Call reviews**: the scorecard table with your six columns, search by mobile number, executive comparison,
  pitch over time, and the full review of any call (tick rows to fix details in bulk or delete them).
- **📖 Playbook**: the New Sales objection playbook (15 objections with recommended responses) and how often
  the team uses each one. Every New Sales call is checked against it: which objections came up, whether the
  executive used the playbook response (✅ / 🟡 / ❌), and the line they should have used. The Overview shows
  the most common objections, playbook adherence by objection and executive, and success when it was followed.
  Edit the playbook in `callanalyzer/playbook.py`.
- **📅 Follow-ups**: payment promises, demos and callbacks by due date (tick *Done* when completed), plus
  **at-risk customers** to call before their renewal.
- **💡 AI insights**: a written report on what's working, what isn't and how to improve, by call type.

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
  audio.py              audio conversion + splitting at pauses (bundled ffmpeg)
  transcribe.py         Groq / local Whisper / Sarvam / OpenAI engines
  review.py             Scorecard schema + AI prompts (Groq or Claude)
  pipeline.py           upload → transcribe → review → store
  store.py              storage (local SQLite file, or online Postgres via DATABASE_URL)
config/settings.toml    Editable settings
Start Call Analyzer.bat Windows launcher (installs on first run)
start-mac-linux.sh      Mac/Linux launcher
.devcontainer/          GitHub Codespaces setup
```
