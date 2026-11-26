"""Upload -> transcribe -> review -> store (review always; recording + timed transcript when
'storage.keep_recordings' is on in config/settings.toml)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from . import store
from .filenames import parse_file_name
from .audio import dead_air, duration_sec, peaks, to_mp3, to_wav16k
from .review import review_call, timed_transcript
from .transcribe import segments_text, transcribe


def guess_meta(file_name: str) -> dict:
    """Pre-fill executive, customer mobile and campaign from the file name."""
    return parse_file_name(file_name)


def process_call(data: bytes, meta: dict, settings: dict, engine: str | None = None) -> int:
    call_id = store.add_call(meta)
    try:
        suffix = Path(meta["file_name"]).suffix or ".wav"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"upload{suffix}"
            path.write_bytes(data)
            wav = to_wav16k(path, Path(tmp) / "call16k.wav")
            dur = duration_sec(wav)
            segments = transcribe(wav, settings, engine)
            stats = {"dead_air": dead_air(wav)}
            keep = settings.get("storage", {}).get("keep_recordings", True)
            if keep:
                store.save_recording(call_id, to_mp3(wav, Path(tmp) / "call.mp3"), "audio/mpeg", peaks(wav))
        if len(segments_text(segments).strip()) < 20:
            raise RuntimeError("Almost no speech was recognised in this recording.")
        store.save_transcript(call_id, segments if keep else [], stats)
        review = review_call(timed_transcript(segments), {**meta, "duration_sec": round(dur)}, settings)
        store.save_review(call_id, review, dur)
    except Exception as e:  # stored so the dashboard can show what failed
        store.save_error(call_id, f"{type(e).__name__}: {e}")
        raise
    return call_id
