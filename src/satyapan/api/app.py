"""FastAPI app: the web front end and the check, review and evidence APIs.

Feature areas plug in through satyapan/plugins (see its docstring): no edits to this file are needed to add pages, APIs,
checks, navigation, footer links, scripts or middleware.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from ..plugins import REGISTRY, include_ext_routers, load_plugins
from . import routes_check, routes_pages, routes_review
from .web import DEVICE_COOKIE, WEB


def _load_dotenv() -> None:
    """Read KEY=value lines from ./.env (git-ignored) without overriding real environment variables. Skipped under pytest."""
    f = Path(".env")
    if "PYTEST_CURRENT_TEST" in os.environ or not f.is_file():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _warm_up() -> None:
    """Load the installed models once in the background so the first real check is not slow. Best effort; never raises."""
    import io
    import threading
    import wave

    def work() -> None:
        try:
            from ..plugins import models_voice
            from ..service import analyse_text
            analyse_text("warm up", kind="message")
            if models_voice.ready():
                sample = Path(__file__).with_name("warmup.wav")  # a short synthetic sentence, so speech-to-text and the voice detector both load
                if sample.is_file():
                    models_voice.check_voice(sample.read_bytes())
                    return
                buf = io.BytesIO()
                with wave.open(buf, "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(16000)
                    w.writeframes(bytes(2) * 16000)
                models_voice.check_voice(buf.getvalue())
        except Exception:  # pragma: no cover
            pass

    threading.Thread(target=work, daemon=True, name="warm-up").start()


def create_app() -> FastAPI:
    _load_dotenv()
    app = FastAPI(title="Satyapan", version="0.3.0")
    load_plugins()

    @app.middleware("http")
    async def device_cookie(request: Request, call_next):
        """Give each browser a random id (no personal data) so visits, streaks and votes can be counted without accounts."""
        response = await call_next(request)
        if request.query_params.get("lang") in ("hi", "en") and "text/html" in response.headers.get("content-type", ""):
            response.set_cookie("sp_lang", request.query_params["lang"], max_age=365 * 86400, samesite="lax")
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
    if "PYTEST_CURRENT_TEST" not in os.environ and os.environ.get("WARM_UP", "1") != "0":
        app.router.on_startup.append(_warm_up)
    return app


app = create_app()
