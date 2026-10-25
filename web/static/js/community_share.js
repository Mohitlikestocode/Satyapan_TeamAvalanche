/* Adds "Share to community" next to the existing share buttons on the result page (/case/<id>) and the Ask-family page (/guardian?case=<id>).
   Those pages belong to the core templates, so the button is added here. If this script does not run, nothing else changes. */
(function () {
  var D = document, path = location.pathname.replace(/\/$/, "");
  var TEXT = { en: "Share to community", hi: "समुदाय में साझा करें" };
  var TIP = { en: "Warn others: share this result in Scam Watch", hi: "दूसरों को चेताएँ: यह नतीजा स्कैम वॉच में साझा करें" };
  function make(caseId, lang) {
    var a = D.createElement("a");
    a.className = "btn bs cm-share-btn"; a.style.width = "auto"; a.style.padding = "0 22px";
    a.href = "/community/report?case=" + encodeURIComponent(caseId);
    a.textContent = TEXT[lang]; a.title = TIP[lang]; a.setAttribute("data-cm-share", "1");
    if (lang === "hi") a.setAttribute("lang", "hi");
    return a;
  }
  var m = path.match(/^\/case\/([A-Za-z0-9_\-]+)$/);
  if (m) {
    D.querySelectorAll(".case-acts").forEach(function (box) {
      if (box.querySelector("[data-cm-share]") || !box.querySelector("[data-speak], a[href^='/guardian']")) return;
      var v = box.closest("[data-variant]"), lang = v && v.getAttribute("data-variant") === "hi" ? "hi" : "en";
      box.appendChild(make(m[1], lang));
    });
  } else if (path === "/guardian") {
    var id = new URLSearchParams(location.search).get("case");
    var box = D.getElementById("wa") && D.getElementById("wa").parentNode;
    if (id && box && !box.querySelector("[data-cm-share]")) {
      var lang = D.documentElement.getAttribute("data-lang") === "hi" ? "hi" : "en";
      box.appendChild(make(id, lang));
    }
  }
})();
