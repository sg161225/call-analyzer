"""Upload -> transcribe -> review -> store (review always; recording + timed transcript when
'storage.keep_recordings' is on in config/settings.toml)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from . import store
from .filenames import parse_file_name
from .audio import dead_air, duration_sec, peaks, to_mp3, to_wav16k
from .review import detect_speakers, review_call, timed_transcript
from .transcribe import segments_text, transcribe


def guess_meta(file_name: str) -> dict:
    """Pre-fill executive, customer mobile and campaign from the file name."""
    return parse_file_name(file_name)


WAITING = "Not reviewed yet: the free AI's daily limit was used up during this upload. The transcript is saved: use 🔁 Retry later."


def process_call(data: bytes, meta: dict, settings: dict, engine: str | None = None, review: bool = True) -> int:
    """Transcribe, store and review one call. review=False only saves the transcript (to review later)."""
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
        store.save_transcript(call_id, segments if keep else [], stats, dur)
        if not review:
            if not keep:
                raise RuntimeError("The free AI's daily limit is used up, and recordings/transcripts aren't kept "
                                   "(keep_recordings is off), so upload this call again later.")
            store.save_error(call_id, WAITING)
            return call_id
        review = review_call(timed_transcript(segments), {**meta, "duration_sec": round(dur)}, settings)
        _speakers(review, segments, settings)
        store.save_review(call_id, review, dur)
    except Exception as e:  # stored so the dashboard can show what failed
        store.save_error(call_id, f"{type(e).__name__}: {e}")
        raise
    return call_id


def _speakers(review: dict, segments: list[dict], settings: dict) -> None:
    """Replace the review's rough speaker labels with a focused second pass (kept as-is if that fails)."""
    ex = detect_speakers(segments, settings)
    if ex is not None:
        review["executive_lines"] = ex
        review["speakers_source"] = "ai"


def recheck_speakers(call_id: int, settings: dict) -> bool:
    df = store.load_calls()
    row = df[df["id"] == call_id].iloc[0]
    ex = detect_speakers(row["segments"], settings)
    if ex is None:
        return False
    store.update_review(call_id, executive_lines=ex, speakers_source="ai")
    return True


def can_retry(raw_row) -> bool:
    """A failed call can be re-reviewed without re-uploading when its transcript was saved."""
    return bool(raw_row.get("segments"))


def retry_review(call_id: int, settings: dict) -> None:
    """Run only the AI review again, from the saved transcript (no new transcription)."""
    df = store.load_calls()
    row = df[df["id"] == call_id].iloc[0]
    segments = row["segments"]
    if not segments:
        raise RuntimeError("No saved transcript for this call: remove it and upload the recording again.")
    d = row.get("duration_sec")
    dur = float(d) if d is not None and d == d and float(d) > 0 else float(segments[-1].get("end") or 0)  # d == d: not NaN
    s = lambda v: "" if v is None or (isinstance(v, float) and v != v) else str(v)  # noqa: E731 (NaN -> "")
    meta = {"file_name": row["file_name"], "executive": s(row.get("executive")), "mobile": s(row.get("mobile")),
            "call_date": s(row.get("call_date")), "campaign": s(row.get("campaign")),
            "pitch_version": s(row.get("pitch_version")), "call_type": s(row.get("call_type")) or None,
            "duration_sec": round(dur)}
    try:
        review = review_call(timed_transcript(segments), meta, settings)
        _speakers(review, segments, settings)
    except Exception as e:
        store.save_error(call_id, f"{type(e).__name__}: {e}")
        raise
    store.save_review(call_id, review, dur)
