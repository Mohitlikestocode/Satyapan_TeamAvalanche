"""Public-site protection as one ASGI middleware: size limits, rate limits, security headers, friendly errors.

Settings come from environment variables, read at request time. Rate limiting is OFF unless RATE_LIMIT=1 (the Docker setup turns it on), so local runs and
tests are never throttled; size limits and security headers are always on.
  RATE_LIMIT=1           turn rate limiting on
  RATE_CHECKS_PER_MIN    checks (POST /api/v1/check) per visitor per minute        default 20
  RATE_REQUESTS_PER_MIN  all other requests per visitor per minute                  default 300
  MAX_UPLOAD_MB          largest accepted upload                                    default 25
  TRUST_PROXY=1          read the client address from X-Forwarded-For (only behind our own proxy)
  PUBLIC_HTTPS=1         send Strict-Transport-Security
A visitor is the device cookie when present, else the client address. Addresses are used in memory only, hashed, never stored.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from collections import deque

CSP = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
       "font-src 'self' data:; connect-src 'self'; media-src 'self' blob: data:; object-src 'none'; base-uri 'self'; form-action 'self'; "
       "frame-ancestors 'none'")
STATIC = ("/static/",)


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class Hardening:
    _hits: dict[str, deque] = {}

    def __init__(self, app):
        self.app = app

    # ---- helpers -------------------------------------------------------------------------------------------
    @staticmethod
    def _headers(scope) -> dict[str, str]:
        return {k.decode("latin1").lower(): v.decode("latin1") for k, v in scope.get("headers", [])}

    def _visitor(self, scope, headers) -> str:
        cookies = headers.get("cookie", "")
        for part in cookies.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "sp_dev" and v:
                return "d:" + v
        addr = scope.get("client", ("?", 0))[0]
        if os.environ.get("TRUST_PROXY") == "1" and headers.get("x-forwarded-for"):
            addr = headers["x-forwarded-for"].split(",")[0].strip()
        return "a:" + hashlib.sha256(addr.encode()).hexdigest()[:16]

    def _limited(self, key: str, limit: int, window: float = 60.0) -> int:
        """Return 0 if allowed, else seconds to wait."""
        now = time.monotonic()
        if len(self._hits) > 50_000:
            self._hits.clear()                          # bounded memory under a flood
        q = self._hits.setdefault(key, deque())
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return max(1, int(window - (now - q[0])) + 1)
        q.append(now)
        return 0

    # ---- middleware ----------------------------------------------------------------------------------------
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path, method = scope["path"], scope["method"]
        headers = self._headers(scope)
        is_static = path.startswith(STATIC)
        https = headers.get("x-forwarded-proto") == "https" or scope.get("scheme") == "https"

        async def respond(status: int, body: bytes, ctype: str, extra: list[tuple[bytes, bytes]] | None = None):
            await send({"type": "http.response.start", "status": status,
                        "headers": [(b"content-type", ctype.encode()), (b"content-length", str(len(body)).encode()), *self._security(https), *(extra or [])]})
            await send({"type": "http.response.body", "body": body})

        if method in ("POST", "PUT", "PATCH"):
            try:
                size = int(headers.get("content-length", "0"))
            except ValueError:
                size = 0
            upload = path == "/api/v1/check"
            cap = _int("MAX_UPLOAD_MB", 25) * 1024 * 1024 if upload else 256 * 1024
            if size > cap:
                await self._error(respond, 413, headers, path, "That file is too large.", "यह फ़ाइल बहुत बड़ी है।")
                return

        if os.environ.get("RATE_LIMIT") == "1" and not is_static and path != "/healthz":
            visitor = self._visitor(scope, headers)
            if method == "POST" and path == "/api/v1/check":
                wait = self._limited("check:" + visitor, _int("RATE_CHECKS_PER_MIN", 20))
            else:
                wait = self._limited("req:" + visitor, _int("RATE_REQUESTS_PER_MIN", 300))
            if wait:
                await self._error(respond, 429, headers, path, "You are going a little fast. Please wait a moment and try again.",
                                  "आप थोड़ा तेज़ जा रहे हैं। कृपया थोड़ी देर रुककर फिर कोशिश करें।", [(b"retry-after", str(wait).encode())])
                return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                existing = {k.lower() for k, _ in message.get("headers", [])}
                extra = [(k, v) for k, v in self._security(https) if k not in existing]
                message["headers"] = list(message.get("headers", [])) + extra
            await send(message)

        started = False

        async def tracking_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send_wrapper(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception:                               # never show a stack trace to a visitor
            if started:
                raise
            await self._error(respond, 500, headers, path, "Something went wrong on our side. Please try again.", "हमारी तरफ़ कुछ गड़बड़ हुई। कृपया फिर कोशिश करें।")

    @staticmethod
    def _security(https: bool) -> list[tuple[bytes, bytes]]:
        h = [(b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"), (b"referrer-policy", b"strict-origin-when-cross-origin"),
             (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"), (b"content-security-policy", CSP.encode())]
        if https and os.environ.get("PUBLIC_HTTPS") == "1":
            h.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
        return h

    @staticmethod
    async def _error(respond, status: int, headers: dict, path: str, en: str, hi: str, extra=None):
        wants_json = path.startswith("/api/") or "application/json" in headers.get("accept", "") or headers.get("content-type", "").startswith(("application/json", "multipart/"))
        lang = "hi" if "sp_lang=hi" in headers.get("cookie", "") else "en"
        msg = hi if lang == "hi" else en
        if wants_json:
            await respond(status, json.dumps({"detail": msg}, ensure_ascii=False).encode(), "application/json; charset=utf-8", extra)
            return
        page = (f'<!doctype html><html lang="{lang}"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>Satyapan</title><body style="font-family:system-ui,sans-serif;max-width:560px;margin:15vh auto;padding:0 20px;line-height:1.5">'
                f'<h1 style="font-size:24px">{msg}</h1><p><a href="/">Satyapan</a></p></body></html>')
        await respond(status, page.encode(), "text/html; charset=utf-8", extra)
