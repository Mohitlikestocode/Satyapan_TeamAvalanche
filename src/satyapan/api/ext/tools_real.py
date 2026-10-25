"""Is this really them? A real check for a message, link or number that claims to be a company (Amazon, a bank, a courier, a government service).

You say which company it claims to be; we run the normal message checks and also compare its links and phone numbers with that company's
official web addresses (layers/l3_payee/brand.py). The result is an ordinary saved result page. Replaces the old static design page.
"""
from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...layers.l3_payee import brand
from ...plugins import REGISTRY
from ...service import analyse_text
from ...store import db
from ..web import render, screen

router = APIRouter()

OPTIONS = [("amazon", "Amazon", "Amazon"), ("sbi", "State Bank of India", "भारतीय स्टेट बैंक"), ("hdfc", "HDFC Bank", "HDFC बैंक"),
           ("icici", "ICICI Bank", "ICICI बैंक"), ("axis", "Axis Bank", "Axis बैंक"), ("flipkart", "Flipkart", "Flipkart"),
           ("paytm", "Paytm", "Paytm"), ("phonepe", "PhonePe", "PhonePe"), ("gpay", "Google Pay", "Google Pay"), ("jio", "Jio", "Jio"),
           ("airtel", "Airtel", "Airtel"), ("courier", "A courier or delivery company", "कूरियर या डिलीवरी कंपनी"),
           ("govt", "A government service (Aadhaar, Income Tax, IRCTC, EPFO)", "सरकारी सेवा (आधार, आयकर, IRCTC, EPFO)"),
           ("electricity", "Electricity or gas", "बिजली या गैस"), ("other", "Another company", "कोई और कंपनी")]


@router.get("/tools", response_class=HTMLResponse, include_in_schema=False)
def tools_form(request: Request, error: str = ""):
    page = screen("tools", "Is this really them?", "tools", [["Is this really them?", None]], i18n="server")
    return render(request, "ext/tools/form.html", page, options=OPTIONS, error=error, listed=sorted(brand.COMPANIES))


@router.post("/tools", include_in_schema=False)
async def tools_check(request: Request, company: str = Form("other"), text: str = Form("")):
    text = (text or "").strip()[:4000]
    if not text:
        return RedirectResponse("/tools?error=empty", status_code=303)
    t0 = time.perf_counter()
    layer = brand.check(company, text)
    res = analyse_text(text, kind="message", topic="customer care number", extra_layers=[layer] if layer else None,
                       extra_names=["brand"] if layer else None)
    db.purge()
    db.save_case(res, "customer care number")
    REGISTRY.emit("check", {"case_id": res.case_id, "kind": "message", "channel": "web-company-check", "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                            "device": request.cookies.get("sp_dev"), "internal": request.cookies.get("sp_internal") == "1", "mode": "engine", "tier": res.tier.value})
    resp = RedirectResponse(f"/case/{res.case_id}", status_code=303)
    return resp


@router.get("/shopkeeper", response_class=HTMLResponse, include_in_schema=False)
def shopkeeper(request: Request):
    """Compare who a customer's payment screenshot says was paid with the shop's own UPI ID (kept only in the browser)."""
    page = screen("shopkeeper", "Shopkeeper check", "tools", [["Shopkeeper check", None]], extra_js=["/static/js/shopkeeper.js"], i18n="server")
    return render(request, "ext/tools/shopkeeper.html", page)


@router.get("/helper", response_class=HTMLResponse, include_in_schema=False)
def helper(request: Request):
    """Helper mode: one item per person, the answer in their language, then wipe before the next person."""
    page = screen("helper", "Helper mode", "tools", [["Helper mode", None]], extra_js=["/static/js/helper.js"], i18n="server")
    return render(request, "ext/tools/helper.html", page)
