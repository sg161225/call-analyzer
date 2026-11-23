"""Speech-to-text engines. Output is plain text used only as input to the review;
it is never stored or shown."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .audio import split_at_pauses, to_wav16k

ENGINES = {"sarvam": "Sarvam AI (Hindi/Hinglish)", "openai": "OpenAI", "local": "Local Whisper (free, slow)"}


def transcribe(audio_path: Path, settings: dict, engine: str | None = None) -> str:
    cfg = settings["transcription"]
    engine = engine or cfg["engine"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        wav = to_wav16k(audio_path, tmp / "call.wav")
        if engine == "sarvam":
            return _sarvam(wav, tmp, cfg)
        if engine == "openai":
            return _openai(wav, tmp, cfg)
        if engine == "local":
            return _local(wav, cfg)
        raise ValueError(f"Unknown transcription engine: {engine}")


def _sarvam(wav: Path, tmp: Path, cfg: dict) -> str:
    from sarvamai import SarvamAI

    key = os.environ.get("SARVAM_API_KEY")
    if not key:
        raise RuntimeError("SARVAM_API_KEY is not set in .env")
    client = SarvamAI(api_subscription_key=key)
    model = cfg.get("sarvam_model", "saaras:v3")
    extra = {}
    if model == "saaras:v4" and cfg.get("keyterms"):
        extra["keyterms"] = cfg["keyterms"][:50]
    parts = []
    # The REST endpoint accepts up to 30 s per request.
    for chunk in split_at_pauses(wav, tmp / "chunks", max_len=28):
        with open(chunk, "rb") as f:
            resp = client.speech_to_text.transcribe(
                file=f, model=model, mode=cfg.get("sarvam_mode", "codemix"),
                language_code=cfg.get("sarvam_language", "unknown"), **extra)
        parts.append(resp.transcript.strip())
    return "\n".join(p for p in parts if p)


def _openai(wav: Path, tmp: Path, cfg: dict) -> str:
    from openai import OpenAI

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set in .env")
    client = OpenAI()
    prompt = "Phone call between a sales/support executive and a customer, Hindi and English mixed. Terms: " + ", ".join(cfg.get("keyterms", []))
    parts = []
    for chunk in split_at_pauses(wav, tmp / "chunks", max_len=600):
        with open(chunk, "rb") as f:
            resp = client.audio.transcriptions.create(model=cfg.get("openai_model", "gpt-4o-transcribe"), file=f, prompt=prompt)
        parts.append(resp.text.strip())
    return "\n".join(p for p in parts if p)


_LOCAL_MODEL = None


def _local(wav: Path, cfg: dict) -> str:
    global _LOCAL_MODEL
    try:
        import numpy as np
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError("Local engine needs: pip install faster-whisper") from e
    if _LOCAL_MODEL is None:
        _LOCAL_MODEL = WhisperModel(cfg.get("local_model", "large-v3"), device="auto", compute_type="int8")
    # Feed raw samples (avoids PyAV decoding issues with phone-recorder files).
    import wave
    with wave.open(str(wav), "rb") as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    segs, _ = _LOCAL_MODEL.transcribe(audio, beam_size=5, condition_on_previous_text=False,
                                      no_repeat_ngram_size=4, compression_ratio_threshold=2.2)
    return "\n".join(s.text.strip() for s in segs)


if __name__ == "__main__":  # quick manual test: python -m callanalyzer.transcribe file.wav [engine]
    import sys

    from .config import load_settings
    print(transcribe(Path(sys.argv[1]), load_settings(), sys.argv[2] if len(sys.argv) > 2 else None))
