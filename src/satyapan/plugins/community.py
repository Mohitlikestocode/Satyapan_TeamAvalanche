"""Registers the Community area: navigation, footer and related links, and the "Family Guardian" badge trigger.
Pages and APIs live in api/ext/community*.py."""
from __future__ import annotations

import logging
from http.cookies import SimpleCookie
from urllib.parse import parse_qs

log = logging.getLogger("satyapan.community")


class FamilyOpenMiddleware:
    """Gives the Family Guardian badge when a visitor opens Ask family (/guardian?case=...) for a result that exists.

    The send itself happens in the visitor's own WhatsApp or messages app, which no website can see, so opening the page for a real
    result is the nearest honest signal. Read-only for the request: it never changes the response and never raises into it.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] == "GET" and scope["path"] == "/guardian":
            try:
                self._note(scope)
            except Exception:  # a badge must never break the page
                log.exception("family badge failed")
        await self.app(scope, receive, send)

    @staticmethod
    def _note(scope) -> None:
        from ..community import progress, store
        from ..store import db
        case = (parse_qs(scope.get("query_string", b"").decode("latin-1")).get("case") or [""])[0]
        cookie = SimpleCookie(dict(scope["headers"]).get(b"cookie", b"").decode("latin-1"))
        raw = store.valid_device(cookie["sp_dev"].value if "sp_dev" in cookie else None)
        if raw and case and db.get_case(case):
            progress.family_open(store.dev_hash(raw))


def setup(registry) -> None:
    registry.add_nav(45, "community", "/community", "Community", "समुदाय")
    registry.add_footer("Services", "Scam Watch (community)", "/community")
    registry.add_footer("Services", "Report a scam you saw", "/community/report")
    registry.add_footer("Learn and about", "My progress and badges", "/me")
    registry.add_footer("Learn and about", "Make a warning card", "/warn")
    registry.add_footer("Learn and about", "Scam posters to print", "/learn/posters")
    registry.add_footer("Learn and about", "Leaderboard", "/learn/leaderboard")
    for section in ("check", "learn", "help", "tools"):
        registry.add_related(section, "Scam Watch: what others saw", "/community")
    registry.add_related("community", "Report a scam you saw", "/community/report")
    registry.add_related("community", "Check something", "/check")
    registry.add_related("community", "Scam Drill", "/learn/drill")
    registry.add_related("community", "Make a warning card", "/warn")
    registry.add_middleware(FamilyOpenMiddleware)
