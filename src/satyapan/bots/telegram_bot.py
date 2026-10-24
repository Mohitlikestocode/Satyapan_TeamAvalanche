"""Telegram bot: forward a suspicious message, picture, PDF or voice note and get the same verdict as the website.

Run:  TELEGRAM_BOT_TOKEN=... PUBLIC_URL=https://your-site python -m satyapan.bots.telegram_bot
It calls the same engine in process, saves each result so the website link works, and counts the check in the metrics tables
(channel "telegram"). Files are handled in memory and never written to disk. Chat ids are stored only as salted hashes.
Group chats are ignored; the bot answers private chats only.
"""
from __future__ import annotations

import logging
import os
import re
import time
import uuid
from collections import defaultdict, deque

import httpx

from ..envfile import load_dotenv
from ..extract.ocr import read_text
from ..extract.qr import decode_qr
from ..ops import metrics
from ..plugins import REGISTRY, load_plugins
from ..service import CaseResult, analyse_image, analyse_pdf, analyse_text
from ..store import db

log = logging.getLogger("satyapan.telegram")
MAX_FILE = 20 * 1024 * 1024
URL_ONLY = re.compile(r"^\s*(https?://\S+)\s*$", re.IGNORECASE)

TXT = {
    "en": {
        "welcome": "Hello. I am Satyapan. Forward me a suspicious message, link, QR picture, screenshot, PDF or voice note, and I will tell you in a minute what looks wrong and who is asking for the money.\n\nI do not keep your file. I only advise: I never block, pay or report anything for you. I will never ask for your OTP, PIN or password.\n\nChoose your language:",
        "help": "Send me a message, link, picture, PDF or voice note to check. Commands: /lang change language, /delete delete my last result, /privacy how I treat your data.",
        "privacy": "Your file is read in memory and thrown away. I keep only the result for 24 hours so the web link works, and a random code for your chat (not your name or number). /delete removes your last result at once.",
        "working": "Checking...",
        "empty": "I could not find anything to check in that. Please send the message, a clear picture, or a PDF.",
        "too_big": "That file is too large for me (limit 20 MB).",
        "unsupported": "I can check text, links, pictures, PDFs and voice notes. I cannot read that kind of file.",
        "no_voice": "Voice checks are not available right now. Please send the text of the message, or a screenshot.",
        "slow": "You are sending a lot at once. Please wait a minute and try again.",
        "error": "Sorry, something went wrong on my side. Please try again.",
        "full": "Full result and next steps",
        "wrong": "Wrong result?", "family": "Ask family", "delete": "Delete my result", "open": "Open on the website",
        "share_q": "Thank you. Should a human reviewer see this result to check it?",
        "share_yes": "Yes, share it", "share_no": "No, just say it was wrong",
        "sent": "Sent for human review. Reference {ref}. You can see the status here: {url}",
        "deleted": "Deleted. I no longer have that result.", "nothing": "There is nothing to delete.",
        "lang_set": "Language set to English.",
        "family_msg": "Please check with me before I pay. Satyapan says: {headline}. {reason} More: {url}",
        "family_hint": "Forward this message to someone you trust:",
    },
    "hi": {
        "welcome": "नमस्ते। मैं सत्यापन हूँ। कोई शक वाला संदेश, लिंक, QR की तस्वीर, स्क्रीनशॉट, PDF या वॉइस नोट मुझे फ़ॉरवर्ड करें। मैं एक मिनट में बताऊँगा कि क्या गड़बड़ दिखती है और पैसे कौन माँग रहा है।\n\nमैं आपकी फ़ाइल नहीं रखता। मैं सिर्फ़ सलाह देता हूँ: आपके लिए कुछ रोकता, चुकाता या दर्ज नहीं करता। मैं आपका OTP, PIN या पासवर्ड कभी नहीं माँगूँगा।\n\nअपनी भाषा चुनें:",
        "help": "जाँचने के लिए संदेश, लिंक, तस्वीर, PDF या वॉइस नोट भेजें। कमांड: /lang भाषा बदलें, /delete मेरा आख़िरी नतीजा मिटाएँ, /privacy आपके डेटा का क्या होता है।",
        "privacy": "आपकी फ़ाइल सिर्फ़ मेमोरी में पढ़ी जाती है और फिर फेंक दी जाती है। वेब लिंक चलता रहे इसलिए नतीजा 24 घंटे रखता हूँ, और आपकी चैट का एक बेतरतीब कोड (नाम या नंबर नहीं)। /delete से आख़िरी नतीजा तुरंत मिट जाता है।",
        "working": "जाँच रहा हूँ...",
        "empty": "इसमें मुझे जाँचने लायक कुछ नहीं मिला। कृपया संदेश, साफ़ तस्वीर या PDF भेजें।",
        "too_big": "यह फ़ाइल मेरे लिए बहुत बड़ी है (सीमा 20 MB)।",
        "unsupported": "मैं पाठ, लिंक, तस्वीरें, PDF और वॉइस नोट जाँच सकता हूँ। इस तरह की फ़ाइल नहीं पढ़ सकता।",
        "no_voice": "वॉइस जाँच अभी उपलब्ध नहीं है। कृपया संदेश का पाठ या स्क्रीनशॉट भेजें।",
        "slow": "आप एक साथ बहुत भेज रहे हैं। कृपया एक मिनट रुककर फिर कोशिश करें।",
        "error": "माफ़ कीजिए, मेरी तरफ़ कुछ गड़बड़ हुई। कृपया फिर कोशिश करें।",
        "full": "पूरा नतीजा और आगे के कदम",
        "wrong": "नतीजा ग़लत है?", "family": "परिवार से पूछें", "delete": "मेरा नतीजा मिटाएँ", "open": "वेबसाइट पर खोलें",
        "share_q": "धन्यवाद। क्या जाँचने के लिए यह नतीजा किसी समीक्षक को दिखाया जाए?",
        "share_yes": "हाँ, दिखाएँ", "share_no": "नहीं, बस बताएँ कि ग़लत था",
        "sent": "मानवीय समीक्षा के लिए भेज दिया। संदर्भ {ref}। स्थिति यहाँ देखें: {url}",
        "deleted": "मिटा दिया। अब मेरे पास वह नतीजा नहीं है।", "nothing": "मिटाने के लिए कुछ नहीं है।",
        "lang_set": "भाषा हिन्दी कर दी गई।",
        "family_msg": "पैसे भेजने से पहले मुझसे बात कर लीजिए। सत्यापन कहता है: {headline}। {reason} और जानें: {url}",
        "family_hint": "यह संदेश किसी भरोसेमंद व्यक्ति को फ़ॉरवर्ड करें:",
    },
}


class TelegramApi:
    """Thin client for the Bot API. Tests replace it with a fake that has the same methods."""

    def __init__(self, token: str):
        self.base = f"https://api.telegram.org/bot{token}"
        self.file_base = f"https://api.telegram.org/file/bot{token}"
        self.http = httpx.Client(timeout=40)

    def call(self, method: str, **params):
        r = self.http.post(f"{self.base}/{method}", json=params)
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"telegram {method} failed: {data.get('description')}")
        return data["result"]

    def get_updates(self, offset: int | None, timeout: int = 30) -> list[dict]:
        return self.call("getUpdates", offset=offset, timeout=timeout, allowed_updates=["message", "callback_query"])

    def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None) -> dict:
        return self.call("sendMessage", chat_id=chat_id, text=text[:4000], reply_markup=reply_markup, disable_web_page_preview=True)

    def answer_callback(self, cb_id: str, text: str = "") -> None:
        self.call("answerCallbackQuery", callback_query_id=cb_id, text=text[:150])

    def download(self, file_id: str) -> bytes | None:
        info = self.call("getFile", file_id=file_id)
        if info.get("file_size", 0) > MAX_FILE:
            return None
        r = self.http.get(f"{self.file_base}/{info['file_path']}")
        return r.content if r.status_code == 200 and len(r.content) <= MAX_FILE else None


class Bot:
    def __init__(self, api, public_url: str = "", clock=time.monotonic):
        self.api, self.public_url, self.clock = api, public_url.rstrip("/"), clock
        self._recent: dict[int, deque] = defaultdict(deque)
        self._last: dict[int, str] = {}     # chat -> last case id, kept in memory only

    # ---- language and limits -----------------------------------------------------------------------------------
    def lang(self, chat_id: int, hint: str | None = None) -> str:
        key = metrics.hash_id(f"tg:{chat_id}")
        with metrics.conn() as c:
            row = c.execute("SELECT lang FROM ops_chat_lang WHERE chat=?", (key,)).fetchone()
        if row:
            return row["lang"]
        return "hi" if (hint or "").startswith("hi") else "en"

    def set_lang(self, chat_id: int, lang: str) -> None:
        with metrics.conn() as c:
            c.execute("INSERT INTO ops_chat_lang(chat,lang,ts) VALUES(?,?,?) ON CONFLICT(chat) DO UPDATE SET lang=excluded.lang, ts=excluded.ts",
                      (metrics.hash_id(f"tg:{chat_id}"), lang, int(time.time())))

    def limited(self, chat_id: int, per_minute: int = 10) -> bool:
        now, q = self.clock(), self._recent[chat_id]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= per_minute:
            return True
        q.append(now)
        return False

    # ---- entry point ----------------------------------------------------------------------------------------------
    def handle_update(self, update: dict) -> None:
        try:
            if "callback_query" in update:
                self._callback(update["callback_query"])
            elif "message" in update:
                self._message(update["message"])
        except Exception:                       # never leak content, never crash the loop
            log.exception("update failed")
            try:
                chat = (update.get("message") or update.get("callback_query", {}).get("message") or {}).get("chat", {}).get("id")
                if chat:
                    self.api.send_message(chat, TXT[self.lang(chat)]["error"])
            except Exception:
                log.exception("could not report the failure")

    # ---- messages -----------------------------------------------------------------------------------------------------
    def _message(self, m: dict) -> None:
        chat = m["chat"]
        if chat.get("type") != "private":
            return
        cid = chat["id"]
        hint = (m.get("from") or {}).get("language_code")
        lang = self.lang(cid, hint)
        t = TXT[lang]
        text = (m.get("text") or "").strip()
        if text.startswith("/"):
            return self._command(cid, text.split()[0].split("@")[0].lower(), lang)
        if self.limited(cid):
            self.api.send_message(cid, t["slow"])
            return
        t0 = time.perf_counter()
        res: CaseResult | None = None
        kind = "message"
        caption = (m.get("caption") or "").strip()
        if text:
            kind = "link" if URL_ONLY.match(text) else "message"
            res = analyse_text(text, kind=kind, case_id=uuid.uuid4().hex[:12])
        elif m.get("photo"):
            kind = "screenshot"
            data = self.api.download(m["photo"][-1]["file_id"])
            if data is None:
                self.api.send_message(cid, t["too_big"])
                return
            res = self._image(data, kind, caption)
        elif m.get("document"):
            d = m["document"]
            mime = (d.get("mime_type") or "").lower()
            if d.get("file_size", 0) > MAX_FILE:
                self.api.send_message(cid, t["too_big"])
                return
            if mime == "application/pdf" or (d.get("file_name") or "").lower().endswith(".pdf"):
                kind, data = "pdf", self.api.download(d["file_id"])
                res = analyse_pdf(data, case_id=uuid.uuid4().hex[:12]) if data else None
            elif mime.startswith("image/"):
                kind, data = "screenshot", self.api.download(d["file_id"])
                res = self._image(data, kind, caption) if data else None
            else:
                self.api.send_message(cid, t["unsupported"])
                return
        elif m.get("voice") or m.get("audio"):
            kind = "voice"
            handler = REGISTRY.handlers.get("voice")
            if handler is None:
                self.api.send_message(cid, t["no_voice"])
                return
            fid = (m.get("voice") or m.get("audio"))["file_id"]
            data = self.api.download(fid)
            res = handler(data, "", uuid.uuid4().hex[:12]) if data else None
        else:
            self.api.send_message(cid, t["unsupported"])
            return
        if res is None:
            self.api.send_message(cid, t["empty"])
            return
        db.save_case(res)
        self._last[cid] = res.case_id
        metrics.record_check(kind=kind, channel="telegram", tier=res.tier.value, mode="engine", elapsed_ms=int((time.perf_counter() - t0) * 1000),
                             device_raw=metrics.hash_id(f"tg:{cid}"), hashed=True)
        self._reply(cid, res, lang)

    def _image(self, data: bytes, kind: str, caption: str) -> CaseResult:
        case_id = uuid.uuid4().hex[:12]
        if caption:     # words typed with the picture are checked together with the picture's text and QR payloads
            return analyse_text("\n".join([*decode_qr(data), read_text(data) or "", caption]), kind=kind, case_id=case_id)
        return analyse_image(data, kind=kind, case_id=case_id)

    def _reply(self, cid: int, res: CaseResult, lang: str) -> None:
        v, t = res.verdicts[lang], TXT[lang]
        lines = [v.headline, ""] + [f"{i}. {r}" for i, r in enumerate(v.reasons_text[:3], 1)] + ["", v.action_text, "", v.footer_text]
        url = f"{self.public_url}/case/{res.case_id}" if self.public_url else ""
        if url:
            lines += ["", f"{t['full']}: {url}"]
        keyboard = [[{"text": t["wrong"], "callback_data": f"wrong:{res.case_id}"}, {"text": t["family"], "callback_data": f"family:{res.case_id}"}],
                    [{"text": t["delete"], "callback_data": f"del:{res.case_id}"}]]
        if url.startswith("https://"):
            keyboard.append([{"text": t["open"], "url": url}])
        self.api.send_message(cid, "\n".join(lines), {"inline_keyboard": keyboard})

    def _command(self, cid: int, cmd: str, lang: str) -> None:
        t = TXT[lang]
        lang_kb = {"inline_keyboard": [[{"text": "English", "callback_data": "lang:en"}, {"text": "हिन्दी", "callback_data": "lang:hi"}]]}
        if cmd == "/start":
            self.api.send_message(cid, t["welcome"], lang_kb)
        elif cmd == "/lang":
            self.api.send_message(cid, "English / हिन्दी", lang_kb)
        elif cmd == "/privacy":
            self.api.send_message(cid, t["privacy"])
        elif cmd == "/delete":
            case = self._last.pop(cid, None)
            ok = bool(case and db.delete_case(case))
            if ok:
                REGISTRY.emit("delete", {"case_id": case})
            self.api.send_message(cid, t["deleted"] if ok else t["nothing"])
        else:
            self.api.send_message(cid, t["help"])

    # ---- buttons --------------------------------------------------------------------------------------------------------
    def _callback(self, cb: dict) -> None:
        cid = cb["message"]["chat"]["id"]
        data = cb.get("data", "")
        action, _, arg = data.partition(":")
        lang = self.lang(cid, (cb.get("from") or {}).get("language_code"))
        t = TXT[lang]
        self.api.answer_callback(cb["id"])
        if action == "lang" and arg in ("en", "hi"):
            self.set_lang(cid, arg)
            self.api.send_message(cid, TXT[arg]["lang_set"] + "\n\n" + TXT[arg]["help"])
        elif action == "wrong":
            kb = {"inline_keyboard": [[{"text": t["share_yes"], "callback_data": f"wrongy:{arg}"}, {"text": t["share_no"], "callback_data": f"wrongn:{arg}"}]]}
            self.api.send_message(cid, t["share_q"], kb)
        elif action in ("wrongy", "wrongn"):
            case = db.get_case(arg)
            ref = db.create_review(case.case_id if case else None, "telegram: user says the result is wrong", "", action == "wrongy")
            REGISTRY.emit("dispute", {"ref": ref, "case_id": case.case_id if case else None})
            self.api.send_message(cid, t["sent"].format(ref=ref, url=f"{self.public_url}/wrong/status?ref={ref}" if self.public_url else ref))
        elif action == "family":
            case = db.get_case(arg)
            if case:
                v = case.verdicts[lang]
                msg = t["family_msg"].format(headline=v.headline, reason=(v.reasons_text[0] if v.reasons_text else ""), url=f"{self.public_url}/g/{case.share_token}")
                self.api.send_message(cid, t["family_hint"])
                self.api.send_message(cid, msg)
        elif action == "del":
            ok = db.delete_case(arg)
            if ok:
                REGISTRY.emit("delete", {"case_id": arg})
            self._last.pop(cid, None)
            self.api.send_message(cid, t["deleted"] if ok else t["nothing"])


def offset_file():
    return db.home() / "telegram_offset"


def run() -> None:
    load_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN (create a bot with @BotFather).")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_plugins()
    api = TelegramApi(token)
    bot = Bot(api, os.environ.get("PUBLIC_URL", ""))
    try:
        offset = int(offset_file().read_text())
    except (OSError, ValueError):
        offset = None
    log.info("bot started")
    while True:
        try:
            for u in api.get_updates(offset):
                offset = u["update_id"] + 1
                bot.handle_update(u)
                offset_file().parent.mkdir(parents=True, exist_ok=True)
                offset_file().write_text(str(offset))
        except (httpx.HTTPError, RuntimeError):
            log.warning("telegram connection problem, retrying")
            time.sleep(5)


if __name__ == "__main__":
    run()


__all__ = ["Bot", "TelegramApi", "run"]
