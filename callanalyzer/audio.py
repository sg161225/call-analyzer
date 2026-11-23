"""Audio helpers built on ffmpeg: normalise to 16 kHz mono and split at pauses."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def to_wav16k(src: Path, dst: Path) -> Path:
    """Convert any audio (wav/mp3/m4a/amr/...) to 16 kHz mono 16-bit WAV."""
    r = _run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(src),
              "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", str(dst)])
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg could not read {src.name}: {r.stderr.strip()[:300]}")
    return dst


def duration_sec(path: Path) -> float:
    """Real duration, decoded (headers on call-recorder WAVs are often wrong)."""
    r = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
              "-of", "default=nw=1:nk=1", str(path)])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _silences(path: Path) -> list[tuple[float, float]]:
    r = _run(["ffmpeg", "-nostdin", "-i", str(path), "-af",
              "silencedetect=noise=-35dB:d=0.3", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return list(zip(starts, ends))


def split_at_pauses(wav: Path, out_dir: Path, max_len: float) -> list[Path]:
    """Split into chunks no longer than max_len seconds, cutting inside pauses
    where possible so words are not chopped in half."""
    total = duration_sec(wav)
    if total <= max_len:
        return [wav]
    mids = [(s + e) / 2 for s, e in _silences(wav)]
    cuts, pos = [], 0.0
    while total - pos > max_len:
        window = [m for m in mids if pos + max_len * 0.5 < m <= pos + max_len]
        cut = max(window) if window else pos + max_len
        cuts.append(cut)
        pos = cut
    bounds = [0.0, *cuts, total]
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks = []
    for i, (a, b) in enumerate(zip(bounds, bounds[1:])):
        p = out_dir / f"chunk_{i:03d}.wav"
        r = _run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(wav),
                  "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-c", "copy", str(p)])
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg split failed: {r.stderr.strip()[:300]}")
        chunks.append(p)
    return chunks
