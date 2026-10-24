/* Upgrades the "Listen" button on result pages to the Sarvam voice when it is set up. If it is not, or it fails, the browser's own voice is used. */
(function () {
  var m = location.pathname.match(/^\/case\/([A-Za-z0-9]{6,40})\/?$/);
  if (!m) return;
  var id = m[1], available = null, bypass = false, current = null;
  function check() {
    if (available !== null) return Promise.resolve(available);
    return fetch("/api/v1/speak/status").then(function (r) { return r.json(); }).then(function (j) { available = !!j.available; return available; })
      .catch(function () { available = false; return false; });
  }
  check();
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-speak]");
    if (!b || bypass || available !== true) return;           // not ready yet or not set up: the built-in handler takes over
    e.stopImmediatePropagation(); e.preventDefault();
    if (current) { current.pause(); current = null; }
    var lang = b.getAttribute("data-speak") === "hi" ? "hi" : "en", label = b.textContent;
    b.disabled = true; b.setAttribute("aria-busy", "true");
    fetch("/api/v1/speak", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ case_id: id, lang: lang }) })
      .then(function (r) { if (!r.ok) throw new Error("no audio"); return r.blob(); })
      .then(function (blob) { current = new Audio(URL.createObjectURL(blob)); return current.play(); })
      .catch(function () { b.disabled = false; bypass = true; b.click(); bypass = false; })   // fall back to the browser voice
      .then(function () { b.disabled = false; b.removeAttribute("aria-busy"); if (b.textContent !== label) b.textContent = label; });
  }, true);
})();
