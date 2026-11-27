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


ENV_PATH = ROOT / ".env"
KEY_NAMES = {"GROQ_API_KEY": "Groq (free: transcription + review)",
             "CEREBRAS_API_KEY": "Cerebras (free: extra reviews when Groq's daily limit is reached, optional)",
             "ANTHROPIC_API_KEY": "Anthropic (paid review, optional)",
             "SARVAM_API_KEY": "Sarvam (paid transcription, optional)",
             "OPENAI_API_KEY": "OpenAI (paid transcription, optional)"}


def save_key(name: str, value: str) -> None:
    """Store a key in .env (kept out of git) and apply it immediately."""
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    lines = [ln for ln in lines if not ln.startswith(f"{name}=")] + [f"{name}={value.strip()}"]
    ENV_PATH.write_text("\n".join(lines) + "\n")
    os.environ[name] = value.strip()


def missing_keys(settings: dict, engine: str | None = None) -> list[str]:
    """Keys still needed for the chosen transcription engine and review provider."""
    need = []
    engine = engine or settings["transcription"]["engine"]
    need += {"groq": ["GROQ_API_KEY"], "sarvam": ["SARVAM_API_KEY"], "openai": ["OPENAI_API_KEY"]}.get(engine, [])
    provider = settings["analysis"].get("provider", "groq")
    need += {"groq": ["GROQ_API_KEY"], "anthropic": ["ANTHROPIC_API_KEY"]}[provider]
    return [k for k in dict.fromkeys(need) if not os.environ.get(k)]


def key_status() -> dict[str, bool]:
    return {
        "Groq (transcription + review)": bool(os.environ.get("GROQ_API_KEY")),
        "Cerebras (extra free reviews)": bool(os.environ.get("CEREBRAS_API_KEY")),
        "Anthropic (analysis)": bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")),
        "Sarvam (transcription)": bool(os.environ.get("SARVAM_API_KEY")),
        "OpenAI (transcription)": bool(os.environ.get("OPENAI_API_KEY")),
    }
