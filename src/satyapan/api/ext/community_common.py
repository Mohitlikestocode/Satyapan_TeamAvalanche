"""Helpers shared by the community routers: device identity, bilingual labels, template filters, page builders.

Not a router itself (no `router` attribute), so the loader skips it.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import Response

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
ERRORS = {
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


templates.env.filters["cm_date"] = _date
templates.env.globals["cm_kinds"] = KIND_LABELS
templates.env.globals["cm_langs"] = LANG_LABELS
templates.env.globals["cm_abuse"] = ABUSE_LABELS
