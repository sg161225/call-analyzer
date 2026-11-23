"""Audio helpers built on ffmpeg: normalise to 16 kHz mono and split at pauses."""
from __future__ import annotations

import re
import shutil
import subprocess
import wave
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    """System ffmpeg if installed, otherwise the copy bundled with the imageio-ffmpeg package."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:  # pragma: no cover
        raise RuntimeError("ffmpeg not found. Run: pip install imageio-ffmpeg") from e


def _run(args: list[str]) -> subprocess.CompletedProcess:
    if args and args[0] == "ffmpeg":
        args = [ffmpeg_exe(), *args[1:]]
    return subprocess.run(args, capture_output=True, text=True, check=False,
                          encoding="utf-8", errors="replace")


def to_wav16k(src: Path, dst: Path) -> Path:
    """Convert any audio (wav/mp3/m4a/amr/...) to 16 kHz mono 16-bit WAV."""
    r = _run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(src),
              "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", str(dst)])
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg could not read {src.name}: {r.stderr.strip()[:300]}")
    return dst


def duration_sec(wav16k: Path) -> float:
    """Real duration of a WAV made by to_wav16k (counted from the samples, because
    the headers written by call recorders are often wrong)."""
    try:
        with wave.open(str(wav16k), "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except (wave.Error, OSError, ZeroDivisionError):
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
