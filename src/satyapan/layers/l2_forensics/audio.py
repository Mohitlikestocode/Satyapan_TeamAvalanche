"""Voice notes: decode safely, transcribe locally, and look for signs of a cloned or machine-made voice.

- Decoding runs ffmpeg as a locked-down subprocess: no shell, input only from a pipe (no files, no network protocols),
  metadata stripped, 16 kHz mono float output, a time limit, a size limit and a duration limit.
- Speech to text runs locally with faster-whisper. Audio is never sent to a third party.
- The voice detector is pretrained (Spectra-AASIST3), with a threshold we calibrated on our own dev split
  (var/models/voice_calibration.json). A second detector, when installed, must agree; if the two disagree we say nothing
  about the voice ("can't tell" for this layer). Forensics alone can never make a result HIGH RISK (fusion enforces it).

Nothing here stores audio or transcripts.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ...contracts.models import Layer, LayerResult, Signal, Strength
from ...store import db

log = logging.getLogger("satyapan.audio")
SR = 16000
MAX_BYTES = 15 * 1024 * 1024
MAX_SECONDS = 120
MIN_SECONDS = 0.8
FFMPEG_TIMEOUT_S = 30


def ffmpeg_path() -> str | None:
    p = os.environ.get("SATYAPAN_FFMPEG") or shutil.which("ffmpeg")
    if p:
        return p
    if sys.platform == "win32":  # winget installs ffmpeg here without always updating PATH for running processes
        base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
        for exe in base.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe"):
            return str(exe)
    return None


def decode(data: bytes, max_seconds: float = MAX_SECONDS) -> np.ndarray | None:
    """Any audio file -> float32 mono 16 kHz samples, or None when it cannot be read. Never raises on bad input."""
    exe = ffmpeg_path()
    if exe is None or not data or len(data) > MAX_BYTES:
        return None
    args = [exe, "-nostdin", "-hide_banner", "-loglevel", "error", "-protocol_whitelist", "pipe", "-i", "pipe:0",
            "-map_metadata", "-1", "-vn", "-sn", "-dn", "-ac", "1", "-ar", str(SR), "-t", str(max_seconds), "-f", "f32le", "pipe:1"]
    kw: dict = {"input": data, "capture_output": True, "timeout": FFMPEG_TIMEOUT_S, "shell": False,
                "env": {k: os.environ[k] for k in ("SYSTEMROOT", "PATH") if k in os.environ}}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        p = subprocess.run(args, **kw)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if p.returncode != 0 or len(p.stdout) < 4 * int(MIN_SECONDS * SR):
        return None
    wav = np.frombuffer(p.stdout[: len(p.stdout) // 4 * 4], dtype="<f4").astype(np.float32)
    if not np.isfinite(wav).all() or float(np.abs(wav).max()) < 1e-4:  # silence or garbage
        return None
    return wav


def encode(wav: np.ndarray, codec: str) -> bytes | None:
    """Re-encode samples like a chat app would (used by calibration and the attack panel). codec: opus24k, aac64k, tel8k, wav."""
    exe = ffmpeg_path()
    if exe is None:
        return None
    out = {"opus24k": ["-c:a", "libopus", "-b:a", "24k", "-f", "ogg"], "aac64k": ["-c:a", "aac", "-b:a", "64k", "-f", "adts"],
           "tel8k": ["-ar", "8000", "-c:a", "pcm_mulaw", "-f", "wav"], "wav": ["-c:a", "pcm_s16le", "-f", "wav"]}[codec]
    args = [exe, "-nostdin", "-hide_banner", "-loglevel", "error", "-protocol_whitelist", "pipe", "-f", "f32le", "-ar", str(SR), "-ac", "1",
            "-i", "pipe:0", *out, "pipe:1"]
    kw: dict = {"input": wav.astype("<f4").tobytes(), "capture_output": True, "timeout": FFMPEG_TIMEOUT_S, "shell": False}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        p = subprocess.run(args, **kw)
    except (subprocess.TimeoutExpired, OSError):
        return None
    return p.stdout if p.returncode == 0 and p.stdout else None


# ---- speech to text ------------------------------------------------------------------------------------------

def models_dir() -> Path:
    return db.home() / "models"


_LOCK = threading.Lock()
_WHISPER: dict = {}


def _device() -> str:
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def whisper_dir() -> Path:
    return models_dir() / "faster-whisper-small"


def transcribe(wav: np.ndarray) -> tuple[str, str] | None:
    """(text, language) using a local faster-whisper model, or None when the model is not installed."""
    d = whisper_dir()
    if not (d / "model.bin").exists():
        return None
    with _LOCK:
        if "m" not in _WHISPER:
            try:
                from faster_whisper import WhisperModel
                dev = _device()
                _WHISPER["m"] = WhisperModel(str(d), device=dev, compute_type="float16" if dev == "cuda" else "int8")
            except Exception:
                log.exception("could not load faster-whisper")
                return None
        model = _WHISPER["m"]
        try:
            segments, info = model.transcribe(wav, beam_size=5, vad_filter=True, condition_on_previous_text=False)
            text = " ".join(s.text.strip() for s in segments).strip()
        except Exception:
            log.exception("transcription failed")
            return None
    lang = info.language if info.language in ("hi", "en") else info.language
    return text, lang


# ---- cloned-voice detection ----------------------------------------------------------------------------------

@dataclass
class VoiceScore:
    primary: float | None             # Spectra-AASIST3 bona-fide logit: higher = more like a real voice
    second: float | None = None       # second detector, same direction (higher = more real), if installed
    versions: dict[str, str] = field(default_factory=dict)


def calibration() -> dict | None:
    """Thresholds chosen on our dev split (training/voice/calibrate.py). None until calibration has run."""
    try:
        return json.loads((models_dir() / "voice_calibration.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


_DET: dict = {}


def _primary():
    d = models_dir() / "spectra-aasist3"
    if not (d / "model.safetensors").exists():
        return None
    with _LOCK:
        if "p" not in _DET:
            try:
                from .spectra_aasist3 import load
                _DET["p"] = load(d, _device())
            except Exception:
                log.exception("could not load Spectra-AASIST3")
                _DET["p"] = None
        return _DET["p"]


def _second():
    d = models_dir() / "voice-second"
    if not (d / "config.json").exists():
        return None
    with _LOCK:
        if "s" not in _DET:
            try:
                from .voice_second import load
                _DET["s"] = load(d, _device())
            except Exception:
                log.exception("could not load the second voice detector")
                _DET["s"] = None
        return _DET["s"]


def detectors_available() -> dict[str, bool]:
    return {"primary": _primary() is not None, "second": _second() is not None, "calibrated": calibration() is not None}


def score(wav: np.ndarray) -> VoiceScore:
    p, s = _primary(), _second()
    out = VoiceScore(primary=None)
    if p is not None:
        with _LOCK:
            out.primary = float(p.score(wav))
        out.versions["voice"] = "spectra-aasist3"
    if s is not None:
        with _LOCK:
            out.second = float(s.score(wav))
        out.versions["voice2"] = s.name
    return out


def judge(vs: VoiceScore, cal: dict | None) -> tuple[str, Strength | None]:
    """Turn detector scores into a band. Returns (band, strength): band is "fake", "real", "disagree" or "unknown"."""
    if vs.primary is None or not cal:
        return "unknown", None
    fake_p = vs.primary < cal["primary"]["threshold"]
    strong = vs.primary < cal["primary"].get("strong_threshold", float("-inf"))
    if vs.second is not None and "second" in cal:
        fake_s = vs.second < cal["second"]["threshold"]
        if fake_p != fake_s:
            return "disagree", None
    if fake_p:
        return "fake", Strength.STRONG_SUSPICIOUS if strong else Strength.WEAK_SUSPICIOUS
    return "real", None


def voice_layer(wav: np.ndarray | None) -> LayerResult:
    """L2 result for the voice itself. Only ever suspicious or silent; it never says a voice is real."""
    if wav is None:
        return LayerResult(layer=Layer.L2, not_checked=["audio"])
    cal = calibration()
    vs = score(wav)
    band, strength = judge(vs, cal)
    signals = []
    if band == "fake" and strength is not None:
        signals.append(Signal(layer=Layer.L2, code="MEDIA_VOICE_SYNTHETIC", strength=strength))
    not_checked = ["audio"] if band in ("unknown", "disagree") else []
    return LayerResult(layer=Layer.L2, signals=signals, not_checked=not_checked, model_versions=vs.versions,
                       internal={"band": band, "primary": vs.primary, "second": vs.second, "seconds": round(len(wav) / SR, 1)})
