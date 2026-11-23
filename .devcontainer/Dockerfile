# Ready-made environment for the app: Python + ffmpeg + all packages preinstalled.
# Built by GitHub Actions (.github/workflows/devcontainer-image.yml) and published to
# GitHub Container Registry, so codespaces start without downloading anything from PyPI.
FROM mcr.microsoft.com/devcontainers/python:3.12

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r /tmp/requirements.txt \
 && python -c "import streamlit, groq, pandas, altair, openpyxl, dotenv, imageio_ffmpeg, sqlalchemy, psycopg2; print('packages ok')" \
 && ffmpeg -version | head -1
