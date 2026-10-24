import pytest
from fastapi.testclient import TestClient

from satyapan.api.app import app
from satyapan.ops import metrics

GOOD = {"org": "Sharma Kirana", "org_type": "shop", "city": "Kanpur", "purpose": "check customers' payment screenshots", "weekly_checks": "40",
        "contact": "9876543210", "consent": "on"}


@pytest.fixture()
def client():
    return TestClient(app, follow_redirects=False)


def test_pilot_request_is_validated_stored_and_listed_for_staff(client):
    assert "Bring Satyapan" in client.get("/pilot").text
    r = client.post("/pilot", data=GOOD)
    assert r.status_code == 303 and r.headers["location"] == "/pilot/thanks"
    assert "Thank you" in client.get("/pilot/thanks").text
    assert metrics.summary()["pilots"] == 1
    client.post("/console/login", data={"reviewer": "reviewer.03"})
    page = client.get("/ops").text
    assert "Sharma Kirana" in page and "Kanpur" in page and "9876543210" in page


@pytest.mark.parametrize("bad,field", [({"org": "x"}, "org"), ({"city": ""}, "city"), ({"org_type": "nonsense"}, "org_type"),
                                       ({"weekly_checks": "lots"}, "weekly_checks"), ({"contact": "call me maybe"}, "contact"), ({"consent": ""}, "consent")])
def test_pilot_form_rejects_bad_input_with_a_clear_message(client, bad, field):
    form = {**GOOD, **bad}
    if not bad.get("consent", "x"):
        form.pop("consent")
    r = client.post("/pilot", data=form)
    assert r.status_code == 422 and 'role="alert"' in r.text and metrics.summary()["pilots"] == 0


def test_pilot_errors_are_in_hindi_when_the_visitor_uses_hindi():
    c = TestClient(app, follow_redirects=False, cookies={"sp_lang": "hi"})
    r = c.post("/pilot", data={**GOOD, "org": ""})
    assert "कृपया अपनी दुकान" in r.text


def test_pilot_honeypot_and_rate_limit(client):
    client.get("/")
    assert client.post("/pilot", data={**GOOD, "website": "http://spam"}).status_code == 303
    assert metrics.summary()["pilots"] == 0
    codes = [client.post("/pilot", data={**GOOD, "org": f"Shop {i}"}).status_code for i in range(7)]
    assert codes.count(303) == 5 and 422 in codes


def test_pilot_html_is_escaped(client):
    client.post("/pilot", data={**GOOD, "org": "<script>alert(1)</script> Store"})
    client.post("/console/login", data={"reviewer": "reviewer.03"})
    assert "<script>alert(1)</script>" not in client.get("/ops").text


def test_feedback_is_one_answer_per_case_per_device_and_scrubbed(client):
    client.get("/")
    case = client.post("/api/v1/check", data={"kind": "message", "text": "hello there"}).json()
    body = {"case_id": case["id"], "rating": 5, "comment": "great, call me on 9876543210 or a@b.com"}
    assert client.post("/api/v1/feedback", json=body).json() == {"saved": True}
    assert client.post("/api/v1/feedback", json={**body, "rating": 1}).json() == {"saved": False}     # same device, same case
    s = metrics.summary()
    assert s["feedback_n"] == 1 and s["feedback_good"] == 1
    with metrics.conn() as c:
        comment = c.execute("SELECT comment FROM feedback_answers").fetchone()[0]
    assert "9876543210" not in comment and "a@b.com" not in comment and "[removed]" in comment


def test_feedback_validation(client):
    client.get("/")
    assert client.post("/api/v1/feedback", json={"case_id": "nope", "rating": 5}).status_code == 404
    case = client.post("/api/v1/check", data={"kind": "message", "text": "hello"}).json()
    assert client.post("/api/v1/feedback", json={"case_id": case["id"], "rating": 9}).status_code == 422
    assert TestClient(app).post("/api/v1/feedback", json={"case_id": case["id"], "rating": 4}).status_code == 400     # no device cookie yet
    assert client.post("/api/v1/feedback", json={"case_id": "site:page", "rating": 4, "comment": "nice"}).json() == {"saved": True}


def test_pages_and_summary_api(client):
    for path in ("/feedback", "/pilot", "/impact"):
        assert client.get(path).status_code == 200
    data = client.get("/api/v1/metrics/summary").json()
    assert data["checks"] == 0 and "by_kind" in data
    nav = client.get("/").text
    assert 'href="/pilot"' in nav and "For shops" in nav
