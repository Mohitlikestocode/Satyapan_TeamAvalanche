"""Shared page helpers: templates, navigation, and a render function."""
from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

WEB = Path(__file__).resolve().parents[3] / "web"
templates = Jinja2Templates(directory=WEB / "templates")

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


def render(request: Request, template: str, page: dict, status_code: int = 200, **ctx) -> HTMLResponse:
    full = {"page": page, "nav": NAV, "related": RELATED.get(page.get("section", ""), []), **ctx}
    return templates.TemplateResponse(request, template, full, status_code=status_code)


def screen(route: str, title: str, section: str, crumbs: list[list]) -> dict:
    return {"route": route, "title": title, "kind": "screen", "section": section, "crumbs": crumbs}
