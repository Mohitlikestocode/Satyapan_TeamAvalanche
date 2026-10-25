"""Registers the Community area: navigation, footer and related links, the "Share to community" button on result pages, and the
"Family Guardian" badge trigger. Pages and APIs live in api/ext/community*.py."""
from __future__ import annotations

import logging
log = logging.getLogger("satyapan.community")


def family_shared(payload: dict) -> None:
    """The visitor pressed Share or Copy on the Ask-family page (core event "guardian"): Family Guardian badge."""
    try:
        from ..community import progress, store
        raw = store.valid_device(payload.get("device"))
        if raw:
            progress.family_open(store.dev_hash(raw))
    except Exception:  # a badge must never break the page
        log.exception("family badge failed")


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
    registry.on("guardian", family_shared)
    registry.add_global_js("/static/js/community_share.js")
    registry.add_global_js("/static/js/community_back.js")      # a Back button in the breadcrumb bar of every inner page
    registry.add_global_css("/static/css/community_back.css")
    registry.add_global_js("/static/js/community_helpline.js")  # a Call 1930 button under every risky verdict
    registry.add_global_css("/static/css/community_helpline.css")
