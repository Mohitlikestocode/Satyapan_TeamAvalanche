"""Sarvam: spoken verdicts (text to speech) and translation into Indian languages.

Two kinds of text can go to Sarvam, and they are kept apart:
* OUR OWN template sentences (the verdict wording): sent freely, cached on disk by hash so a repeat costs nothing.
* THE USER'S OWN TEXT (what a message or screenshot says, a voice transcript): only when the user pressed "Explain in my language",
  never stored or cached by us, and the calling route requires an explicit consent flag.

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
# code -> (Sarvam language code, English name, name in its own script). Translation (mayura:v1) and speech (bulbul) both cover these 11.
LANGS = {
    "en": ("en-IN", "English", "English"), "hi": ("hi-IN", "Hindi", "हिन्दी"), "bn": ("bn-IN", "Bengali", "বাংলা"),
    "ta": ("ta-IN", "Tamil", "தமிழ்"), "te": ("te-IN", "Telugu", "తెలుగు"), "mr": ("mr-IN", "Marathi", "मराठी"),
    "gu": ("gu-IN", "Gujarati", "ગુજરાતી"), "kn": ("kn-IN", "Kannada", "ಕನ್ನಡ"), "ml": ("ml-IN", "Malayalam", "മലയാളം"),
    "pa": ("pa-IN", "Punjabi", "ਪੰਜਾਬੀ"), "od": ("od-IN", "Odia", "ଓଡ଼ିଆ"),
}
LANG_CODES = {k: v[0] for k, v in LANGS.items()}
TRANSLATE_URL = "https://api.sarvam.ai/translate"
TRANSLATE_CHUNK = 900     # mayura:v1 accepts up to 1000 characters per call
MAX_TRANSLATE_CHARS = 4000
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


def _tts(text: str, lang: str) -> bytes | None:
    """One text-to-speech call; None on any failure or when the daily cap is reached."""
    if not configured() or lang not in LANG_CODES or not text.strip() or over_daily_cap():
        return None
    model = os.environ.get("SARVAM_MODEL", "bulbul:v3")
    speaker = os.environ.get("SARVAM_SPEAKER", "shubh")
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
    return audio if audio.startswith(b"RIFF") else None


def speak(text: str, lang: str) -> bytes | None:
    """WAV bytes for OUR template `text`, or None when no key is set, the daily cap is reached, or Sarvam fails (the browser then uses its own voice).
    Cached on disk by a hash of the text, so use speak_raw for anything that came from a user."""
    if not configured() or lang not in LANG_CODES or not text.strip():
        return None
    model = os.environ.get("SARVAM_MODEL", "bulbul:v3")
    speaker = os.environ.get("SARVAM_SPEAKER", "shubh")
    p = _cache_path(text, lang, model, speaker)
    if p.exists():
        return p.read_bytes()
    audio = _tts(text, lang)
    if audio is None:
        return None
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(audio)
    return audio


def speak_raw(text: str, lang: str) -> bytes | None:
    """Speech for text that came from a user (a translation of their message): never cached, never written to disk."""
    return _tts(text, lang)


def _chunks(text: str, size: int = TRANSLATE_CHUNK) -> list[str]:
    """Split at line ends and sentence ends so each piece fits one translation call."""
    import re
    parts = [p for p in re.split(r"(?<=[.!?।\n])\s+", text.strip()) if p]
    out: list[str] = []
    cur = ""
    for p in parts:
        while len(p) > size:                      # a very long sentence: cut at a space
            cut = p.rfind(" ", 0, size) or size
            out.append((cur + " " + p[:cut]).strip() if cur else p[:cut])
            cur, p = "", p[cut:].strip()
        if len(cur) + len(p) + 1 > size:
            out.append(cur)
            cur = p
        else:
            cur = (cur + " " + p).strip()
    if cur:
        out.append(cur)
    return [c for c in out if c.strip()]



_KEEP = None


def _keep_re():
    """UPI IDs, links and long digit strings must come back exactly as they went in, so they are swapped for tokens during translation."""
    global _KEEP
    if _KEEP is None:
        import re
        _KEEP = re.compile(r"(https?://\S+|upi://\S+|[\w.\-]{2,}@[\w.\-]{2,}|\b[\w\-]+(?:\.[\w\-]+)*\.(?:com|in|xyz|top|co|net|org|online|shop|info|site|club|live|icu|vip)\b\S*|\b\d{9,}\b)", re.IGNORECASE)
    return _KEEP


def _protect(text: str) -> tuple[str, list[str]]:
    saved: list[str] = []

    def sub(m):
        saved.append(m.group(0).rstrip(".,;:)"))
        tail = m.group(0)[len(saved[-1]):]
        return f"[[Q{len(saved) - 1}]]{tail}"
    return _keep_re().sub(sub, text), saved


def _restore(text: str, saved: list[str]) -> str:
    import re
    return re.sub(r"[\[\(【［]{1,2}\s*(?:Q|क्यू)\s*(\d+)\s*[\]\)】］]{1,2}", lambda m: saved[int(m.group(1))] if int(m.group(1)) < len(saved) else m.group(0), text)

def translate(text: str, target: str, source: str = "auto") -> tuple[str, str | None] | None:
    """Translate into `target` (one of LANGS). Returns (translated text, detected source language code) or None.
    The text is never stored here. Callers must have the user's consent when the text is theirs."""
    if not configured() or target not in LANG_CODES or not text.strip():
        return None
    protected, saved = _protect(text[:MAX_TRANSLATE_CHARS])
    pieces = _chunks(protected)
    day = time.strftime("%Y-%m-%d")
    out: list[str] = []
    detected: str | None = None
    try:
        with http_client() as c:
            for piece in pieces:
                if over_daily_cap():
                    return None
                _calls[day] = _calls.get(day, 0) + 1
                r = c.post(TRANSLATE_URL, headers={"api-subscription-key": os.environ["SARVAM_API_KEY"], "Content-Type": "application/json"},
                           json={"input": piece, "source_language_code": source if source == "auto" else LANG_CODES.get(source, "auto"),
                                 "target_language_code": LANG_CODES[target], "model": "mayura:v1", "mode": "formal"})
                if r.status_code != 200:
                    return None
                j = r.json()
                out.append(str(j.get("translated_text", "")).strip())
                detected = j.get("source_language_code") or detected
    except (httpx.HTTPError, ValueError):
        return None
    joined = _restore("\n".join(x for x in out if x), saved)
    return (joined, detected) if joined else None


def translate_template(text: str, target: str) -> str | None:
    """Translate OUR OWN fixed sentence (verdict wording). Cached on disk by hash, so each sentence is translated once per language."""
    if target == "en" or not text.strip():
        return text
    h = hashlib.sha256(f"tr|{target}|{text}".encode()).hexdigest()[:32]
    p = db.home() / "tts_cache" / f"{h}.txt"
    if p.exists():
        return p.read_text(encoding="utf-8")
    got = translate(text, target, source="en")
    if got is None:
        return None
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(got[0], encoding="utf-8")
    return got[0]
