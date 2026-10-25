/* Satyapan front end: shell controls (language, text size, contrast, menu), check flow, My checks. No tracking, no third-party calls. */
(function () {
  var D = document, H = D.documentElement;
  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* storage may be blocked */ } }
  function toast(msg) {
    var t = D.createElement("div");
    t.className = "toast"; t.setAttribute("role", "status"); t.textContent = msg;
    D.body.appendChild(t); setTimeout(function () { t.remove(); }, 2600);
  }
  window.satyapanToast = toast;
  var path = location.pathname.replace(/\/$/, "") || "/";

  // ---- shell controls --------------------------------------------------------
  function setOn(group, idx) {
    group.querySelectorAll("button").forEach(function (x, i) {
      var on = i === idx; x.classList.toggle("on", on); x.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }
  var variants = !!D.querySelector("[data-variant]");
  function applyLang(l) {
    H.setAttribute("data-lang", l);
    H.lang = l === "hi" && variants ? "hi" : "en";
    D.querySelectorAll('[data-tool="lang"]').forEach(function (g) { setOn(g, l === "hi" ? 1 : 0); });
  }
  function applySize(n) {
    H.setAttribute("data-size", String(n));
    D.querySelectorAll('[data-tool="size"]').forEach(function (g) { setOn(g, n); });
  }
  function applyContrast(on) {
    H.classList.toggle("hc", on);
    D.querySelectorAll("[data-contrast]").forEach(function (b) { b.setAttribute("aria-pressed", on ? "true" : "false"); });
  }
  function syncLangCookie(l) {  // lets the server render pages in the visitor's language
    var m = D.cookie.match(/(?:^|; )sp_lang=([^;]*)/), cur = m ? m[1] : "en";
    if (cur === l) return false;
    D.cookie = "sp_lang=" + l + "; path=/; max-age=31536000; samesite=lax";
    return true;
  }
  var serverI18n = D.body.getAttribute("data-i18n") === "server";
  var qLang = new URLSearchParams(location.search).get("lang");
  if (qLang === "hi" || qLang === "en") set("sp-lang", qLang);   // a shared ?lang=hi link opens in Hindi
  var startLang = get("sp-lang") === "hi" ? "hi" : "en";
  if (syncLangCookie(startLang) && serverI18n) { location.reload(); return; }
  applyLang(startLang);
  applySize(get("sp-size") === "0" ? 0 : get("sp-size") === "2" ? 2 : 1);
  applyContrast(get("sp-hc") === "1");

  D.addEventListener("click", function (e) {
    var b = e.target.closest("[data-tool] button");
    if (b) {
      var g = b.parentElement, idx = Array.prototype.indexOf.call(g.querySelectorAll("button"), b), tool = g.getAttribute("data-tool");
      if (tool === "lang") {
        set("sp-lang", idx ? "hi" : "en"); applyLang(idx ? "hi" : "en");
        if (syncLangCookie(idx ? "hi" : "en") && serverI18n) { location.reload(); return; }
        if (!variants && idx) toast("Language saved. Result pages are shown in Hindi; other screens are English for now.");
      }
      if (tool === "size") { set("sp-size", String(idx)); applySize(idx); }
      return;
    }
    var c = e.target.closest("[data-contrast]");
    if (c) { var on = c.getAttribute("aria-pressed") !== "true"; set("sp-hc", on ? "1" : "0"); applyContrast(on); return; }
    var m = e.target.closest(".menu-btn");
    if (m) {
      var nav = m.closest(".mainnav"), open = !nav.classList.contains("open");
      nav.classList.toggle("open", open); m.setAttribute("aria-expanded", open ? "true" : "false");
    }
  });

  // ---- links the design left as "#" -----------------------------------------
  D.addEventListener("click", function (e) {
    var a = e.target.closest("a[data-todo]"); if (!a) return;
    e.preventDefault(); toast("Not available in this demo yet");
  });
  D.addEventListener("click", function (e) {
    var a = e.target.closest("a");
    if (!a || path !== "/report/complaint" || a.textContent.trim().indexOf("Copy text") !== 0) return;
    e.preventDefault();
    var txt = (D.querySelector(".bd") || D.body).innerText;
    var p = navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject();
    p.then(function () { toast("Copied"); }, function () { toast("Copy not available here"); });
  });
  D.addEventListener("click", function (e) {
    var a = e.target.closest("a");
    if (!a || path !== "/warn" || !navigator.share || a.getAttribute("href") !== "/guardian/share") return;
    e.preventDefault(); navigator.share({ title: "Satyapan", text: D.title, url: location.origin + "/" }).catch(function () {});
  });
  D.addEventListener("click", function (e) { if (e.target.closest("[data-print]")) window.print(); });

  // ---- history kept on this device only ---------------------------------------
  var TIERS = {
    "/result/qr": ["HIGH RISK", "r"], "/result/screenshot": ["HIGH RISK", "r"], "/result/invoice": ["VERIFY FIRST", "a"],
    "/result/cant-tell": ["CAN'T TELL", "n"], "/result/no-flags": ["NO RED FLAGS FOUND", "g"],
    "/tools/result": ["OFFICIAL CHANNEL CHECK", "n"], "/check/voice": ["TEXT TO REVIEW", "n"]
  };
  var ENGINE_TIERS = {
    HIGH_RISK: ["HIGH RISK", "r"], REGISTRY_HIT: ["REGISTRY HIT", "r"], SUSPICIOUS: ["SUSPICIOUS", "a"],
    CANT_TELL: ["CAN'T TELL", "n"], NO_RED_FLAGS: ["NO RED FLAGS FOUND", "g"]
  };
  var KIND_LABEL = { screenshot: "Screenshot or photo", pdf: "PDF or invoice", qr: "QR code", link: "Link", message: "Message or number", voice: "Voice note" };
  function history() { try { return JSON.parse(get("sp-history") || "[]"); } catch (e) { return []; } }
  function saveHistory(list) { set("sp-history", JSON.stringify(list.slice(0, 50))); }
  function remember(entry) { var l = history(); l.unshift(entry); saveHistory(l); }

  if (path === "/check") initCheck();
  if (path === "/check/progress") initProgress();
  if (path === "/dashboard") initDashboard();
  if (path === "/learn/drill/score") set("sp-drill", String(Date.now()));

  function initCheck() {
    var KINDS = ["screenshot", "pdf", "qr", "link", "message", "voice"];
    var ACCEPT = { screenshot: "image/*", pdf: "application/pdf", qr: "image/*", voice: "audio/*,video/*" };
    var opts = D.querySelectorAll(".opt"), fileCard = D.querySelector(".file");
    var state = { kind: "screenshot", file: null };
    var input = D.createElement("input"); input.type = "file"; input.hidden = true; D.body.appendChild(input);
    var box = D.createElement("div"); box.style.display = "none"; box.style.gridColumn = "1 / -1";
    var ta = D.createElement("textarea"); ta.className = "ta-in"; ta.setAttribute("aria-label", "Text to check"); ta.maxLength = 4000;
    box.appendChild(ta);
    var err = D.createElement("p"); err.className = "fileerr"; err.setAttribute("role", "alert");
    var go = D.querySelector("a.btn.bp"); go.parentNode.insertBefore(err, go);
    fileCard.style.display = "none";
    var spans = fileCard.querySelectorAll("span span");

    function pick(i, open) {
      state.kind = KINDS[i]; state.file = null; input.value = ""; fileCard.style.display = "none"; err.textContent = "";
      opts.forEach(function (o, j) { o.classList.toggle("on", i === j); o.setAttribute("aria-pressed", i === j ? "true" : "false"); });
      var textual = state.kind === "link" || state.kind === "message";
      box.style.display = textual ? "block" : "none";
      opts[i].insertAdjacentElement("afterend", box);
      var hiL = D.documentElement.getAttribute("data-lang") === "hi";
      ta.placeholder = state.kind === "link" ? (hiL ? "यहाँ लिंक चिपकाएँ" : "Paste the link here") : (hiL ? "यहाँ संदेश या फ़ोन नंबर चिपकाएँ" : "Paste the message or phone number here");
      if (textual) { if (open) ta.focus(); } else if (open) { input.accept = ACCEPT[state.kind]; input.click(); }
    }
    opts.forEach(function (o, i) { o.addEventListener("click", function () { pick(i, true); }); });
    var wanted = KINDS.indexOf(new URLSearchParams(location.search).get("type") || "");
    if (wanted >= 0) pick(wanted, false);
    // From the browser extension: the text arrives after "#t=" (a fragment, never sent to a server). Fill it in, clear the address bar,
    // and run the check only when the extension asked for it (autorun=1), because its user chose "Check with Satyapan" from the menu.
    var frag = location.hash.match(/^#t=(.*)$/);
    if (frag) {
      var incoming = "";
      try { incoming = decodeURIComponent(frag[1]); } catch (e) { incoming = ""; }
      if (incoming.trim()) {
        pick(/^\s*(https?:\/\/|www\.)\S+\s*$/i.test(incoming) ? 3 : 4, false);
        ta.value = incoming.slice(0, 4000);
        try { history.replaceState(null, "", location.pathname + location.search.replace(/[?&]autorun=1/, "")); } catch (e) { /* ignore */ }
        if (new URLSearchParams(location.search).get("autorun") === "1") setTimeout(function () { go.click(); }, 400);
      }
    }
    input.addEventListener("change", function () {
      var f = input.files[0]; if (!f) return;
      if (f.size > 20 * 1024 * 1024) { err.textContent = "That file is too large (limit 20 MB)."; input.value = ""; return; }
      state.file = f; err.textContent = "";
      spans[0].textContent = f.name; spans[1].textContent = Math.max(1, Math.round(f.size / 1024)) + " KB";
      fileCard.style.display = "flex"; opts[KINDS.indexOf(state.kind)].insertAdjacentElement("afterend", fileCard);
    });
    fileCard.querySelector("button").addEventListener("click", function () { state.file = null; input.value = ""; fileCard.style.display = "none"; });
    var cbs = D.querySelectorAll(".cb input");
    go.addEventListener("click", function (e) {
      e.preventDefault(); err.textContent = "";
      var text = ta.value.trim(), textual = state.kind === "link" || state.kind === "message";
      if (textual ? !text : !state.file) { err.textContent = D.documentElement.getAttribute("data-lang") === "hi" ? "कृपया वह जोड़ें जो आप जँचवाना चाहते हैं।" : "Please add what you want us to check."; return; }
      if (!cbs[1].checked) { err.textContent = D.documentElement.getAttribute("data-lang") === "hi" ? "आगे बढ़ने के लिए “मैं समझता/समझती हूँ” पर टिक करें।" : "Please tick “I understand” to continue."; return; }
      var fd = new FormData();
      fd.append("kind", state.kind); fd.append("speak_aloud", cbs[0].checked ? "true" : "false");
      var chip = D.querySelector(".chips .chip.on"); if (chip) fd.append("topic", chip.getAttribute("data-topic") || chip.textContent.trim());
      if (textual) fd.append("text", text);
      if (state.file) fd.append("file", state.file);
      if (go.getAttribute("aria-busy") === "true") return;
      go.setAttribute("aria-busy", "true");
      var hi = D.documentElement.getAttribute("data-lang") === "hi";
      err.textContent = hi ? "जाँच चल रही है… वॉइस नोट में कुछ सेकंड लग सकते हैं।" : "Checking now… a voice note can take a few seconds.";
      err.style.color = "#1F4E8C";
      fetch("/api/v1/check", { method: "POST", body: fd })
        .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.detail || "failed"); return j; }); })
        .then(function (j) {
          var label = state.file ? state.file.name : text.slice(0, 60);
          var t = ENGINE_TIERS[j.tier] || TIERS[j.result_url] || ["SAMPLE RESULT", "n"];
          remember({ id: j.id, kind: state.kind, label: label, at: Date.now(), url: j.result_url, tier: t[0], cls: t[1] });
          try { sessionStorage.setItem("sp-read-" + j.id, JSON.stringify({ text: j.text_read || "", kind: state.kind })); } catch (e) { /* private mode: the page then says the text is not available */ }
          location.href = j.result_url;
        })
        .catch(function (x) { go.removeAttribute("aria-busy"); err.style.color = ""; err.textContent = "Could not start the check: " + x.message; });
    });
  }

  function initProgress() {
    var q = new URLSearchParams(location.search), to = q.get("to"), id = q.get("id");
    var safe = to && to.charAt(0) === "/" && to.charAt(1) !== "/";
    var stop = D.querySelector("button.btn.bq");
    if (stop) stop.addEventListener("click", function () {
      saveHistory(history().filter(function (h) { return h.id !== id; }));
      var done = function () { location.href = "/deletion"; };
      if (id) { fetch("/api/v1/check/" + encodeURIComponent(id), { method: "DELETE" }).then(done, done); } else { done(); }
    });
    if (safe) setTimeout(function () { location.href = to; }, 5000);
  }

  function initDashboard() {
    var rows = D.getElementById("rows"), empty = D.getElementById("empty"), wrap = D.getElementById("tblwrap"), note = D.getElementById("sample-note");
    function fmt(ms) { return new Date(ms).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); }
    function render() {
      var l = history(), n = { total: l.length, high: 0, verify: 0, clear: 0 };
      rows.textContent = "";
      l.forEach(function (h) {
        if (h.cls === "r") n.high++; else if (h.cls === "a") n.verify++; else if (h.cls === "g") n.clear++;
        var tr = D.createElement("tr");
        var td = function (t) { var c = D.createElement("td"); c.textContent = t; tr.appendChild(c); return c; };
        td(fmt(h.at)); td(KIND_LABEL[h.kind] || h.kind); td(h.label || "");
        var r = td(""), p = D.createElement("span"); p.className = "pill pill-" + h.cls; p.textContent = h.tier; r.appendChild(p);
        var a = td(""), link = D.createElement("a"); link.className = "btn-sm"; link.href = h.url; link.textContent = "View"; a.appendChild(link);
        rows.appendChild(tr);
      });
      D.querySelectorAll("[data-k]").forEach(function (b) { b.textContent = String(n[b.getAttribute("data-k")]); });
      empty.hidden = l.length > 0; wrap.hidden = l.length === 0;
      note.hidden = !l.some(function (h) { return h.sample; });
      var dr = get("sp-drill"), bar = D.getElementById("drill-bar"), txt = D.getElementById("drill-txt");
      bar.style.width = dr ? "100%" : "0";
      txt.textContent = dr ? "Completed on " + new Date(Number(dr)).toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : "Not started";
    }
    D.getElementById("load-sample").addEventListener("click", function () {
      var now = Date.now(), HR = 3600e3;
      var s = [
        ["qr", "vip_profits_qr.jpg", "/result/qr", 0.4], ["pdf", "INV-2026-1042.pdf", "/result/invoice", 5],
        ["screenshot", "payment_9090.png", "/result/screenshot", 26], ["message", "Amazon refund pending...", "/tools/result", 50],
        ["screenshot", "receipt_blurry.jpg", "/result/cant-tell", 75], ["pdf", "electricity_bill.pdf", "/result/no-flags", 120]
      ].map(function (x, i) {
        var t = TIERS[x[2]];
        return { id: "sample" + i, kind: x[0], label: x[1], at: now - x[3] * HR, url: x[2], tier: t[0], cls: t[1], sample: true };
      });
      saveHistory(s.concat(history().filter(function (h) { return !h.sample; })));
      render();
    });
    D.getElementById("clear-all").addEventListener("click", function () {
      if (!history().length) { toast("Nothing to delete"); return; }
      if (confirm("Delete all checks saved on this device?")) { saveHistory([]); render(); toast("Deleted"); }
    });
    render();
  }
})();
