import httpx
import pytest
from fastapi.testclient import TestClient

from satyapan.api.app import create_app
from satyapan.integrations import sarvam


@pytest.fixture
def fake(monkeypatch):
    sent = []

    def handler(req: httpx.Request) -> httpx.Response:
        import json
        body = json.loads(req.content)
        sent.append((str(req.url), body))
        if str(req.url).endswith("/translate"):
            return httpx.Response(200, json={"translated_text": f"[{body['target_language_code']}] {body['input']}", "source_language_code": "hi-IN"})
        import base64
        return httpx.Response(200, json={"audios": [base64.b64encode(b"RIFF" + b"\0" * 40).decode()]})

    monkeypatch.setenv("SARVAM_API_KEY", "test-key-not-real")
    monkeypatch.setattr(sarvam, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    sarvam._calls.clear()
    return sent


def client():
    return TestClient(create_app())


def test_check_receipt_returns_the_text_it_read_and_does_not_store_it(fake):
    c = client()
    r = c.post("/api/v1/check", data={"kind": "message", "text": "Pay a processing fee of Rs 500 to claim your lottery prize"}).json()
    assert r["text_read"].startswith("Pay a processing fee")
    from satyapan.store import db
    assert "processing fee" not in str(db.get_case(r["id"]).__dict__)   # the saved case holds the verdict, not the message


def test_translate_needs_consent_and_goes_through_english(fake):
    c = client()
    assert c.post("/api/v1/understand/translate", json={"text": "hello", "lang": "ta"}).status_code == 400
    r = c.post("/api/v1/understand/translate", json={"text": "Bhai paise bhejo", "lang": "ta", "consent": True}).json()
    assert r["lang"] == "ta" and r["translated"].startswith("[ta-IN] [en-IN]") and r["detected"] == "hi-IN"
    targets = [b["target_language_code"] for u, b in fake if u.endswith("/translate")]
    assert targets == ["en-IN", "ta-IN"]


def test_user_text_is_never_cached_but_verdict_sentences_are(fake, tmp_path):
    c = client()
    r = c.post("/api/v1/check", data={"kind": "message", "text": "Pay a processing fee of Rs 500 to claim your lottery prize"}).json()
    n = len(fake)
    c.post("/api/v1/understand/verdict", json={"case_id": r["id"], "lang": "ta"})
    first = len(fake) - n
    c.post("/api/v1/understand/verdict", json={"case_id": r["id"], "lang": "ta"})
    assert len(fake) - n == first and first > 0                       # the second call came from the cache
    c.post("/api/v1/understand/translate", json={"text": "same words", "lang": "hi", "consent": True})
    m = len(fake)
    c.post("/api/v1/understand/translate", json={"text": "same words", "lang": "hi", "consent": True})
    assert len(fake) - m == 2                                          # sent again every time (English hop + target): nothing is kept


def test_speak_needs_consent_and_returns_audio(fake):
    c = client()
    assert c.post("/api/v1/understand/speak", json={"text": "hi", "lang": "ta"}).status_code == 400
    r = c.post("/api/v1/understand/speak", json={"text": "hi", "lang": "ta", "consent": True})
    assert r.status_code == 200 and r.content.startswith(b"RIFF") and r.headers["cache-control"] == "no-store"


def test_hindi_and_english_verdicts_need_no_translation_service(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    c = client()
    r = c.post("/api/v1/check", data={"kind": "message", "text": "Pay a processing fee of Rs 500 to claim your lottery prize"}).json()
    j = c.post("/api/v1/understand/verdict", json={"case_id": r["id"], "lang": "hi"}).json()
    assert j["headline"] and j["machine_translated"] is False
    assert c.post("/api/v1/understand/verdict", json={"case_id": r["id"], "lang": "ta"}).status_code == 503
    assert c.get("/api/v1/understand/languages").json()["available"] is False
