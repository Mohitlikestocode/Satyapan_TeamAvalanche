/* Satyapan front end: language/text-size toggles, check flow, small helpers. No tracking, no third-party calls. */
(function () {
  var D = document, H = D.documentElement;
  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* storage may be blocked */ } }

  function toast(msg) {
    var t = D.createElement("div");
    t.className = "toast"; t.setAttribute("role", "status"); t.textContent = msg;
    D.body.appendChild(t); setTimeout(function () { t.remove(); }, 2600);
  }

  // ---- language + text size -------------------------------------------------
  function setOn(group, idx) {
    group.querySelectorAll("button").forEach(function (x, i) {
      var on = i === idx; x.classList.toggle("on", on); x.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }
  var variants = !!D.querySelector("[data-variant]");
  function applyLang(l) {
    H.setAttribute("data-lang", l);
    if (!variants) return;  // single-language screens keep the language they were designed in
    H.lang = l === "hi" ? "hi" : "en";
    D.querySelectorAll('[data-tool="lang"]').forEach(function (g) { setOn(g, l === "hi" ? 1 : 0); });
  }
  function applySize(big) {
    H.classList.toggle("big", big);
    D.querySelectorAll('[data-tool="size"]').forEach(function (g) { setOn(g, big ? 1 : 0); });
  }
  applyLang(get("sp-lang") === "hi" ? "hi" : "en");
  applySize(get("sp-big") === "1");
  D.addEventListener("click", function (e) {
    var b = e.target.closest("[data-tool] button"); if (!b) return;
    var g = b.parentElement, second = b === g.querySelectorAll("button")[1], tool = g.getAttribute("data-tool");
    if (tool === "lang") {
      set("sp-lang", second ? "hi" : "en"); applyLang(second ? "hi" : "en");
      if (!variants) toast("Language saved. This screen is shown in one language for now.");
    }
    if (tool === "size") { set("sp-big", second ? "1" : "0"); applySize(second); }
  });

  // ---- nav highlight --------------------------------------------------------
  var path = location.pathname.replace(/\/$/, "") || "/";
  D.querySelectorAll(".mnav a, .snav a").forEach(function (a) {
    var h = a.getAttribute("href"); a.classList.remove("on"); a.removeAttribute("aria-current");
    var on = h === "/" ? path === "/" : (path === h || path.indexOf(h + "/") === 0);
    if (on) { a.classList.add("on"); a.setAttribute("aria-current", "page"); }
  });
  if (path.indexOf("/result") === 0 || path.indexOf("/check") === 0) {
    D.querySelectorAll(".snav a").forEach(function (a) { if (a.getAttribute("href") === "/check") a.classList.add("on"); });
  }

  // ---- links the design left as "#" ----------------------------------------
  D.addEventListener("click", function (e) {
    var a = e.target.closest("a[data-todo]"); if (!a) return;
    e.preventDefault(); toast("Not available in this demo yet");
  });
  // copy-to-clipboard on the complaint draft
  D.addEventListener("click", function (e) {
    var a = e.target.closest("a");
    if (!a || path !== "/report/complaint" || a.textContent.trim().indexOf("Copy text") !== 0) return;
    e.preventDefault();
    var txt = (D.querySelector(".bd") || D.body).innerText;
    var p = navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject();
    p.then(function () { toast("Copied"); }, function () { toast("Copy not available here"); });
  });
  // Warn others: use the phone's own share sheet when there is one
  D.addEventListener("click", function (e) {
    var a = e.target.closest("a");
    if (!a || path !== "/warn" || !navigator.share || a.getAttribute("href") !== "/guardian/share") return;
    e.preventDefault(); navigator.share({ title: "Satyapan", text: D.title, url: location.origin + "/" }).catch(function () {});
  });

  // ---- check flow -----------------------------------------------------------
  if (path === "/check") initCheck();
  if (path === "/check/progress") initProgress();

  function initCheck() {
    var KINDS = ["screenshot", "pdf", "qr", "link", "message", "voice"];
    var ACCEPT = { screenshot: "image/*", pdf: "application/pdf", qr: "image/*", voice: "audio/*,video/*" };
    var opts = D.querySelectorAll(".opt"), fileCard = D.querySelector(".file");
    var state = { kind: "screenshot", file: null };
    var input = D.createElement("input"); input.type = "file"; input.hidden = true; D.body.appendChild(input);
    var box = D.createElement("div"); box.style.display = "none";
    var ta = D.createElement("textarea"); ta.className = "ta-in"; ta.setAttribute("aria-label", "Text to check"); ta.maxLength = 4000;
    box.appendChild(ta);
    var err = D.createElement("p"); err.className = "fileerr"; err.setAttribute("role", "alert");
    var go = D.querySelector("a.btn.bp"); go.parentNode.insertBefore(err, go);
    fileCard.style.display = "none";
    var spans = fileCard.querySelectorAll("span span");

    function pick(i) {
      state.kind = KINDS[i]; state.file = null; input.value = ""; fileCard.style.display = "none"; err.textContent = "";
      opts.forEach(function (o, j) { o.classList.toggle("on", i === j); o.setAttribute("aria-pressed", i === j ? "true" : "false"); });
      var textual = state.kind === "link" || state.kind === "message";
      box.style.display = textual ? "block" : "none";
      opts[i].insertAdjacentElement("afterend", box);
      ta.placeholder = state.kind === "link" ? "Paste the link here" : "Paste the message or phone number here";
      if (textual) { ta.focus(); } else { input.accept = ACCEPT[state.kind]; input.click(); }
    }
    opts.forEach(function (o, i) { o.addEventListener("click", function () { pick(i); }); });
    input.addEventListener("change", function () {
      var f = input.files[0]; if (!f) return;
      if (f.size > 20 * 1024 * 1024) { err.textContent = "That file is too large (limit 20 MB)."; input.value = ""; return; }
      state.file = f; err.textContent = "";
      spans[0].textContent = f.name; spans[1].textContent = Math.max(1, Math.round(f.size / 1024)) + " KB";
      fileCard.style.display = "flex"; opts[KINDS.indexOf(state.kind)].insertAdjacentElement("afterend", fileCard);
    });
    fileCard.querySelector("button").addEventListener("click", function () { state.file = null; input.value = ""; fileCard.style.display = "none"; });
    var chips = D.querySelectorAll(".chips .chip");
    chips.forEach(function (c) {
      c.addEventListener("click", function () {
        chips.forEach(function (x) { x.classList.toggle("on", x === c); x.setAttribute("aria-pressed", x === c ? "true" : "false"); });
      });
    });
    var cbs = D.querySelectorAll(".cb input");
    go.addEventListener("click", function (e) {
      e.preventDefault(); err.textContent = "";
      var text = ta.value.trim(), textual = state.kind === "link" || state.kind === "message";
      if (textual ? !text : !state.file) { err.textContent = "Please add what you want us to check."; return; }
      if (!cbs[1].checked) { err.textContent = "Please tick “I understand” to continue."; return; }
      var fd = new FormData();
      fd.append("kind", state.kind); fd.append("speak_aloud", cbs[0].checked ? "true" : "false");
      var chip = D.querySelector(".chips .chip.on"); if (chip) fd.append("topic", chip.textContent.trim());
      if (textual) fd.append("text", text);
      if (state.file) fd.append("file", state.file);
      go.setAttribute("aria-busy", "true");
      fetch("/api/v1/check", { method: "POST", body: fd })
        .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.detail || "failed"); return j; }); })
        .then(function (j) { location.href = "/check/progress?id=" + encodeURIComponent(j.id) + "&to=" + encodeURIComponent(j.result_url); })
        .catch(function (x) { go.removeAttribute("aria-busy"); err.textContent = "Could not start the check: " + x.message; });
    });
  }

  function initProgress() {
    var q = new URLSearchParams(location.search), to = q.get("to"), id = q.get("id");
    var safe = to && to.charAt(0) === "/" && to.charAt(1) !== "/";
    var stop = D.querySelector("button.btn.bq");
    if (stop) stop.addEventListener("click", function () {
      var done = function () { location.href = "/deletion"; };
      if (id) { fetch("/api/v1/check/" + encodeURIComponent(id), { method: "DELETE" }).then(done, done); } else { done(); }
    });
    if (safe) setTimeout(function () { location.href = to; }, 5000);
  }
})();
document.addEventListener("click", function (e) { if (e.target.closest("[data-print]")) window.print(); });
