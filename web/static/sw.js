/* Satyapan service worker: keeps the shell fast and shows a helpline page when the network is gone.
   It never caches API calls, uploads, results or anything personal. Bump VERSION when this file changes. */
const VERSION = "sp-v1-b";
const SHELL = ["/offline", "/static/gov.css", "/static/fonts.css", "/static/site.js", "/static/pages.js", "/static/favicon.svg"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/static/")) {            // assets: cache first, refresh in the background
    e.respondWith(caches.match(req).then((hit) => {
      const fresh = fetch(req).then((r) => { if (r.ok) caches.open(VERSION).then((c) => c.put(req, r.clone())); return r; }).catch(() => hit);
      return hit || fresh;
    }));
    return;
  }
  if (req.mode === "navigate" && !url.pathname.startsWith("/api/") && !url.pathname.startsWith("/case/") && !url.pathname.startsWith("/console")) {
    e.respondWith(fetch(req).catch(() => caches.match("/offline")));   // pages: network only, helpline page when offline
  }
});
