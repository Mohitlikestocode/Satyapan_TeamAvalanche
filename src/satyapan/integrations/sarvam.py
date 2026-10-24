"""Sarvam text-to-speech for the verdict. Only OUR template text is sent: never a user's file, message or transcript.

API (docs.sarvam.ai, text-to-speech convert): POST https://api.sarvam.ai/text-to-speech with header `api-subscription-key`
and JSON {text, language_code, model, speaker, pace, speech_sample_rate}; the answer holds `audios`, a list of base64 WAV strings.
Settings from the environment: SARVAM_API_KEY (required), SARVAM_MODEL (default bulbul:v3), SARVAM_SPEAKER (default shubh),
SARVAM_DAILY_CAP (calls per day per process, default 300, protects free credits).
Audio is cached on disk by a hash of text, language, model and speaker, so a repeated verdict costs nothing.
"""
from __future__ import annotations

import base64
import hashlib
import os
import time
from pathlib import Path

import httpx

from ..store import db

URL = "https://api.sarvam.ai/text-to-speech"
MAX_CHARS = 2400          # the service allows 2,500 for bulbul:v3
LANG_CODES = {"en": "en-IN", "hi": "hi-IN"}
_calls: dict[str, int] = {}


def configured() -> bool:
    return bool(os.environ.get("SARVAM_API_KEY"))


def http_client() -> httpx.Client:
    return httpx.Client(timeout=30)


def speech_text(verdict, max_reasons: int = 3) -> str:
    """What is read aloud: the headline, the first reasons and the action line. All from the catalogue; nothing from media."""
    parts = [verdict.headline + "."] + [r.rstrip(".") + "." for r in verdict.reasons_text[:max_reasons]] + [verdict.action_text]
    return " ".join(parts)[:MAX_CHARS]


def _cache_path(text: str, lang: str, model: str, speaker: str) -> Path:
    h = hashlib.sha256(f"{lang}|{model}|{speaker}|{text}".encode()).hexdigest()[:32]
    return db.home() / "tts_cache" / f"{h}.wav"


def over_daily_cap() -> bool:
    day = time.strftime("%Y-%m-%d")
    cap = int(os.environ.get("SARVAM_DAILY_CAP", "300"))
    return _calls.get(day, 0) >= cap


def speak(text: str, lang: str) -> bytes | None:
    """WAV bytes for `text`, or None when no key is set, the daily cap is reached, or Sarvam fails (the browser then uses its own voice)."""
    if not configured() or lang not in LANG_CODES or not text.strip():
        return None
    model = os.environ.get("SARVAM_MODEL", "bulbul:v3")
    speaker = os.environ.get("SARVAM_SPEAKER", "shubh")
    p = _cache_path(text, lang, model, speaker)
    if p.exists():
        return p.read_bytes()
    if over_daily_cap():
        return None
    day = time.strftime("%Y-%m-%d")
    _calls[day] = _calls.get(day, 0) + 1
    try:
        with http_client() as c:
            r = c.post(URL, headers={"api-subscription-key": os.environ["SARVAM_API_KEY"], "Content-Type": "application/json"},
                       json={"text": text[:MAX_CHARS], "language_code": LANG_CODES[lang], "model": model, "speaker": speaker, "pace": 0.95,
                             "speech_sample_rate": 22050})
        if r.status_code != 200:
            return None
        audio = base64.b64decode("".join(r.json().get("audios") or []))
    except (httpx.HTTPError, ValueError):
        return None
    if not audio.startswith(b"RIFF"):
        return None
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(audio)
    return audio
