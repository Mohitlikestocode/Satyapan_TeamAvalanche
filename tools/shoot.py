"""Developer tool: take README screenshots of real flows by driving headless Chrome over its debugging protocol.

usage: python tools/shoot.py http://127.0.0.1:8000 docs/img
Needs Chrome, `pip install websocket-client`, and the site running with a Sarvam key (for the explain screenshots).
It types real input into the real pages and saves what the browser shows. Nothing here is mocked.
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
SCAM = ("Bhai main Army me hu, aapka scooty pasand aaya. Advance bhej raha hu, aap bas QR scan karke apna UPI PIN daalo, paise aa jayenge.")


class Page:
    def __init__(self, port: int):
        tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
        self.ws = websocket.create_connection([t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"], suppress_origin=True, timeout=60)
        self.n = 0

    def call(self, method: str, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.n:
                return m.get("result", {})

    def js(self, code: str):
        r = self.call("Runtime.evaluate", expression=code, awaitPromise=True, returnByValue=True)
        return r.get("result", {}).get("value")

    def shot(self, path: Path, full: bool = False, selector: str | None = None, pad: int = 12, max_h: int | None = None):
        params: dict = {"format": "png", "captureBeyondViewport": full}
        if selector:
            r = self.js(f"(()=>{{const e=document.querySelector({selector!r});if(!e)return null;const b=e.getBoundingClientRect();return [b.x+scrollX,b.y+scrollY,b.width,b.height]}})()")
            if r:
                params["clip"] = {"x": max(0, r[0] - pad), "y": max(0, r[1] - pad), "width": r[2] + 2 * pad, "height": min(r[3] + 2 * pad, max_h or 10_000), "scale": 1}
                params["captureBeyondViewport"] = True
        d = self.call("Page.captureScreenshot", **params)["data"]
        path.write_bytes(base64.b64decode(d))
        print("saved", path)


def main() -> None:
    base, out = sys.argv[1].rstrip("/"), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    port = 9333
    prof = tempfile.mkdtemp()
    proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--remote-debugging-port={port}", f"--user-data-dir={prof}", "--window-size=1360,1000",
                             "--hide-scrollbars", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/json")
                break
            except OSError:
                time.sleep(0.5)
        pg = Page(port)
        pg.call("Page.enable")
        pg.call("Emulation.setDeviceMetricsOverride", width=1360, height=1000, deviceScaleFactor=1, mobile=False)
        # 1. a real check from the extension-style link, then the explain panel in Tamil
        from urllib.parse import quote
        pg.call("Page.navigate", url=f"{base}/check?lang=en&autorun=1#t={quote(SCAM)}")
        time.sleep(7)
        pg.js("document.getElementById('und-lang') && (document.getElementById('und-lang').value='ta')")
        pg.js("document.getElementById('und-go') && document.getElementById('und-go').click()")
        time.sleep(14)
        pg.js("window.scrollTo(0,0)")
        pg.shot(out / "explain-tamil.png", selector="#understand")
        # 2. the same message in Hindi UI: the panel in Hindi with a different language chosen
        pg.js("document.getElementById('und-lang').value='te'; document.getElementById('und-go').click()")
        time.sleep(14)
        pg.shot(out / "explain-telugu.png", selector="#understand")
        # 3. company check
        pg.call("Page.navigate", url=f"{base}/tools?lang=en")
        time.sleep(3)
        pg.js("document.getElementById('company').value='amazon'; document.getElementById('text').value='Amazon refund pending. Claim now at http://amazon-refund-help.top/claim or call 9876543210'; document.querySelector('form button').click()")
        time.sleep(6)
        pg.shot(out / "company-check.png", selector="main", max_h=1500)
        # 4. helper mode with a Hindi-speaking person
        pg.call("Page.navigate", url=f"{base}/helper?lang=en")
        time.sleep(3)
        pg.js("document.getElementById('hp-lang').value='hi'; document.getElementById('hp-text').value='आपके नाम से एक पार्सल पकड़ा गया है जिसमें ड्रग्स मिले हैं। यह सीबीआई अधिकारी का कॉल है। वीडियो कॉल पर बने रहें और किसी को न बताएँ।'; document.getElementById('hp-go').click()")
        time.sleep(8)
        pg.shot(out / "helper-mode.png", selector="main", max_h=1500)
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
