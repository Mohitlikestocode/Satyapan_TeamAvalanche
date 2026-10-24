"""Spoken verdict: POST /api/v1/speak returns WAV audio of a saved result, read by Sarvam; 503 means "use the browser voice"."""
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


class SpeakIn(BaseModel):
    case_id: str = Field(max_length=40)
    lang: str = Field("en", pattern="^(en|hi)$")


@router.get("/api/v1/speak/status")
def status() -> dict:
    return {"available": sarvam.configured() and not sarvam.over_daily_cap()}


@router.post("/api/v1/speak")
def speak(body: SpeakIn, request: Request) -> Response:
    case = db.get_case(body.case_id)
    if case is None:
        raise HTTPException(404, "unknown or deleted check")
    if not sarvam.configured():
        raise HTTPException(503, "spoken verdicts are not set up")
    dev = request.cookies.get("sp_dev") or "?"
    now = time.time()
    _HITS[dev] = [t for t in _HITS[dev] if now - t < 3600] + [now]
    if len(_HITS[dev]) > 30:
        raise HTTPException(429, "too many requests")
    audio = sarvam.speak(sarvam.speech_text(case.verdicts[body.lang]), body.lang)
    if audio is None:
        raise HTTPException(503, "the voice service is not available right now")
    return Response(audio, media_type="audio/wav", headers={"Cache-Control": "private, max-age=3600"})
