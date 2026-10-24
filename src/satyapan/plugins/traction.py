"""Traction plugin: metrics listeners, the page-view beacon, footer links."""
from __future__ import annotations


def setup(registry) -> None:
    from ..ops import metrics
    registry.on("check", metrics.on_check)
    registry.on("dispute", metrics.on_dispute)
    registry.on("decision", metrics.on_decision)
    registry.on("delete", metrics.on_delete)
    from ..ops.hardening import Hardening
    registry.add_middleware(Hardening)
    registry.add_global_js("/static/js/traction_pv.js")
    registry.add_global_js("/static/js/traction_feedback.js")
    registry.add_global_js("/static/js/traction_pwa.js")
    registry.add_global_js("/static/js/traction_speak.js")
    registry.add_nav(75, "pilot", "/pilot", "For shops", "दुकानों के लिए")
    registry.add_footer("Services", "Ask for a pilot at your shop", "/pilot")
    registry.add_footer("Services", "Make a shop poster", "/poster")
    registry.add_footer("Learn and about", "Tell us what to fix", "/feedback")
    registry.add_footer("Learn and about", "Live impact", "/impact")
