"""Pilot requests (shops, NGOs, colleges, bank branches, police cyber cells) and feedback answers."""
from __future__ import annotations

import re
import time

from . import metrics

ORG_TYPES = {
    "shop": ("Shop or small business", "दुकान या छोटा कारोबार"),
    "ngo": ("NGO or community group", "संस्था या सामुदायिक समूह"),
    "college": ("School or college", "स्कूल या कॉलेज"),
    "bank": ("Bank or payment company", "बैंक या भुगतान कंपनी"),
    "police": ("Police or cyber cell", "पुलिस या साइबर सेल"),
    "other": ("Other", "अन्य"),
}

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_DIGITS = re.compile(r"\d[\d\s-]{6,}\d")


def scrub(text: str) -> str:
    """Remove contact details and long digit runs from free text we store as feedback."""
    return _DIGITS.sub("[removed]", _EMAIL.sub("[removed]", text or "")).strip()


def validate_pilot(form: dict, lang: str = "en") -> tuple[dict, dict]:
    """Return (clean values, errors). Errors are in the visitor's language."""
    hi = lang == "hi"
    e: dict[str, str] = {}

    def need(msg_en: str, msg_hi: str) -> str:
        return msg_hi if hi else msg_en

    org = (form.get("org") or "").strip()[:80]
    city = (form.get("city") or "").strip()[:60]
    org_type = form.get("org_type") or ""
    purpose = (form.get("purpose") or "").strip()[:500]
    contact = (form.get("contact") or "").strip()[:120]
    weekly = form.get("weekly_checks")
    if len(org) < 2:
        e["org"] = need("Please enter the name of your shop or organisation.", "कृपया अपनी दुकान या संस्था का नाम लिखें।")
    if len(city) < 2:
        e["city"] = need("Please enter your city or town.", "कृपया अपना शहर या कस्बा लिखें।")
    if org_type not in ORG_TYPES:
        e["org_type"] = need("Please choose one.", "कृपया एक चुनें।")
    n = None
    if weekly not in (None, ""):
        try:
            n = int(str(weekly).strip())
            if not 0 <= n <= 1_000_000:
                raise ValueError
        except ValueError:
            e["weekly_checks"] = need("Enter a whole number, or leave it empty.", "पूरी संख्या लिखें, या खाली छोड़ दें।")
    if contact and not (_EMAIL.fullmatch(contact) or re.fullmatch(r"\+?[\d\s-]{8,15}", contact)):
        e["contact"] = need("Enter a phone number or an email address, or leave it empty.", "फ़ोन नंबर या ईमेल लिखें, या खाली छोड़ दें।")
    if form.get("consent") not in ("on", "1", "true", True):
        e["consent"] = need("Please tick the box to continue.", "आगे बढ़ने के लिए बॉक्स पर निशान लगाएँ।")
    return {"org": org, "org_type": org_type, "city": city, "purpose": purpose, "weekly_checks": n, "contact": contact}, e


def save_pilot(clean: dict, device_raw: str | None, internal: bool) -> int:
    with metrics.conn() as c:
        cur = c.execute("INSERT INTO pilot_requests(ts,org,org_type,city,purpose,weekly_checks,contact,consent,device,internal) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (int(time.time()), clean["org"], clean["org_type"], clean["city"], clean["purpose"], clean["weekly_checks"],
                         clean["contact"], 1, metrics.hash_id(device_raw), int(internal)))
        return int(cur.lastrowid)


def save_feedback(case_id: str, device_raw: str, rating: int, comment: str, tier: str | None, internal: bool) -> bool:
    """One answer per case per device. Returns False when this device already answered."""
    with metrics.conn() as c:
        cur = c.execute("INSERT OR IGNORE INTO feedback_answers(ts,case_id,device,rating,comment,tier,internal) VALUES(?,?,?,?,?,?,?)",
                        (int(time.time()), case_id, metrics.hash_id(device_raw), rating, scrub(comment)[:300], tier, int(internal)))
        return cur.rowcount == 1
