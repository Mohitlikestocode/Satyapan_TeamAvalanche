"""Public Impact page, staff Ops page, the internal-traffic switch and the page-view beacon."""
from __future__ import annotations

import csv
import hmac
import io
import os
import time
from collections import defaultdict

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from ...ops import metrics
from ..routes_review import who
from ..web import render, wide

router = APIRouter()
CSS = ["/static/css/traction.css"]

KIND_LABELS = {"message": ("Messages", "संदेश"), "link": ("Links", "लिंक"), "qr": ("QR codes", "QR कोड"), "pdf": ("PDFs", "PDF"),
               "screenshot": ("Screenshots", "स्क्रीनशॉट"), "voice": ("Voice notes", "वॉइस नोट")}
CHANNEL_LABELS = {"web": ("Website", "वेबसाइट"), "telegram": ("Telegram", "टेलीग्राम")}
TIER_LABELS = {"HIGH_RISK": ("High risk", "ज़्यादा जोखिम"), "SUSPICIOUS": ("Suspicious", "संदिग्ध"), "CANT_TELL": ("Can't tell", "कह नहीं सकते"),
               "NO_RED_FLAGS": ("No red flags found", "कोई चेतावनी नहीं मिली"), "REGISTRY_HIT": ("Known scam", "जाना-पहचाना स्कैम")}


def bars(counter: dict, labels: dict, lang: str) -> list[dict]:
    total = sum(counter.values()) or 1
    i = 1 if lang == "hi" else 0
    return [{"label": labels.get(k, (k, k))[i], "n": v, "pct": round(100 * v / total)} for k, v in sorted(counter.items(), key=lambda kv: -kv[1])]


def human_duration(seconds: int | None, lang: str) -> str:
    if seconds is None:
        return "-"
    if seconds < 90:
        return f"{seconds} सेकंड" if lang == "hi" else f"{seconds} s"
    if seconds < 5400:
        m = round(seconds / 60)
        return f"{m} मिनट" if lang == "hi" else f"{m} min"
    h = round(seconds / 3600, 1)
    return f"{h} घंटे" if lang == "hi" else f"{h} h"


def chart(days: list[dict]) -> dict:
    top = max([d["checks"] for d in days] + [1])
    w, h, gap = 28, 120, 6
    return {"bars": [{"x": i * (w + gap), "h": round(h * d["checks"] / top), "day": d["day"], "n": d["checks"]} for i, d in enumerate(days)],
            "w": w, "h": h, "width": len(days) * (w + gap), "top": top}


@router.get("/impact", response_class=HTMLResponse, include_in_schema=False)
def impact(request: Request):
    lang = "hi" if request.cookies.get("sp_lang") == "hi" else "en"
    s = metrics.summary()
    page = wide("impact", "Live impact", "how", [["Live impact", None]], extra_css=CSS, i18n="server")
    return render(request, "ext/traction/impact.html", page, s=s, kinds=bars(s["by_kind"], KIND_LABELS, lang),
                  channels=bars(s["by_channel"], CHANNEL_LABELS, lang), tiers=bars(s["by_tier"], TIER_LABELS, lang),
                  chart=chart(metrics.daily(14)), decision=human_duration(s["median_decision_s"], lang),
                  helpful_pct=round(100 * s["feedback_good"] / s["feedback_n"]) if s["feedback_n"] else None)


@router.get("/ops", response_class=HTMLResponse, include_in_schema=False)
def ops(request: Request):
    me = who(request)
    if not me:
        return RedirectResponse("/console", status_code=303)
    s = metrics.summary()
    with metrics.conn() as c:
        pilots = [dict(r) for r in c.execute("SELECT * FROM pilot_requests ORDER BY id DESC LIMIT 50")]
        feedback = [dict(r) for r in c.execute("SELECT ts,rating,comment,tier,internal FROM feedback_answers ORDER BY id DESC LIMIT 50")]
    page = wide("ops", "Operations", "how", [["Operations", None]], extra_css=CSS, i18n="server")
    return render(request, "ext/traction/ops.html", page, s=s, daily=metrics.daily(14), refs=metrics.by_ref(), pilots=pilots, feedback=feedback,
                  fmt=lambda ts: metrics.datetime.fromtimestamp(ts, metrics.IST).strftime("%d %b %H:%M"), me=me)


@router.get("/ops/daily.csv", include_in_schema=False)
def daily_csv(request: Request):
    if not who(request):
        return RedirectResponse("/console", status_code=303)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["day_ist", "checks", "people"])
    for d in metrics.daily(60):
        w.writerow([d["day"], d["checks"], d["people"]])
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=satyapan_daily.csv"})


@router.get("/internal", response_class=HTMLResponse, include_in_schema=False)
def internal(request: Request, key: str = "", off: str = ""):
    """Mark this browser as team/test traffic so it is not counted. Needs INTERNAL_KEY in the server's environment."""
    expected = os.environ.get("INTERNAL_KEY", "")
    page = wide("internal", "Internal traffic", "how", [], extra_css=CSS, i18n="server")
    if off == "1":
        r = render(request, "ext/traction/internal.html", page, state="off")
        r.delete_cookie("sp_internal")
        return r
    if not expected or not hmac.compare_digest(key.encode(), expected.encode()):
        return render(request, "ext/traction/internal.html", page, state="denied", status_code=404)
    r = render(request, "ext/traction/internal.html", page, state="on")
    r.set_cookie("sp_internal", "1", max_age=365 * 86400, httponly=True, samesite="lax")
    return r


class PvIn(BaseModel):
    path: str = Field("/", max_length=200)
    lang: str = Field("en", max_length=5)
    ref: str = Field("", max_length=40)


_WINDOW: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
SKIP = ("/console", "/ops", "/api", "/internal", "/static")


@router.post("/api/v1/metrics/pv", status_code=204)
def pageview(body: PvIn, request: Request) -> Response:
    """One beacon per page load. Quietly ignores staff pages, over-eager clients and Do-Not-Track."""
    if request.headers.get("dnt") == "1" or body.path.startswith(SKIP):
        return Response(status_code=204)
    dev = request.cookies.get("sp_dev") or ""
    hour = int(time.time() // 3600)
    start, n = _WINDOW[dev]
    n = n + 1 if start == hour else 1
    _WINDOW[dev] = (hour, n)
    if dev and n > 300:
        return Response(status_code=204)
    ref = "".join(ch for ch in (body.ref or request.cookies.get("sp_ref", "")) if ch.isalnum() or ch in "-_")[:40]
    metrics.record_pageview(body.path, body.lang, dev or None, request.cookies.get("sp_internal") == "1", ref or None)
    return Response(status_code=204)
