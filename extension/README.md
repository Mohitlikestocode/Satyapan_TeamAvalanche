# Satyapan browser extension (Chrome, Edge, Brave)

Right-click selected text or a link, choose **Check with Satyapan**, and the Satyapan check page opens with it filled in and the check running. The
full result, including "what does this say" in your own language, is the normal site flow.

## Install (no store needed)
1. Open `chrome://extensions`, switch on **Developer mode**.
2. Press **Load unpacked** and choose this `extension/` folder.
3. Click the extension icon, set **Satyapan server** to your site address (default `http://127.0.0.1:8000`; use your tunnel address once you have one).

## What it does and does not do
* It has **no host permissions** and never reads the pages you visit. It only sees the text or link you right-click.
* Your text is passed in the web address after `#` (the fragment). Browsers never send a fragment to a server. The Satyapan page reads it, removes it
  from the address bar, and checks it when it runs, which happens because you chose the menu item.
* It only advises. It does not block pages or send anything on its own.

## Files
`manifest.json` (Manifest V3) · `background.js` (context menu) · `popup.html` / `popup.js` (paste box and settings) · `icons/`.
