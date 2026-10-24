import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from satyapan.api.app import app

client = TestClient(app)
import json

WEB = Path(__file__).resolve().parents[1] / "web"
ROUTES = ["/" + m["route"] for m in json.loads((WEB / "pages.json").read_text(encoding="utf-8"))]


def test_health():
    assert client.get("/api/v1/health").json() == {"status": "ok"}


@pytest.mark.parametrize("route", ROUTES)
def test_page_serves(route):
    r = client.get(route)
    assert r.status_code == 200
    assert "Skip to main content" in r.text or route.startswith("/console")
    assert "sc-raw" not in r.text and "sc-camel" not in r.text  # design-tool leftovers


def test_internal_links_resolve():
    targets = set()
    for route in ROUTES:
        html = client.get(route).text
        targets |= set(re.findall(r'(?:href|src)="(/[^"/][^"]*)"', html))
    for t in targets:
        assert client.get(t).status_code == 200, t


def test_link_check_runs_the_engine_and_renders_a_result_page():
    r = client.post("/api/v1/check", data={"kind": "link", "text": "http://hdfc-bank-kyc.example/pay"})
    body = r.json()
    assert r.status_code == 200 and body["mode"] == "engine" and body["tier"] == "SUSPICIOUS"
    page = client.get(body["result_url"])
    assert page.status_code == 200 and "SUSPICIOUS" in page.text and "imitates an official website" in page.text
    assert client.get(f"/api/v1/case/{body['id']}").json()["reason_codes"] == ["LINK_LOOKALIKE_DOMAIN"]
    assert client.delete(f"/api/v1/check/{body['id']}").status_code == 204
    assert client.get(body["result_url"]).status_code == 404


def test_result_page_escapes_untrusted_text():
    r = client.post("/api/v1/check", data={"kind": "message", "text": "upi://pay?pa=a.b@ybl&pn=<script>alert(1)</script> guaranteed returns"})
    page = client.get(r.json()["result_url"]).text
    assert "<script>alert(1)</script>" not in page


def test_unknown_case_page_is_a_friendly_404():
    r = client.get("/case/doesnotexist")
    assert r.status_code == 404 and "no longer here" in r.text


def test_qr_upload_is_decoded_and_checked():
    segno = pytest.importorskip("segno")
    import io
    buf = io.BytesIO()
    segno.make("upi://pay?pa=alpha.gain88@ybl&pn=Ramesh%20K&am=25000").save(buf, kind="png", scale=8, border=4)
    r = client.post("/api/v1/check", data={"kind": "qr", "text": "Guaranteed 30% a month, VIP group"}, files={"file": ("q.png", buf.getvalue())})
    assert r.json()["tier"] == "HIGH_RISK"
    bad = client.post("/api/v1/check", data={"kind": "qr"}, files={"file": ("q.png", b"not an image")})
    assert bad.json()["tier"] == "CANT_TELL"


def test_screenshot_still_points_to_a_labelled_sample():
    r = client.post("/api/v1/check", data={"kind": "screenshot"}, files={"file": ("a.png", b"x")})
    assert r.json()["mode"] == "demo-sample" and r.json()["result_url"] == "/result/screenshot"


def test_check_file_kinds_need_a_file():
    assert client.post("/api/v1/check", data={"kind": "pdf"}).status_code == 422
    r = client.post("/api/v1/check", data={"kind": "pdf"}, files={"file": ("a.pdf", b"%PDF-1.4")})
    assert r.json()["result_url"] == "/result/invoice" and r.json()["mode"] == "demo-sample"


def test_check_rejects_unknown_kind_and_empty_text():
    assert client.post("/api/v1/check", data={"kind": "nope"}).status_code == 422
    assert client.post("/api/v1/check", data={"kind": "message", "text": "  "}).status_code == 422


def test_wrong_result_is_queued():
    r = client.post("/api/v1/wrong-result", json={"reason": "It is genuine", "share_for_review": True})
    assert r.status_code == 201 and r.json()["status"] == "needs_review"
