"""Pages: the result page, the pages that depend on a saved check, and the static design pages from pages.json."""
from __future__ import annotations

import json
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from ..evidence.pack import build_pack, public_key_id, report_id, sign_pack
from ..plugins import REGISTRY
from ..store import db
from .routes_review import STATUS_LABEL
from .web import WEB, device_id, render, screen

router = APIRouter()

PERSONAL = {"HIGH_RISK": "high risk", "REGISTRY_HIT": "a known scam", "SUSPICIOUS": "suspicious", "CANT_TELL": "something we cannot tell",
            "NO_RED_FLAGS": "no red flags found"}


def _case(case: str) -> db.StoredCase | None:
    return db.get_case(case) if case else None


@router.post("/api/guardian/shared", include_in_schema=False)
def guardian_shared(request: Request, case: str = "") -> JSONResponse:
    """Beacon from the Ask-family page when the visitor presses Share or Copy. Only counted for a real saved check."""
    if _case(case):
        REGISTRY.emit("guardian", {"case_id": case, "device": device_id(request)})
    return JSONResponse({"ok": True})


@router.get("/case/{case_id}", response_class=HTMLResponse, include_in_schema=False)
def case_page(request: Request, case_id: str) -> HTMLResponse:
    c = db.get_case(case_id)
    rv = db.get_review(c.review_ref) if c and c.review_ref else None
    return render(request, "case.html", screen("case", "Your result", "check", [["Check", "/check"], ["Your result", None]]),
                  res=c, review=rv, status_label=STATUS_LABEL, status_code=200 if c else 404)


def wrong_status(request: Request, ref: str = ""):
    r = db.get_review(ref) if ref else None
    if r is None:  # no real review: the caller falls back to the design's sample page
        return None
    return render(request, "wrong_status.html", screen("wrong/status", "Wrong result: status", "help", [["Wrong result?", "/wrong"], ["Status", None]]), r=r,
                  status_label=STATUS_LABEL)


def _with_case(route: str, title: str, crumbs, template: str):
    """A page that needs a saved check (?case=<id>). Without one, the design's sample page is shown."""
    def view(request: Request, case: str = ""):
        c = _case(case)
        if c is None:
            return sample(route, request)
        pack = sign_pack(build_pack(c))
        origin = str(request.base_url).rstrip("/")
        return render(request, template, screen(route, title, "help", crumbs), c=c, pack=pack, rid=report_id(c.case_id),
                      key_id=public_key_id(), origin=origin, quote=quote, personal=PERSONAL, pack_json=json.dumps(pack, ensure_ascii=False, indent=1))
    return view


def sample(route: str, request: Request):
    meta = next(m for m in PAGES if m["route"] == route)
    return render(request, meta["template"], {**meta, "sample": True})


router.add_api_route("/report", _with_case("report", "Evidence report", [["If you paid", "/already-paid"], ["Evidence report", None]], "report.html"),
                     methods=["GET"], response_class=HTMLResponse, include_in_schema=False)
router.add_api_route("/report/complaint", _with_case("report/complaint", "Complaint draft", [["Evidence report", "/report"], ["Complaint draft", None]], "complaint.html"),
                     methods=["GET"], response_class=HTMLResponse, include_in_schema=False)
router.add_api_route("/guardian", _with_case("guardian", "Guardian Review", [["If you paid", "/already-paid"], ["Guardian Review", None]], "guardian.html"),
                     methods=["GET"], response_class=HTMLResponse, include_in_schema=False)


@router.get("/g/{token}", response_class=HTMLResponse, include_in_schema=False)
def guardian_view(request: Request, token: str):
    c = db.get_case_by_token(token)
    return render(request, "guardian_view.html", screen("g", "A message to check with you", "help", [["Guardian's view", None]]), c=c,
                  status_code=200 if c else 404)


PAGES = json.loads((WEB / "pages.json").read_text(encoding="utf-8"))


# Design pages that show made-up example content. They get a visible "EXAMPLE ONLY" band so nobody mistakes them for a real result.
SAMPLE_ROUTES = {"result", "result/qr", "result/invoice", "result/screenshot", "result/cant-tell", "result/no-flags", "explain", "listen",
                 "helper/verdict", "check/progress", "states", "tools/result", "guardian/share", "guardian/view"}
# Old design routes whose real versions live elsewhere
REDIRECTS = {"check/voice": "/models/voice", "report/print": "/report"}


def _static(meta: dict):
    def view(request: Request) -> HTMLResponse:
        return render(request, meta["template"], {**meta, "sample": meta["route"] in SAMPLE_ROUTES})
    return view


def _redirect(target: str):
    def view(request: Request) -> RedirectResponse:
        q = request.url.query
        return RedirectResponse(target + (("?" + q) if q else ""), status_code=302)
    return view


for _r, _t in REDIRECTS.items():
    router.add_api_route("/" + _r, _redirect(_t), methods=["GET"], include_in_schema=False, name="redirect:" + _r)


for _meta in PAGES:
    if _meta["route"] in {"report", "report/complaint", "guardian", "wrong/status"} or _meta["route"] in REDIRECTS or _meta["route"].startswith("console"):
        continue  # served above, with a fallback to the design sample where it makes sense
    router.add_api_route("/" + _meta["route"], _static(_meta), methods=["GET"], response_class=HTMLResponse,
                         include_in_schema=False, name="page:" + (_meta["route"] or "home"))
def wrong_status_view(request: Request, ref: str = ""):
    return wrong_status(request, ref) or sample("wrong/status", request)


router.add_api_route("/wrong/status", wrong_status_view, methods=["GET"], response_class=HTMLResponse, include_in_schema=False)
