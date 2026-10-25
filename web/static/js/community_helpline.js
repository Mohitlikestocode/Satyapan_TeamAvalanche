/* Under every HIGH RISK, REGISTRY HIT and SUSPICIOUS verdict, a button to call the national cyber-crime helpline (1930).
   Works on the result page, Ask family, the family view, the evidence report and Scam Watch posts: they all mark a verdict as
   <section class="vbanner vb-r|vb-a">. Not added for "no red flags found" or "can't tell". If this script does not run, nothing else changes. */
(function () {
  var D = document;
  var T = {
    en: { call: "Call 1930 now", sub: "National cyber-crime helpline",
          note: "Already paid, or shared an OTP, PIN or bank details? Call within the first hour. You can also report at", aria: "Call the cyber-crime helpline, 1930" },
    hi: { call: "अभी 1930 पर कॉल करें", sub: "राष्ट्रीय साइबर-अपराध हेल्पलाइन",
          note: "पैसे भेज दिए हैं, या OTP, PIN या बैंक की जानकारी बता दी है? पहले घंटे में कॉल करें। आप यहाँ भी शिकायत कर सकते हैं:", aria: "साइबर-अपराध हेल्पलाइन 1930 पर कॉल करें" }
  };
  var PHONE = '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.9.6 2.8.7a2 2 0 0 1 1.7 2z" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  D.querySelectorAll("main section.vbanner.vb-r, main section.vbanner.vb-a").forEach(function (banner) {
    if (banner.nextElementSibling && banner.nextElementSibling.hasAttribute("data-cm-helpline")) return;
    var v = banner.closest("[data-variant]"), page = D.documentElement.getAttribute("data-lang") === "hi" ? "hi" : "en";
    var lang = v ? (v.getAttribute("data-variant") === "hi" ? "hi" : "en") : page, t = T[lang];
    var box = D.createElement("div");
    box.className = "cm-help"; box.setAttribute("data-cm-helpline", "1"); box.setAttribute("role", "group"); if (lang === "hi") box.setAttribute("lang", "hi");
    box.innerHTML = '<a class="cm-help-call" href="tel:1930" aria-label="' + t.aria + '">' + PHONE + '<span><b>' + t.call + '</b><small>' + t.sub + '</small></span></a>' +
                    '<p class="cm-help-note">' + t.note + ' <a href="https://cybercrime.gov.in" rel="noopener">cybercrime.gov.in</a></p>';
    banner.parentNode.insertBefore(box, banner.nextSibling);
  });
})();
