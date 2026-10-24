"""Shared page helpers: templates, navigation, and a render function."""
from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

from ..plugins import REGISTRY

WEB = Path(__file__).resolve().parents[3] / "web"
templates = Jinja2Templates(directory=WEB / "templates")
DEVICE_COOKIE = "sp_dev"
LANG_COOKIE = "sp_lang"


@pass_context
def tr(ctx, en: str, hi: str) -> str:
    """In templates: {{ tr("Report a scam", "धोखाधड़ी की सूचना दें") }}. Picks the language from the visitor's cookie."""
    return hi if ctx.get("lang") == "hi" else en


templates.env.globals["tr"] = tr


def lang_of(request: Request) -> str:
    return "hi" if request.cookies.get(LANG_COOKIE) == "hi" else "en"


def device_id(request: Request) -> str | None:
    """The visitor's random first-party device id (set automatically on page loads). Not tied to a person."""
    return request.cookies.get(DEVICE_COOKIE)

NAV = [
    ("home", "/", "Home", "मुख्य पृष्ठ"),
    ("check", "/check", "Check now", "जाँच करें"),
    ("dashboard", "/dashboard", "My checks", "मेरी जाँचें"),
    ("tools", "/tools", "Is this real?", "असली है?"),
    ("learn", "/learn", "Learn", "सीखें"),
    ("help", "/already-paid", "If you paid", "पैसे भेज दिए?"),
    ("how", "/how-it-works", "How it works", "कैसे काम करता है"),
]
RELATED = {
    "home": [],
    "dashboard": [],
    "check": [("See a sample result", "/result"), ("Is this really Amazon?", "/tools"), ("My checks", "/dashboard"), ("Scam Drill", "/learn/drill")],
    "help": [("Evidence report", "/report"), ("Complaint draft", "/report/complaint"), ("Warn others", "/warn"), ("Wrong result?", "/wrong")],
    "tools": [("Check something", "/check"), ("Shopkeeper check", "/shopkeeper"), ("Helper mode", "/helper"), ("Safety guide", "/learn/safety")],
    "learn": [("Scam Drill", "/learn/drill"), ("Safety guide", "/learn/safety"), ("Family safe-word card", "/learn/safe-word"), ("Check something", "/check")],
    "how": [("How it works", "/how-it-works"), ("System states", "/states"), ("Check something", "/check")],
}


RELATED_HI = {
    "See a sample result": "नमूना नतीजा देखें", "Is this really Amazon?": "क्या यह सच में Amazon है?", "My checks": "मेरी जाँचें", "Scam Drill": "स्कैम ड्रिल",
    "Evidence report": "सबूत रिपोर्ट", "Complaint draft": "शिकायत का मसौदा", "Warn others": "दूसरों को चेताएँ", "Wrong result?": "नतीजा ग़लत है?",
    "Check something": "कुछ जाँचें", "Shopkeeper check": "दुकानदार जाँच", "Helper mode": "सहायक मोड", "Safety guide": "सुरक्षा गाइड",
    "Family safe-word card": "परिवार का सेफ़-वर्ड कार्ड", "How it works": "यह कैसे काम करता है", "System states": "सिस्टम की स्थितियाँ",
    "Scam Watch: what others saw": "स्कैम वॉच: दूसरों ने क्या देखा",
}
templates.env.globals["RELATED_HI"] = RELATED_HI

FOOTER_COLUMNS = {"Services", "If you paid", "Learn and about"}


def render(request: Request, template: str, page: dict, status_code: int = 200, **ctx) -> HTMLResponse:
    """Render a page. `page` may carry `extra_css` / `extra_js` (lists of /static paths) for feature-specific assets."""
    section = page.get("section", "")
    full = {"page": page, "nav": REGISTRY.nav(NAV), "related": RELATED.get(section, []) + REGISTRY.related.get(section, []),
            "reg": REGISTRY, "lang": lang_of(request), "device": device_id(request), **ctx}
    return templates.TemplateResponse(request, template, full, status_code=status_code)


def screen(route: str, title: str, section: str, crumbs: list[list], extra_css: list[str] | None = None, extra_js: list[str] | None = None,
           i18n: str = "client") -> dict:
    """Page with the help side panel on the right (good for forms and results).
    i18n="server" means the template uses tr(en, hi) and the page reloads when the visitor switches language."""
    return {"route": route, "title": title, "kind": "screen", "section": section, "crumbs": crumbs, "extra_css": extra_css or [], "extra_js": extra_js or [],
            "i18n": i18n}


def wide(route: str, title: str, section: str, crumbs: list[list], extra_css: list[str] | None = None, extra_js: list[str] | None = None,
         i18n: str = "client") -> dict:
    """Full-width page (landing pages, dashboards, feeds). Your template supplies its own layout inside {% block content %}."""
    return {"route": route, "title": title, "kind": "wide", "section": section, "crumbs": crumbs, "extra_css": extra_css or [], "extra_js": extra_js or [],
            "i18n": i18n}
