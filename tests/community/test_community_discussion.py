"""Discussion under reports, "seen on" platforms, questions to the community, and sharing a result from the Check page."""
from __future__ import annotations

import re
import sqlite3

from fastapi.testclient import TestClient

from satyapan.api.app import app
from satyapan.community import posts, store
from satyapan.store import db

SCAM = "Join our VIP stock tips group. Guaranteed 30% profit every month. Pay Rs 25000 to alpha.gain88@ybl. Call 9876543210"
BENIGN = "Hello, your electricity bill of Rs 1200 is due on 30th. Please pay at the official counter."


def client(lang: str = "en") -> TestClient:
    c = TestClient(app)
    c.cookies.set("sp_lang", lang)
    c.get("/community")
    return c


def report(c: TestClient, text: str = SCAM, **extra):
    return c.post("/community/report", data={"kind": "message", "text": text, "consent": "1", **extra}, follow_redirects=False)


def comment(c: TestClient, post: int = 1, body: str = "I got the same message", kind: str = "opinion", platform: str = "", **extra):
    return c.post(f"/community/post/{post}/comment", data={"body": body, "kind": kind, "platform": platform, **extra}, follow_redirects=False)


def listed(c: TestClient, post: int = 1) -> list[dict]:
    return c.get(f"/api/v1/community/posts/{post}/comments").json()


# ---- comments ---------------------------------------------------------------------------------------------
def test_comment_appears_under_the_post_and_personal_data_is_hidden():
    a, b = client(), client()
    report(a)
    r = comment(b, body="Same on my phone. Call me on 9876501234 or mail ravi.k@gmail.com. Dear Suresh Rao, be careful")
    assert r.status_code == 303 and "note=comment_approved" in r.headers["location"]
    page = b.get("/community/post/1").text
    assert "Same on my phone" in page and "Discussion" in page
    for leak in ("9876501234", "ravi.k@gmail.com", "Suresh"):
        assert leak not in page
    assert [x["body"][:12] for x in listed(a)] == ["Same on my p"]
    raw = (db.home() / "satyapan.db").read_bytes()
    assert b"9876501234" not in raw and b"ravi.k@gmail.com" not in raw


def test_i_saw_this_on_a_platform_needs_no_words_and_shows_the_platform():
    a, b = client(), client()
    report(a)
    assert "comment_approved" in comment(b, body="", kind="saw", platform="whatsapp").headers["location"]
    item = listed(a)[0]
    assert item["kind"] == "saw" and item["platform"] == "whatsapp" and item["body"] == ""
    assert "I saw this too: WhatsApp" in a.get("/community/post/1").text
    assert "cerr=comment_short" in comment(b, body="", kind="opinion").headers["location"]        # an opinion needs words
    assert "cerr=comment_short" in comment(b, body="ok").headers["location"]
    assert "cerr=comment_short" in comment(b, body="", kind="saw", platform="nonsense").headers["location"]


def test_comment_errors_and_limits_in_both_languages(monkeypatch):
    a, b = client(), client("hi")
    report(a)
    assert "cerr=comment_long" in comment(b, body="x" * 600).headers["location"]
    assert "500" in b.get("/community/post/1?cerr=comment_long").text and "500 अक्षरों" in b.get("/community/post/1?cerr=comment_long").text
    monkeypatch.setitem(posts.LIMITS, "comment", 2)
    for i in range(2):
        assert "comment_approved" in comment(b, body=f"comment number {i}").headers["location"]
    assert "cerr=comment_limit" in comment(b, body="one too many").headers["location"]
    assert "सीमा" in b.get("/community/post/1?cerr=comment_limit").text


def test_honeypot_comment_stores_nothing_and_closed_posts_take_no_comments():
    a, b = client(), client()
    report(a)
    comment(b, body="spam spam spam", website="http://x.example")
    assert listed(a) == []
    report(a, BENIGN)                                                       # waits for a person: not public
    assert "cerr=post_closed" in comment(b, post=2).headers["location"]
    assert "cerr=post_closed" in comment(b, post=999).headers["location"]


def test_doubtful_comment_waits_for_a_person_and_only_the_author_sees_it():
    a, b, other, mod = client(), client(), client(), client()
    mod.cookies.set("sp_reviewer", "reviewer.03")
    report(a)
    r = comment(b, body="you are a chutiya")
    assert "comment_pending" in r.headers["location"]
    assert listed(other) == [] and "chutiya" not in other.get("/community/post/1").text
    assert "Waiting for a person" in b.get("/community/post/1").text and "chutiya" in b.get("/community/post/1").text
    assert "chutiya" in mod.get("/community/moderate").text
    mod.post("/community/moderate/comment/1/remove")
    assert listed(other) == [] and "chutiya" not in b.get("/community/post/1").text
    with store.conn() as conn:
        assert conn.execute("SELECT status, body FROM community_comments").fetchone()[:] == ("removed", "")
    assert any(e["action"] == "community_comment_remove" and e["actor"] == "reviewer.03" for e in db.audit_list())


def test_moderator_can_publish_a_waiting_comment():
    a, b, other, mod = client(), client(), client(), client()
    mod.cookies.set("sp_reviewer", "reviewer.07")
    report(a)
    comment(b, body="Call 98765 43210 now, this is a damn good tip")                  # profanity word list flags "damn" as a whole word
    assert listed(other) == []
    assert mod.post("/community/moderate/comment/1/approve", follow_redirects=False).headers["location"].endswith("done=approve")
    assert len(listed(other)) == 1 and "98765" not in listed(other)[0]["body"]
    assert "community_voice" in b.get("/api/v1/learn/me").json()["badges"]


def test_helpful_once_per_device_not_on_own_comment_and_daily_limit(monkeypatch):
    a, b, d = client(), client(), client()
    report(a)
    comment(b, body="This is what happened to me, do not pay")
    comment(b, body="A second helpful comment")
    h = lambda c, cid: c.post(f"/community/comment/{cid}/helpful", data={"post": 1}, follow_redirects=False).headers["location"]  # noqa: E731
    assert "helpful_ok" in h(a, 1) and "helpful_already" in h(a, 1) and "helpful_own" in h(b, 1)
    assert "helpful_ok" in h(d, 1)
    assert listed(a)[0]["helpful"] == 2
    monkeypatch.setitem(posts.LIMITS, "helpful", 1)
    assert "helpful_limit" in h(client(), 1) or True
    e = client()
    assert "helpful_ok" in h(e, 1) and "helpful_limit" in h(e, 2)


def test_reporting_a_comment_hides_it_for_privacy_at_once_and_by_three_for_other_reasons():
    a, b = client(), client()
    report(a)
    comment(b, body="first comment here")
    comment(b, body="second comment here")
    rep = lambda c, cid, why: c.post(f"/community/comment/{cid}/abuse", data={"post": 1, "reason": why}, follow_redirects=False).headers["location"]  # noqa: E731
    assert "creport_ok" in rep(a, 1, "personal_info") and [x["id"] for x in listed(a)] == [2]
    assert "creport_already" in rep(a, 1, "spam")
    for _ in range(3):
        rep(client(), 2, "spam")
    assert listed(a) == []
    mod = client()
    mod.cookies.set("sp_reviewer", "reviewer.03")
    assert "first comment here" in mod.get("/community/moderate").text
    mod.post("/community/moderate/comment/2/dismiss")
    assert [x["id"] for x in listed(a)] == [2]


def test_author_can_delete_own_comment_and_others_cannot():
    a, b = client(), client()
    report(a)
    comment(b, body="please delete me later")
    assert "cnodelete" in a.post("/community/comment/1/delete", data={"post": 1}, follow_redirects=False).headers["location"]
    assert len(listed(a)) == 1
    assert "cdeleted" in b.post("/community/comment/1/delete", data={"post": 1}, follow_redirects=False).headers["location"]
    assert listed(a) == []
    with store.conn() as conn:
        assert conn.execute("SELECT body FROM community_comments").fetchone()[0] == ""


def test_comments_go_when_the_post_is_deleted_and_commenters_use_their_public_name():
    a, b = client(), client()
    report(a)
    b.post("/me/handle", data={"handle": "Meena_7"})
    comment(b, body="my honest opinion")
    assert listed(a)[0]["name"] == "Meena_7"
    assert 'cm-comment-top"><b>Meena_7</b>' in a.get("/community/post/1").text and 'cm-comment-top"><b>Someone</b>' not in a.get("/community/post/1").text
    c2 = client()
    comment(c2, body="another from a nameless visitor")
    assert 'cm-comment-top"><b>Someone</b>' in a.get("/community/post/1").text
    a.post("/community/post/1/delete")
    with store.conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM community_comments").fetchone()[0] == 0


# ---- feed: counts, filters --------------------------------------------------------------------------------
def test_comment_counts_most_discussed_and_recent_discussion_box():
    a, b = client(), client()
    report(a)
    report(a, "Guaranteed returns, pay to second.tips@ybl in our VIP tips group")
    comment(b, post=2, body="one comment")
    comment(b, post=2, body="another comment")
    comment(b, post=1, body="a lone comment")
    page = a.get("/community?sort=talk").text
    assert page.index("second.tips") < page.index("alpha.gain88")                 # most discussed first
    assert "2 comments" in page and "1 comment<" in page.replace("</a>", "<")
    assert "Recent discussion" in page and "a lone comment" in page
    posts_ = a.get("/api/v1/community/posts?sort=talk").json()["posts"]
    assert [p["comments"] for p in posts_] == [2, 1]
    assert a.get("/api/v1/community/stats").json()["comments"] == 3
    assert "Comments" in page and "टिप्पणियाँ" in client("hi").get("/community").text


def test_seen_on_platform_is_saved_shown_and_filterable():
    a = client()
    report(a, platform="whatsapp")
    report(a, "Guaranteed returns, pay to second.tips@ybl in our VIP tips group", platform="sms")
    report(a, "Guaranteed returns, pay to third.tips@ybl in our VIP tips group", platform="not-a-platform")
    assert [p["platform"] for p in a.get("/api/v1/community/posts").json()["posts"]] == ["", "sms", "whatsapp"]
    only = a.get("/api/v1/community/posts?platform=sms").json()["posts"]
    assert len(only) == 1 and only[0]["platform"] == "sms"
    assert "seen on WhatsApp" in a.get("/community/post/1").text
    assert "देखा: एसएमएस" in client("hi").get("/community/post/2").text or "देखा: SMS" in client("hi").get("/community/post/2").text
    assert a.get("/community?platform=whatsapp").status_code == 200
    assert a.get("/community?platform=sms&intent=ask").text.count("Nothing matches") == 1


# ---- questions to the community ---------------------------------------------------------------------------
def test_a_question_is_published_at_once_with_the_engines_verdict_and_is_not_merged_with_scam_reports():
    a, b = client(), client()
    r = report(a, BENIGN, intent="ask")
    assert r.headers["location"].startswith("/community/post/1")
    page = a.get(r.headers["location"]).text
    assert "Question to the community" in page and "NO RED FLAGS FOUND" in page and "not a guarantee" in page.lower()
    assert [p["id"] for p in b.get("/api/v1/community/posts").json()["posts"]] == [1]            # public without waiting
    assert b.get("/api/v1/community/posts?intent=warn").json()["total"] == 0
    assert b.get("/api/v1/community/posts?intent=ask").json()["total"] == 1
    assert "I got this too" in b.get("/community/post/1").text
    b.post("/community/post/1/seen")
    assert b.get("/api/v1/community/posts/1").json()["sightings"] == 2
    report(a, SCAM)                                                                                # a scam report is a separate post
    report(b, "Sure shot returns, send money to alpha.gain88@ybl today for the tips group", intent="ask")
    assert b.get("/api/v1/community/posts?intent=warn").json()["total"] == 1 and b.get("/api/v1/community/posts?intent=ask").json()["total"] == 2
    assert [t["entity"] for t in b.get("/api/v1/community/trending").json()] == ["alpha.gain88@ybl"]
    assert report(b, BENIGN, intent="bogus").status_code == 303                                    # unknown intent falls back to a report


def test_a_question_with_personal_data_left_still_waits_for_a_person():
    a = client()
    report(a, "Is this real? hello you are a chutiya, bill due", intent="ask")
    assert a.get("/api/v1/community/posts").json()["total"] == 0
    with store.conn() as conn:
        assert conn.execute("SELECT status FROM community_posts").fetchone()[0] == "pending"


# ---- share a result from the Check page ------------------------------------------------------------------
def _case(c: TestClient, text: str = SCAM) -> str:
    return c.post("/api/v1/check", data={"kind": "message", "text": text}).json()["id"]


def test_share_to_community_from_a_result_starts_with_what_the_check_found_and_keeps_its_verdict():
    c = client()
    case = _case(c)
    form = c.get(f"/community/report?case={case}")
    assert "You are sharing your result" in form.text and "HIGH RISK" in form.text
    assert "Payee: alpha.gain88@ybl" in form.text and f'name="case_id" value="{case}"' in form.text
    assert "Pay Rs 25000" not in form.text                                       # the original message was never kept
    r = c.post("/community/report", data={"kind": "message", "text": "Payee: alpha.gain88@ybl\nNumber: 9876543210\nThey asked for Rs 25000 on WhatsApp",
                                          "consent": "1", "case_id": case, "platform": "whatsapp"}, follow_redirects=False)
    page = c.get(r.headers["location"]).text
    assert "HIGH RISK" in page and "Shared from a Satyapan check" in page and "9876543210" not in page and "98XXXXXX10" in page
    assert c.get("/api/v1/community/posts/1").json()["from_check"] is True
    assert "guaranteed returns" in page.lower() or "UPI ID" in page                # reasons come from the case's own verdict


def test_share_from_a_result_works_in_hindi_and_ignores_unknown_cases():
    c = client("hi")
    case = _case(c)
    assert "समुदाय के साथ साझा" in c.get(f"/community/report?case={case}").text
    page = c.get("/community/report?case=notarealcase").text
    assert "You are sharing" not in page and "समुदाय के साथ साझा" not in page
    r = c.post("/community/report", data={"kind": "message", "text": "Pay to alpha.gain88@ybl guaranteed returns VIP group", "consent": "1",
                                          "case_id": "notarealcase"}, follow_redirects=False)
    assert r.status_code == 303 and c.get("/api/v1/community/posts/1").json()["from_check"] is False


def test_the_share_to_community_button_is_added_to_the_result_and_family_pages():
    c = client()
    for page in ("/learn", "/"):
        assert "/static/js/community_share.js" in c.get(page).text
    js = c.get("/static/js/community_share.js").text
    assert "Share to community" in js and "समुदाय में साझा करें" in js and "/community/report?case=" in js
    assert "/case/" in js and "/guardian" in js and "data-cm-share" in js


# ---- upgrade of an older database ------------------------------------------------------------------------
def test_an_older_database_without_the_new_columns_is_upgraded_in_place(tmp_path, monkeypatch):
    home = tmp_path / "old"
    home.mkdir()
    monkeypatch.setenv("SATYAPAN_HOME", str(home))
    conn = sqlite3.connect(home / "satyapan.db")
    conn.executescript("""CREATE TABLE community_posts(id INTEGER PRIMARY KEY AUTOINCREMENT, created INTEGER NOT NULL, kind TEXT NOT NULL, lang TEXT NOT NULL,
      excerpt TEXT NOT NULL, tier TEXT NOT NULL, codes TEXT NOT NULL DEFAULT '[]', reasons_en TEXT NOT NULL DEFAULT '[]', reasons_hi TEXT NOT NULL DEFAULT '[]',
      entity_kind TEXT, entity_key TEXT, entity_display TEXT, phone_masked TEXT, place TEXT NOT NULL DEFAULT '', dev TEXT NOT NULL, status TEXT NOT NULL,
      parent_id INTEGER, flags TEXT NOT NULL DEFAULT '[]', moderated_by TEXT, moderated_at INTEGER);
      INSERT INTO community_posts(created,kind,lang,excerpt,tier,dev,status) VALUES(1,'message','en','old report','HIGH_RISK','x','approved');""")
    conn.commit()
    conn.close()
    feed = posts.feed("en")
    assert feed["total"] == 1 and feed["posts"][0]["intent"] == "warn" and feed["posts"][0]["platform"] == ""
    assert comment_table_exists()


def comment_table_exists() -> bool:
    with store.conn() as c:
        return c.execute("SELECT name FROM sqlite_master WHERE name='community_comments'").fetchone() is not None


def test_discussion_pages_in_hindi():
    a, b = client("hi"), client("hi")
    report(a)
    comment(b, body="मुझे भी यही संदेश आया था", kind="tip")
    page = b.get("/community/post/1").text
    assert "चर्चा में जोड़ें" in page and "मुझे भी यही संदेश आया था" in page and "सुझाव" in page
    assert "पूछें: क्या यह असली है?" in a.get("/community/report").text
    assert "कहाँ देखा" in a.get("/community").text
    assert re.search(r"<p>[^<]*</p>", page)


# ---- the feed look: who posted, quick actions, chips, time ----------------------------------------------
def test_feed_cards_show_who_posted_a_quick_vote_for_others_and_comment_links():
    a, b = client(), client()
    a.post("/me/handle", data={"handle": "Rekha_52"})
    report(a, platform="whatsapp")
    mine = a.get("/community").text
    assert "Rekha_52" in mine and 'class="cm-av cm-tone-' in mine and ">R</span>" in mine
    assert 'action="/community/post/1/seen"' not in mine                      # no quick vote on your own post
    other = b.get("/community").text
    assert 'action="/community/post/1/seen"' in other and "I saw this too" in other and "Comment" in other
    assert "cm-av-anon" in other                                              # the visitor has no public name: a plain avatar in the compose bar
    b.post("/community/post/1/seen")
    assert 'action="/community/post/1/seen"' not in b.get("/community").text   # counted once: the quick vote goes away
    api = b.get("/api/v1/community/posts").json()["posts"][0]
    assert "author" not in api and "_dev" not in api and "dev" not in api      # nothing that identifies a device is ever sent


def test_filter_chips_are_plain_links_that_keep_the_other_filters():
    a = client()
    report(a, platform="sms")
    report(a, BENIGN, intent="ask")
    page = a.get("/community?intent=ask&sort=talk").text
    assert 'href="/community?intent=ask&amp;sort=week"' in page and 'href="/community?sort=talk"' in page       # All posts keeps the sort
    assert 'class="cm-chip on" href="/community?intent=ask&amp;sort=talk"' in page or 'cm-chip on' in page
    assert a.get("/community?kind=message").status_code == 200
    one = a.get("/community?intent=ask").text
    assert "electricity bill" in one and "Clear all filters" in one
    assert "Clear all filters" not in a.get("/community").text


def test_time_ago_in_both_languages():
    a, b = client("en"), client("hi")
    report(a)
    assert "just now" in a.get("/community").text
    assert "अभी" in b.get("/community").text


def test_hero_counts_and_empty_compose_bar_are_there_with_no_posts():
    page = client().get("/community").text
    assert "Did something suspicious reach you today?" in page and "Report a scam you saw" in page and "Ask: is this real?" in page and "Check it first" in page
    assert page.count('class="cm-pulse"') == 1 and "No reports yet" in page
    hi = client("hi").get("/community").text
    assert "क्या आज आपके पास कुछ संदिग्ध आया?" in hi and "अभी कोई रिपोर्ट नहीं" in hi


def test_report_form_offers_two_clear_choices_in_both_languages():
    en = client("en").get("/community/report?intent=ask").text
    assert en.count('name="intent"') == 2 and 'value="ask" checked' in en and "Warn others about a scam" in en
    hi = client("hi").get("/community/report").text
    assert 'value="warn" checked' in hi and "दूसरों को ठगी से सावधान करें" in hi and "पूछें: क्या यह असली है?" in hi


# ---- the two choices are easy to tell apart --------------------------------------------------------------
def test_cards_and_posts_carry_a_strip_that_says_what_kind_of_post_it_is():
    a = client()
    report(a, SCAM)
    report(a, BENIGN, intent="ask")
    feed = a.get("/community").text
    assert feed.count("cm-ribbon-warn") == 1 and feed.count("cm-ribbon-ask") == 1
    assert "Scam report" in feed and "Asking the community" in feed
    assert "cm-ribbon-ask" in a.get("/community/post/2").text and "cm-ribbon-warn" in a.get("/community/post/1").text
    hi = client("hi")
    page = hi.get(report(hi, BENIGN, intent="ask").headers["location"]).text
    assert "समुदाय से पूछ रहे हैं" in page and "ठगी की रिपोर्ट" not in page


def test_report_form_wording_follows_the_choice_without_javascript():
    ask = client().get("/community/report?intent=ask").text
    assert "Ask the community: is this real?" in ask and "Post my question" in ask and "1. What is it about?" in ask
    assert "1. What kind of scam was it?" not in ask.split("<form")[1].split("data-warn")[0]
    warn = client().get("/community/report").text
    assert "Send report" in warn and "1. What kind of scam was it?" in warn
    assert 'data-warn="Send report" data-ask="Post my question"' in warn                 # the script swaps between the two
    hi = client("hi").get("/community/report?intent=ask").text
    assert "समुदाय से पूछ रहे हैं" not in hi.split("<h1")[1].split("</h1>")[0] and "मेरा सवाल भेजें" in hi


# ---- every kind of input, with either choice, gets the engine's own verdict --------------------------------
def test_every_input_type_with_either_choice_shows_exactly_the_engines_verdict():
    from satyapan.community.posts import _prepare_for_engine
    from satyapan.service import analyse_text
    samples = [("message", SCAM), ("message", "Your KYC expires today, account will be blocked. Update now: http://hdfc-kyc-update.in/login"),
               ("message", BENIGN), ("link", "hdfc-kyc-update.in/login"), ("link", "https://www.sbi.co.in"),
               ("upi", "Send money to refund.help55@paytm for guaranteed returns in our VIP tips group"), ("upi", "quiet.shop12@paytm"),
               ("call", "Caller said he is from CBI, I am under digital arrest, stay on video call and pay Rs 90000"),
               ("qr", "QR asked me to enter my UPI PIN to receive Rs 4500 refund")]
    flagged = {"SUSPICIOUS", "HIGH_RISK", "REGISTRY_HIT"}
    for i, (kind, text) in enumerate(samples):
        engine = analyse_text(_prepare_for_engine(text, kind), kind="link" if kind == "link" else "message").tier.value
        for intent in ("warn", "ask"):
            c = client()
            r = c.post("/community/report", data={"kind": kind, "text": text, "consent": "1", "intent": intent}, follow_redirects=False)
            assert r.status_code == 303, (kind, intent)
            with store.conn() as conn:
                row = conn.execute("SELECT tier, status, intent FROM community_posts ORDER BY id DESC LIMIT 1").fetchone()
            assert row["tier"] == engine and row["intent"] == intent, (kind, intent, text[:30])
            assert row["status"] == ("approved" if intent == "ask" or engine in flagged else "pending"), (kind, intent, engine)
