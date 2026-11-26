"""Speech-to-text engines. Each returns timed segments: [{"start": s, "end": s, "text": "..."}]."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .audio import chunk_offsets, duration_sec, split_at_pauses, to_wav16k

ENGINES = {"groq": "Groq Whisper (free tier)", "local": "Local Whisper (free, slow)",
           "sarvam": "Sarvam AI (paid, Hindi/Hinglish)", "openai": "OpenAI (paid)"}

Segments = list[dict]


def transcribe(audio_path: Path, settings: dict, engine: str | None = None) -> Segments:
    cfg = settings["transcription"]
    engine = engine or cfg["engine"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        wav = to_wav16k(audio_path, tmp / "call.wav")
        if engine == "groq":
            segs = _groq(wav, tmp, cfg)
        elif engine == "sarvam":
            segs = _sarvam(wav, tmp, cfg)
        elif engine == "openai":
            segs = _openai(wav, tmp, cfg)
        elif engine == "local":
            segs = _local(wav, cfg)
        else:
            raise ValueError(f"Unknown transcription engine: {engine}")
    return [s for s in segs if s["text"]]


def segments_text(segs: Segments) -> str:
    return "\n".join(s["text"] for s in segs)


def _seg(start: float, end: float, text: str) -> dict:
    return {"start": round(float(start), 2), "end": round(float(end), 2), "text": (text or "").strip()}


def _field(obj, name):
    """Read a field from an SDK object or dict (extra fields such as 'segments' included)."""
    if isinstance(obj, dict):
        return obj.get(name)
    val = getattr(obj, name, None)
    if val is None and getattr(obj, "model_extra", None):
        val = obj.model_extra.get(name)
    return val


def _from_verbose(resp, offset: float, chunk_len: float) -> Segments:
    """Segments from a Whisper 'verbose_json' response; one segment for the chunk if none."""
    raw = _field(resp, "segments") or []
    out = [_seg(offset + float(_field(s, "start") or 0), offset + float(_field(s, "end") or 0), _field(s, "text") or "")
           for s in raw]
    if not out:
        out = [_seg(offset, offset + chunk_len, _field(resp, "text") or "")]
    return out


def _groq(wav: Path, tmp: Path, cfg: dict) -> Segments:
    import groq

    if not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError("Groq API key is not set. Add it on the Settings page.")
    client = groq.Groq()
    translate = cfg.get("groq_task", "translate") == "translate"
    prompt = "Phone call between a software company executive and a customer. Terms: " + ", ".join(cfg.get("keyterms", []))
    segs: Segments = []
    # Free tier accepts files up to 25 MB; 10 minutes of 16 kHz mono WAV is about 19 MB.
    chunks = split_at_pauses(wav, tmp / "chunks", max_len=600)
    for chunk, off in zip(chunks, chunk_offsets(chunks)):
        with open(chunk, "rb") as f:
            try:
                if translate:  # translation is only offered on whisper-large-v3
                    resp = client.audio.translations.create(model="whisper-large-v3", file=f, prompt=prompt,
                                                            response_format="verbose_json")
                else:
                    resp = client.audio.transcriptions.create(model=cfg.get("groq_model", "whisper-large-v3"), file=f,
                                                              prompt=prompt, response_format="verbose_json")
            except groq.RateLimitError as e:
                raise RuntimeError("Groq free-tier audio limit reached. Wait a while (limits reset hourly/daily) "
                                   "or switch the engine to 'Local Whisper'.") from e
        segs += _from_verbose(resp, off, duration_sec(chunk))
    return segs


def _sarvam(wav: Path, tmp: Path, cfg: dict) -> Segments:
    from sarvamai import SarvamAI

    key = os.environ.get("SARVAM_API_KEY")
    if not key:
        raise RuntimeError("SARVAM_API_KEY is not set in .env")
    client = SarvamAI(api_subscription_key=key)
    model = cfg.get("sarvam_model", "saaras:v3")
    extra = {}
    if model == "saaras:v4" and cfg.get("keyterms"):
        extra["keyterms"] = cfg["keyterms"][:50]
    segs: Segments = []
    # The REST endpoint accepts up to 30 s per request; each chunk becomes one timed segment.
    chunks = split_at_pauses(wav, tmp / "chunks", max_len=28)
    for chunk, off in zip(chunks, chunk_offsets(chunks)):
        with open(chunk, "rb") as f:
            resp = client.speech_to_text.transcribe(
                file=f, model=model, mode=cfg.get("sarvam_mode", "codemix"),
                language_code=cfg.get("sarvam_language", "unknown"), **extra)
        segs.append(_seg(off, off + duration_sec(chunk), resp.transcript))
    return segs


def _openai(wav: Path, tmp: Path, cfg: dict) -> Segments:
    from openai import OpenAI

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set in .env")
    client = OpenAI()
    model = cfg.get("openai_model", "gpt-4o-transcribe")
    prompt = "Phone call between a sales/support executive and a customer, Hindi and English mixed. Terms: " + ", ".join(cfg.get("keyterms", []))
    segs: Segments = []
    # Short chunks so each piece gets a useful time stamp (gpt-4o models return no segment times).
    chunks = split_at_pauses(wav, tmp / "chunks", max_len=600 if model == "whisper-1" else 30)
    for chunk, off in zip(chunks, chunk_offsets(chunks)):
        with open(chunk, "rb") as f:
            if model == "whisper-1":
                resp = client.audio.transcriptions.create(model=model, file=f, prompt=prompt, response_format="verbose_json")
                segs += _from_verbose(resp, off, duration_sec(chunk))
            else:
                resp = client.audio.transcriptions.create(model=model, file=f, prompt=prompt)
                segs.append(_seg(off, off + duration_sec(chunk), resp.text))
    return segs


_LOCAL_MODEL = None


def _local(wav: Path, cfg: dict) -> Segments:
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
    task = "translate" if cfg.get("groq_task", "translate") == "translate" else "transcribe"
    segs, _ = _LOCAL_MODEL.transcribe(audio, task=task, beam_size=5, condition_on_previous_text=False,
                                      no_repeat_ngram_size=4, compression_ratio_threshold=2.2)
    return [_seg(s.start, s.end, s.text) for s in segs]


if __name__ == "__main__":  # quick manual test: python -m callanalyzer.transcribe file.wav [engine]
    import sys

    from .config import load_settings
    for s in transcribe(Path(sys.argv[1]), load_settings(), sys.argv[2] if len(sys.argv) > 2 else None):
        print(f"[{s['start']:7.1f}] {s['text']}")
