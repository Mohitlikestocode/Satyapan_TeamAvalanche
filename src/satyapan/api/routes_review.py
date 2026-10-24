"""Reviewer console (demo sign-in) and the decision API.

Sign-in is a demo: pick one of two reviewer identities. No password is asked for or stored. It exists so the four-eyes rule
(two different reviewers must confirm before anything enters the known-fake registry) can be shown live.
"""
from __future__ import annotations

import time
from datetime import datetime

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from ..evidence.pack import IST
from ..store import db
from .web import render

REVIEWERS = {"reviewer.03": "Fraud desk", "reviewer.07": "Fraud desk"}
COOKIE = "sp_reviewer"
router = APIRouter()

STATUS_LABEL = {"needs_review": "Needs review", "unsure": "Needs review (unsure)", "awaiting_second": "Awaiting 2nd reviewer",
                "escalated": "Escalated", "confirmed": "Closed · confirmed scam", "not_scam": "Closed · not a scam"}
TIER_CLS = {"HIGH_RISK": "r", "REGISTRY_HIT": "r", "SUSPICIOUS": "a", "NO_RED_FLAGS": "g", "CANT_TELL": "n"}
GROUPS = [("needs_review", "Needs review"), ("awaiting_second", "Awaiting 2nd reviewer"), ("escalated", "Escalated"), ("closed", "Closed")]


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(confirm_scam|not_scam|unsure|escalate)$")
    note: str = Field("", max_length=1000)


def who(request: Request) -> str | None:
    v = request.cookies.get(COOKIE)
    return v if v in REVIEWERS else None


def fmt_ts(ts: int | None) -> str:
    return datetime.fromtimestamp(ts, IST).strftime("%d %b %Y, %H:%M") if ts else "-"


def short_codes(codes: list[str]) -> list[str]:
    skip = {"NO_FLAGS_NOT_GUARANTEE", "NO_PAYEE_FOUND", "PAYEE_UNVERIFIED"}
    return [c for c in codes if c not in skip][:4]


def page(route: str, title: str) -> dict:
    return {"route": route, "title": title, "kind": "console", "section": "how", "crumbs": []}


def ctx(request: Request, reviewer: str) -> dict:
    return {"reviewer": reviewer, "counts": db.counts(), "fmt_ts": fmt_ts, "tier_cls": TIER_CLS, "status_label": STATUS_LABEL,
            "short_codes": short_codes}


@router.get("/console", response_class=HTMLResponse, include_in_schema=False)
def console_login(request: Request) -> HTMLResponse:
    return render(request, "console/login.html", page("console", "Reviewer console: sign in"), reviewers=list(REVIEWERS))


@router.post("/console/login", include_in_schema=False)
def console_do_login(reviewer: str = Form(...)) -> RedirectResponse:
    if reviewer not in REVIEWERS:
        raise HTTPException(400, "unknown reviewer")
    r = RedirectResponse("/console/queue", status_code=303)
    r.set_cookie(COOKIE, reviewer, httponly=True, samesite="strict", max_age=8 * 3600)
    db.audit(reviewer, "sign_in", "console", "demo sign-in")
    return r


@router.get("/console/logout", include_in_schema=False)
def console_logout() -> RedirectResponse:
    r = RedirectResponse("/console", status_code=303)
    r.delete_cookie(COOKIE)
    return r


def _guard(request: Request):
    me = who(request)
    return me, (None if me else RedirectResponse("/console", status_code=303))


@router.get("/console/queue", response_class=HTMLResponse, include_in_schema=False)
def console_queue(request: Request, status: str = "needs_review", q: str = ""):
    me, redirect = _guard(request)
    if redirect:
        return redirect
    rows = db.list_reviews(status if status in {g[0] for g in GROUPS} else "needs_review", q[:60])
    return render(request, "console/queue.html", page("console/queue", "Reviewer console: queue"), rows=rows, status=status,
                  groups=GROUPS, q=q, **ctx(request, me))


@router.get("/console/case", response_class=HTMLResponse, include_in_schema=False)
def console_case(request: Request, ref: str = ""):
    me, redirect = _guard(request)
    if redirect:
        return redirect
    r = db.get_review(ref)
    case = db.get_case(r["case_id"]) if r and r["case_id"] else None
    seen = 0
    if case:
        for p in case.payees:
            seen = max(seen, next((g["count"] for g in db.campaigns() if g["payee"] == p["upi"].lower()), 0))
    return render(request, "console/case.html", page("console/case", "Reviewer console: case"), r=r, case=case, seen=seen,
                  **ctx(request, me), status_code=200 if r else 404)


@router.get("/console/campaign", response_class=HTMLResponse, include_in_schema=False)
def console_campaign(request: Request):
    me, redirect = _guard(request)
    if redirect:
        return redirect
    return render(request, "console/campaign.html", page("console/campaign", "Reviewer console: campaigns"),
                  groups_=db.campaigns(), registry=db.registry_list(), **ctx(request, me))


@router.get("/console/audit", response_class=HTMLResponse, include_in_schema=False)
def console_audit(request: Request):
    me, redirect = _guard(request)
    if redirect:
        return redirect
    return render(request, "console/audit.html", page("console/audit", "Reviewer console: audit log"), entries=db.audit_list(200),
                  chain_ok=db.audit_verify(), **ctx(request, me))


@router.post("/api/v1/console/reviews/{ref}/decision")
def decide(ref: str, body: DecisionIn, request: Request) -> dict:
    me = who(request)
    if not me:
        raise HTTPException(401, "sign in to the console first")
    try:
        r = db.decide(ref, me, body.decision, body.note)
    except KeyError:
        raise HTTPException(404, "unknown review")
    except PermissionError as e:
        raise HTTPException(409, str(e))
    return {"ref": r["ref"], "status": r["status"], "registry_updated": r["status"] == "confirmed"}


@router.get("/api/v1/console/registry")
def registry(request: Request) -> list[dict]:
    if not who(request):
        raise HTTPException(401, "sign in to the console first")
    return db.registry_list()
