// /results: "Run the text kit" button. Shows only numbers the server just computed.
(function () {
  "use strict";
  var btn = document.getElementById("ml-run");
  if (!btn) return;
  var hi = document.documentElement.lang === "hi";
  var T = function (en, h) { return hi ? h : en; };
  var status = document.getElementById("ml-run-status");
  var out = document.getElementById("ml-run-out");

  function rate(r) {
    if (!r || !r.n) return T("not evaluated", "मापा नहीं गया");
    return r.k + "/" + r.n + " = " + Math.round(100 * r.k / r.n) + "% (95% CI " + Math.round(100 * r.lo) + "–" + Math.round(100 * r.hi) + "%)";
  }
  function el(tag, text, cls) {
    var e = document.createElement(tag);
    if (text !== undefined) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  }
  function table(res) {
    var wrap = el("div", undefined, "tbl-wrap");
    var t = el("table", undefined, "tbl ml-tbl");
    var head = el("tr");
    [T("Method", "तरीका"), T("Scams caught", "पकड़े गए स्कैम"), T("Genuine wrongly flagged", "गलती से संदिग्ध असली संदेश")].forEach(function (h) {
      var th = el("th", h); th.scope = "col"; head.appendChild(th);
    });
    var thead = el("thead"); thead.appendChild(head); t.appendChild(thead);
    var tb = el("tbody");
    res.rows.forEach(function (r) {
      var tr = el("tr", undefined, r.baseline ? "ml-base" : "");
      var th = el("th", r.name); th.scope = "row"; tr.appendChild(th);
      tr.appendChild(el("td", rate(r.tpr)));
      tr.appendChild(el("td", rate(r.fpr)));
      tb.appendChild(tr);
    });
    t.appendChild(tb); wrap.appendChild(t);
    return wrap;
  }
  function block(title, res) {
    var d = el("div");
    d.appendChild(el("h4", title, "ml-run-h"));
    d.appendChild(el("p", res.dataset + " · " + res.split + " · " + res.hardware + " · " + res.elapsed_s + " s", "dnote"));
    d.appendChild(table(res));
    var n = res.failures.length;
    d.appendChild(el("p", T("Failures in this run: ", "इस बार की गलतियाँ: ") + n, "dnote"));
    return d;
  }

  btn.addEventListener("click", function () {
    btn.disabled = true;
    status.className = "ml-status";
    status.textContent = T("Running every message through the checks…", "हर संदेश की जाँच चल रही है…");
    fetch("/api/v1/models/run-kit", { method: "POST", headers: { "Accept": "application/json" } })
      .then(function (r) {
        if (r.status === 429) throw new Error(T("A run is already in progress. Try again in a moment.", "एक जाँच पहले से चल रही है। थोड़ी देर बाद फिर कोशिश करें।"));
        if (!r.ok) throw new Error(T("The run failed. Please try again.", "जाँच नहीं हो पाई। फिर से कोशिश करें।"));
        return r.json();
      })
      .then(function (data) {
        out.textContent = "";
        if (data.held) out.appendChild(block(T("Held-out messages (written by teammates)", "अलग रखे गए संदेश (टीम के लोगों ने लिखे)"), data.held));
        else out.appendChild(el("p", T("Held-out messages: not evaluated (no held-out files yet).", "अलग रखे गए संदेश: मापा नहीं गया (अभी फ़ाइलें नहीं हैं)।"), "ml-none"));
        out.appendChild(block(T("Development kit (optimistic)", "डेवलपमेंट किट (आशावादी)"), data.dev));
        status.textContent = data.cached ? T("Showing the run from a few seconds ago.", "कुछ सेकंड पहले का नतीजा दिखा रहे हैं।") : T("Done.", "हो गया।");
      })
      .catch(function (e) {
        status.className = "ml-status ml-err";
        status.textContent = e.message;
      })
      .then(function () { btn.disabled = false; });
  });
})();
