const t = document.getElementById("t"), srv = document.getElementById("srv"), lang = document.getElementById("lang");
chrome.storage.sync.get(["server", "lang"]).then((v) => { srv.value = v.server || ""; lang.value = v.lang || "en"; });
srv.addEventListener("change", () => chrome.storage.sync.set({ server: srv.value.trim() }));
lang.addEventListener("change", () => chrome.storage.sync.set({ lang: lang.value.trim() === "hi" ? "hi" : "en" }));
document.getElementById("go").addEventListener("click", () => {
  if (!t.value.trim()) { t.focus(); return; }
  chrome.runtime.sendMessage({ type: "check", text: t.value });
  window.close();
});
