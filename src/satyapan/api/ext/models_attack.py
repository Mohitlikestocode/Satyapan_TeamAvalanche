"""/attack: "Attack yourself". Apply real perturbations to a message, screenshot or voice note and show what our checks miss.

Every row is a fresh run of the real checks on the changed input. Nothing is stored and no result is saved as a case.
"""
from __future__ import annotations

import json
import threading

from fastapi import APIRouter, File, Form, Request, UploadFile

from ...eval import attacks, results
from ...layers.l2_forensics import audio
from ..web import render, wide

router = APIRouter()
MAX_IMAGE = 10 * 1024 * 1024
_HEAVY = threading.Semaphore(2)  # image and audio attacks run the full pipeline 6 to 7 times; limit how many run at once


def _page():
    return wide("attack", "Attack yourself", "results", [["Results", "/results"], ["Attack yourself", None]],
                extra_css=["/static/css/models.css"], i18n="server")


def _measured() -> dict:
    """Numbers for "what an attacker could do": only from results files that exist."""
    out: dict = {}
    p = results.RESULTS_DIR / "attack_text.json"
    if p.exists():
        try:
            out["text"] = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            pass
    for s in results.sections():
        if s.status == "measured" and s.key in ("screenshot_synthetic", "screenshot_real", "voice"):
            out[s.key] = s
    return out


async def _read(file: UploadFile, limit: int) -> bytes | None:
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data += chunk
        if len(data) > limit:
            await file.close()
            return None
    await file.close()
    return bytes(data)


def _show(request: Request, status_code: int = 200, **ctx):
    return render(request, "ext/models/attack.html", _page(), status_code=status_code, measured=_measured(), cond=results.condition_label,
                  fmt=results.fmt_rate, voice_ready=audio.ffmpeg_path() is not None, **ctx)


@router.get("/attack")
def attack_page(request: Request):
    return _show(request)


@router.post("/attack/text")
def attack_text(request: Request, text: str = Form(..., min_length=1, max_length=4000)):
    base, outs = attacks.attack_text(text)
    return _show(request, mode="text", base=base, outs=outs, original=text)


@router.post("/attack/image")
async def attack_image(request: Request, file: UploadFile = File(...)):
    data = await _read(file, MAX_IMAGE)
    if data is None:
        return _show(request, 413, error="too_big")
    from .models_screenshot import _readable
    if not data or not _readable(data):
        return _show(request, 422, error="unreadable")
    if not _HEAVY.acquire(timeout=30):
        return _show(request, 429, error="busy")
    try:
        base, outs = attacks.attack_image(data)
    except Exception:
        return _show(request, 422, error="unreadable")
    finally:
        _HEAVY.release()
    return _show(request, mode="image", base=base, outs=outs)


@router.post("/attack/audio")
async def attack_audio(request: Request, file: UploadFile = File(...)):
    data = await _read(file, audio.MAX_BYTES)
    if data is None:
        return _show(request, 413, error="too_big")
    if not _HEAVY.acquire(timeout=30):
        return _show(request, 429, error="busy")
    try:
        base, outs, info = attacks.attack_audio(data)
    finally:
        _HEAVY.release()
    if base is None:
        return _show(request, 422, error="unreadable_audio")
    return _show(request, mode="audio", base=base, outs=outs, info=info)
