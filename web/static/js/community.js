/* Community pages: live preview of what will be saved, copy link, confirm before delete. Pages work without this script. */
(function () {
  var D = document;
  function toast(msg) { if (window.satyapanToast) window.satyapanToast(msg); }

  var ta = D.getElementById("cm-text");
  if (ta) {
    var count = D.getElementById("cm-count"), box = D.getElementById("cm-preview"), out = D.getElementById("cm-preview-text"),
        note = D.getElementById("cm-preview-note"), url = ta.getAttribute("data-preview"), timer = null, seq = 0;
    var hi = D.documentElement.getAttribute("data-lang") === "hi";
    var NAMES = { phone: hi ? "फ़ोन नंबर" : "phone numbers", email: hi ? "ई-मेल" : "e-mail addresses", long_number: hi ? "लंबे नंबर" : "long numbers",
                  secret_code: hi ? "OTP/PIN" : "OTP or PIN values", pan: "PAN", name: hi ? "नाम" : "names", link_details: hi ? "लिंक का बाकी हिस्सा" : "link details",
                  payment_link: hi ? "पेमेंट लिंक" : "payment links", link: hi ? "लिंक" : "links" };
    var update = function () {
      count.textContent = ta.value.length;
      clearTimeout(timer);
      if (!ta.value.trim()) { box.hidden = true; return; }
      var mine = ++seq;
      timer = setTimeout(function () {
        var fd = new FormData(); fd.append("text", ta.value);
        fetch(url, { method: "POST", body: fd }).then(function (r) { return r.json(); }).then(function (d) {
          if (mine !== seq) return;
          out.textContent = d.excerpt; box.hidden = false;
          var parts = Object.keys(d.masked || {}).map(function (k) { return d.masked[k] + " " + (NAMES[k] || k); });
          note.textContent = parts.length ? (hi ? "छिपाया गया: " : "Hidden: ") + parts.join(", ") + "."
            : (hi ? "इसमें कुछ छिपाने की ज़रूरत नहीं पड़ी।" : "Nothing needed hiding.");
          if (!d.clean) note.textContent += hi ? " इसे प्रकाशित करने से पहले कोई व्यक्ति देखेगा।" : " A person will look at it before it is published.";
        }).catch(function () { box.hidden = true; });
      }, 400);
    };
    ta.addEventListener("input", update); update();
  }

  D.addEventListener("click", function (e) {
    var c = e.target.closest("[data-cm-copy]");
    if (c) {
      var link = c.getAttribute("data-cm-copy"), hi2 = D.documentElement.getAttribute("data-lang") === "hi";
      var p = navigator.clipboard ? navigator.clipboard.writeText(link) : Promise.reject();
      p.then(function () { toast(hi2 ? "लिंक कॉपी हो गया" : "Link copied"); }, function () { window.prompt("Copy this link", link); });
      return;
    }
    var d = e.target.closest("[data-cm-confirm]");
    if (d && !window.confirm(d.getAttribute("data-cm-confirm"))) e.preventDefault();
  });
})();

/* Share a picture the way phones expect (WhatsApp and others), with a plain download as the fallback. */
(function () {
  var D = document;
  D.addEventListener("click", function (e) {
    var b = e.target.closest("[data-cm-share-img]");
    if (!b) return;
    var url = b.getAttribute("data-cm-share-img");
    fetch(url).then(function (r) { return r.blob(); }).then(function (blob) {
      var file = new File([blob], "satyapan-warning.png", { type: "image/png" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) return navigator.share({ files: [file], title: "Satyapan" });
      var a = D.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "satyapan-warning.png"; D.body.appendChild(a); a.click(); a.remove();
    }).catch(function () {});
  });

  // Tell the server the visitor's time zone (minutes east of UTC) so streaks change at their own midnight.
  try {
    var off = String(-new Date().getTimezoneOffset());
    if (D.cookie.indexOf("sp_tz=" + off) < 0) D.cookie = "sp_tz=" + off + "; path=/; max-age=31536000; samesite=lax";
  } catch (err) { /* cookies blocked: the server falls back to India time */ }
})();


/* The report form: when the visitor switches between "warn others" and "ask the community", the headings and the button change wording. */
(function () {
  var D = document, radios = D.querySelectorAll('input[name="intent"]');
  if (!radios.length) return;
  function apply() {
    var ask = D.querySelector('input[name="intent"][value="ask"]').checked;
    D.querySelectorAll("[data-intent-text]").forEach(function (el) { el.textContent = el.getAttribute(ask ? "data-ask" : "data-warn"); });
  }
  radios.forEach(function (r) { r.addEventListener("change", apply); });
  apply();
})();
