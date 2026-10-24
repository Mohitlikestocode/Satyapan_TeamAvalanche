import json
import re

import pytest
from fastapi.testclient import TestClient

from satyapan.api.app import app
from satyapan.extract.qr import decode_qr
from satyapan.ops import metrics


@pytest.fixture()
def client():
    return TestClient(app, follow_redirects=False)


def make(client, name="Sharma Kirana", city="Kanpur"):
    r = client.post("/poster", data={"name": name, "city": city})
    assert r.status_code == 303
    return r.headers["location"].rsplit("/", 1)[1]


def test_poster_form_validates_in_both_languages(client):
    assert client.post("/poster", data={"name": "x", "city": "Kanpur"}).status_code == 422
    r = TestClient(app, cookies={"sp_lang": "hi"}).post("/poster", data={"name": "", "city": ""})
    assert r.status_code == 422 and "कृपया" in r.text


def test_poster_page_has_a_scannable_qr_with_the_shops_code(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_URL", "https://satyapan.example")
    code = make(client)
    assert re.fullmatch(r"sharma-kirana-[0-9a-f]{4}", code)
    html = client.get(f"/poster/{code}").text
    assert "Sharma Kirana" in html and "Kanpur" in html and "Check before you pay" in html and "पैसे भेजने से पहले जाँचें" in html
    assert "satyapan.example" in html and "1930" in html
    with metrics.conn() as c:
        assert c.execute("SELECT name, city FROM ref_codes WHERE code=?", (code,)).fetchone()["name"] == "Sharma Kirana"


def test_the_qr_really_decodes_to_the_referral_link(client, monkeypatch):
    pytest.importorskip("segno")
    from satyapan.api.ext.traction_poster import qr_svg
    import io
    segno = __import__("segno")
    monkeypatch.setenv("PUBLIC_URL", "https://satyapan.example")
    code = make(client)
    link = f"https://satyapan.example/?ref={code}"
    png = io.BytesIO()
    segno.make(link, error="m").save(png, kind="png", scale=8, border=4)
    assert decode_qr(png.getvalue()) == [link]
    assert "<svg" in qr_svg(link)


def test_poster_html_is_escaped_and_unknown_codes_are_404(client):
    code = make(client, name="<script>alert(1)</script> Store")
    assert "<script>alert(1)</script>" not in client.get(f"/poster/{code}").text
    assert client.get("/poster/nope-0000").status_code == 404


def test_referral_visits_and_checks_are_attributed_to_the_shop(client, monkeypatch):
    code = make(client)
    c = TestClient(app)
    c.get("/")
    c.post("/api/v1/metrics/pv", json={"path": "/", "lang": "en", "ref": code})
    c.post("/api/v1/check", data={"kind": "message", "text": "hello there"})
    row = [r for r in metrics.by_ref() if r["code"] == code][0]
    assert row["name"] == "Sharma Kirana" and row["people"] == 1 and row["checks"] == 1


def test_poster_is_rate_limited_per_browser(client):
    client.get("/")
    codes = [client.post("/poster", data={"name": f"Shop {i}", "city": "Kanpur"}).status_code for i in range(12)]
    assert codes.count(303) == 10 and codes.count(422) == 2


def test_pwa_files_are_served_with_the_right_types_and_scope(client):
    sw = client.get("/sw.js")
    assert sw.status_code == 200 and "javascript" in sw.headers["content-type"] and sw.headers["service-worker-allowed"] == "/"
    assert "/api/" in sw.text and "offline" in sw.text
    m = client.get("/manifest.webmanifest")
    data = json.loads(m.text)
    assert data["start_url"].startswith("/") and data["display"] == "standalone" and "manifest+json" in m.headers["content-type"]
    for icon in data["icons"]:
        assert client.get(icon["src"]).status_code == 200


def test_offline_page_shows_the_helpline_in_both_languages():
    assert "1930" in TestClient(app).get("/offline").text
    assert "1930" in TestClient(app, cookies={"sp_lang": "hi"}).get("/offline").text


def test_global_scripts_are_loaded_on_every_page(client):
    html = client.get("/").text
    for js in ("traction_pv.js", "traction_feedback.js", "traction_pwa.js"):
        assert js in html
