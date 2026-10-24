"""Check a deployed site: HTTPS, headers, health, a real check end to end, throttling on.

usage: python scripts/deploy_check.py https://your-site.example   (make deploy-check URL=https://your-site.example)
Exit code 0 only if every required check passes. Sends a few harmless requests; the test checks are marked as internal if INTERNAL_KEY is given.
"""
from __future__ import annotations

import os
import sys

import httpx

REQUIRED_HEADERS = ["x-content-type-options", "x-frame-options", "content-security-policy", "referrer-policy"]


def main(base: str) -> int:
    base = base.rstrip("/")
    results: list[tuple[bool, str]] = []

    def ok(cond: bool, msg: str) -> None:
        results.append((bool(cond), msg))

    with httpx.Client(timeout=20, follow_redirects=False) as c:
        ok(base.startswith("https://") or "127.0.0.1" in base or "localhost" in base, "site is served over HTTPS")
        key = os.environ.get("INTERNAL_KEY")
        if key:
            c.get(f"{base}/internal", params={"key": key})        # keep our own test traffic out of the public numbers
        h = c.get(f"{base}/healthz")
        j = h.json() if h.headers.get("content-type", "").startswith("application/json") else {}
        ok(h.status_code == 200 and j.get("status") == "ok", f"/healthz is ok ({j.get('version', '?')})")
        ok(j.get("rate_limit") is True, "rate limiting is switched on")
        home = c.get(base + "/")
        ok(home.status_code == 200 and "Satyapan" in home.text, "home page loads")
        for name in REQUIRED_HEADERS:
            ok(name in home.headers, f"header {name} is set")
        if base.startswith("https://"):
            ok("strict-transport-security" in home.headers, "HSTS header is set")
        r = c.post(f"{base}/api/v1/check", data={"kind": "message", "text": "Guaranteed 30% a month, pay alpha.gain88@ybl now"})
        body = r.json() if r.status_code == 200 else {}
        ok(r.status_code == 200 and body.get("mode") == "engine", "a real check runs end to end")
        if body.get("result_url"):
            page = c.get(base + body["result_url"])
            ok(page.status_code == 200 and "alpha.gain88@ybl" in page.text, "the result page renders")
            ok(c.delete(f"{base}/api/v1/check/{body['id']}").status_code == 204, "deleting a result works")
        ok(c.get(base + "/impact").status_code == 200, "/impact page loads")
        ok(c.get(base + "/ops").status_code in (303, 307), "/ops is staff-only")
        ok(c.get(base + "/api/v1/evidence/doesnotexist").status_code == 404, "unknown results return 404")

    width = max(len(m) for _, m in results)
    for passed, msg in results:
        print(("PASS  " if passed else "FAIL  ") + msg.ljust(width))
    failed = sum(1 for p, _ in results if not p)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python scripts/deploy_check.py https://your-site.example")
    sys.exit(main(sys.argv[1]))
