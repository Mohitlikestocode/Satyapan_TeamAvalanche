"""Sarvam text-to-speech with a fake Sarvam server: no network, no key."""
import base64

import httpx
import pytest
from fastapi.testclient import TestClient

from satyapan.api.app import app
from satyapan.integrations import sarvam

WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 30
SCAM = "Guaranteed 30% a month, join our VIP group. Pay upi://pay?pa=alpha.gain88@ybl&pn=Ramesh%20K&am=25000"


@pytest.fixture()
def fake_sarvam(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "test-key-not-real")
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append({"url": str(request.url), "key": request.headers.get("api-subscription-key"), "json": __import__("json").loads(request.content)})
        return httpx.Response(200, json={"request_id": "r1", "audios": [base64.b64encode(WAV).decode()]})

    monkeypatch.setattr(sarvam, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    sarvam._calls.clear()
    return seen


@pytest.fixture()
def client():
    return TestClient(app)


def case(client, text=SCAM):
    return client.post("/api/v1/check", data={"kind": "message", "text": text}).json()["id"]


def test_not_configured_means_the_browser_voice_is_used(client, monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    assert client.get("/api/v1/speak/status").json() == {"available": False}
    assert client.post("/api/v1/speak", json={"case_id": case(client), "lang": "hi"}).status_code == 503


def test_only_our_template_text_is_sent_in_the_right_language(client, fake_sarvam):
    cid = case(client)
    r = client.post("/api/v1/speak", json={"case_id": cid, "lang": "hi"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.content == WAV
    sent = fake_sarvam[0]
    assert sent["url"] == "https://api.sarvam.ai/text-to-speech" and sent["key"] == "test-key-not-real"
    assert sent["json"]["language_code"] == "hi-IN" and sent["json"]["model"] == "bulbul:v3"
    assert "ज़्यादा जोखिम" in sent["json"]["text"]                       # catalogue text, in Hindi
    assert "Ramesh" not in sent["json"]["text"] and len(sent["json"]["text"]) <= 2400


def test_same_verdict_is_cached_and_not_sent_twice(client, fake_sarvam):
    cid = case(client)
    client.post("/api/v1/speak", json={"case_id": cid, "lang": "en"})
    client.post("/api/v1/speak", json={"case_id": cid, "lang": "en"})
    assert len(fake_sarvam) == 1
    client.post("/api/v1/speak", json={"case_id": cid, "lang": "hi"})
    assert len(fake_sarvam) == 2


def test_failures_fall_back_without_an_error_page(client, monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "k")
    monkeypatch.setattr(sarvam, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500, text="boom"))))
    sarvam._calls.clear()
    assert client.post("/api/v1/speak", json={"case_id": case(client), "lang": "en"}).status_code == 503
    monkeypatch.setattr(sarvam, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"audios": [base64.b64encode(b"not wav").decode()]}))))
    assert client.post("/api/v1/speak", json={"case_id": case(client, "another message to check"), "lang": "en"}).status_code == 503


def test_daily_cap_protects_free_credits(client, fake_sarvam, monkeypatch):
    monkeypatch.setenv("SARVAM_DAILY_CAP", "1")
    assert client.post("/api/v1/speak", json={"case_id": case(client), "lang": "en"}).status_code == 200
    assert client.get("/api/v1/speak/status").json() == {"available": False}
    assert client.post("/api/v1/speak", json={"case_id": case(client, "second different text"), "lang": "en"}).status_code == 503


def test_unknown_case_and_bad_language(client, fake_sarvam):
    assert client.post("/api/v1/speak", json={"case_id": "nope", "lang": "en"}).status_code == 404
    assert client.post("/api/v1/speak", json={"case_id": case(client), "lang": "fr"}).status_code == 422


def test_speaking_is_rate_limited_per_browser(client, fake_sarvam):
    client.get("/")
    cid = case(client)
    codes = [client.post("/api/v1/speak", json={"case_id": cid, "lang": "en"}).status_code for _ in range(32)]
    assert codes.count(200) == 30 and codes.count(429) == 2


def test_the_listen_upgrade_script_is_loaded(client):
    assert "traction_speak.js" in client.get("/").text
