"""Shop poster generator (printable page with a QR code and a referral code) and the offline/PWA pieces."""
from __future__ import annotations

import io
import os
import re
import secrets
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

import segno
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

from ...ops import metrics
from ..web import WEB, render, screen, wide

router = APIRouter()
CSS = ["/static/css/traction.css"]
_HITS: dict[str, list[float]] = defaultdict(list)


def public_base(request: Request) -> str:
    return (os.environ.get("PUBLIC_URL") or str(request.base_url)).rstrip("/")


def qr_svg(text: str, dark: str = "#0B2A4A") -> str:
    """Inline SVG of a QR code. Generated here from our own URL, so it is safe to place in a page unescaped."""
    out = io.BytesIO()
    segno.make(text, error="m").save(out, kind="svg", scale=1, border=0, dark=dark, xmldecl=False, svgns=True, nl=False, omitsize=True)
    return out.getvalue().decode("utf-8")


def make_code(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:18] or "shop"
    return f"{slug}-{secrets.token_hex(2)}"


@router.get("/poster", response_class=HTMLResponse, include_in_schema=False)
def poster_form(request: Request):
    page = screen("poster", "Shop poster", "pilot", [["For shops", "/pilot"], ["Poster", None]], extra_css=CSS, i18n="server")
    return render(request, "ext/traction/poster_form.html", page, values={}, errors={})


@router.post("/poster", response_class=HTMLResponse, include_in_schema=False)
async def poster_make(request: Request):
    form = dict((await request.form()).items())
    name, city = (form.get("name") or "").strip()[:50], (form.get("city") or "").strip()[:40]
    hi = request.cookies.get("sp_lang") == "hi"
    errors = {}
    if len(name) < 2:
        errors["name"] = "कृपया दुकान या संस्था का नाम लिखें।" if hi else "Please enter the name of your shop or organisation."
    if len(city) < 2:
        errors["city"] = "कृपया शहर या कस्बा लिखें।" if hi else "Please enter your city or town."
    dev = request.cookies.get("sp_dev") or "?"
    now = time.time()
    _HITS[dev] = [t for t in _HITS[dev] if now - t < 3600] + [now]
    if not errors and len(_HITS[dev]) > 10:
        errors["name"] = "कृपया थोड़ी देर बाद फिर कोशिश करें।" if hi else "Too many posters from this browser. Please try again later."
    if errors:
        page = screen("poster", "Shop poster", "pilot", [["For shops", "/pilot"], ["Poster", None]], extra_css=CSS, i18n="server")
        return render(request, "ext/traction/poster_form.html", page, status_code=422, values=form, errors=errors)
    code = make_code(name)
    with metrics.conn() as c:
        c.execute("INSERT INTO ref_codes(code,name,city,created) VALUES(?,?,?,?)", (code, name, city, int(now)))
    return RedirectResponse(f"/poster/{code}", status_code=303)


@router.get("/poster/{code}", response_class=HTMLResponse, include_in_schema=False)
def poster_print(request: Request, code: str):
    with metrics.conn() as c:
        row = c.execute("SELECT name, city FROM ref_codes WHERE code=?", (code,)).fetchone()
    page = wide("poster/" + code, "Poster", "pilot", [["For shops", "/pilot"], ["Poster", None]], extra_css=CSS, i18n="server")
    if row is None:
        return render(request, "ext/traction/poster_missing.html", page, status_code=404)
    base = public_base(request)
    link = f"{base}/?ref={quote(code)}"
    bot = os.environ.get("TELEGRAM_BOT_USERNAME", "").lstrip("@")
    return render(request, "ext/traction/poster.html", page, name=row["name"], city=row["city"], code=code, link=link, short=re.sub(r"^https?://", "", base),
                  qr=qr_svg(link), tg_qr=qr_svg(f"https://t.me/{bot}") if bot else "", bot=bot,
                  wa=f"https://wa.me/?text={quote('Check before you pay: ' + link)}")


# ---- PWA ---------------------------------------------------------------------------------------------------------------
@router.get("/sw.js", include_in_schema=False)
def service_worker() -> Response:
    """Served from the site root so it can control every page."""
    p = Path(WEB / "static" / "sw.js")
    return Response(p.read_text(encoding="utf-8"), media_type="application/javascript", headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})


@router.get("/manifest.webmanifest", include_in_schema=False)
def manifest() -> FileResponse:
    return FileResponse(WEB / "static" / "manifest.webmanifest", media_type="application/manifest+json")


@router.get("/offline", response_class=HTMLResponse, include_in_schema=False)
def offline(request: Request):
    page = screen("offline", "You are offline", "how", [], extra_css=CSS, i18n="server")
    return render(request, "ext/traction/offline.html", page, bot=os.environ.get("TELEGRAM_BOT_USERNAME", "").lstrip("@"))


@router.get("/api/v1/pwa", include_in_schema=False)
def pwa_info() -> JSONResponse:
    return JSONResponse({"offline_page": "/offline", "manifest": "/manifest.webmanifest", "service_worker": "/sw.js"})
