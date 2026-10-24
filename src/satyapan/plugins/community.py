"""Registers the Community area: navigation, footer and related links. Pages and APIs live in api/ext/community*.py."""
from __future__ import annotations


def setup(registry) -> None:
    registry.add_nav(45, "community", "/community", "Community", "समुदाय")
    registry.add_footer("Services", "Scam Watch (community)", "/community")
    registry.add_footer("Services", "Report a scam you saw", "/community/report")
    for section in ("check", "learn", "help", "tools"):
        registry.add_related(section, "Scam Watch: what others saw", "/community")
    registry.add_related("community", "Report a scam you saw", "/community/report")
    registry.add_related("community", "Check something", "/check")
    registry.add_related("community", "Scam Drill", "/learn/drill")
