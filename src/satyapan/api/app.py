"""FastAPI app: the web front end and the check, review and evidence APIs.

Feature areas plug in through satyapan/plugins (see its docstring): no edits to this file are needed to add pages, APIs,
checks, navigation, footer links, scripts or middleware.
"""
from __future__ import annotations

import secrets

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from ..plugins import REGISTRY, include_ext_routers, load_plugins
from . import routes_check, routes_pages, routes_review
from .web import DEVICE_COOKIE, WEB


def create_app() -> FastAPI:
    app = FastAPI(title="Satyapan", version="0.3.0")
    load_plugins()

    @app.middleware("http")
    async def device_cookie(request: Request, call_next):
        """Give each browser a random id (no personal data) so visits, streaks and votes can be counted without accounts."""
        response = await call_next(request)
        if DEVICE_COOKIE not in request.cookies and not request.url.path.startswith(("/static", "/api")) and "text/html" in response.headers.get("content-type", ""):
            response.set_cookie(DEVICE_COOKIE, secrets.token_urlsafe(12), max_age=180 * 86400, samesite="lax", httponly=True)
        return response

    for cls, options in REGISTRY.middlewares:
        app.add_middleware(cls, **options)
    include_ext_routers(app)            # first, so an ext route can override a design page with the same path
    app.include_router(routes_check.router)
    app.include_router(routes_review.router)
    app.include_router(routes_pages.router)
    app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")
    return app


app = create_app()
