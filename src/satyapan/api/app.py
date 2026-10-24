"""FastAPI app: the web front end and the check, review and evidence APIs."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import routes_check, routes_pages, routes_review
from .web import WEB

app = FastAPI(title="Satyapan", version="0.2.0")
app.include_router(routes_check.router)
app.include_router(routes_review.router)
app.include_router(routes_pages.router)
app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")
