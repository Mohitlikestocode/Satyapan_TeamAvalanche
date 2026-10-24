"""/models/voice: the transcript-first voice check ("Here's what we heard", then "Check this text").

Step 1 (upload): decode, transcribe and score the voice in memory, then throw the audio away. The page shows the transcript
for the visitor to correct. The voice result travels to step 2 only as a small signed token holding the band (never audio,
never scores). Step 2 (check): run the confirmed words and the voice band through the normal checks and open the result page.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from ...contracts.models import Layer, LayerResult, Signal, Strength
from ...layers.l2_forensics import audio
from ...plugins import REGISTRY
from ...plugins.models_voice import check_voice
from ...store import db
from ..web import render, screen

router = APIRouter()
TOKEN_TTL_S = 15 * 60
MAX_TRANSCRIPT = 4000


def _key() -> bytes:
    p = db.home() / "models_voice.key"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(secrets.token_bytes(32))
    return p.read_bytes()


def sign(payload: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    mac = hmac.new(_key(), body.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{mac}"


def verify(token: str) -> dict | None:
    try:
        body, mac = token.rsplit(".", 1)
        if not hmac.compare_digest(mac, hmac.new(_key(), body.encode(), hashlib.sha256).hexdigest()[:32]):
            return None
        data = json.loads(base64.urlsafe_b64decode(body.encode()))
    except (ValueError, TypeError):
        return None
    return data if data.get("exp", 0) >= time.time() else None


def layer_from(tok: dict) -> LayerResult:
    signals = []
    if tok.get("band") == "fake" and tok.get("strength") in (Strength.WEAK_SUSPICIOUS.value, Strength.STRONG_SUSPICIOUS.value):
        signals.append(Signal(layer=Layer.L2, code="MEDIA_VOICE_SYNTHETIC", strength=Strength(tok["strength"])))
    return LayerResult(layer=Layer.L2, signals=signals, not_checked=["audio"] if tok.get("band") in ("unknown", "disagree", None) else [],
                       model_versions=tok.get("versions") or {})


def _page():
    return screen("models-voice", "Check a voice note", "check", [["Check now", "/check"], ["Voice note", None]],
                  extra_css=["/static/css/models.css"], i18n="server")


def _status() -> dict:
    return {"ffmpeg": audio.ffmpeg_path() is not None, "whisper": (audio.whisper_dir() / "model.bin").exists(), **audio.detectors_available()}


@router.get("/models/voice")
def voice_form(request: Request):
    return render(request, "ext/models/voice.html", _page(), status=_status())


@router.post("/models/voice")
async def voice_upload(request: Request, file: UploadFile = File(...)):
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data += chunk
        if len(data) > audio.MAX_BYTES:
            await file.close()
            return render(request, "ext/models/voice.html", _page(), status_code=413, status=_status(), error="too_big")
    await file.close()
    wav = audio.decode(bytes(data))
    del data  # the upload is not kept
    if wav is None:
        return render(request, "ext/models/voice.html", _page(), status_code=422, status=_status(), error="unreadable")
    layer = audio.voice_layer(wav)
    t = audio.transcribe(wav)
    seconds = round(len(wav) / audio.SR, 1)
    del wav
    strength = layer.signals[0].strength.value if layer.signals else None
    token = sign({"band": layer.internal.get("band"), "strength": strength, "versions": layer.model_versions, "s": seconds,
                  "exp": int(time.time()) + TOKEN_TTL_S})
    return render(request, "ext/models/voice.html", _page(), status=_status(), heard=True, transcript=(t[0] if t else ""),
                  lang_heard=(t[1] if t else None), seconds=seconds, token=token, no_text=not (t and t[0].strip()))


@router.post("/models/voice/check")
def voice_check(request: Request, token: str = Form(...), transcript: str = Form("", max_length=MAX_TRANSCRIPT), topic: str = Form("", max_length=80)):
    t0 = time.perf_counter()
    tok = verify(token)
    if tok is None:
        return render(request, "ext/models/voice.html", _page(), status_code=400, status=_status(), error="expired")
    res = check_voice(b"", topic=topic, transcript=transcript, layer=layer_from(tok))
    db.save_case(res, topic)
    REGISTRY.emit("check", {"case_id": res.case_id, "kind": "voice", "channel": "web-models", "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                            "device": request.cookies.get("sp_dev"), "internal": request.cookies.get("sp_internal") == "1", "mode": "engine",
                            "tier": res.tier.value})
    return RedirectResponse(f"/case/{res.case_id}", status_code=303)
