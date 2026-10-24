/* Makes the site installable: adds the manifest and registers the service worker. Does nothing if the browser lacks support. */
(function () {
  try {
    if (!document.querySelector('link[rel="manifest"]')) {
      var l = document.createElement("link"); l.rel = "manifest"; l.href = "/manifest.webmanifest"; document.head.appendChild(l);
    }
    if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
      window.addEventListener("load", function () { navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () { /* optional */ }); });
    }
  } catch (e) { /* never break the page */ }
})();
