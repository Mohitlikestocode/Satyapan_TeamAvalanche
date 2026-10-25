"""Helpers shared by the community routers: device identity, bilingual labels, template filters, page builders.

Not a router itself (no `router` attribute), so the loader skips it.
"""
from __future__ import annotations

import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import Response
from jinja2 import pass_context

from ...community import store
from ..web import DEVICE_COOKIE, templates, wide

IST = timezone(timedelta(hours=5, minutes=30))
CSS = ["/static/css/community.css"]
JS = ["/static/js/community.js"]

KIND_LABELS = [("message", "Message (SMS or WhatsApp)", "संदेश (SMS या WhatsApp)"), ("link", "Link or website", "लिंक या वेबसाइट"),
               ("upi", "UPI ID", "UPI आईडी"), ("call", "Phone call", "फ़ोन कॉल"), ("qr", "QR code", "QR कोड")]
LANG_LABELS = [("en", "English", "अंग्रेज़ी"), ("hi", "हिन्दी", "हिन्दी"), ("mix", "Hinglish (mixed)", "हिंग्लिश (मिली-जुली)"), ("other", "Other", "अन्य")]
ABUSE_LABELS = [("spam", "Spam or advertising", "स्पैम या विज्ञापन"), ("personal_info", "Shows someone's private details", "किसी की निजी जानकारी दिख रही है"),
                ("not_a_scam", "This is not a scam", "यह धोखाधड़ी नहीं है"), ("abusive", "Rude or harmful", "अभद्र या हानिकारक"),
                ("other", "Something else", "कुछ और")]
PLATFORM_LABELS = [("whatsapp", "WhatsApp", "WhatsApp"), ("sms", "SMS", "SMS"), ("telegram", "Telegram", "टेलीग्राम"),
                   ("social", "Instagram or Facebook", "इंस्टाग्राम या फ़ेसबुक"), ("youtube", "YouTube", "यूट्यूब"), ("call", "Phone call", "फ़ोन कॉल"),
                   ("email", "E-mail", "ई-मेल"), ("web", "A website or advert", "कोई वेबसाइट या विज्ञापन"), ("other", "Somewhere else", "कहीं और")]
INTENT_LABELS = [("warn", "Warn others about a scam", "दूसरों को ठगी से सावधान करें"), ("ask", "Ask: is this real?", "पूछें: क्या यह असली है?")]
COMMENT_KIND_LABELS = [("saw", "I saw this too", "मैंने भी देखा"), ("opinion", "My opinion", "मेरी राय"), ("tip", "A tip: what to do", "सुझाव: क्या करें")]
ERRORS = {
    "comment_short": ("Please write a little more (at least 3 characters).", "कृपया थोड़ा और लिखें (कम से कम 3 अक्षर)।"),
    "comment_long": ("That comment is too long. Please keep it under 500 characters.", "यह टिप्पणी बहुत लंबी है। कृपया 500 अक्षरों से कम रखें।"),
    "comment_limit": ("You have reached today's limit of 20 comments. Please come back tomorrow.", "आज की 20 टिप्पणियों की सीमा पूरी हो गई। कृपया कल आइए।"),
    "post_closed": ("This report is not open for comments.", "इस रिपोर्ट पर टिप्पणी नहीं की जा सकती।"),
    "consent": ("Please tick the box to agree that your report will be public.", "कृपया बॉक्स पर टिक करें कि आपकी रिपोर्ट सबको दिखेगी।"),
    "too_short": ("Please write a little more (at least 8 characters).", "कृपया थोड़ा और लिखें (कम से कम 8 अक्षर)।"),
    "too_long": ("That is too long. Please keep it under 1,000 characters.", "यह बहुत लंबा है। कृपया 1,000 अक्षरों से कम रखें।"),
    "need_link": ("Please paste the link you received, for example example.com/offer.", "कृपया मिला हुआ लिंक चिपकाएँ, जैसे example.com/offer।"),
    "need_upi": ("Please write the UPI ID that asked for money, like name@bank.", "कृपया वह UPI आईडी लिखें जिसने पैसे माँगे, जैसे name@bank।"),
    "rate_limit": ("You have reached today's limit of 5 reports. Please come back tomorrow.", "आज की 5 रिपोर्ट की सीमा पूरी हो गई। कृपया कल फिर आइए।"),
    "bad_kind": ("Please choose what kind of scam you saw.", "कृपया चुनें कि आपने किस तरह की धोखाधड़ी देखी।"),
}


def device(request: Request) -> tuple[str, str, bool]:
    """(raw cookie value, hashed device, is_new). Only the hash is ever stored."""
    raw = store.valid_device(request.cookies.get(DEVICE_COOKIE))
    new = raw is None
    raw = raw or secrets.token_urlsafe(12)
    return raw, store.dev_hash(raw), new


def keep_device(response: Response, raw: str, new: bool) -> Response:
    """Set the device cookie on a redirect or JSON reply. Not used on HTML replies: the core middleware already does that."""
    if new:
        response.set_cookie(DEVICE_COOKIE, raw, max_age=180 * 86400, samesite="lax", httponly=True)
    return response


def page(route: str, title: str, section: str, crumbs: list[list], kind: str = "wide", extra_js: list[str] | None = None) -> dict:
    return wide(route, title, section, crumbs, extra_css=CSS, extra_js=extra_js if extra_js is not None else JS, i18n="server")


def origin(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def whatsapp(text: str) -> str:
    return "https://wa.me/?text=" + quote(text)


def _date(ts: int | None) -> str:
    return datetime.fromtimestamp(ts, IST).strftime("%d %b %Y") if ts else ""


@pass_context
def _ago(ctx, ts: int | None) -> str:
    """"5 minutes ago" in the visitor's language; falls back to a date after a month."""
    if not ts:
        return ""
    sec = max(0, int(time.time()) - int(ts))
    hi = ctx.get("lang") == "hi"
    for limit, div, en, hin in ((60, 1, "just now", "अभी"), (3600, 60, "{n} min ago", "{n} मिनट पहले"), (86400, 3600, "{n} h ago", "{n} घंटे पहले"),
                                (30 * 86400, 86400, "{n} days ago", "{n} दिन पहले")):
        if sec < limit:
            return (hin if hi else en).format(n=sec // div)
    return _date(ts)


def _initial(name: str | None) -> str:
    return (name or "?")[:1].upper()


def _tone(name: str | None) -> int:
    return sum(map(ord, name or "")) % 6


templates.env.filters["cm_date"] = _date
templates.env.globals["cm_ago"] = _ago
templates.env.globals["cm_initial"] = _initial
templates.env.globals["cm_tone"] = _tone
templates.env.globals["cm_kinds"] = KIND_LABELS
templates.env.globals["cm_platforms"] = PLATFORM_LABELS
templates.env.globals["cm_intents"] = INTENT_LABELS
templates.env.globals["cm_ckinds"] = COMMENT_KIND_LABELS
templates.env.globals["cm_langs"] = LANG_LABELS
templates.env.globals["cm_abuse"] = ABUSE_LABELS
