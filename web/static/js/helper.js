/* Helper mode: check one item for one person, show the verdict in their language (Sarvam for the regional ones), read it aloud, then wipe it
   (server result deleted, screen cleared) before the next person. Nothing is stored in this browser between people. */
(function () {
  var root = document.getElementById("helper");
  if (!root) return;
  var D = document, hi = function () { return D.documentElement.getAttribute("data-lang") === "hi"; };
  var T = {
    en: { person: "Person", need: "Please add what they are showing you.", wait: "Checking…", fail: "Could not check that. Try again or use a clearer picture.", listen: "Listen",
          wipe: "End and wipe", wiped: "Wiped. Ready for the next person.", full: "Full result", sug: "This is only a suggestion. Please also check the official app or ask someone you trust." },
    hi: { person: "व्यक्ति", need: "कृपया वह जोड़ें जो वे आपको दिखा रहे हैं।", wait: "जाँच हो रही है…", fail: "यह जाँच नहीं पाए। फिर कोशिश करें या साफ़ तस्वीर लें।", listen: "सुनें",
          wipe: "खत्म करें और मिटाएँ", wiped: "मिटा दिया। अगला व्यक्ति आ सकता है।", full: "पूरा नतीजा", sug: "यह सिर्फ़ एक सुझाव है। आधिकारिक ऐप भी देखें या किसी भरोसेमंद से पूछें।" }
  };
  function t(k) { return T[hi() ? "hi" : "en"][k]; }
  function esc(s) { var d = D.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; }
  var lang = D.getElementById("hp-lang"), kind = D.getElementById("hp-kind"), text = D.getElementById("hp-text"), file = D.getElementById("hp-file");
  var err = D.getElementById("hp-err"), out = D.getElementById("hp-out"), go = D.getElementById("hp-go");
  var count = 1, done = 0, current = null, audio = null;

  fetch("/api/v1/understand/languages").then(function (r) { return r.json(); }).then(function (j) {
    var list = j.available ? j.languages : j.languages.filter(function (l) { return l.code === "en" || l.code === "hi"; });
    lang.innerHTML = list.map(function (l) { return '<option value="' + l.code + '">' + esc(l.native) + (l.name !== l.native ? " (" + esc(l.name) + ")" : "") + "</option>"; }).join("");
    lang.value = hi() ? "hi" : "en";
  });
  kind.addEventListener("change", function () {
    var textual = kind.value === "message" || kind.value === "link";
    D.getElementById("hp-text-row").hidden = !textual; D.getElementById("hp-file-row").hidden = textual;
  });

  function say(tx, code, btn) {
    if (audio) { audio.pause(); audio = null; }
    var label = btn.textContent; btn.disabled = true; btn.textContent = "…";
    fetch("/api/v1/understand/speak", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: tx, lang: code, consent: true }) })
      .then(function (r) { if (!r.ok) throw new Error("no audio"); return r.blob(); })
      .then(function (b) { audio = new Audio(URL.createObjectURL(b)); return audio.play(); })
      .catch(function () { if (window.speechSynthesis) { var u = new SpeechSynthesisUtterance(tx); u.lang = code; window.speechSynthesis.speak(u); } })
      .then(function () { btn.disabled = false; btn.textContent = label; });
  }

  function wipe() {
    if (current) fetch("/api/v1/check/" + encodeURIComponent(current), { method: "DELETE" }).catch(function () { /* it expires anyway */ });
    current = null; text.value = ""; file.value = ""; out.innerHTML = '<p class="vb-act">' + esc(t("wiped")) + "</p>"; err.textContent = "";
    done++; count++;
    D.getElementById("hp-done").textContent = String(done);
    D.getElementById("hp-person").textContent = t("person") + " " + count;
  }

  D.getElementById("hp-form").addEventListener("submit", function (e) {
    e.preventDefault(); err.textContent = "";
    var textual = kind.value === "message" || kind.value === "link";
    if (textual ? !text.value.trim() : !file.files[0]) { err.textContent = t("need"); return; }
    go.disabled = true; out.hidden = false; out.innerHTML = "<p><b>" + esc(t("wait")) + "</b></p>";
    var fd = new FormData(); fd.append("kind", kind.value); fd.append("channel", "web-helper");
    if (textual) fd.append("text", text.value.trim()); else fd.append("file", file.files[0]);
    var code = lang.value;
    fetch("/api/v1/check", { method: "POST", body: fd })
      .then(function (r) { if (!r.ok) throw new Error("check"); return r.json(); })
      .then(function (j) {
        current = j.id;
        return fetch("/api/v1/understand/verdict", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ case_id: j.id, lang: code }) })
          .then(function (r) { if (!r.ok) throw new Error("verdict"); return r.json(); }).then(function (v) { return { j: j, v: v }; });
      })
      .then(function (x) {
        var v = x.v, tier = x.j.tier, cls = tier === "HIGH_RISK" || tier === "REGISTRY_HIT" ? "r" : tier === "SUSPICIOUS" ? "a" : tier === "NO_RED_FLAGS" ? "g" : "n";
        var body = [v.headline].concat(v.reasons || [], [v.action]).join(". ");
        out.innerHTML = '<div class="vbanner vb-' + cls + '"><div><h2 class="vb-h" lang="' + esc(code) + '" style="font-size:26px">' + esc(v.headline) + '</h2><p class="vb-act" lang="' + esc(code) + '" style="font-size:20px">' + esc(v.action) + "</p></div></div>" +
          '<ol lang="' + esc(code) + '" style="font-size:19px;line-height:1.7">' + (v.reasons || []).map(function (r) { return "<li>" + esc(r) + "</li>"; }).join("") + "</ol>" +
          '<p class="xs">' + esc(t("sug")) + "</p>" +
          '<p><button type="button" class="btn bn" id="hp-listen" style="width:auto;padding:0 26px;min-height:56px;font-size:19px">' + esc(t("listen")) + "</button> " +
          '<a class="btn bs" style="width:auto;padding:0 22px" target="_blank" rel="noopener" href="/case/' + encodeURIComponent(x.j.id) + '">' + esc(t("full")) + "</a> " +
          '<button type="button" class="btn bq" id="hp-wipe" style="width:auto;padding:0 22px">' + esc(t("wipe")) + "</button></p>";
        D.getElementById("hp-listen").addEventListener("click", function () { say(body, code, this); });
        D.getElementById("hp-wipe").addEventListener("click", wipe);
        go.disabled = false;
      })
      .catch(function () { go.disabled = false; out.innerHTML = '<p class="ops-err">' + esc(t("fail")) + "</p>"; });
  });
})();
