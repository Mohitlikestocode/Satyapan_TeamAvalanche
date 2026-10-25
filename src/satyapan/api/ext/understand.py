"""Understand first: show what a message, screenshot, PDF or voice note actually says, in the visitor's own language, before any verdict.

The extracted text is never stored by us. The check response hands it to the visitor's browser (kept only for that tab); when the
visitor presses "Explain in my language" the browser sends it back here, we ask Sarvam to translate it, and return the translation.
Rules: the visitor's text is sent to Sarvam only with an explicit consent flag, is never cached or written to disk, and rate limits apply.
Our own verdict sentences are translated separately and cached, because they are fixed templates, not user content.
"""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ...integrations import sarvam
from ...store import db

router = APIRouter()
_HITS: dict[str, list[float]] = defaultdict(list)
LIMIT_PER_HOUR = 40
LANG_PATTERN = "^(" + "|".join(sarvam.LANGS) + ")$"


def _limit(request: Request) -> None:
    dev = request.cookies.get("sp_dev") or (request.client.host if request.client else "?")
    now = time.time()
    _HITS[dev] = [t for t in _HITS[dev] if now - t < 3600] + [now]
    if len(_HITS[dev]) > LIMIT_PER_HOUR:
        raise HTTPException(429, "too many requests, please wait a few minutes")


class TranslateIn(BaseModel):
    text: str = Field(min_length=1, max_length=sarvam.MAX_TRANSLATE_CHARS)
    lang: str = Field(pattern=LANG_PATTERN)
    consent: bool = False


class VerdictIn(BaseModel):
    case_id: str = Field(max_length=40)
    lang: str = Field(pattern=LANG_PATTERN)


class SpeakTextIn(BaseModel):
    text: str = Field(min_length=1, max_length=2400)
    lang: str = Field(pattern=LANG_PATTERN)
    consent: bool = False


@router.get("/api/v1/understand/languages")
def languages() -> dict:
    return {"available": sarvam.configured() and not sarvam.over_daily_cap(),
            "languages": [{"code": k, "name": v[1], "native": v[2]} for k, v in sarvam.LANGS.items()]}


@router.post("/api/v1/understand/translate")
def translate(body: TranslateIn, request: Request) -> dict:
    """Translate what the visitor's message says. Needs consent=true: the text is sent to Sarvam. Nothing is stored."""
    if not body.consent:
        raise HTTPException(400, "consent is required: this sends the text to Sarvam for translation")
    if not sarvam.configured():
        raise HTTPException(503, "translation is not set up on this server")
    _limit(request)
    got = sarvam.translate_via_english(body.text, body.lang)
    if got is None:
        raise HTTPException(503, "the translation service is not available right now")
    translated, english, detected = got
    return {"lang": body.lang, "translated": translated, "english": english, "detected": detected}


@router.post("/api/v1/understand/verdict")
def verdict_in(body: VerdictIn, request: Request) -> dict:
    """Our own verdict sentences in another language: headline, up to three reasons and the action line. Cached per sentence."""
    case = db.get_case(body.case_id)
    if case is None:
        raise HTTPException(404, "unknown or deleted check")
    if body.lang in ("en", "hi"):
        v = case.verdicts[body.lang]
        return {"lang": body.lang, "headline": v.headline, "reasons": v.reasons_text[:3], "action": v.action_text, "machine_translated": False}
    if not sarvam.configured():
        raise HTTPException(503, "translation is not set up on this server")
    _limit(request)
    v = case.verdicts["en"]
    parts = [v.headline, *v.reasons_text[:3], v.action_text]
    done = [sarvam.translate_template(p, body.lang) for p in parts]
    if any(x is None for x in done):
        raise HTTPException(503, "the translation service is not available right now")
    return {"lang": body.lang, "headline": done[0], "reasons": done[1:-1], "action": done[-1], "machine_translated": True}


@router.post("/api/v1/understand/speak")
def speak_text(body: SpeakTextIn, request: Request) -> Response:
    """Read a translation (or our translated verdict) aloud with Sarvam. The text is not cached. Needs consent for the visitor's own text."""
    if not body.consent:
        raise HTTPException(400, "consent is required")
    if not sarvam.configured():
        raise HTTPException(503, "spoken answers are not set up on this server")
    _limit(request)
    audio = sarvam.speak_raw(body.text, body.lang)
    if audio is None:
        raise HTTPException(503, "the voice service is not available right now")
    return Response(audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})
