/* One page-view beacon per page load, plus remembering ?ref= for 30 days. No IP, no fingerprinting; Do Not Track is respected. */
(function () {
  try {
    var q = new URLSearchParams(location.search), ref = (q.get("ref") || "").replace(/[^A-Za-z0-9_-]/g, "").slice(0, 40);
    if (ref) { document.cookie = "sp_ref=" + ref + "; path=/; max-age=2592000; samesite=lax"; }
    if (navigator.doNotTrack === "1") return;
    var body = JSON.stringify({ path: location.pathname, lang: document.documentElement.lang === "hi" ? "hi" : "en", ref: ref });
    if (navigator.sendBeacon) { navigator.sendBeacon("/api/v1/metrics/pv", new Blob([body], { type: "application/json" })); }
    else { fetch("/api/v1/metrics/pv", { method: "POST", headers: { "Content-Type": "application/json" }, body: body, keepalive: true }); }
  } catch (e) { /* never break the page */ }
})();
