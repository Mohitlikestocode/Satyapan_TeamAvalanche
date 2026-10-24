"""Traction plugin: metrics listeners, the page-view beacon, footer links."""
from __future__ import annotations


def setup(registry) -> None:
    from ..ops import metrics
    registry.on("check", metrics.on_check)
    registry.on("dispute", metrics.on_dispute)
    registry.on("decision", metrics.on_decision)
    registry.on("delete", metrics.on_delete)
    registry.add_global_js("/static/js/traction_pv.js")
    registry.add_footer("Learn and about", "Live impact", "/impact")
