"""Understand-first plugin: loads the panel script and styles on every page (the script only acts on result pages)."""
from __future__ import annotations


def setup(registry) -> None:
    registry.add_global_js("/static/js/understand.js?v=3")
    registry.add_global_css("/static/css/understand.css?v=3")
