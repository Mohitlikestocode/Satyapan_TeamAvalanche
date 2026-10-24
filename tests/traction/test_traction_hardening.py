import pytest
from fastapi.testclient import TestClient

from satyapan.api.app import app
from satyapan.ops.hardening import Hardening


@pytest.fixture()
def client(monkeypatch):
    Hardening._hits.clear()
    return TestClient(app)


def test_security_headers_are_on_every_response(client):
    for path in ("/", "/static/gov.css", "/api/v1/health", "/healthz"):
        h = client.get(path).headers
        assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
        assert "frame-ancestors 'none'" in h["content-security-policy"] and "object-src 'none'" in h["content-security-policy"]


def test_hsts_only_over_https_when_enabled(client, monkeypatch):
    assert "strict-transport-security" not in client.get("/").headers
    monkeypatch.setenv("PUBLIC_HTTPS", "1")
    assert "strict-transport-security" not in client.get("/").headers                               # still plain http
    assert "max-age" in client.get("/", headers={"X-Forwarded-Proto": "https"}).headers["strict-transport-security"]


def test_rate_limit_is_off_by_default_so_dev_and_tests_are_never_throttled(client):
    assert all(client.post("/api/v1/check", data={"kind": "message", "text": "hi"}).status_code == 200 for _ in range(30))


def test_checks_are_rate_limited_per_visitor_when_enabled(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "1")
    monkeypatch.setenv("RATE_CHECKS_PER_MIN", "3")
    client.get("/")
    codes = [client.post("/api/v1/check", data={"kind": "message", "text": "hi"}).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    r = client.post("/api/v1/check", data={"kind": "message", "text": "hi"})
    assert "retry-after" in r.headers and "wait" in r.json()["detail"]
    other = TestClient(app)                                                                            # another visitor is not affected
    other.get("/")
    assert other.post("/api/v1/check", data={"kind": "message", "text": "hi"}).status_code == 200


def test_rate_limit_message_is_hindi_for_hindi_visitors(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "1")
    monkeypatch.setenv("RATE_REQUESTS_PER_MIN", "2")
    c = TestClient(app, cookies={"sp_lang": "hi", "sp_dev": "dev-hi-1"})
    c.get("/check"); c.get("/check")
    r = c.get("/check")
    assert r.status_code == 429 and "कृपया" in r.text and "text/html" in r.headers["content-type"]


def test_static_files_and_health_are_never_throttled(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "1")
    monkeypatch.setenv("RATE_REQUESTS_PER_MIN", "1")
    client.get("/")
    assert all(client.get("/static/gov.css").status_code == 200 for _ in range(5))
    assert all(client.get("/healthz").status_code == 200 for _ in range(5))


def test_forwarded_address_is_used_only_when_the_proxy_is_trusted(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "1")
    monkeypatch.setenv("RATE_REQUESTS_PER_MIN", "2")
    codes = [TestClient(app).get("/check", headers={"X-Forwarded-For": f"10.0.0.{i}"}).status_code for i in range(4)]
    assert codes == [200, 200, 429, 429]                                                              # header ignored: all one client
    Hardening._hits.clear()
    monkeypatch.setenv("TRUST_PROXY", "1")
    codes = [TestClient(app).get("/check", headers={"X-Forwarded-For": f"10.0.0.{i}"}).status_code for i in range(4)]
    assert codes == [200, 200, 200, 200]                                                              # four different clients


def test_oversized_bodies_are_refused_before_reading(client, monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    big = b"x" * (2 * 1024 * 1024)
    r = client.post("/api/v1/check", data={"kind": "pdf"}, files={"file": ("a.pdf", big)})
    assert r.status_code == 413 and "large" in r.json()["detail"]
    assert client.post("/api/v1/wrong-result", content=b"{" + b"a" * 300_000 + b"}", headers={"content-type": "application/json"}).status_code == 413


def test_healthz_reports_status_and_database(client):
    r = client.get("/healthz").json()
    assert r["status"] == "ok" and r["database"] == "ok" and "traction" in r["plugins"] and r["uptime_s"] >= 0


def test_errors_never_show_a_stack_trace(client, monkeypatch):
    from satyapan.api import routes_check
    monkeypatch.setattr(routes_check.db, "purge", lambda: (_ for _ in ()).throw(RuntimeError("secret internals")))
    r = TestClient(app, raise_server_exceptions=False).post("/api/v1/check", data={"kind": "message", "text": "hi"}, headers={"accept": "application/json"})
    assert r.status_code == 500 and "secret internals" not in r.text and "wrong" in r.json()["detail"]
