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


def to_mp3(wav: Path, dst: Path, bitrate: str = "32k") -> bytes:
    """Compact mono MP3 for storage and playback (about 1 MB per 4 minutes)."""
    r = _run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(wav), "-ac", "1",
              "-codec:a", "libmp3lame", "-b:a", bitrate, str(dst)])
    if r.returncode != 0:
        raise RuntimeError(f"Could not compress the recording: {r.stderr.strip()[:200]}")
    return dst.read_bytes()


def peaks(wav: Path, n: int = 160) -> list[float]:
    """Loudness envelope (0..1) in n buckets, for drawing a waveform."""
    import array
    try:
        with wave.open(str(wav), "rb") as w:
            raw = w.readframes(w.getnframes())
    except (wave.Error, OSError):
        return []
    samples = array.array("h", raw)
    if not samples:
        return []
    size = max(1, len(samples) // n)
    out = []
    for i in range(0, len(samples), size):
        chunk = samples[i:i + size]
        out.append(max(abs(min(chunk)), abs(max(chunk))) / 32768)
    top = max(out) or 1
    return [round(v / top, 3) for v in out[:n]]


def dead_air(wav: Path, min_len: float = 4.0) -> dict:
    """Long silences in the call (possible fumbling / hold without telling the customer)."""
    gaps = [(round(s, 1), round(e - s, 1)) for s, e in _silences_min(wav, min_len)]
    return {"count": len(gaps), "total_sec": round(sum(d for _, d in gaps), 1),
            "longest_sec": max((d for _, d in gaps), default=0), "at": gaps[:20], "min_len": min_len}


def _silences_min(path: Path, min_len: float) -> list[tuple[float, float]]:
    r = _run(["ffmpeg", "-nostdin", "-i", str(path), "-af",
              f"silencedetect=noise=-35dB:d={min_len}", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return list(zip(starts, ends))


def chunk_offsets(chunks: list[Path]) -> list[float]:
    """Start time (seconds) of each chunk within the whole call."""
    offs, t = [], 0.0
    for c in chunks:
        offs.append(t)
        t += duration_sec(c)
    return offs
