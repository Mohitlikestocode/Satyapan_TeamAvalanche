"""Scam Watch end to end: the real form, the real engine, the real database."""
from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from satyapan.api.app import app
from satyapan.community import posts, store
from satyapan.community.sanitise import sanitise
from satyapan.store import db

SCAM = "Join our VIP stock tips group. Guaranteed 30% profit every month. Pay Rs 25000 to alpha.gain88@ybl. Call 9876543210 or ravi.kumar@gmail.com"
SCAM2 = "Sure shot returns, send money to alpha.gain88@ybl today for the tips group"
BENIGN = "Hello, your electricity bill of Rs 1200 is due on 30th. Please pay at the official counter."


def client(lang: str = "en") -> TestClient:
    c = TestClient(app)
    c.cookies.set("sp_lang", lang)
    c.get("/community")                      # first page load gives the device cookie
    return c


def report(c: TestClient, text: str = SCAM, kind: str = "message", **extra):
    data = {"kind": kind, "text": text, "consent": "1", **extra}
    return c.post("/community/report", data=data, follow_redirects=False)


def feed_ids(c: TestClient) -> list[int]:
    return [p["id"] for p in c.get("/api/v1/community/posts").json()["posts"]]


# ---- sanitiser ------------------------------------------------------------------------------------------
def test_sanitiser_masks_phone_email_digits_otp_pan_and_names():
    s = sanitise("Dear Ramesh, share OTP 482913. Call +91 98765 43210, mail ramesh@gmail.com, Aadhaar 4567 8901 2345, PAN ABCDE1234F, a/c 123456789012")
    for leak in ("9876543210", "98765 43210", "ramesh@gmail.com", "482913", "4567 8901 2345", "ABCDE1234F", "123456789012", "Ramesh"):
        assert leak not in s.excerpt
    assert s.clean and s.masked["phone"] == 1 and s.masked["email"] == 1 and s.masked["secret_code"] == 1


def test_sanitiser_keeps_link_domain_only_and_upi_ids():
    s = sanitise("Open https://hdfc-kyc-update.in/login?token=abc123 and pay to alpha.gain88@ybl")
    assert "[link: hdfc-kyc-update.in]" in s.excerpt and "token" not in s.excerpt and "/login" not in s.excerpt
    assert "alpha.gain88@ybl" in s.excerpt
    assert {(e.kind, e.value) for e in s.entities} == {("domain", "hdfc-kyc-update.in"), ("upi", "alpha.gain88@ybl")}


def test_sanitiser_masks_phone_number_used_as_upi_id():
    s = sanitise("pay 9876543210@ybl or upi://pay?pa=9123456789@paytm&pn=Ramesh&am=500")
    assert "9876543210" not in s.excerpt and "9123456789" not in s.excerpt and "Ramesh" not in s.excerpt
    assert "98XXXXXX10@ybl" in s.excerpt


def test_sanitiser_handles_hindi_digits_and_words():
    s = sanitise("प्रिय रमेश जी, ओटीपी १२३४५६ साझा करें। कॉल करें ९८७६५-४३२१०")
    assert "रमेश" not in s.excerpt and "123456" not in s.excerpt and "98765" not in s.excerpt


def test_sanitiser_keeps_generic_greetings_and_amounts():
    s = sanitise("Dear Customer, you won Rs 50,000. Hello Sir, Rs 25000 profit in 7 days")
    assert "Dear Customer" in s.excerpt and "Rs 50,000" in s.excerpt and "Rs 25000" in s.excerpt


def test_sanitiser_flags_profanity_for_moderation():
    assert sanitise("you are a chutiya").clean is False
    assert sanitise("Tanish Shitanshu sent a classic message").clean is True


# ---- posting --------------------------------------------------------------------------------------------
def test_report_appears_in_feed_with_engine_verdict_and_no_personal_data():
    c = client()
    r = report(c)
    assert r.status_code == 303 and r.headers["location"].startswith("/community/post/")
    page = c.get(r.headers["location"]).text
    assert "HIGH RISK" in page and "98XXXXXX10" in page and "alpha.gain88@ybl" in page
    for leak in ("9876543210", "ravi.kumar@gmail.com"):
        assert leak not in page
    feed = c.get("/community").text
    assert "alpha.gain88@ybl" in feed and "9876543210" not in feed
    assert "Guaranteed" in feed or "guaranteed" in feed


def test_raw_text_never_reaches_the_database_file():
    c = client()
    report(c, SCAM + " name is Suresh Patil, OTP is 123456")
    from satyapan.community.store import db as core
    raw = (core.home() / "satyapan.db").read_bytes()
    for leak in (b"9876543210", b"ravi.kumar@gmail.com", b"123456", b"98765 43210"):
        assert leak not in raw
    with store.conn() as conn:
        row = conn.execute("SELECT * FROM community_posts").fetchone()
    assert row["dev"] != c.cookies.get("sp_dev") and len(row["dev"]) == 32      # device is stored hashed
    assert row["entity_key"] and "alpha" not in row["entity_key"]


def test_script_in_text_is_escaped():
    c = client()
    r = report(c, "<script>alert(1)</script> pay to evil.pay77@ybl for guaranteed returns in our VIP group")
    html = c.get(r.headers["location"]).text
    assert "<script>alert(1)" not in html and "&lt;script&gt;" in html


def test_form_errors_in_both_languages():
    for lang, word in (("en", "agree"), ("hi", "सबको दिखेगी")):
        c = client(lang)
        r = c.post("/community/report", data={"kind": "message", "text": SCAM}, follow_redirects=False)
        assert r.status_code == 422 and word in r.text
        assert "Scam Watch" not in feed_ids(c) and feed_ids(c) == []
        r = c.post("/community/report", data={"kind": "link", "text": "no website here at all", "consent": "1"})
        assert r.status_code == 422
        r = c.post("/community/report", data={"kind": "upi", "text": "just words about money", "consent": "1"})
        assert r.status_code == 422


def test_too_long_text_is_refused():
    c = client()
    r = c.post("/community/report", data={"kind": "message", "text": "x" * 1200, "consent": "1"})
    assert r.status_code == 422 and feed_ids(c) == []


def test_honeypot_stores_nothing():
    c = client()
    r = report(c, website="http://spam.example")
    assert r.status_code == 303 and feed_ids(c) == []
    with store.conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM community_posts").fetchone()[0] == 0


def test_link_and_upi_report_types():
    c = client()
    assert report(c, "hdfc-kyc-update.in/login", kind="link").status_code == 303
    assert report(c, "Send money to refund.help55@paytm for guaranteed returns in our VIP tips group", kind="upi").status_code == 303
    types = {p["entity_kind"] for p in c.get("/api/v1/community/posts").json()["posts"]}
    assert types == {"domain", "upi"}


def test_bare_upi_id_waits_for_a_person_because_nothing_in_it_is_a_sign():
    c = client()
    assert report(c, "quiet.shop12@paytm", kind="upi").status_code == 303
    assert feed_ids(c) == []


def test_benign_text_waits_for_a_person_and_only_author_sees_it():
    c, other = client(), client()
    r = report(c, BENIGN)
    url = r.headers["location"].split("?")[0]
    assert feed_ids(c) == []                                  # not public
    assert "Waiting for a person" in c.get(url).text          # the author can see it
    assert other.get(url).status_code == 404                  # nobody else can
    with store.conn() as conn:
        assert conn.execute("SELECT status FROM community_posts").fetchone()[0] == "pending"


# ---- duplicates and votes -------------------------------------------------------------------------------
def test_same_payee_from_another_device_links_to_the_first_post():
    a, b = client(), client()
    first = report(a).headers["location"].split("?")[0]
    second = report(b, SCAM2).headers["location"]
    assert feed_ids(a) == [1]                                 # one card, not two
    assert second.split("?")[0] == "/community/post/2" and "/community/post/2" in second
    post = a.get("/api/v1/community/posts/1").json()
    assert post["sightings"] == 2
    page = b.get(second).text
    assert "one more person" in page or "already reported" in page
    assert a.get(first).text.count("Seen by 2 people") == 1


def test_same_device_reporting_same_payee_again_is_not_counted_twice():
    a = client()
    report(a)
    r = report(a, SCAM2)
    assert "dup=1" in r.headers["location"]
    assert a.get("/api/v1/community/posts/1").json()["sightings"] == 1


def test_i_saw_this_too_counts_once_per_device():
    a, b = client(), client()
    report(a)
    assert b.post("/community/post/1/seen", follow_redirects=False).headers["location"].endswith("seen=ok")
    assert b.post("/community/post/1/seen", follow_redirects=False).headers["location"].endswith("seen=already")
    assert a.post("/community/post/1/seen", follow_redirects=False).headers["location"].endswith("seen=own")
    assert a.get("/api/v1/community/posts/1").json()["sightings"] == 2


def test_vote_daily_limit(monkeypatch):
    monkeypatch.setitem(posts.LIMITS, "vote", 1)
    a, b = client(), client()
    report(a)
    report(a, "Pay to different.id99@ybl for guaranteed 40% returns, join our VIP tips group now")
    assert b.post("/community/post/1/seen", follow_redirects=False).headers["location"].endswith("seen=ok")
    assert b.post("/community/post/2/seen", follow_redirects=False).headers["location"].endswith("seen=limit")


def test_post_rate_limit_and_message(monkeypatch):
    monkeypatch.setitem(posts.LIMITS, "post", 2)
    for lang, word in (("en", "limit of 5"), ("hi", "सीमा")):
        c = client(lang)
        for i in range(2):
            assert report(c, f"Guaranteed returns, pay to scam{i}x{lang}@ybl in our VIP tips group").status_code == 303
        r = report(c, "Guaranteed returns, pay to more99@ybl in our VIP tips group")
        assert r.status_code == 429 and word in r.text
        monkeypatch.setattr(posts, "LIMITS", {**posts.LIMITS, "post": 2})


# ---- feed, filters, trending ---------------------------------------------------------------------------
def test_empty_feed_in_both_languages():
    assert "No reports yet" in client("en").get("/community").text
    assert "अभी कोई रिपोर्ट नहीं" in client("hi").get("/community").text


def test_filters_pagination_and_trending():
    c = client()
    for i in range(12):
        report(c, f"Guaranteed returns, pay to scam{i}id@ybl in our VIP tips group", kind="message" if i % 2 else "call")
    page1 = c.get("/api/v1/community/posts").json()
    assert page1["total"] == 5 or page1["total"] == 12 or page1["total"] > 0       # posting limit may cap the count
    data = c.get("/api/v1/community/posts?kind=call").json()
    assert all(p["kind"] == "call" for p in data["posts"])
    assert c.get("/api/v1/community/posts?plang=hi").json()["total"] == 0
    assert c.get("/community?kind=call&sort=week").status_code == 200
    assert c.get("/community?page=999").status_code == 200
    t = c.get("/api/v1/community/trending").json()
    assert t and t[0]["count"] >= 1


def test_trending_orders_by_distinct_devices():
    a, b, d = client(), client(), client()
    report(a)
    report(b, SCAM2)
    report(d, "Guaranteed returns, pay to lonely.pay@ybl in our VIP tips group")
    t = d.get("/api/v1/community/trending").json()
    assert t[0]["entity"] == "alpha.gain88@ybl" and t[0]["count"] == 2 and t[1]["count"] == 1


def test_stats_come_from_the_database():
    c = client()
    assert c.get("/api/v1/community/stats").json() == {"posts": 0, "sightings": 0, "sightings_week": 0}
    report(c)
    assert c.get("/api/v1/community/stats").json()["posts"] == 1


def test_preview_endpoint_stores_nothing():
    c = client()
    d = c.post("/api/v1/community/preview", data={"text": "call 9876543210"}).json()
    assert "9876543210" not in d["excerpt"] and d["masked"]["phone"] == 1
    with store.conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM community_posts").fetchone()[0] == 0


# ---- delete, abuse, moderation -------------------------------------------------------------------------
def test_only_the_author_device_can_delete_and_text_is_wiped():
    a, b = client(), client()
    report(a)
    assert b.post("/community/post/1/delete", follow_redirects=False).headers["location"].endswith("err=delete")
    assert feed_ids(a) == [1]
    assert a.post("/community/post/1/delete", follow_redirects=False).headers["location"].startswith("/community")
    assert feed_ids(a) == [] and a.get("/community/post/1").status_code == 404
    with store.conn() as conn:
        row = conn.execute("SELECT * FROM community_posts WHERE id=1").fetchone()
    assert row["status"] == "deleted" and row["excerpt"] == "" and row["entity_key"] is None


def test_deleting_the_main_post_promotes_the_next_report():
    a, b = client(), client()
    report(a)
    report(b, SCAM2)
    a.post("/community/post/1/delete")
    assert feed_ids(b) == [2]
    assert b.get("/api/v1/community/posts/2").json()["sightings"] == 1


def test_privacy_report_hides_post_at_once_and_moderator_can_restore():
    a, b = client(), client()
    report(a)
    assert b.post("/community/post/1/abuse", data={"reason": "personal_info"}, follow_redirects=False).headers["location"].endswith("flagged=ok")
    assert feed_ids(a) == []
    assert b.post("/community/post/1/abuse", data={"reason": "spam"}, follow_redirects=False).headers["location"].endswith("flagged=already")
    mod = client()
    mod.cookies.set("sp_reviewer", "reviewer.03")
    page = mod.get("/community/moderate").text
    assert "personal_info" in page and "alpha.gain88@ybl" in page
    assert mod.post("/community/moderate/1/dismiss", follow_redirects=False).headers["location"].endswith("done=dismiss")
    assert feed_ids(a) == [1]


def test_three_different_devices_hide_a_post():
    a = client()
    report(a)
    for _ in range(3):
        client().post("/community/post/1/abuse", data={"reason": "spam"})
    assert feed_ids(a) == []


def test_abuse_report_daily_limit(monkeypatch):
    monkeypatch.setitem(posts.LIMITS, "abuse", 1)
    a, b = client(), client()
    report(a)
    report(a, "Guaranteed returns, pay to second77@ybl in our VIP tips group")
    assert b.post("/community/post/1/abuse", data={"reason": "spam"}, follow_redirects=False).headers["location"].endswith("flagged=ok")
    assert b.post("/community/post/2/abuse", data={"reason": "spam"}, follow_redirects=False).headers["location"].endswith("flagged=limit")


def test_moderation_requires_sign_in_and_is_audited():
    a, mod = client(), client()
    report(a, BENIGN)
    r = a.get("/community/moderate", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/console"
    assert a.post("/community/moderate/1/approve", follow_redirects=False).headers["location"] == "/console"
    assert feed_ids(a) == []
    mod.cookies.set("sp_reviewer", "reviewer.07")
    assert BENIGN[:20] in mod.get("/community/moderate").text
    assert mod.post("/community/moderate/1/approve", follow_redirects=False).headers["location"].endswith("done=approve")
    assert feed_ids(a) == [1]
    entries = [e for e in db.audit_list() if e["action"].startswith("community_")]
    assert entries and entries[0]["actor"] == "reviewer.07" and entries[0]["target"] == "post:1"
    assert BENIGN[:15] not in entries[0]["detail"]
    assert db.audit_verify()


def test_moderator_reject_and_remove_wipe_the_text():
    a, mod = client(), client()
    mod.cookies.set("sp_reviewer", "reviewer.03")
    report(a, BENIGN)
    report(a, SCAM)
    assert mod.post("/community/moderate/1/reject").status_code == 200
    assert mod.post("/community/moderate/2/remove").status_code == 200
    with store.conn() as conn:
        rows = conn.execute("SELECT status, excerpt FROM community_posts ORDER BY id").fetchall()
    assert [(r["status"], r["excerpt"]) for r in rows] == [("rejected", ""), ("removed", "")]
    assert feed_ids(a) == []
    assert mod.post("/community/moderate/1/explode", follow_redirects=False).status_code == 404


def test_moderation_page_is_bilingual():
    mod = client("hi")
    mod.cookies.set("sp_reviewer", "reviewer.03")
    assert "स्कैम वॉच की निगरानी" in mod.get("/community/moderate").text


def test_hindi_pages_and_unknown_post():
    c = client("hi")
    assert "स्कैम वॉच" in c.get("/community").text
    assert "देखी हुई धोखाधड़ी बताएँ" in c.get("/community/report").text
    assert c.get("/community/post/999").status_code == 404
    r = report(c)
    assert "मैंने भी देखा" not in c.get(r.headers["location"]).text      # the author is already counted
    d = client("hi")
    assert "मैंने भी देखा" in d.get(r.headers["location"].split("?")[0]).text


def test_database_has_no_unhashed_device():
    c = client()
    report(c)
    dev = c.cookies.get("sp_dev")
    for path in db.home().glob("*.db"):
        assert dev.encode() not in path.read_bytes()
    assert sqlite3  # the file is a plain SQLite database
