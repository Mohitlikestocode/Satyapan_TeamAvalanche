from fastapi.testclient import TestClient

from satyapan.api.app import create_app
from satyapan.plugins import REGISTRY


def _client() -> TestClient:
    return TestClient(create_app())


def test_hindi_shell_has_no_english_chrome():
    c = _client()
    c.cookies.set("sp_lang", "hi")
    html = c.get("/check").text
    for english in ("Advisory</span>", "Skip to main content", ">Services<", "Lost money to fraud?"):
        assert english not in html
    assert "सलाह" in html and "सेवाएँ" in html


def test_english_shell_unchanged():
    html = _client().get("/check").text
    assert "Advisory" in html and "Services" in html


def test_guardian_beacon_emits_only_for_a_real_case():
    seen = []
    REGISTRY.on("guardian", seen.append)
    c = _client()
    assert c.post("/api/guardian/shared?case=nope").json() == {"ok": True}
    assert seen == []
    r = c.post("/api/v1/check", data={"kind": "message", "text": "Pay a processing fee of Rs 500 to claim your lottery prize"})
    case_id = r.json()["id"]
    c.post(f"/api/guardian/shared?case={case_id}")
    assert seen and seen[-1]["case_id"] == case_id
