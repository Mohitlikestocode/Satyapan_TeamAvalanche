"""Pilot sign-up page, feedback API and the site feedback page."""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from ...ops import metrics, pilot
from ...store import db
from ..web import render, screen

router = APIRouter()
CSS = ["/static/css/traction.css"]
_HITS: dict[tuple[str, str], list[float]] = defaultdict(list)


def _limited(kind: str, key: str, limit: int, window: int = 3600) -> bool:
    """In-memory only: remember recent timestamps per key for a moment, never written anywhere."""
    now = time.time()
    hits = [t for t in _HITS[(kind, key)] if now - t < window]
    hits.append(now)
    _HITS[(kind, key)] = hits
    return len(hits) > limit


def _lang(request: Request) -> str:
    return "hi" if request.cookies.get("sp_lang") == "hi" else "en"


@router.get("/pilot", response_class=HTMLResponse, include_in_schema=False)
def pilot_form(request: Request):
    page = screen("pilot", "For shops and organisations", "pilot", [["For shops", None]], extra_css=CSS, i18n="server")
    return render(request, "ext/traction/pilot.html", page, values={}, errors={}, types=pilot.ORG_TYPES)


@router.post("/pilot", response_class=HTMLResponse, include_in_schema=False)
async def pilot_submit(request: Request):
    form = dict((await request.form()).items())
    dev = request.cookies.get("sp_dev") or "?"
    lang = _lang(request)
    page = screen("pilot", "For shops and organisations", "pilot", [["For shops", None]], extra_css=CSS, i18n="server")
    if form.get("website"):  # honeypot: real people never fill this hidden field
        return RedirectResponse("/pilot/thanks", status_code=303)
    clean, errors = pilot.validate_pilot(form, lang)
    if not errors and _limited("pilot", dev, 5):
        errors["org"] = "कृपया थोड़ी देर बाद फिर कोशिश करें।" if lang == "hi" else "Too many requests from this browser. Please try again later."
    if errors:
        return render(request, "ext/traction/pilot.html", page, status_code=422, values=form, errors=errors, types=pilot.ORG_TYPES)
    pilot.save_pilot(clean, request.cookies.get("sp_dev"), request.cookies.get("sp_internal") == "1")
    return RedirectResponse("/pilot/thanks", status_code=303)


@router.get("/pilot/thanks", response_class=HTMLResponse, include_in_schema=False)
def pilot_thanks(request: Request):
    page = screen("pilot/thanks", "Thank you", "pilot", [["For shops", "/pilot"], ["Thank you", None]], extra_css=CSS, i18n="server")
    return render(request, "ext/traction/pilot_thanks.html", page)


class FeedbackIn(BaseModel):
    case_id: str = Field(max_length=40)
    rating: int = Field(ge=1, le=5)
    comment: str = Field("", max_length=300)


@router.post("/api/v1/feedback", status_code=201)
def feedback(body: FeedbackIn, request: Request) -> dict:
    dev = request.cookies.get("sp_dev")
    if not dev:
        raise HTTPException(400, "open the site first")
    if _limited("feedback", dev, 30):
        raise HTTPException(429, "too many answers")
    site = body.case_id.startswith("site:")
    case = None if site else db.get_case(body.case_id)
    if not site and case is None:
        raise HTTPException(404, "unknown or deleted check")
    stored = pilot.save_feedback(body.case_id if not site else f"site:{int(time.time() // 3600)}", dev, body.rating, body.comment,
                                 case.tier.value if case else None, request.cookies.get("sp_internal") == "1")
    return {"saved": stored}


@router.get("/feedback", response_class=HTMLResponse, include_in_schema=False)
def feedback_page(request: Request):
    page = screen("feedback", "Tell us what to fix", "how", [["Feedback", None]], extra_css=CSS, i18n="server")
    return render(request, "ext/traction/feedback.html", page)


@router.get("/api/v1/metrics/summary")
def public_summary() -> dict:
    """The same numbers as /impact, for anyone to read. Team and test traffic excluded."""
    s = metrics.summary()
    return {k: s[k] for k in ("since", "people", "checks", "came_back", "visitors", "by_kind", "by_channel", "by_tier", "p50_ms", "p95_ms",
                              "disputes", "cleared", "confirmed", "pending", "feedback_n", "feedback_good", "pilots")}

