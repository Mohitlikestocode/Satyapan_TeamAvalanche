"""/models/explain: type any message, see the verdict and which of our 33 scam-warning rules it breaks, with the words that matched.

The verdict and reasons come from the normal check (fusion + our templates). The rule table shows the AI rule check's matches;
the quoted words are the visitor's own text, shown escaped. Nothing is stored except the verdict, as for any check.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Form, Request

from ...layers.l4_semantic import llm_check
from ...layers.l4_semantic.ground_rules import RULES
from ...layers.l4_semantic.normalise import normalise
from ...plugins import REGISTRY
from ...service import analyse_text
from ...store import db
from ..web import render, wide

router = APIRouter()
GROUPS = {"investment": ("Investment and returns", "निवेश और मुनाफ़ा"), "advance_fee": ("Pay first to receive", "पाने के लिए पहले भुगतान"),
          "credentials": ("OTP, PIN, apps and links", "OTP, PIN, ऐप और लिंक"), "pressure": ("Pressure and secrecy", "दबाव और गोपनीयता"),
          "impersonation": ("Pretending to be someone", "किसी और का रूप धरना"), "jobs": ("Jobs", "नौकरी"), "loans": ("Loans", "लोन"),
          "parcel": ("Parcels", "पार्सल"), "refund": ("Refunds and payments", "रिफ़ंड और भुगतान"), "invoice": ("Changed accounts", "बदला खाता"),
          "threat": ("Threats", "धमकी"), "heuristic": ("Common sense", "सामान्य समझ")}


def _page():
    return wide("models-explain", "Why is this a scam?", "check", [["Check now", "/check"], ["Why is this a scam?", None]],
                extra_css=["/static/css/models.css"], i18n="server")


@router.get("/models/explain")
def explain_form(request: Request):
    return render(request, "ext/models/explain.html", _page(), rules=RULES, groups=GROUPS, ai_on=llm_check.config() is not None)


@router.post("/models/explain")
def explain_check(request: Request, text: str = Form(..., min_length=1, max_length=4000)):
    t0 = time.perf_counter()
    res = analyse_text(text, kind="message")
    ai = llm_check.check(normalise(text).text)  # same call the check just made: served from the in-memory cache
    db.save_case(res, "")
    REGISTRY.emit("check", {"case_id": res.case_id, "kind": "message", "channel": "web-explain", "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                            "device": request.cookies.get("sp_dev"), "internal": request.cookies.get("sp_internal") == "1", "mode": "engine",
                            "tier": res.tier.value})
    lang = "hi" if request.cookies.get("sp_lang") == "hi" else "en"
    matched = {m.rule: m for m in (ai.matches if ai else [])}
    return render(request, "ext/models/explain.html", _page(), rules=RULES, groups=GROUPS, ai_on=llm_check.config() is not None,
                  res=res, verdict=res.verdicts[lang], ai=ai, matched=matched, original=text)
