"""Upload -> transcribe (in memory/temp only) -> review -> store."""
from __future__ import annotations

import tempfile
from pathlib import Path

from . import store
from .filenames import parse_file_name
from .audio import duration_sec, to_wav16k
from .review import review_call
from .transcribe import transcribe


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
            text = transcribe(wav, settings, engine)
        # The audio and transcript are discarded here; only the review is stored.
        if len(text.strip()) < 20:
            raise RuntimeError("Almost no speech was recognised in this recording.")
        review = review_call(text, meta, settings)
        store.save_review(call_id, review, dur)
    except Exception as e:  # stored so the dashboard can show what failed
        store.save_error(call_id, f"{type(e).__name__}: {e}")
        raise
    return call_id
