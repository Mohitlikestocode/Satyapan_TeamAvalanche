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
