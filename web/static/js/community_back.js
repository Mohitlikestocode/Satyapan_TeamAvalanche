/* A small "Back" button on every inner page, in the breadcrumb bar the way public-service sites do it.
   Behaviour: go back one step in this visit when that makes sense; otherwise go "up" to the previous level in the breadcrumb (or Home).
   It is not shown on the home page, the reviewer console, or while a check is running. If this script does not run, nothing else changes. */
(function () {
  var D = document, path = location.pathname.replace(/\/$/, "") || "/";
  if (path === "/" || path === "/offline" || path.indexOf("/console") === 0 || path === "/check/progress") return;
  if (D.body && D.body.getAttribute("data-kind") === "console") return;
  if (D.querySelector("[data-cm-back]")) return;

  var lang = (D.documentElement.getAttribute("data-lang") === "hi") ? "hi" : "en";
  var LABEL = { en: "Back", hi: "वापस" }, TIP = { en: "Go back to the previous page", hi: "पिछले पृष्ठ पर वापस जाएँ" };

  // The level above this page: the last link in the breadcrumb that is not Home, else Home.
  var up = "/", crumbs = D.querySelector(".crumbs");
  if (crumbs) {
    var links = crumbs.querySelectorAll("ol a");
    for (var i = links.length - 1; i >= 0; i--) {
      var h = links[i].getAttribute("href");
      if (h && h !== "/" && h.replace(/\/$/, "") !== path) { up = h; break; }
    }
  }

  // Going back in history is right only when we arrived from another page of this site, and not from a form or the middle of a round
  // (going back there would show an empty form or an old question).
  var FORMS = ["/community/report", "/check", "/drill/play", "/me/recover", "/learn/safe-word", "/warn"];
  function canGoBack() {
    try {
      if (!D.referrer || history.length < 2) return false;
      var r = new URL(D.referrer);
      if (r.origin !== location.origin) return false;
      var rp = r.pathname.replace(/\/$/, "") || "/";
      if (rp === path) return false;
      for (var j = 0; j < FORMS.length; j++) if (rp === FORMS[j] || rp.indexOf(FORMS[j] + "/") === 0) return false;
      return true;
    } catch (e) { return false; }
  }

  var a = D.createElement("a");
  a.className = "cm-back"; a.setAttribute("data-cm-back", "1"); a.href = up; a.title = TIP[lang]; a.setAttribute("aria-label", TIP[lang]);
  a.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false"><path d="M15 6l-6 6 6 6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg><span></span>';
  a.lastChild.textContent = LABEL[lang];
  if (lang === "hi") a.setAttribute("lang", "hi");
  a.addEventListener("click", function (e) {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    if (canGoBack()) { e.preventDefault(); history.back(); }
  });

  if (crumbs) {
    var wrap = crumbs.querySelector(".wrap") || crumbs;
    wrap.classList.add("cm-crumbs-flex"); wrap.insertBefore(a, wrap.firstChild);
  } else {
    var main = D.getElementById("main");
    if (!main || !main.parentNode) return;
    var bar = D.createElement("div"); bar.className = "cm-backbar"; var w = D.createElement("div"); w.className = "wrap";
    w.appendChild(a); bar.appendChild(w); main.parentNode.insertBefore(bar, main);
  }
})();
