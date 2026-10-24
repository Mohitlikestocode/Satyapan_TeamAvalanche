"""/results: measured error rates from docs/results/, plus a live run of the text kit on this server."""
from __future__ import annotations

import threading
import time

from fastapi import APIRouter, HTTPException, Request

from ...eval import report, results
from ..web import render, wide

router = APIRouter()
_RUN_LOCK = threading.Lock()
_LAST: dict = {"t": 0.0, "res": None}
RUN_COOLDOWN_S = 20  # a repeat click within this window gets the previous run instead of a new one


@router.get("/results")
def results_page(request: Request):
    page = wide("results", "Measured results", "results", [["Results", None]], extra_css=["/static/css/models.css"],
                extra_js=["/static/js/models-results.js"], i18n="server")
    return render(request, "ext/models/results.html", page, sections=results.sections(), fmt=results.fmt_rate,
                  cond=results.condition_label)


@router.post("/api/v1/models/run-kit")
def run_kit() -> dict:
    """Run every message in data/kit/ through the checks now, rules only and as deployed. Nothing is stored."""
    if not _RUN_LOCK.acquire(blocking=False):
        raise HTTPException(429, "a run is already in progress")
    try:
        if _LAST["res"] is not None and time.time() - _LAST["t"] < RUN_COOLDOWN_S:
            return {**_LAST["res"], "cached": True}
        dev, held = report.kit_files()
        out: dict = {"dev": report.measure(dev, held_out=False), "held": report.measure(held, held_out=True) if held else None, "cached": False}
        _LAST.update(t=time.time(), res=out)
        return out
    finally:
        _RUN_LOCK.release()
