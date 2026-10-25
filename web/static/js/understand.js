/* "First, what does this say?": on a result page, show what we read from the visitor's message, screenshot, PDF or voice note,
   and let them have it explained in their own language (Sarvam) before they look at our verdict. The text is kept only in this browser
   tab (sessionStorage); our server never stores it. Pressing "Explain" is the consent to send it to Sarvam for translation. */
(function () {
  var m = location.pathname.match(/^\/case\/([A-Za-z0-9]{6,40})\/?$/);
  if (!m) return;
  var id = m[1];
  var D = document;
  function ready(fn) { if (D.readyState !== "loading") fn(); else D.addEventListener("DOMContentLoaded", fn); }

  var T = {
    en: {
      h: "First, what does this say?",
      sub: "This is what we read from what you sent. We do not judge it here. Understand it first, then decide whether to look at our verdict.",
      none: "We do not keep what you sent, so it cannot be shown again. Open this page from the same device right after a check to see it.",
      lang: "Explain in my language", go: "Explain", again: "Explain again",
      consent: "Pressing Explain sends the text above to Sarvam, an Indian AI company, to translate it. We do not store it.",
      consentNoText: "Pressing the button sends only our own fixed verdict sentences to Sarvam.",
      working: "Translating…", failed: "The translation service is not available right now. You can still read our verdict below.",
      said: "What it says, in", verdict: "Our check, in", listen: "Listen",
      caveat: "This is a plain translation. It is not a verdict. Machine translation can make mistakes, so use the original words if something looks odd.",
      suggest: "This is only a suggestion: the message may or may not be a scam. Check with someone you trust before you pay.",
      orig: "What we read", chars: "characters",
      fix: "Heard something wrong? Edit the words and check again", heard: "What we heard (speech to text, on our own server)"
    },
    hi: {
      h: "पहले समझें: इसमें क्या लिखा है?",
      sub: "आपके भेजे हुए में से हमने यह पढ़ा है। यहाँ हम कोई फ़ैसला नहीं सुना रहे। पहले इसे समझ लें, फिर चाहें तो हमारा नतीजा देखें।",
      none: "आपका भेजा हुआ हम नहीं रखते, इसलिए दोबारा नहीं दिखा सकते। जाँच के तुरंत बाद उसी डिवाइस से यह पन्ना खोलें।",
      lang: "मेरी भाषा में समझाएँ", go: "समझाएँ", again: "फिर समझाएँ",
      consent: "समझाएँ दबाने पर ऊपर का पाठ अनुवाद के लिए Sarvam (एक भारतीय AI कंपनी) को भेजा जाता है। हम इसे सहेजते नहीं।",
      consentNoText: "बटन दबाने पर सिर्फ़ हमारे अपने तय नतीजे वाले वाक्य Sarvam को भेजे जाते हैं।",
      working: "अनुवाद हो रहा है…", failed: "अनुवाद सेवा अभी उपलब्ध नहीं है। नीचे हमारा नतीजा फिर भी पढ़ सकते हैं।",
      said: "इसमें लिखा है, इस भाषा में:", verdict: "हमारी जाँच, इस भाषा में:", listen: "सुनें",
      caveat: "यह सीधा अनुवाद है, कोई नतीजा नहीं। मशीनी अनुवाद में गलतियाँ हो सकती हैं, इसलिए कुछ अजीब लगे तो असली शब्द देखें।",
      suggest: "यह सिर्फ़ एक सुझाव है: यह संदेश धोखाधड़ी हो भी सकता है और नहीं भी। पैसे भेजने से पहले किसी भरोसेमंद से पूछें।",
      orig: "हमने क्या पढ़ा", chars: "अक्षर",
      fix: "कुछ गलत सुना गया? शब्द ठीक करें और फिर जाँचें", heard: "हमने क्या सुना (स्पीच से टेक्स्ट, हमारे अपने सर्वर पर)"
    }
  };
  function lang() { return D.documentElement.getAttribute("data-lang") === "hi" ? "hi" : "en"; }
  function t(k) { return T[lang()][k]; }
  function esc(s) { var d = D.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; }

  var stored = null;
  try { stored = JSON.parse(sessionStorage.getItem("sp-read-" + id) || "null"); } catch (e) { stored = null; }
  var text = stored && stored.text ? String(stored.text) : "";

  var LANGS = [];
  var current = null;
  var audio = null;

  function speak(payload, btn) {
    if (audio) { audio.pause(); audio = null; }
    var label = btn.textContent; btn.disabled = true; btn.textContent = "…";
    fetch("/api/v1/understand/speak", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: payload.text, lang: payload.lang, consent: true }) })
      .then(function (r) { if (!r.ok) throw new Error("no audio"); return r.blob(); })
      .then(function (b) { audio = new Audio(URL.createObjectURL(b)); return audio.play(); })
      .catch(function () {
        if (window.speechSynthesis) { var u = new SpeechSynthesisUtterance(payload.text); u.lang = payload.lang; window.speechSynthesis.speak(u); }
      })
      .then(function () { btn.disabled = false; btn.textContent = label; });
  }

  function render(sec) {
    var opts = LANGS.map(function (l) { return '<option value="' + l.code + '">' + esc(l.native) + (l.name !== l.native ? " (" + esc(l.name) + ")" : "") + "</option>"; }).join("");
    var saved = "";
    try { saved = localStorage.getItem("sp-explain-lang") || ""; } catch (e) { /* no storage */ }
    sec.innerHTML =
      '<h2 id="und-h">' + esc(t("h")) + "</h2>" +
      '<p class="und-sub">' + esc(t("sub")) + "</p>" +
      (text
        ? '<details class="und-orig" open><summary>' + esc(stored && stored.kind === "voice" ? t("heard") : t("orig")) + " · " + text.length + " " + esc(t("chars")) + '</summary><blockquote id="und-text"></blockquote>' +
          (stored && stored.kind === "voice" ? '<p class="und-sub" style="padding:0 12px 10px"><a href="/check?lang=' + (lang() === "hi" ? "hi" : "en") + '#t=' + encodeURIComponent(text.slice(0, 3500)) + '">' + esc(t("fix")) + "</a></p>" : "") + "</details>"
        : '<p class="und-none">' + esc(t("none")) + "</p>") +
      '<div class="und-row"><label for="und-lang">' + esc(t("lang")) + '</label><select id="und-lang">' + opts + '</select> <button type="button" class="btn bn" id="und-go">' + esc(t("go")) + "</button></div>" +
      '<p class="und-consent">' + esc(text ? t("consent") : t("consentNoText")) + "</p>" +
      '<div id="und-out" hidden aria-live="polite"></div>';
    if (text) D.getElementById("und-text").textContent = text;
    var sel = D.getElementById("und-lang");
    sel.value = saved && LANGS.some(function (l) { return l.code === saved; }) ? saved : (lang() === "hi" ? "hi" : "ta");
    D.getElementById("und-go").addEventListener("click", function () { run(sec); });
    try { if (sessionStorage.getItem("sp-explain-auto") === "1" && LANGS.length) run(sec); } catch (e) { /* no storage */ }
  }

  function block(title, code, body, speakText) {
    return '<div class="und-block"><h3>' + esc(title) + '</h3><div class="und-body" lang="' + esc(code) + '">' + body + "</div>" +
      '<button type="button" class="btn bq und-listen" data-lang="' + esc(code) + '">' + esc(t("listen")) + "</button></div>";
  }

  function run(sec) {
    var code = D.getElementById("und-lang").value, btn = D.getElementById("und-go"), out = D.getElementById("und-out");
    var native = (LANGS.filter(function (l) { return l.code === code; })[0] || {}).native || code;
    try { localStorage.setItem("sp-explain-lang", code); sessionStorage.setItem("sp-explain-auto", "1"); } catch (e) { /* no storage */ }
    btn.disabled = true; out.hidden = false; out.innerHTML = '<p class="und-busy">' + esc(t("working")) + "</p>";
    var tr = text
      ? fetch("/api/v1/understand/translate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: text, lang: code, consent: true }) }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
      : Promise.resolve(null);
    var vd = fetch("/api/v1/understand/verdict", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ case_id: id, lang: code }) }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
    Promise.all([tr, vd]).then(function (res) {
      var a = res[0], v = res[1], html = "";
      current = { tr: a, v: v, code: code };
      if (a && a.translated) {
        html += block(t("said") + " " + native, code, "<p>" + esc(a.translated).replace(/\n/g, "<br>") + "</p>") ;
      }
      if (v) {
        var list = (v.reasons || []).map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("");
        html += block(t("verdict") + " " + native, code, "<p><b>" + esc(v.headline) + "</b></p><ol>" + list + "</ol><p>" + esc(v.action) + "</p>");
      }
      if (!html) html = '<p class="und-err">' + esc(t("failed")) + "</p>";
      else html += '<p class="und-note">' + esc(t("caveat")) + '</p><p class="und-note"><b>' + esc(t("suggest")) + "</b></p>";
      out.innerHTML = html;
      btn.disabled = false; btn.textContent = t("again");
      Array.prototype.forEach.call(out.querySelectorAll(".und-listen"), function (b, i) {
        b.addEventListener("click", function () {
          var which = i === 0 && a && a.translated ? a.translated : (v ? [v.headline].concat(v.reasons || [], [v.action]).join(". ") : "");
          speak({ text: which, lang: code }, b);
        });
      });
    });
  }

  ready(function () {
    var main = D.getElementById("main") || D.querySelector("main");
    if (!main || !D.querySelector(".case")) return;
    var sec = D.createElement("section");
    sec.id = "understand"; sec.className = "und"; sec.setAttribute("aria-labelledby", "und-h");
    main.insertBefore(sec, main.firstChild);
    fetch("/api/v1/understand/languages").then(function (r) { return r.json(); }).then(function (j) {
      if (!j.available) { sec.remove(); return; }       // no Sarvam key on this server: do not show a feature that cannot work
      LANGS = j.languages; render(sec);
    }).catch(function () { sec.remove(); });
    D.addEventListener("click", function (e) {         // follow the page's English / Hindi switch
      if (e.target.closest('[data-tool="lang"] button')) setTimeout(function () { if (D.getElementById("understand")) { var o = current; render(sec); if (o) run(sec); } }, 50);
    });
  });
})();
