"""Health check for the load balancer, uptime monitors and `make deploy-check`."""
from __future__ import annotations

import os
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ...plugins import REGISTRY
from ...store import db

router = APIRouter()
STARTED = time.time()


@router.get("/healthz", include_in_schema=False)
def healthz() -> JSONResponse:
    ok, detail = True, "ok"
    try:
        with db.conn() as c:
            c.execute("SELECT 1").fetchone()
    except Exception as e:  # report, never raise: monitors want a status code
        ok, detail = False, type(e).__name__
    body = {"status": "ok" if ok else "down", "database": detail, "uptime_s": int(time.time() - STARTED), "version": os.environ.get("APP_VERSION", "dev"),
            "build_time": os.environ.get("BUILD_TIME", ""), "rate_limit": os.environ.get("RATE_LIMIT") == "1", "plugins": sorted(REGISTRY.loaded)}
    return JSONResponse(body, status_code=200 if ok else 503)
