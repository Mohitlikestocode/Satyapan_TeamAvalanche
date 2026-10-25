"""The Telegram bot, driven with fake Telegram updates (no network, no token)."""
import io

import pytest

from satyapan.bots.telegram_bot import Bot
from satyapan.ops import metrics
from satyapan.plugins import REGISTRY, load_plugins
from satyapan.service import analyse_text
from satyapan.store import db

CHAT = 424242
SCAM = "Guaranteed 30% a month, join our VIP group. Pay upi://pay?pa=alpha.gain88@ybl&pn=Ramesh%20K&am=25000"


class FakeApi:
    def __init__(self):
        self.sent, self.answered, self.files = [], [], {}

    def send_message(self, chat_id, text, reply_markup=None):
        self.sent.append({"chat": chat_id, "text": text, "markup": reply_markup})
        return {}

    def answer_callback(self, cb_id, text=""):
        self.answered.append(cb_id)

    def download(self, file_id):
        return self.files.get(file_id)

    @property
    def last(self):
        return self.sent[-1]


def msg(text=None, chat=CHAT, chat_type="private", lang="en", **extra):
    m = {"chat": {"id": chat, "type": chat_type}, "from": {"language_code": lang}}
    if text is not None:
        m["text"] = text
    m.update(extra)
    return {"update_id": 1, "message": m}


def press(data, chat=CHAT, lang="en"):
    return {"update_id": 2, "callback_query": {"id": "cb1", "data": data, "from": {"language_code": lang}, "message": {"chat": {"id": chat, "type": "private"}}}}


@pytest.fixture()
def bot():
    load_plugins()          # the real bot does this at start-up, so metrics listeners are registered
    api = FakeApi()
    return Bot(api, "https://site.example"), api


def buttons(markup):
    return [b["callback_data"] for row in markup["inline_keyboard"] for b in row if "callback_data" in b]


def test_start_offers_language_choice_and_a_hindi_phone_gets_hindi_by_default(bot):
    b, api = bot
    b.handle_update(msg("/start"))
    assert "Satyapan" in api.last["text"] and buttons(api.last["markup"]) == ["lang:en", "lang:hi"]
    b.handle_update(msg("/start", chat=7, lang="hi"))
    assert "नमस्ते" in api.last["text"]


def test_a_scam_message_gets_the_verdict_reasons_action_footer_and_link(bot):
    b, api = bot
    b.handle_update(msg(SCAM))
    text = api.last["text"]
    assert text.startswith("HIGH RISK") and "1. " in text and "2. " in text and "3. " in text
    assert "Do not pay or join" in text and "never moves or blocks money" in text
    case_id = text.split("/case/")[1].split()[0]
    assert db.get_case(case_id) is not None                                                 # the web link works
    assert set(buttons(api.last["markup"])) == {f"wrong:{case_id}", f"family:{case_id}", f"del:{case_id}"}
    assert api.last["markup"]["inline_keyboard"][-1][0]["url"].startswith("https://site.example/case/")


def test_checks_are_counted_as_telegram_without_storing_the_chat_id(bot):
    b, api = bot
    b.handle_update(msg(SCAM))
    b.handle_update(msg("lunch tomorrow?", chat=555))
    s = metrics.summary()
    assert s["checks"] == 2 and s["people"] == 2 and s["by_channel"] == {"telegram": 2}
    with db.conn() as c:
        dump = " ".join(str(tuple(r)) for t in ("metrics_events", "metrics_devices", "ops_chat_lang", "cases") for r in c.execute(f"SELECT * FROM {t}"))
    assert str(CHAT) not in dump and "alpha.gain88" in dump                                      # payee kept, chat id not


def test_language_choice_sticks(bot):
    b, api = bot
    b.handle_update(press("lang:hi"))
    assert "हिन्दी" in api.last["text"]
    b.handle_update(msg(SCAM))
    assert api.last["text"].startswith("ज़्यादा जोखिम") and "पूरा नतीजा" in api.last["text"]


def test_a_picture_of_a_qr_code_is_decoded_and_checked(bot):
    segno = pytest.importorskip("segno")
    b, api = bot
    buf = io.BytesIO()
    segno.make("upi://pay?pa=alpha.gain88@ybl&pn=Ramesh%20K&am=25000").save(buf, kind="png", scale=8, border=4)
    api.files["p1"] = buf.getvalue()
    b.handle_update(msg(None, photo=[{"file_id": "small"}, {"file_id": "p1"}], caption="Guaranteed 30% a month, VIP group"))
    assert api.last["text"].startswith("HIGH RISK")


def test_a_pdf_document_is_checked(bot):
    from tests.traction.test_traction_telegram import make_pdf  # noqa: F401  (defined below)
    b, api = bot
    api.files["d1"] = make_pdf()
    b.handle_update(msg(None, document={"file_id": "d1", "mime_type": "application/pdf", "file_name": "inv.pdf", "file_size": 2000}))
    assert api.last["text"].startswith("SUSPICIOUS") and "different bank" in api.last["text"]


def make_pdf():
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for i, line in enumerate(["TAX INVOICE", "Bank: ICICI Bank  IFSC: HDFC0001234", "Our bank account has changed. Pay to the new account."]):
        c.drawString(60, 780 - 22 * i, line)
    c.save()
    return buf.getvalue()


def test_voice_notes_use_the_voice_handler_when_it_exists_else_say_so(bot, monkeypatch):
    b, api = bot
    api.files["v1"] = b"audio"
    monkeypatch.setitem(REGISTRY.handlers, "voice", None)
    monkeypatch.delitem(REGISTRY.handlers, "voice")
    b.handle_update(msg(None, voice={"file_id": "v1"}))
    assert "Voice checks are not available" in api.last["text"]
    monkeypatch.setitem(REGISTRY.handlers, "voice", lambda data, topic, case_id: analyse_text(SCAM, kind="voice", case_id=case_id))
    b.handle_update(msg(None, voice={"file_id": "v1"}))
    assert api.last["text"].startswith("HIGH RISK")


def test_big_or_unsupported_files_get_a_clear_answer(bot):
    b, api = bot
    b.handle_update(msg(None, photo=[{"file_id": "huge"}]))
    assert "too large" in api.last["text"]
    b.handle_update(msg(None, document={"file_id": "z", "mime_type": "application/zip", "file_name": "a.zip", "file_size": 10}))
    assert "cannot read that kind" in api.last["text"]
    b.handle_update(msg(None, sticker={"file_id": "s"}))
    assert "I can check text" in api.last["text"]


def test_group_chats_are_ignored(bot):
    b, api = bot
    b.handle_update(msg(SCAM, chat=-100123, chat_type="supergroup"))
    assert api.sent == []


def test_a_flood_from_one_chat_is_slowed(bot):
    b, api = bot
    for _ in range(12):
        b.handle_update(msg("hello"))
    assert sum("sending a lot" in m["text"] for m in api.sent) == 2


def test_wrong_result_asks_for_consent_then_creates_a_review(bot):
    b, api = bot
    b.handle_update(msg("Join the school WhatsApp group for notes."))
    case_id = db.get_case(api.last["text"].split("/case/")[1].split()[0]).case_id
    b.handle_update(press(f"wrong:{case_id}"))
    assert buttons(api.last["markup"]) == [f"wrongy:{case_id}", f"wrongn:{case_id}"]
    b.handle_update(press(f"wrongy:{case_id}"))
    ref = api.last["text"].split("Reference ")[1].split(".")[0]
    r = db.get_review(ref)
    assert r["case_id"] == case_id and r["shared"] == 1 and "/wrong/status?ref=" in api.last["text"]
    b.handle_update(press(f"wrongn:{case_id}"))
    ref2 = api.last["text"].split("Reference ")[1].split(".")[0]
    assert db.get_review(ref2)["shared"] == 0
    assert metrics.summary()["disputes"] == 2


def test_ask_family_gives_a_forwardable_message_with_a_share_link(bot):
    b, api = bot
    b.handle_update(msg(SCAM))
    case = db.get_case(api.last["text"].split("/case/")[1].split()[0])
    b.handle_update(press(f"family:{case.case_id}"))
    assert f"https://site.example/g/{case.share_token}" in api.last["text"] and "HIGH RISK" in api.last["text"]


def test_delete_button_and_command_remove_the_result(bot):
    b, api = bot
    b.handle_update(msg(SCAM))
    cid = api.last["text"].split("/case/")[1].split()[0]
    b.handle_update(press(f"del:{cid}"))
    assert db.get_case(cid) is None and "Deleted" in api.last["text"]
    b.handle_update(msg(SCAM))
    cid2 = api.last["text"].split("/case/")[1].split()[0]
    b.handle_update(msg("/delete"))
    assert db.get_case(cid2) is None and "Deleted" in api.last["text"]
    b.handle_update(msg("/delete"))
    assert "nothing to delete" in api.last["text"]


def test_a_failure_gets_an_apology_not_a_crash_and_no_content_leak(bot, monkeypatch):
    b, api = bot
    from satyapan.bots import telegram_bot
    monkeypatch.setattr(telegram_bot, "analyse_text", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("secret internals")))
    b.handle_update(msg("anything"))
    assert "something went wrong" in api.last["text"] and "secret" not in api.last["text"]


def test_the_bot_never_calls_anything_safe(bot):
    b, api = bot
    b.handle_update(msg("Your Amazon order will be delivered today."))
    low = api.last["text"].lower()
    assert api.last["text"].startswith("NO RED FLAGS FOUND") and "not a guarantee" in low and " is safe" not in low


@pytest.fixture()
def fake_sarvam(monkeypatch):
    import httpx
    from satyapan.integrations import sarvam
    sent = []

    def handler(req: httpx.Request) -> httpx.Response:
        import json
        body = json.loads(req.content)
        sent.append(body)
        return httpx.Response(200, json={"translated_text": f"[{body['target_language_code']}] {body['input']}", "source_language_code": "hi-IN"})

    monkeypatch.setenv("SARVAM_API_KEY", "test-key-not-real")
    monkeypatch.setattr(sarvam, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    sarvam._calls.clear()
    return sent


def test_explain_button_appears_only_when_translation_is_set_up(bot, monkeypatch):
    b, api = bot
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    b.handle_update(msg(SCAM))
    assert not any(x.startswith("explain:") for x in buttons(api.last["markup"]))


def test_explain_in_my_language_translates_the_message_and_our_verdict(bot, fake_sarvam):
    b, api = bot
    b.handle_update(msg(SCAM))
    case_id = api.last["text"].split("/case/")[1].split()[0]
    assert f"explain:{case_id}" in buttons(api.last["markup"])
    b.handle_update(press(f"explain:{case_id}"))
    assert "Sarvam" in api.last["text"] and f"xl:ta:{case_id}" in buttons(api.last["markup"])      # consent wording and a language list
    b.handle_update(press(f"xl:ta:{case_id}"))
    reply = api.last["text"]
    assert "[ta-IN]" in reply and "Guaranteed 30%" in reply.replace("[en-IN] ", "") and "suggestion" in reply
    assert b._read[CHAT][0].startswith("Guaranteed")           # held in memory only


def test_explained_text_expires_and_is_never_in_the_database(bot, fake_sarvam):
    b, api = bot
    b.handle_update(msg(SCAM))
    case_id = api.last["text"].split("/case/")[1].split()[0]
    b._read[CHAT] = (b._read[CHAT][0], 0.0)                     # pretend 15 minutes passed
    b.handle_update(press(f"xl:hi:{case_id}"))
    assert any("15" in m["text"] for m in api.sent)             # told it cannot translate what it no longer holds
    assert "Guaranteed 30%" not in str(db.get_case(case_id).__dict__)


def test_real_api_wrapper_never_sends_null_parameters(monkeypatch):
    """Telegram answers 400 to "reply_markup": null; the fake API used elsewhere in this file could not catch that."""
    import json

    import httpx

    from satyapan.bots.telegram_bot import TelegramApi
    posted = []

    def handler(req: httpx.Request) -> httpx.Response:
        posted.append(json.loads(req.content))
        return httpx.Response(200, json={"ok": True, "result": {}})

    api = TelegramApi("123:fake")
    api.http = httpx.Client(transport=httpx.MockTransport(handler))
    api.send_message(5, "hello")                                        # no buttons
    api.send_message(5, "hello", {"inline_keyboard": [[{"text": "x", "callback_data": "y"}]]})
    api.get_updates(None)
    assert "reply_markup" not in posted[0] and "reply_markup" in posted[1] and "offset" not in posted[2]
    assert all(v is not None for p in posted for v in p.values())
