"""Honest metrics: real checks are counted, team traffic is not, nothing identifying is stored."""
import pytest
from fastapi.testclient import TestClient

from satyapan.api.app import app
from satyapan.ops import metrics
from satyapan.store import db

SCAM = "Guaranteed 30% a month, join our VIP group. Pay upi://pay?pa=alpha.gain88@ybl&pn=Ramesh%20K&am=25000"


@pytest.fixture()
def client():
    return TestClient(app)


def check(c, text="hello there, lunch tomorrow?", **extra):
    return c.post("/api/v1/check", data={"kind": "message", "text": text, **extra}).json()


def test_a_real_check_is_counted_and_shows_on_the_impact_page(client):
    assert metrics.summary()["checks"] == 0
    assert "Nothing counted yet" in client.get("/impact").text           # honest empty state
    client.get("/")                                                        # first visit sets the device cookie
    check(client, SCAM)
    check(client, "hello", channel="telegram")
    s = metrics.summary()
    assert s["checks"] == 2 and s["people"] == 1 and s["by_channel"] == {"web": 1, "telegram": 1}
    assert s["by_tier"] == {"HIGH_RISK": 1, "NO_RED_FLAGS": 1} and s["since"] is not None
    page = client.get("/impact").text
    assert "Counting since" in page and "Team and test traffic is not included" in page


def test_team_traffic_is_stored_but_never_counted(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_KEY", "k" * 24)
    assert client.get("/internal?key=wrong").status_code == 404
    assert client.get("/internal?key=" + "k" * 24).status_code == 200
    assert client.cookies.get("sp_internal") == "1"
    check(client, SCAM)
    client.post("/api/v1/metrics/pv", json={"path": "/check", "lang": "en"})
    s = metrics.summary()
    assert s["checks"] == 0 and s["people"] == 0 and s["visitors"] == 0
    with metrics.conn() as c:
        assert c.execute("SELECT COUNT(*) FROM metrics_events WHERE internal=1").fetchone()[0] >= 1      # kept, just not public
    assert client.get("/internal?off=1").status_code == 200
    check(client, SCAM)
    assert metrics.summary()["checks"] == 1


def test_internal_switch_is_disabled_when_no_key_is_configured(client, monkeypatch):
    monkeypatch.delenv("INTERNAL_KEY", raising=False)
    assert client.get("/internal?key=").status_code == 404


def test_raw_device_ids_and_message_text_are_not_stored(client):
    client.get("/")
    raw = client.cookies.get("sp_dev")
    assert raw
    check(client, "my-secret-phrase-98765")
    client.post("/api/v1/metrics/pv", json={"path": "/case/abcdef123456", "lang": "hi"})
    with db.conn() as c:
        dump = " ".join(str(tuple(r)) for t in ("metrics_events", "metrics_pageviews", "metrics_devices") for r in c.execute(f"SELECT * FROM {t}"))
    assert raw not in dump and "my-secret-phrase" not in dump and "abcdef123456" not in dump
    assert "/case/*" in dump                                                # ids in paths are masked


def test_page_view_beacon_rules(client):
    client.get("/")
    assert client.post("/api/v1/metrics/pv", json={"path": "/check", "lang": "hi"}).status_code == 204
    assert client.post("/api/v1/metrics/pv", json={"path": "/console/queue"}).status_code == 204          # staff pages are not counted
    assert client.post("/api/v1/metrics/pv", json={"path": "/check"}, headers={"DNT": "1"}).status_code == 204
    assert metrics.summary()["pageviews"] == 1 and metrics.summary()["visitors"] == 1


def test_people_who_come_back_on_another_day_are_counted(client):
    client.get("/")
    check(client, "one")
    check(client, "two")
    assert metrics.summary()["came_back"] == 0                            # same day
    with metrics.conn() as c:
        c.execute("UPDATE metrics_events SET ts = ts - 86400 WHERE id = 1")
    assert metrics.summary()["came_back"] == 1


def test_disputes_and_review_outcomes_are_reported(client):
    r = check(client, "Join the school WhatsApp group for notes.")
    ref = client.post("/api/v1/wrong-result", json={"case_id": r["id"], "reason": "genuine", "share_for_review": True}).json()["id"]
    assert metrics.summary()["disputes"] == 1 and metrics.summary()["pending"] == 1
    client.post("/console/login", data={"reviewer": "reviewer.03"})
    client.post(f"/api/v1/console/reviews/{ref}/decision", json={"decision": "not_scam"})
    s = metrics.summary()
    assert s["cleared"] == 1 and s["pending"] == 0 and s["median_decision_s"] is not None
    assert "Cleared by a person" in client.get("/impact").text


def test_ops_page_is_staff_only_and_csv_works(client):
    assert client.get("/ops", follow_redirects=False).status_code == 303
    assert client.get("/ops/daily.csv", follow_redirects=False).status_code == 303
    client.post("/console/login", data={"reviewer": "reviewer.07"})
    client.get("/")
    check(client)
    assert client.get("/ops").status_code == 200
    csv_text = client.get("/ops/daily.csv").text
    assert csv_text.startswith("day_ist,checks,people") and ",1,1" in csv_text


def test_referral_codes_are_attributed_on_first_touch(client):
    with metrics.conn() as c:
        c.execute("INSERT INTO ref_codes(code,name,city,created) VALUES('shop-1','Sharma Kirana','Kanpur',1)")
    client.get("/")
    client.post("/api/v1/metrics/pv", json={"path": "/", "lang": "en", "ref": "shop-1"})
    check(client)
    row = [r for r in metrics.by_ref() if r["code"] == "shop-1"][0]
    assert row["name"] == "Sharma Kirana" and row["people"] == 1 and row["checks"] == 1


def test_impact_page_is_bilingual(client):
    assert "लाइव असर" in TestClient(app, cookies={"sp_lang": "hi"}).get("/impact").text
    assert "Live impact" in client.get("/impact").text
