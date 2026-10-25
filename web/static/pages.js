/* Per-page behaviour for the converted design pages. Everything here is local to the browser except the /api/v1 calls. */
(function () {
  var D = document;
  var path = location.pathname.replace(/\/$/, "") || "/";
  function toast(msg) {
    var t = D.createElement("div");
    t.className = "toast"; t.setAttribute("role", "status"); t.textContent = msg;
    D.body.appendChild(t); setTimeout(function () { t.remove(); }, 2600);
  }
  function siblingsOf(b) {
    return Array.prototype.filter.call(b.parentElement.children, function (x) { return x.tagName === "BUTTON"; });
  }

  // ---- exclusive button groups: segmented views, filters, chips, tabs ------
  D.addEventListener("click", function (e) {
    var b = e.target.closest(".seg button, .flt, .chips .chip");
    if (!b || b.hasAttribute("data-tool")) return;
    siblingsOf(b).forEach(function (x) { var on = x === b; x.classList.toggle("on", on); x.setAttribute("aria-pressed", on ? "true" : "false"); });
    var seg = b.closest(".seg");
    if (seg) {  // "Original" hides the outlined areas, "Areas to inspect" shows them
      var host = seg.closest(".card") || seg.parentElement;
      host.classList.toggle("orig", siblingsOf(b)[0] === b);
    }
  });

  // ---- switches -------------------------------------------------------------
  D.addEventListener("click", function (e) {
    var t = e.target.closest("[role=switch]"); if (!t) return;
    var on = t.getAttribute("aria-checked") !== "true";
    t.setAttribute("aria-checked", on ? "true" : "false");
    if (t.id === "es" || /explain|आसान/i.test(t.getAttribute("aria-label") || "")) {
      if (path === "/result/invoice" && on) { location.href = "/explain"; return; }
      if (path === "/explain" && !on) { location.href = "/result/invoice"; return; }
      t.setAttribute("aria-checked", "false");
      toast("Plain-words explanation is ready for the invoice sample only in this demo");
    }
  });

  // ---- buttons the design draws but the demo does not back yet --------------
  var LATER = {
    "/console": [],
    "/guardian": ["Save as image"], "/warn": ["फ़ोटो के रूप में सेव करें"],
  };
  D.addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    var txt = b.textContent.trim();
    var copy = /^(Copy text|Copy link|Copy)$/.test(txt);
    if (copy) {
      var src = (b.closest(".card, article, .bd") || D.body).innerText;
      var p = navigator.clipboard ? navigator.clipboard.writeText(path === "/guardian" ? src : location.href) : Promise.reject();
      p.then(function () { toast("Copied"); }, function () { toast("Copy not available here"); });
      return;
    }
    if (/^(Print card|Print or save as PDF)$/.test(txt)) { window.print(); return; }
    if ((LATER[path] || []).indexOf(txt) >= 0) { toast("Not available in this demo yet"); }
  });

  // ---- console (demo only: no real sign-in, no real decisions) --------------
  if (path.indexOf("/console") === 0) {
    D.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      var txt = b.textContent.trim();
      if (path === "/console" && /Verify and sign in/.test(txt)) { location.href = "/console/queue"; return; }
      if (path === "/console/case" && /Confirm as scam|Not a scam|Unsure|Escalate|Save decision/.test(txt)) {
        toast("Demo only: nothing was saved. Real decisions need a second reviewer.");
      }
      if (/Export/.test(txt)) { toast("Export is not available in this demo"); }
    });
  }

  // ---- delete a saved result, then show the receipt ----------------------------
  D.addEventListener("click", function (e) {
    var a = e.target.closest("[data-delete-case]"); if (!a) return;
    e.preventDefault();
    var id = a.getAttribute("data-delete-case"), go = function () { location.href = "/deletion?ref=" + encodeURIComponent("SP-" + id.slice(0, 4).toUpperCase() + "-" + id.slice(4, 8).toUpperCase()); };
    try { var h = JSON.parse(localStorage.getItem("sp-history") || "[]").filter(function (x) { return x.id !== id; }); localStorage.setItem("sp-history", JSON.stringify(h)); } catch (err) { /* ignore */ }
    fetch("/api/v1/check/" + encodeURIComponent(id), { method: "DELETE" }).then(go, go);
  });
  D.addEventListener("click", function (e) { if (e.target.closest("[data-thanks]")) toast("Thank you. Talk to them before any money moves."); });

  // ---- deletion receipt -----------------------------------------------------
  if (path === "/deletion") {
    var dq = new URLSearchParams(location.search), dref = dq.get("ref");
    var when = new Date().toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata" }) + " IST";
    var dr = D.getElementById("dr-ref"), dw = D.getElementById("dr-when");
    if (dr) dr.textContent = dref || "-";
    if (dw) dw.textContent = when;
    var all = D.getElementById("dr-all"), note = D.getElementById("dr-note");
    if (all) all.addEventListener("click", function () {
      var ids = [];
      try { ids = JSON.parse(localStorage.getItem("sp-history") || "[]").filter(function (x) { return x && x.id && !x.sample; }).map(function (x) { return x.id; }); } catch (err) { ids = []; }
      all.disabled = true;
      Promise.all(ids.map(function (id) { return fetch("/api/v1/check/" + encodeURIComponent(id), { method: "DELETE" }).catch(function () { return null; }); })).then(function () {
        try {
          Object.keys(localStorage).filter(function (k) { return k.indexOf("sp-") === 0; }).forEach(function (k) { localStorage.removeItem(k); });
          Object.keys(sessionStorage).filter(function (k) { return k.indexOf("sp-") === 0; }).forEach(function (k) { sessionStorage.removeItem(k); });
        } catch (err) { /* ignore */ }
        if (note) note.textContent = (ids.length || 0) + " saved result(s) deleted from the server, and this browser's history and settings cleared.";
      });
    });
  }

  // ---- wrong result? -> human review ---------------------------------------
  if (path === "/wrong") {
    D.addEventListener("click", function (e) {
      var a = e.target.closest("a"); if (!a || a.getAttribute("href") !== "/wrong/status") return;
      e.preventDefault();
      var picked = D.querySelector("input[type=radio]:checked"), caseId = new URLSearchParams(location.search).get("case");
      var reason = picked ? (picked.closest("label") || picked.parentElement).textContent.trim() : "";
      var note = (D.querySelector("textarea") || {}).value || "";
      var share = D.querySelector("input[type=checkbox]");
      fetch("/api/v1/wrong-result", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ case_id: caseId, reason: reason, note: note, share_for_review: !!(share && share.checked) })
      }).then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
        .then(function (j) { location.href = "/wrong/status?ref=" + encodeURIComponent(j.id); })
        .catch(function () { toast("Could not send. Please try again."); });
    });
  }

  // ---- read the result aloud (/case/<id>) -------------------------------------
  D.addEventListener("click", function (e) {
    var b = e.target.closest("[data-speak]"); if (!b) return;
    var lang = b.getAttribute("data-speak"), host = b.closest("[data-variant]") || D;
    var src = host.querySelector(".speak-src"); if (!src || !window.speechSynthesis) { toast("This browser cannot read aloud"); return; }
    window.speechSynthesis.cancel();
    var u = new SpeechSynthesisUtterance(src.textContent.replace(/\s+/g, " ").trim());
    u.lang = lang === "hi" ? "hi-IN" : "en-IN"; window.speechSynthesis.speak(u);
  });

  // ---- read aloud: the browser's own speech voice as the local fallback -----
  if (path === "/listen") {
    var synth = window.speechSynthesis;
    var text = (D.querySelector(".card") || D.body).innerText.replace(/\s+/g, " ").trim();
    var lang = "hi-IN", rate = 1;
    var say = function () {
      if (!synth) { toast("This browser cannot read aloud"); return; }
      synth.cancel(); var u = new SpeechSynthesisUtterance(text); u.lang = lang; u.rate = rate; synth.speak(u);
    };
    D.addEventListener("click", function (e) {
      var b = e.target.closest("button.pb, button.sb"); if (!b) return;
      var t = b.textContent.trim();
      if (b.classList.contains("pb")) {
        if (!synth) { toast("This browser cannot read aloud"); return; }
        if (synth.speaking && !synth.paused) { synth.pause(); } else if (synth.paused) { synth.resume(); } else { say(); }
      } else if (/फिर से/.test(t)) { say(); }
      else if (/धीमे/.test(t)) { rate = rate === 1 ? 0.7 : 1; say(); }
      else if (/English/.test(t)) { lang = lang === "hi-IN" ? "en-IN" : "hi-IN"; say(); }
    });
  }
})();
