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


def test_check_link_returns_sample_receipt():
    r = client.post("/api/v1/check", data={"kind": "link", "text": "http://example.test/pay"})
    body = r.json()
    assert r.status_code == 200 and body["result_url"] == "/result/qr" and body["mode"] == "demo-sample"
    assert client.get(f"/api/v1/check/{body['id']}").status_code == 200
    assert client.delete(f"/api/v1/check/{body['id']}").status_code == 204
    assert client.get(f"/api/v1/check/{body['id']}").status_code == 404


def test_check_file_kinds_need_a_file():
    assert client.post("/api/v1/check", data={"kind": "pdf"}).status_code == 422
    r = client.post("/api/v1/check", data={"kind": "pdf"}, files={"file": ("a.pdf", b"%PDF-1.4")})
    assert r.json()["result_url"] == "/result/invoice"


def test_check_rejects_unknown_kind_and_empty_text():
    assert client.post("/api/v1/check", data={"kind": "nope"}).status_code == 422
    assert client.post("/api/v1/check", data={"kind": "message", "text": "  "}).status_code == 422


def test_wrong_result_is_queued():
    r = client.post("/api/v1/wrong-result", json={"reason": "It is genuine", "share_for_review": True})
    assert r.status_code == 201 and r.json()["status"] == "waiting_for_review"
