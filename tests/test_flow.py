"""The response flow, end to end: check, dispute, human review, registry, evidence, sharing, deletion."""

import pytest
from fastapi.testclient import TestClient

from satyapan.api.app import app
from satyapan.store import db

SCAM = "Guaranteed 30% a month, join our VIP group. Pay upi://pay?pa=alpha.gain88@ybl&pn=Ramesh%20K&am=25000"


@pytest.fixture()
def client():
    return TestClient(app, follow_redirects=False)


def check(client, text=SCAM, kind="message"):
    return client.post("/api/v1/check", data={"kind": kind, "text": text}).json()


def sign_in(client, who):
    r = client.post("/console/login", data={"reviewer": who})
    assert r.status_code == 303


def test_dispute_reaches_the_queue_and_a_reviewer_can_clear_it(client):
    r = check(client, "Join the school WhatsApp group. Telegram channel for notes.")
    ref = client.post("/api/v1/wrong-result", json={"case_id": r["id"], "reason": "It is genuine", "note": "my school group", "share_for_review": True}).json()["id"]
    assert client.get(f"/wrong/status?ref={ref}").status_code == 200
    sign_in(client, "reviewer.03")
    q = client.get("/console/queue").text
    assert ref in q
    assert client.post(f"/api/v1/console/reviews/{ref}/decision", json={"decision": "not_scam", "note": "genuine group"}).json()["status"] == "not_scam"
    page = client.get(r["result_url"]).text
    assert "found it genuine" in page
    assert "A reviewer cleared it" in client.get(f"/wrong/status?ref={ref}").text


def test_registry_needs_two_different_reviewers_and_then_flags_a_resend(client):
    first = check(client)
    assert first["tier"] == "HIGH_RISK"
    ref = client.post("/api/v1/wrong-result", json={"case_id": first["id"], "reason": "report", "share_for_review": True}).json()["id"]
    sign_in(client, "reviewer.03")
    d = client.post(f"/api/v1/console/reviews/{ref}/decision", json={"decision": "confirm_scam"}).json()
    assert d["status"] == "awaiting_second" and not d["registry_updated"]
    again = client.post(f"/api/v1/console/reviews/{ref}/decision", json={"decision": "confirm_scam"})
    assert again.status_code == 409                         # same reviewer cannot be the second
    assert check(client)["tier"] == "HIGH_RISK"             # nothing in the registry yet
    sign_in(client, "reviewer.07")
    d = client.post(f"/api/v1/console/reviews/{ref}/decision", json={"decision": "confirm_scam"}).json()
    assert d["registry_updated"]
    resend = check(client, "Different words entirely, same account: pay alpha.gain88@ybl now")
    assert resend["tier"] == "REGISTRY_HIT"
    page = client.get(resend["result_url"]).text
    assert "previously confirmed" in page


def test_console_needs_sign_in(client):
    assert client.get("/console/queue").status_code == 303
    assert client.post("/api/v1/console/reviews/R-000000/decision", json={"decision": "unsure"}).status_code == 401


def test_evidence_pack_verifies_and_detects_tampering(client):
    r = check(client)
    signed = client.get(f"/api/v1/evidence/{r['id']}").json()
    assert client.post("/api/v1/evidence/verify", json=signed).json() == {"valid": True}
    signed["pack"]["tier"] = "NO_RED_FLAGS"
    assert client.post("/api/v1/evidence/verify", json=signed).json() == {"valid": False}


def test_report_complaint_and_guardian_pages_use_the_saved_check(client):
    r = check(client)
    rep = client.get(f"/report?case={r['id']}").text
    assert "alpha.gain88@ybl" in rep and "Fingerprint (SHA-256)" in rep
    comp = client.get(f"/report/complaint?case={r['id']}").text
    assert "You submit this yourself" in comp and "alpha.gain88@ybl" in comp
    gd = client.get(f"/guardian?case={r['id']}").text
    token = client.get(f"/api/v1/case/{r['id']}").json()["share_token"]
    assert token in gd
    view = client.get(f"/g/{token}").text
    assert "HIGH RISK" in view and "alpha.gain88" in view          # the family member sees the scammer's UPI ID, which helps them
    assert "Fingerprint" not in view                               # but not the report
    assert client.get("/g/nope").status_code == 404


def test_report_without_a_case_falls_back_to_the_sample(client):
    assert client.get("/report").status_code == 200
    assert client.get("/guardian").status_code == 200


def test_delete_removes_the_result_and_the_guardian_link(client):
    r = check(client)
    token = client.get(f"/api/v1/case/{r['id']}").json()["share_token"]
    assert client.delete(f"/api/v1/check/{r['id']}").status_code == 204
    assert client.get(r["result_url"]).status_code == 404
    assert client.get(f"/g/{token}").status_code == 404


def test_old_results_are_purged():
    from satyapan.service import analyse_text
    res = analyse_text(SCAM, case_id="oldcase00001")
    db.save_case(res)
    with db.conn() as c:
        c.execute("UPDATE cases SET created = created - 90000")
    assert db.purge() == 1 and db.get_case("oldcase00001") is None


def test_audit_chain_detects_edits(client):
    check(client)
    ref = client.post("/api/v1/wrong-result", json={"reason": "x"}).json()["id"]
    sign_in(client, "reviewer.03")
    client.post(f"/api/v1/console/reviews/{ref}/decision", json={"decision": "unsure"})
    assert db.audit_verify()
    assert "CHAIN INTACT" in client.get("/console/audit").text
    with db.conn() as c:
        c.execute("UPDATE audit SET detail = 'edited' WHERE id = 1")
    assert not db.audit_verify()
    assert "CHAIN BROKEN" in client.get("/console/audit").text


def test_no_raw_message_text_is_stored(client):
    secret = "my-secret-phrase-12345"
    check(client, SCAM + " " + secret)
    with db.conn() as c:
        dump = " ".join(str(tuple(r)) for t in ("cases", "reviews", "audit", "registry") for r in c.execute(f"SELECT * FROM {t}"))
    assert secret not in dump
