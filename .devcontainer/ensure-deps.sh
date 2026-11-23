#!/usr/bin/env bash
# Safety net: the codespace image normally has everything installed already.
# If something is missing (e.g. requirements changed after the image was built),
# install it, retrying a few times because PyPI can be flaky from Codespaces.
set -u
if python -c "import streamlit, groq, pandas, altair, openpyxl, dotenv" 2>/dev/null; then
  echo "✅ All packages already installed."
else
  for i in 1 2 3 4 5; do
    echo "Installing packages (attempt $i of 5)…"
    python -m pip install --retries 10 --timeout 120 -r requirements.txt && break
    sleep 15
  done
fi
command -v ffmpeg >/dev/null || { sudo apt-get update && sudo apt-get install -y ffmpeg; }
exit 0
