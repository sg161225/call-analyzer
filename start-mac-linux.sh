#!/usr/bin/env bash
# Call Analyzer for Mac / Linux. Run:  bash start-mac-linux.sh
# First run installs everything; later runs start the app and open the browser.
set -u
cd "$(dirname "$0")" || exit 1

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.10+ is not installed. Install it from https://www.python.org/downloads/ and run this again."
  exit 1
fi

[ -x .venv/bin/python ] || "$PY" -m venv .venv || { echo "Could not create the environment."; exit 1; }
VPY=.venv/bin/python
CHECK="import streamlit, groq, pandas, altair, openpyxl, dotenv, imageio_ffmpeg, sqlalchemy, psycopg2"
if ! "$VPY" -c "$CHECK" 2>/dev/null; then
  echo "Installing the app's packages (a few minutes the first time)..."
  for i in 1 2 3; do
    "$VPY" -m pip install --retries 10 --timeout 120 --disable-pip-version-check -r requirements.txt && break
    sleep 10
  done
  "$VPY" -c "$CHECK" || { echo "Package installation did not finish. Check your internet and run again."; exit 1; }
else
  "$VPY" -m pip install -q --disable-pip-version-check -r requirements.txt >/dev/null 2>&1
fi

echo
echo "  Call Analyzer is starting at http://localhost:8501  (Ctrl+C to stop)"
echo
( sleep 6; (command -v open >/dev/null && open http://localhost:8501) || (command -v xdg-open >/dev/null && xdg-open http://localhost:8501) ) >/dev/null 2>&1 &
exec "$VPY" -m streamlit run app.py --server.port 8501 --server.headless true --browser.gatherUsageStats false
