/* Shopkeeper check: upload the customer's payment screenshot, then compare who the screenshot says was paid with the shop's own UPI ID.
   The UPI ID is kept only in this browser (localStorage). The screenshot goes through the normal /api/v1/check and is deleted after. */
(function () {
  var form = document.getElementById("shop-form");
  if (!form) return;
  var D = document;
  var hi = function () { return D.documentElement.getAttribute("data-lang") === "hi"; };
  var T = {
    en: { need: "Please add your UPI ID and a screenshot.", wait: "Checking…", fail: "Could not check that picture. Try a clearer screenshot.",
          wrongPayee: "Do not hand over the goods yet. This screenshot says the money went to someone else, not to you.",
          shows: "The screenshot says the payee is", yours: "Your UPI ID is", amountShown: "Amount on the screenshot",
          amountOff: "The amount on the screenshot is not the amount you expected.",
          match: "The screenshot names your UPI ID. That still does not prove the money arrived: check your own app, soundbox or SMS.",
          none: "We could not read a UPI ID from this screenshot. Check your own app, soundbox or SMS before you hand over the goods.",
          ourCheck: "Our check of the picture", full: "See the full result", another: "Check another screenshot" },
    hi: { need: "कृपया अपनी UPI ID और स्क्रीनशॉट डालें।", wait: "जाँच हो रही है…", fail: "यह तस्वीर जाँच नहीं पाए। ज़्यादा साफ़ स्क्रीनशॉट आज़माएँ।",
          wrongPayee: "अभी सामान न दें। इस स्क्रीनशॉट के हिसाब से पैसे किसी और को गए हैं, आपको नहीं।",
          shows: "स्क्रीनशॉट में पाने वाला है", yours: "आपकी UPI ID है", amountShown: "स्क्रीनशॉट में रकम",
          amountOff: "स्क्रीनशॉट की रकम वह नहीं है जो आप चाहते थे।",
          match: "स्क्रीनशॉट में आपकी UPI ID का नाम है। फिर भी इससे यह साबित नहीं होता कि पैसे आ गए: अपना ऐप, साउंडबॉक्स या SMS देखें।",
          none: "इस स्क्रीनशॉट से हम कोई UPI ID नहीं पढ़ पाए। सामान देने से पहले अपना ऐप, साउंडबॉक्स या SMS देखें।",
          ourCheck: "तस्वीर की हमारी जाँच", full: "पूरा नतीजा देखें", another: "दूसरा स्क्रीनशॉट जाँचें" }
  };
  function t(k) { return T[hi() ? "hi" : "en"][k]; }
  function esc(s) { var d = D.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; }
  var upi = D.getElementById("shop-upi"), amt = D.getElementById("shop-amount"), file = D.getElementById("shop-file");
  var err = D.getElementById("shop-err"), out = D.getElementById("shop-out"), go = D.getElementById("shop-go");
  try { upi.value = localStorage.getItem("sp-shop-upi") || ""; } catch (e) { /* no storage */ }
  var norm = function (s) { return String(s || "").trim().toLowerCase(); };
  var num = function (s) { var n = parseFloat(String(s || "").replace(/[^0-9.]/g, "")); return isNaN(n) ? null : n; };

  form.addEventListener("submit", function (e) {
    e.preventDefault(); err.textContent = "";
    var mine = norm(upi.value);
    if (!mine || mine.indexOf("@") < 1 || !file.files[0]) { err.textContent = t("need"); return; }
    try { localStorage.setItem("sp-shop-upi", mine); } catch (x) { /* no storage */ }
    go.disabled = true; out.hidden = false; out.innerHTML = "<p><b>" + esc(t("wait")) + "</b></p>";
    var fd = new FormData(); fd.append("kind", "screenshot"); fd.append("file", file.files[0]); fd.append("channel", "web-shopkeeper");
    fetch("/api/v1/check", { method: "POST", body: fd })
      .then(function (r) { if (!r.ok) throw new Error("check"); return r.json(); })
      .then(function (j) { return fetch("/api/v1/case/" + encodeURIComponent(j.id)).then(function (r) { if (!r.ok) throw new Error("case"); return r.json(); }).then(function (c) { c._id = j.id; c._text = j.text_read || ""; return c; }); })
      .then(function (c) {
        var payees = c.payees || [], html = "", bad = false;
        var others = payees.filter(function (p) { return norm(p.upi) !== mine; });
        var same = payees.filter(function (p) { return norm(p.upi) === mine; });
        if (!payees.length) {
          html += '<div class="vbanner vb-n"><div><h2 class="vb-h" style="font-size:20px">?</h2><p class="vb-act">' + esc(t("none")) + "</p></div></div>";
        } else if (others.length && !same.length) {
          bad = true;
          html += '<div class="vbanner vb-r"><div><h2 class="vb-h" style="font-size:22px">' + esc(t("wrongPayee")) + "</h2></div></div>" +
            '<dl class="kv2"><div><dt>' + esc(t("shows")) + '</dt><dd class="mono">' + esc(others[0].upi) + "</dd></div><div><dt>" + esc(t("yours")) + '</dt><dd class="mono">' + esc(mine) + "</dd></div></dl>";
        } else {
          html += '<div class="vbanner vb-a"><div><p class="vb-act">' + esc(t("match")) + "</p></div></div>";
        }
        var want = num(amt.value), seen = [];
        (c._text || "").replace(/(?:₹|rs\.?|inr|天|三)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)/gi, function (m0, g) { var n = num(g); if (n !== null && seen.indexOf(n) < 0) seen.push(n); return m0; });
        if (want !== null && seen.length) {
          html += '<dl class="kv2"><div><dt>' + esc(t("amountShown")) + '</dt><dd>' + seen.map(function (n) { return "₹" + esc(n); }).join(", ") + "</dd></div></dl>";
          if (!seen.some(function (n) { return Math.abs(want - n) < 0.01; })) html += '<p class="ops-err">' + esc(t("amountOff")) + "</p>";
        }
        html += "<h3>" + esc(t("ourCheck")) + "</h3><p><b>" + esc(c.headline) + "</b></p><ol>" + (c.reasons || []).slice(0, 3).map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + "</ol>" +
          '<p><a class="btn bs" style="width:auto;padding:0 22px" href="/case/' + encodeURIComponent(c._id) + '">' + esc(t("full")) + '</a> <a class="btn bq" style="width:auto;padding:0 22px" href="/shopkeeper">' + esc(t("another")) + "</a></p>";
        out.innerHTML = html; go.disabled = false;
      })
      .catch(function () { go.disabled = false; out.innerHTML = '<p class="ops-err">' + esc(t("fail")) + "</p>"; });
  });
})();
