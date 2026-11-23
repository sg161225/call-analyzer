"""Settings loading: config/settings.toml + .env for API keys."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / "config" / "settings.toml"
DATA_DIR = Path(os.environ.get("CALL_ANALYZER_DATA", ROOT / "data"))
DB_PATH = DATA_DIR / "calls.db"

load_dotenv(ROOT / ".env")


def load_settings() -> dict:
    with open(SETTINGS_PATH, "rb") as f:
        return tomllib.load(f)


def key_status() -> dict[str, bool]:
    return {
        "Anthropic (analysis)": bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")),
        "Sarvam (transcription)": bool(os.environ.get("SARVAM_API_KEY")),
        "OpenAI (transcription)": bool(os.environ.get("OPENAI_API_KEY")),
    }
