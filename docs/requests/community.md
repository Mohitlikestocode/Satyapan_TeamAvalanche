# Requests for core changes (workstream B)

Nothing here blocks the community features: each has a working workaround in place.

1. **DONE (Mohit added it): a "guardian shared" event.** The Family Guardian badge now uses it. Original request: **A "guardian shared" event.** The Family Guardian badge is given when a visitor opens `/guardian?case=<id>` for a real result (a tiny ASGI middleware in `plugins/community.py`). The actual send happens in the visitor's own WhatsApp, so no site can see it. If the Ask-family page could `REGISTRY.emit("guardian", {"case_id": ..., "device": ...})` when its Share button is pressed (a POST or a beacon), the badge could use that exact moment. Core files: `routes_pages.py`, `guardian.html`.
2. **Footer link to Scam Watch in `base.html`.** The plugin adds "Scam Watch" and the learning links to the footer through the registry, so no change is needed; this is only noted so the integrator knows the links come from the plugin.
3. **Public site address.** Cards and posters print the address from the request (`request.base_url`). Behind a proxy that does not forward the host, this will be wrong. A `SATYAPAN_PUBLIC_URL` setting read by `api/web.py` would fix it; until then run uvicorn with `--proxy-headers` and `--forwarded-allow-ips`.
4. **`db.purge()` for community rows.** Rate-limit events (`community_events`) are only counted for the last 24 hours but never deleted. A nightly delete of rows older than 2 days would keep the table small. It is harmless to leave for the event.
