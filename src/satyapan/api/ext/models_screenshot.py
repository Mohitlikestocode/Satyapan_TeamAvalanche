"""/models/screenshot: check a payment screenshot and see where the tamper model thinks it was edited.

The core result page cannot show the picture, because uploads are never stored. This page runs the same full check
(satyapan.service.analyse_image), draws the predicted area on the picture in memory, and returns it inside the page as a
data URL. Nothing about the picture is written anywhere; only the verdict is saved, exactly as for a normal check.
"""
from __future__ import annotations

import base64
import io
import time

from fastapi import APIRouter, File, Request, UploadFile

from ...layers.l2_forensics import screenshot
from ...plugins import REGISTRY
from ...service import analyse_image
from ...store import db
from ..web import render, screen

router = APIRouter()
MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 40_000_000
SHOW_HEIGHT = 900


def _page():
    return screen("models-screenshot", "Check a payment screenshot", "check", [["Check now", "/check"], ["Payment screenshot", None]],
                  extra_css=["/static/css/models.css"], i18n="server")


def annotate(data: bytes, box: tuple[int, int, int, int] | None) -> str:
    """Return the picture as a JPEG data URL, with the suspected edit circled when there is one. Kept in memory only."""
    from PIL import Image, ImageDraw, ImageOps
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    if box:
        d = ImageDraw.Draw(img)
        x0, y0, x1, y1 = box
        pad = max(10, (y1 - y0) // 3)
        w = max(4, img.width // 140)
        d.ellipse((x0 - 2 * pad, y0 - pad, x1 + 2 * pad, y1 + pad), outline=(200, 20, 30), width=w)
    if img.height > SHOW_HEIGHT:
        img = img.resize((max(1, int(img.width * SHOW_HEIGHT / img.height)), SHOW_HEIGHT))
    b = io.BytesIO()
    img.save(b, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode("ascii")


def _readable(data: bytes) -> bool:
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as im:
            return im.width * im.height <= MAX_PIXELS
    except Exception:
        return False


@router.get("/models/screenshot")
def screenshot_form(request: Request):
    return render(request, "ext/models/screenshot.html", _page(), model_ready=screenshot.available())


@router.post("/models/screenshot")
async def screenshot_check(request: Request, file: UploadFile = File(...)):
    t0 = time.perf_counter()
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data += chunk
        if len(data) > MAX_BYTES:
            await file.close()
            return render(request, "ext/models/screenshot.html", _page(), status_code=413, model_ready=screenshot.available(), error="too_big")
    await file.close()
    data = bytes(data)
    if not data or not _readable(data):
        return render(request, "ext/models/screenshot.html", _page(), status_code=422, model_ready=screenshot.available(), error="unreadable")
    res = analyse_image(data, kind="screenshot")
    forensic = screenshot.run(data)
    fired = bool(forensic and forensic.signals)
    box = forensic.internal.get("box") if fired else None
    picture = annotate(data, box)
    del data  # the upload is not kept
    db.save_case(res, "")
    REGISTRY.emit("check", {"case_id": res.case_id, "kind": "screenshot", "channel": "web-models", "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                            "device": request.cookies.get("sp_dev"), "internal": request.cookies.get("sp_internal") == "1", "mode": "engine",
                            "tier": res.tier.value})
    lang = "hi" if request.cookies.get("sp_lang") == "hi" else "en"
    return render(request, "ext/models/screenshot.html", _page(), model_ready=screenshot.available(), res=res, verdict=res.verdicts[lang],
                  picture=picture, fired=fired, has_box=bool(box), model_ran=forensic is not None)
