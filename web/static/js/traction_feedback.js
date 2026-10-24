/* "Was this helpful?" on result pages, and the site feedback form. One answer per case per browser. No tracking beyond the answer itself. */
(function () {
  var hi = document.documentElement.lang === "hi";
  function t(en, h) { return hi ? h : en; }
  function post(caseId, rating, comment) {
    return fetch("/api/v1/feedback", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ case_id: caseId, rating: rating, comment: comment }) });
  }
  function done(box) { box.innerHTML = ""; var p = document.createElement("p"); p.className = "ops-ok"; p.setAttribute("role", "status");
    p.textContent = t("Thank you. We read every answer.", "धन्यवाद। हम हर जवाब पढ़ते हैं।"); box.appendChild(p); }

  // site feedback page: markup is in the template
  var site = document.querySelector("[data-site-feedback]");
  if (site) {
    var rating = 0, err = document.getElementById("fb-err");
    site.querySelectorAll("[data-rating]").forEach(function (b) {
      b.addEventListener("click", function () {
        rating = Number(b.getAttribute("data-rating"));
        site.querySelectorAll("[data-rating]").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      });
    });
    document.getElementById("fb-send").addEventListener("click", function () {
      err.hidden = true;
      if (!rating) { err.textContent = t("Please choose a number from 1 to 5.", "कृपया 1 से 5 में से एक संख्या चुनें।"); err.hidden = false; return; }
      post("site:page", rating, document.getElementById("fb-comment").value).then(function (r) {
        if (!r.ok) throw new Error();
        site.querySelector("#fb-send").hidden = true; document.getElementById("fb-done").hidden = false;
      }).catch(function () { err.textContent = t("Could not send. Please try again.", "भेजा नहीं जा सका। कृपया फिर कोशिश करें।"); err.hidden = false; });
    });
    return;
  }

  // result pages: /case/<id>
  var m = location.pathname.match(/^\/case\/([A-Za-z0-9]{6,40})\/?$/);
  var all = m ? Array.prototype.slice.call(document.querySelectorAll(".pmain .case")) : [];
  var host = all.filter(function (h) { return h.offsetParent !== null; })[0] || all[0];   // the visible language variant
  if (!host) return;
  var id = m[1], key = "sp-fb-" + id;
  try { if (localStorage.getItem(key)) return; } catch (e) { /* storage may be blocked */ }
  var box = document.createElement("section"); box.className = "ops-fb"; box.setAttribute("aria-labelledby", "fb-h");
  var h = document.createElement("h2"); h.id = "fb-h"; h.textContent = t("Was this helpful?", "क्या यह काम का था?"); box.appendChild(h);
  var row = document.createElement("div"); row.className = "ops-fb-row"; row.setAttribute("role", "group"); row.setAttribute("aria-label", t("Rating from 1 to 5", "1 से 5 की रेटिंग"));
  var chosen = 0, ta, send, err2;
  for (var n = 1; n <= 5; n++) {
    (function (n) {
      var b = document.createElement("button"); b.type = "button"; b.textContent = String(n); b.setAttribute("aria-pressed", "false");
      b.setAttribute("aria-label", n + " / 5");
      b.addEventListener("click", function () {
        chosen = n; row.querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
        if (!ta) {
          ta = document.createElement("textarea"); ta.maxLength = 300; ta.setAttribute("aria-label", t("What could be better? (optional)", "क्या बेहतर हो सकता है? (वैकल्पिक)"));
          ta.placeholder = t("What could be better? (optional, no phone numbers)", "क्या बेहतर हो सकता है? (वैकल्पिक, फ़ोन नंबर न लिखें)");
          send = document.createElement("button"); send.type = "button"; send.textContent = t("Send", "भेजें"); send.style.marginTop = "10px";
          err2 = document.createElement("p"); err2.className = "ops-err"; err2.setAttribute("role", "alert"); err2.hidden = true;
          box.appendChild(ta); box.appendChild(err2); box.appendChild(send);
          send.addEventListener("click", function () {
            post(id, chosen, ta.value).then(function (r) {
              if (!r.ok && r.status !== 201) throw new Error();
              try { localStorage.setItem(key, "1"); } catch (e) { /* ignore */ }
              done(box);
            }).catch(function () { err2.textContent = t("Could not send. Please try again.", "भेजा नहीं जा सका। कृपया फिर कोशिश करें।"); err2.hidden = false; });
          });
        }
      });
      row.appendChild(b);
    })(n);
  }
  var hint = document.createElement("p"); hint.className = "ops-hint"; hint.textContent = t("1 is not helpful, 5 is very helpful.", "1 बिल्कुल काम का नहीं, 5 बहुत काम का।");
  box.appendChild(row); box.appendChild(hint); host.appendChild(box);
})();
