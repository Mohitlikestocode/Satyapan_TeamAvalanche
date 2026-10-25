// Satyapan extension: right-click selected text, a link or a phone number and open the Satyapan check page with it filled in.
// The text goes in the URL fragment (#t=...), which the browser never sends to any server; the page reads it, then clears it from the address bar.
// The extension has no host permissions and never reads the pages you visit: it only sees what you right-click.
const DEFAULT_SERVER = "http://127.0.0.1:8000";

async function server() {
  const { server: s } = await chrome.storage.sync.get("server");
  return (s || DEFAULT_SERVER).replace(/\/+$/, "");
}

async function openCheck(text, autorun) {
  const base = await server();
  const t = String(text || "").trim().slice(0, 4000);
  if (!t) return;
  chrome.tabs.create({ url: `${base}/check?lang=${(await chrome.storage.sync.get("lang")).lang || "en"}${autorun ? "&autorun=1" : ""}#t=${encodeURIComponent(t)}` });
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: "sp-selection", title: "Check “%s” with Satyapan", contexts: ["selection"] });
  chrome.contextMenus.create({ id: "sp-link", title: "Check this link with Satyapan", contexts: ["link"] });
});

chrome.contextMenus.onClicked.addListener((info) => {
  if (info.menuItemId === "sp-selection") openCheck(info.selectionText, true);
  if (info.menuItemId === "sp-link") openCheck(info.linkUrl, true);
});

chrome.runtime.onMessage.addListener((msg) => {
  if (msg && msg.type === "check") openCheck(msg.text, true);
});
