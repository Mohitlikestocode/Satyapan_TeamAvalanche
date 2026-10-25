"""End-to-end check of every feature on a running Satyapan site. Prints PASS / FAIL per feature and exits non-zero if anything fails.

    python scripts/final_check.py http://127.0.0.1:8000

Uses the files in demo/. It marks itself as team traffic (INTERNAL_KEY from .env) so /impact does not count it. It creates and then
deletes one community report and leaves a few test results that expire on their own, so run it before you reset the database for the demo.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
S = requests.Session()
results: list[tuple[str, bool, str]] = []


def env(name: str) -> str:
    f = ROOT / ".env"
    if os.environ.get(name):
        return os.environ[name]
    if f.is_file():
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip()
    return ""


def check(name: str, fn) -> None:
    t0 = time.time()
    try:
        ok, detail = fn()
    except Exception as e:  # noqa: BLE001
        ok, detail = False, f"{type(e).__name__}: {str(e)[:100]}"
    results.append((name, bool(ok), f"{detail} ({time.time() - t0:.1f}s)"))
    print(("PASS " if ok else "FAIL ") + name.ljust(52) + str(detail)[:90], flush=True)


def post_check(kind: str, text: str | None = None, file: Path | None = None, mime: str = "application/octet-stream") -> dict:
    if file is not None:
        with open(file, "rb") as f:
            r = S.post(BASE + "/api/v1/check", data={"kind": kind}, files={"file": (file.name, f, mime)}, timeout=300)
    else:
        r = S.post(BASE + "/api/v1/check", data={"kind": kind, "text": text}, timeout=300)
    r.raise_for_status()
    return r.json()


def tier_is(res: dict, *tiers: str):
    return res.get("tier") in tiers, f"{res.get('tier')} via {res.get('mode')}"


def main() -> int:
    key = env("INTERNAL_KEY")
    if key:
        S.get(BASE + f"/internal?key={key}", timeout=30)

    check("server health and plugins", lambda: (lambda h: (h["status"] == "ok" and "understand" in h["plugins"], ", ".join(h["plugins"])))(S.get(BASE + "/healthz").json()))

    # ---- all pages, both languages
    def crawl(lang: str):
        ses = requests.Session()
        if lang == "hi":
            ses.cookies.set("sp_lang", "hi")
        seen, q, bad = {"/"}, ["/"], []
        while q:
            u = q.pop(0)
            r = ses.get(BASE + u, timeout=120)
            if r.status_code >= 500 or "Traceback" in r.text or "UndefinedError" in r.text:
                bad.append((u, r.status_code))
            if "text/html" in r.headers.get("content-type", ""):
                for h in re.findall(r'href="(/[^"#?]*)"', r.text):
                    if h not in seen and not h.startswith(("/static", "/api", "/g/")) and not h.endswith((".pdf", ".png", ".zip", ".json", ".csv")):
                        seen.add(h)
                        q.append(h)
        return not bad, f"{len(seen)} pages, problems: {bad[:3]}"
    check("every page loads (English)", lambda: crawl("en"))
    check("every page loads (Hindi)", lambda: crawl("hi"))

    # ---- the six inputs
    scam_en = "This is Inspector Verma, Mumbai Cyber Cell. A SIM card in your name was used for illegal activity. Do not disconnect this video call or inform anyone. Transfer Rs 90,000 to the RBI verification account."
    check("message: scam in English", lambda: tier_is(post_check("message", scam_en), "SUSPICIOUS", "HIGH_RISK"))
    check("message: scam in Hindi", lambda: tier_is(post_check("message", "आपके नाम से एक पार्सल पकड़ा गया है जिसमें ड्रग्स मिले हैं। यह सीबीआई अधिकारी का कॉल है। वीडियो कॉल पर बने रहें और किसी को न बताएँ।"), "SUSPICIOUS", "HIGH_RISK"))
    check("message: scam in Hinglish", lambda: tier_is(post_check("message", "Bhai main Army me hu, aapka scooty pasand aaya. Advance bhej raha hu, aap bas QR scan karke apna UPI PIN daalo, paise aa jayenge."), "SUSPICIOUS", "HIGH_RISK"))
    check("message: lottery fee is HIGH RISK", lambda: tier_is(post_check("message", "Congratulations! You have won Rs 25,00,000 in the KBC lucky draw. To claim, pay the processing fee of Rs 12,500 to UPI id kbc.claim@oksbi."), "HIGH_RISK"))
    check("message: genuine bank alert is not flagged", lambda: tier_is(post_check("message", "Rs 2,500.00 debited from A/c XX1234 on 22-10-26 to VPA swiggy@icici. If not you, call your bank. -SBI"), "NO_RED_FLAGS"))
    check("message: genuine OTP warning is not flagged", lambda: tier_is(post_check("message", "Your OTP for login is 482910. Do not share this with anyone, including bank staff. Valid for 10 minutes."), "NO_RED_FLAGS"))
    check("link: look-alike bank link", lambda: tier_is(post_check("link", "http://sbi-yono-kyc.in/update"), "SUSPICIOUS", "HIGH_RISK"))
    check("link: real bank site", lambda: tier_is(post_check("link", "https://www.sbi.co.in"), "NO_RED_FLAGS"))
    check("QR: collect trap", lambda: tier_is(post_check("qr", file=ROOT / "demo/qr/collect_trap__clean.png", mime="image/png"), "SUSPICIOUS", "HIGH_RISK"))
    check("QR card with scam words", lambda: tier_is(post_check("qr", file=ROOT / "demo/qr_cards/scam_card_1.png", mime="image/png"), "SUSPICIOUS", "HIGH_RISK"))
    check("QR card of a genuine shop", lambda: tier_is(post_check("qr", file=ROOT / "demo/qr_cards/genuine_card_1.png", mime="image/png"), "NO_RED_FLAGS"))
    check("PDF: scam brochure", lambda: tier_is(post_check("pdf", file=ROOT / "demo/pdf/scam_investment_brochure.pdf", mime="application/pdf"), "SUSPICIOUS", "HIGH_RISK"))
    check("PDF: genuine electricity bill", lambda: tier_is(post_check("pdf", file=ROOT / "demo/pdf/genuine_electricity_bill.pdf", mime="application/pdf"), "NO_RED_FLAGS"))

    def screenshot():
        r = post_check("screenshot", file=ROOT / "demo/screens/genuine_000000.jpg", mime="image/jpeg")
        c = S.get(BASE + f"/api/v1/case/{r['id']}").json()
        return bool(c["payees"]) and r["tier"] in ("NO_RED_FLAGS", "SUSPICIOUS"), f"{r['tier']}, payee {c['payees'][0]['upi'] if c['payees'] else None}, text read {len(r.get('text_read') or '')} chars"
    check("screenshot: reads the payee and answers", screenshot)

    def voice():
        r = post_check("voice", file=ROOT / "demo/voice/scam_hi.wav", mime="audio/wav")
        return r["tier"] in ("SUSPICIOUS", "HIGH_RISK") and bool(r.get("text_read")), f"{r['tier']}, heard: {(r.get('text_read') or '')[:40]}"
    check("voice note: speech to text, then verdict", voice)

    # ---- understand first
    case = post_check("message", scam_en)
    cid = case["id"]
    check("result carries the text we read", lambda: (bool(case.get("text_read")), f"{len(case.get('text_read') or '')} chars"))
    check("explain needs consent", lambda: (S.post(BASE + "/api/v1/understand/translate", json={"text": "hi", "lang": "ta"}).status_code == 400, "400 without consent"))

    def translate():
        r = S.post(BASE + "/api/v1/understand/translate", json={"text": "Bhai paise bhejo, UPI kbc.claim@oksbi par", "lang": "ta", "consent": True}, timeout=120)
        j = r.json()
        return r.status_code == 200 and "kbc.claim@oksbi" in j["translated"] and re.search(r"[஀-௿]", j["translated"]), j.get("translated", "")[:50]
    check("explain in Tamil keeps the UPI ID intact", translate)

    def verdict_in():
        j = S.post(BASE + "/api/v1/understand/verdict", json={"case_id": cid, "lang": "te"}, timeout=120).json()
        return bool(re.search(r"[ఀ-౿]", j["headline"])) and len(j["reasons"]) > 0, j["headline"]
    check("our verdict in Telugu", verdict_in)

    def speak():
        r = S.post(BASE + "/api/v1/understand/speak", json={"text": "नमस्ते, यह एक परीक्षण है।", "lang": "hi", "consent": True}, timeout=120)
        return r.status_code == 200 and r.content[:4] == b"RIFF", f"{len(r.content)} bytes of audio"
    check("Listen: Sarvam speech in Hindi", speak)
    check("Listen on a saved result (English)", lambda: (lambda r: (r.status_code == 200 and r.content[:4] == b"RIFF", f"{r.status_code}"))(S.post(BASE + "/api/v1/speak", json={"case_id": cid, "lang": "en"}, timeout=120)))

    # ---- tools
    def company():
        r = S.post(BASE + "/tools", data={"company": "amazon", "text": "Amazon refund pending. Claim at http://amazon-refund-help.top/claim or call 9876543210"}, allow_redirects=True, timeout=120)
        return "not one of that company" in r.text, f"{r.status_code} {r.url.rsplit('/', 1)[-1]}"
    check("Is this really them? (Amazon look-alike link)", company)
    check("Shopkeeper page loads with its script", lambda: (S.get(BASE + "/shopkeeper").status_code == 200 and S.get(BASE + "/static/js/shopkeeper.js").status_code == 200, "page and script"))
    check("Helper mode page loads with its script", lambda: (S.get(BASE + "/helper").status_code == 200 and S.get(BASE + "/static/js/helper.js").status_code == 200, "page and script"))

    # ---- the action after a result
    def evidence():
        ev = S.get(BASE + f"/api/v1/evidence/{cid}").json()
        v = S.post(BASE + "/api/v1/evidence/verify", json=ev).json()
        ev["pack"]["not_checked"] = "tampered"
        v2 = S.post(BASE + "/api/v1/evidence/verify", json=ev).json()
        return v["valid"] and not v2["valid"], "signature valid; edited copy rejected"
    check("evidence report is signed and tamper-evident", evidence)
    check("evidence and complaint pages", lambda: (all(S.get(BASE + f"/{p}?case={cid}").status_code == 200 for p in ("report", "report/complaint")), "report + complaint"))

    def guardian():
        seen = []
        ok1 = S.get(BASE + f"/guardian?case={cid}").status_code == 200
        r = S.post(BASE + f"/api/guardian/shared?case={cid}")
        return ok1 and r.json() == {"ok": True}, "guardian page and share event"
    check("Ask family (guardian) and share event", guardian)

    def wrong():
        r = S.post(BASE + "/api/v1/wrong-result", json={"case_id": cid, "reason": "not_scam", "note": "final check", "share_for_review": False})
        ref = r.json()["id"]
        st = S.get(BASE + f"/api/v1/review/{ref}").json()
        return r.status_code == 201 and st["status"] == "needs_review", f"{ref} {st['status']}"
    check("Wrong result? creates a review ticket", wrong)
    check("reviewer console sign-in page", lambda: (S.get(BASE + "/console").status_code == 200, "page"))

    def delete():
        d = post_check("message", "Pay a processing fee of Rs 500 to claim your lottery prize")["id"]
        a = S.delete(BASE + f"/api/v1/check/{d}").status_code
        b = S.get(BASE + f"/api/v1/case/{d}").status_code
        page = S.get(BASE + "/deletion?ref=SP-TEST-0001").text
        return a == 204 and b == 404 and "SP-TEST-0001" in page or "dr-ref" in page, f"delete {a}, then {b}"
    check("delete really deletes, and the receipt is real", delete)

    # ---- community, learning, traction, measurement
    def community():
        r = S.post(BASE + "/community/report", data={"kind": "message", "text": "Final check: someone asked me to pay a fee to release a prize.", "consent": "on", "intent": "warn", "lang": "en"}, allow_redirects=False)
        loc = r.headers.get("location", "")
        m = re.search(r"/community/post/(\d+)", loc)
        if not m:
            return False, f"{r.status_code} {loc}"
        pid = m.group(1)
        page = S.get(BASE + f"/community/post/{pid}").status_code
        S.post(BASE + f"/community/post/{pid}/delete", allow_redirects=False)
        return page == 200, f"post {pid} created, viewed, deleted"
    check("Scam Watch: report, view, delete", community)
    check("Learn, Scam Drill, leaderboard, safe word", lambda: (all(S.get(BASE + p).status_code == 200 for p in ("/learn", "/learn/drill", "/learn/leaderboard", "/learn/safe-word", "/learn/safety", "/warn")), "6 pages"))

    def poster():
        r = S.post(BASE + "/poster", data={"name": "Final Check Store", "city": "Delhi"})
        return r.status_code == 200 and "<svg" in r.text, f"{r.status_code}, QR drawn"
    check("shop poster with QR", poster)
    check("pilot form and feedback page", lambda: (all(S.get(BASE + p).status_code == 200 for p in ("/pilot", "/feedback")), "2 pages"))
    check("impact page and JSON numbers", lambda: (S.get(BASE + "/impact").status_code == 200 and "checks" in json.dumps(S.get(BASE + "/api/v1/metrics/summary").json()).lower(), "page + summary"))
    check("results page reads from files", lambda: (lambda t: ("Measured" in t and "Not evaluated" in t, "has measured and not-evaluated rows"))(S.get(BASE + "/results").text))

    def attack():
        r = S.post(BASE + "/attack/text", data={"text": scam_en}, timeout=300)
        return r.status_code == 200 and "Spacing" in r.text, f"{r.status_code}"
    check("Attack yourself: perturb a message", attack)
    check("PWA files (manifest, service worker)", lambda: (S.get(BASE + "/manifest.webmanifest").status_code == 200 and S.get(BASE + "/sw.js").status_code == 200, "manifest + sw"))

    # ---- Telegram
    tok = env("TELEGRAM_BOT_TOKEN")
    if tok:
        def tg():
            j = requests.get(f"https://api.telegram.org/bot{tok}/getMe", timeout=20).json()
            return j.get("ok"), "@" + j["result"]["username"]
        check("Telegram bot token is valid", tg)

    bad = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(bad)} passed, {len(bad)} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
