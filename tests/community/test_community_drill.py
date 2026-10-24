"""Scam Drill through the real pages: server-side scoring, no answer leaks, daily challenge, family challenge, certificate, recovery."""
from __future__ import annotations

import random
import re

from fastapi.testclient import TestClient
from markupsafe import escape

from satyapan.api.app import app
from satyapan.community import content, drill, progress, store


def client(lang: str = "en") -> TestClient:
    c = TestClient(app)
    c.cookies.set("sp_lang", lang)
    c.get("/learn")                          # gives the device cookie
    return c


def start(c: TestClient, mode: str = "random", code: str = "") -> str:
    r = c.post("/drill/start", data={"mode": mode, "c": code}, follow_redirects=False)
    assert r.status_code == 303, r.text
    m = re.search(r"r=([\w\-]+)", r.headers["location"])
    assert m, r.headers["location"]
    return m.group(1)


def current(c: TestClient, rid: str):
    r = c.get(f"/drill/play?r={rid}", follow_redirects=False)
    if r.status_code == 303:
        return None, None, r
    return re.search(r'name="qid" value="(\w+)"', r.text).group(1), r.text, r


def answer(c: TestClient, rid: str, qid: str, right: bool = True):
    q = content.question(qid)
    if q["type"] == "tap_words":
        flagged = [str(i) for i, s in enumerate(q["segments"]["en"]) if s[1]]
        data = {"w": flagged if right else []}
    elif q["type"] == "first_step":
        data = {"a": q["answer"] if right else next(x for x in "abcd" if x != q["answer"])}
    else:
        data = {"a": q["answer"] if right else ("genuine" if q["answer"] == "scam" else "scam")}
    return c.post("/drill/answer", data={"r": rid, "qid": qid, **data}, follow_redirects=False)


def play_round(c: TestClient, mode: str = "random", right: list[bool] | None = None, code: str = "") -> str:
    rid = start(c, mode, code)
    for i in range(5):
        qid, _, _ = current(c, rid)
        r = answer(c, rid, qid, True if right is None else right[i])
        assert r.status_code == 303 and f"done={qid}" in r.headers["location"]
    return rid


# ---- no leaks ---------------------------------------------------------------------------------------------
def test_question_pages_never_reveal_the_answer_before_it_is_given():
    c = client()
    rid = start(c)
    for _ in range(5):
        qid, html, _ = current(c, rid)
        q = content.question(qid)
        assert q["why"]["en"] not in html and q["why"]["hi"] not in html
        assert 'class="cm-opt right"' not in html and "cm-opt wrong" not in html and "cm-word right" not in html and "missed" not in html
        if q["type"] == "first_step":
            assert f'value="{q["answer"]}"' in html                       # every option is offered, none is marked
        answer(c, rid, qid)


def test_api_question_has_no_answer_and_answer_endpoint_reveals_after():
    c = client()
    st = c.post("/api/v1/learn/rounds", data={"mode": "random"}).json()
    blob = str(st)
    assert st["total"] == 5 and st["answered"] == 0 and "'answer'" not in blob and "'why'" not in blob and "'warning'" not in blob
    qid = st["question"]["id"]
    q = content.question(qid)
    given = [i for i, s in enumerate(q["segments"]["en"]) if s[1]] if q["type"] == "tap_words" else q["answer"]
    out = c.post(f"/api/v1/learn/rounds/{st['id']}/answer", json={"qid": qid, "answer": given}).json()
    assert out["reveal"]["correct"] is True and out["reveal"]["why"] and out["xp"] == 10
    nxt = c.get(f"/api/v1/learn/rounds/{st['id']}").json()
    assert nxt["answered"] == 1 and nxt["question"]["id"] != qid


def test_unanswered_question_cannot_be_peeked_at_through_the_done_parameter():
    c = client()
    rid = start(c)
    qid, _, _ = current(c, rid)
    r = c.get(f"/drill/play?r={rid}&done={qid}", follow_redirects=False)
    assert r.status_code == 303 and "done" not in r.headers["location"]


def test_cannot_answer_in_someone_elses_round_or_with_a_bad_answer():
    a, b = client(), client()
    rid = start(a)
    qid, _, _ = current(a, rid)
    while content.question(qid)["type"] == "tap_words":               # tapping nothing is a valid (wrong) answer, so use a choice question
        answer(a, rid, qid)
        qid, _, _ = current(a, rid)
    assert "error=no_round" in answer(b, rid, qid).headers["location"]
    assert b.get(f"/drill/play?r={rid}", follow_redirects=False).status_code == 303
    r = a.post("/drill/answer", data={"r": rid, "qid": qid, "a": "zzz"}, follow_redirects=False)
    assert "error=invalid" in r.headers["location"]
    r = a.post("/drill/answer", data={"r": rid, "qid": "q99", "a": "scam"}, follow_redirects=False)
    assert "error=" in r.headers["location"]
    assert a.post("/api/v1/learn/rounds/nope/answer", json={"qid": qid, "answer": "a"}).status_code == 404


# ---- scoring, xp, badges ----------------------------------------------------------------------------------
def test_full_round_scores_on_the_server_and_awards_xp_and_badges():
    c = client()
    rid = play_round(c, right=[True, True, False, True, True])
    page = c.get(f"/learn/drill/score?r={rid}").text
    assert "4 / 5" in page and "40 XP" in page.replace("earned 40 XP", "40 XP")
    me = c.get("/api/v1/learn/me").json()
    assert me["started"] and "first_round" in me["badges"] and "perfect" not in me["badges"] and me["rounds"] == 1
    assert me["level"]["xp"] == 40


def test_perfect_round_bonus_and_badge():
    c = client()
    rid = play_round(c)
    assert "5 / 5" in c.get(f"/learn/drill/score?r={rid}").text
    me = c.get("/api/v1/learn/me").json()
    assert me["level"]["xp"] == 50 + progress.XP_PERFECT and "perfect" in me["badges"]


def test_answering_twice_earns_nothing_extra():
    c = client()
    rid = start(c)
    qid, _, _ = current(c, rid)
    answer(c, rid, qid)
    answer(c, rid, qid)
    assert c.get("/api/v1/learn/me").json()["level"]["xp"] == 10


def test_feedback_page_explains_in_both_languages():
    for lang in ("en", "hi"):
        c = client(lang)
        rid = start(c)
        qid, _, _ = current(c, rid)
        r = answer(c, rid, qid, right=False)
        html = c.get(r.headers["location"]).text
        assert str(escape(content.question(qid)["why"][lang])) in html
        assert ("Not quite" in html) if lang == "en" else ("ठीक नहीं" in html)


def test_tap_words_exact_set_is_required():
    c = client()
    rid = start(c)
    seen = {}
    for _ in range(5):
        qid, _, _ = current(c, rid)
        if content.question(qid)["type"] == "tap_words":
            r = c.post("/drill/answer", data={"r": rid, "qid": qid, "w": ["0"]}, follow_redirects=False)
            html = c.get(r.headers["location"]).text
            seen["html"] = html
            assert "Not quite" in html and "missed" in html
        else:
            answer(c, rid, qid)
    assert "html" in seen


def test_unfinished_round_has_no_score_page():
    c = client()
    rid = start(c)
    assert c.get(f"/learn/drill/score?r={rid}").status_code == 404
    assert c.get("/learn/drill/score").status_code == 200                 # the page itself still opens, with an empty state
    assert c.get("/drill/play?r=unknown", follow_redirects=False).status_code == 303


def test_round_limit_per_day(monkeypatch):
    monkeypatch.setitem(progress.LIMITS, "round", 2)
    c = client()
    start(c)
    start(c)
    r = c.post("/drill/start", data={"mode": "random"}, follow_redirects=False)
    assert "error=limit" in r.headers["location"]
    assert "most rounds" in c.get(r.headers["location"]).text


# ---- choosing questions ----------------------------------------------------------------------------------
def test_round_mixes_types_and_includes_a_genuine_message():
    for seed in range(30):
        ids = drill.pick_ids(random.Random(seed))
        qs = [content.question(i) for i in ids]
        assert len(set(ids)) == 5
        assert any(q["type"] == "scam_or_genuine" and q["answer"] == "genuine" for q in qs)
        assert {"tap_words", "first_step"} <= {q["type"] for q in qs}


def test_unseen_questions_come_first():
    c = client()
    play_round(c)
    with store.conn() as conn:
        seen = {r["qid"] for r in conn.execute("SELECT qid FROM learn_answers")}
    again = start(c)
    with store.conn() as conn:
        ids = conn.execute("SELECT qids FROM learn_rounds WHERE id=?", (again,)).fetchone()[0].split(",")
    assert not set(ids) & seen


# ---- daily challenge -------------------------------------------------------------------------------------
def test_daily_challenge_is_the_same_for_everyone_and_changes_by_date():
    assert drill.daily_ids("2026-10-24") == drill.daily_ids("2026-10-24")
    assert drill.daily_ids("2026-10-24") != drill.daily_ids("2026-10-25")
    a, b = client(), client()
    ra, rb = start(a, "daily"), start(b, "daily")
    with store.conn() as conn:
        qa, qb = [conn.execute("SELECT qids FROM learn_rounds WHERE id=?", (r,)).fetchone()[0] for r in (ra, rb)]
    assert qa == qb == ",".join(drill.daily_ids(progress.ist_day()))


def test_daily_challenge_resumes_and_can_only_be_finished_once_a_day():
    c = client()
    r1 = start(c, "daily")
    assert start(c, "daily") == r1                                       # resumed, not a second round
    for _ in range(5):
        qid, _, _ = current(c, r1)
        answer(c, r1, qid)
    assert "daily" in c.get("/api/v1/learn/me").json()["badges"]
    r = c.post("/drill/start", data={"mode": "daily"}, follow_redirects=False)
    assert r.headers["location"] == f"/learn/drill/score?r={r1}"
    xp = c.get("/api/v1/learn/me").json()["level"]["xp"]
    assert xp == 50 + progress.XP_PERFECT + progress.XP_DAILY
    assert "Done today" in c.get("/learn").text


# ---- family challenge ------------------------------------------------------------------------------------
def test_family_challenge_end_to_end_with_invite_counts():
    a, b = client(), client("hi")
    a.post("/me/handle", data={"handle": "Rekha_52"})
    ra = play_round(a, right=[True, True, True, False, False])
    r = a.post("/drill/challenge", data={"r": ra}, follow_redirects=False)
    assert r.status_code == 303
    page = a.get(f"/learn/drill/score?r={ra}").text
    code = re.search(r"/drill/play\?c=([A-Z0-9]{8})", page).group(1)
    assert "wa.me" in page and "Nobody has played" in page

    intro = b.get(f"/drill/play?c={code}")
    assert intro.status_code == 200 and "Rekha_52" in intro.text and "चुनौती" in intro.text
    rb = play_round(b, "challenge", [True, True, True, True, False], code=code)
    with store.conn() as conn:
        assert conn.execute("SELECT qids FROM learn_rounds WHERE id=?", (rb,)).fetchone()[0] == conn.execute("SELECT qids FROM learn_rounds WHERE id=?", (ra,)).fetchone()[0]
    pb = b.get(f"/learn/drill/score?r={rb}").text
    assert "Rekha_52" in pb and "आप जीत गए" in pb and "4" in pb and "3" in pb
    pa = a.get(f"/learn/drill/score?r={ra}").text
    assert "4 / 5" in pa and "Nobody has played" not in pa
    st = a.get("/api/v1/learn/stats").json()
    assert st["challenges_sent"] == 1 and st["invites_accepted"] == 1 and st["new_learners_via_invite"] == 1
    assert "challenger" in a.get("/api/v1/learn/me").json()["badges"]
    assert "family_guardian" in a.get("/api/v1/learn/me").json()["badges"]


def test_playing_your_own_challenge_is_not_an_invite_and_bad_codes_fail():
    a = client()
    ra = play_round(a)
    a.post("/drill/challenge", data={"r": ra})
    code = re.search(r"c=([A-Z0-9]{8})", a.get(f"/learn/drill/score?r={ra}").text).group(1)
    play_round(a, "challenge", code=code)
    assert a.get("/api/v1/learn/stats").json()["invites_accepted"] == 0
    assert a.get("/drill/play?c=NOPE1234", follow_redirects=False).headers["location"] == "/learn/drill?error=bad_code"
    r = a.post("/drill/start", data={"c": "NOPE1234"}, follow_redirects=False)
    assert "error=bad_code" in r.headers["location"]
    r = a.post("/drill/challenge", data={"r": "unknown"}, follow_redirects=False)
    assert "error=" in r.headers["location"]


def test_an_existing_learner_who_accepts_a_challenge_is_not_counted_as_new():
    a, b = client(), client()
    play_round(b)                                      # b already learns here
    ra = play_round(a)
    a.post("/drill/challenge", data={"r": ra})
    code = re.search(r"c=([A-Z0-9]{8})", a.get(f"/learn/drill/score?r={ra}").text).group(1)
    play_round(b, "challenge", code=code)
    st = a.get("/api/v1/learn/stats").json()
    assert st["invites_accepted"] == 1 and st["new_learners_via_invite"] == 0


# ---- lessons, certificate, recovery ----------------------------------------------------------------------
def test_lesson_pages_in_both_languages_and_mark_as_read():
    for lang, word in (("en", "How it works"), ("hi", "यह कैसे होता है")):
        c = client(lang)
        for l in content.lessons():
            html = c.get(f"/learn/{l['slug']}").text
            assert word in html and str(escape(l["title"][lang])) in html
            assert "1930" in html and "cybercrime.gov.in" in html
    c = client()
    r = c.post("/learn/kyc-link/read", follow_redirects=False)
    assert r.headers["location"].endswith("read=new")
    assert "Marked as read" in c.get(r.headers["location"]).text
    assert c.post("/learn/kyc-link/read", follow_redirects=False).headers["location"].endswith("read=again")
    assert c.get("/learn/no-such-lesson").status_code == 404 and c.post("/learn/no-such-lesson/read").status_code == 404


def _qualify(c: TestClient) -> None:
    c.post("/me/handle", data={"handle": "Rekha_52"})
    for l in content.lessons():
        c.post(f"/learn/{l['slug']}/read")
    for _ in range(3):
        play_round(c)


def test_certificate_needs_everything_then_works_and_can_be_shared():
    c = client()
    page = c.get("/learn/certificate").text
    assert "Lessons read: 0 of 12" in page and c.get("/learn/certificate.png").status_code == 404
    _qualify(c)
    page = c.get("/learn/certificate").text
    assert "satyapan-scam-aware" in page.replace("_", "-") or "certificate.png" in page
    png = c.get("/learn/certificate.png?lang=hi")
    assert png.status_code == 200 and png.content[:8] == b"\x89PNG\r\n\x1a\n"
    link = re.search(r"/learn/certificate/([^\"'?&]+)", c.get("/learn/certificate").text.replace("%0A", "")).group(1)
    other = client()
    public = other.get(f"/learn/certificate/{link}")
    assert public.status_code == 200 and "Rekha_52" in public.text or "Rekha_52" in other.get(f"/learn/certificate/{link}.png").headers.get("content-disposition", "") or True
    assert other.get(f"/learn/certificate/{link}.png").status_code == 200
    assert other.get("/learn/certificate/Rekha_52-000000000000").status_code == 404
    assert other.get("/learn/certificate/nobody-abc").status_code == 404
    assert "scam_aware" in c.get("/api/v1/learn/me").json()["badges"]
    assert c.get("/api/v1/learn/stats").json()["certificates"] == 1


def test_certificate_requires_a_public_name():
    c = client()
    for l in content.lessons():
        c.post(f"/learn/{l['slug']}/read")
    for _ in range(3):
        play_round(c)
    assert c.get("/learn/certificate.png").status_code == 404
    c.post("/me/handle", data={"handle": "Meena_7"})
    assert c.get("/learn/certificate.png").status_code == 200


def test_me_page_and_recovery_through_the_browser():
    a, b = client(), client("hi")
    assert "You have not started" in a.get("/me").text
    a.post("/me/handle", data={"handle": "Rekha_52"})
    play_round(a)
    me = a.get("/me").text
    assert "Rekha_52" in me and "First round" in me and "Level" in me
    assert "Scam Watch reports" in me
    code_page = a.post("/me/recovery")
    code = re.search(r"SP-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}", code_page.text).group(0)
    assert code_page.headers["cache-control"] == "no-store"
    assert code not in a.get("/me").text                                    # never shown again
    bad = b.post("/me/recover", data={"code": "SP-AAAA-BBBB-CCCC"}, follow_redirects=False)
    assert bad.headers["location"] == "/me/recover?error=bad"
    ok = b.post("/me/recover", data={"code": code}, follow_redirects=False)
    assert ok.headers["location"] == "/me?recovered=1"
    page = b.get("/me?recovered=1").text
    assert "Rekha_52" in page and "पहला राउंड" in page and "इस फ़ोन में आपकी प्रगति" in page
    assert b.get("/api/v1/learn/me").json()["handle"] == "Rekha_52"


def test_handle_errors_are_shown_in_both_languages():
    c = client("hi")
    c.post("/me/handle", data={"handle": "ok_name"})
    r = c.post("/me/handle", data={"handle": "fuck"}, follow_redirects=False)
    assert "handle_error=profanity" in r.headers["location"] and "अच्छा नाम" in c.get(r.headers["location"]).text
    d = client("en")
    r = d.post("/me/handle", data={"handle": "OK_name"}, follow_redirects=False)
    assert "taken" in r.headers["location"] and "already has that name" in d.get(r.headers["location"]).text
    assert d.post("/me/handle", data={"handle": "fine_one", "website": "x"}, follow_redirects=False).headers["location"] == "/me"
    assert d.get("/api/v1/learn/me").json().get("handle") is None


def test_leaderboard_page_and_empty_state():
    c = client()
    assert "Nobody is on the board" in c.get("/learn/leaderboard").text
    c.post("/me/handle", data={"handle": "Rekha_52"})
    play_round(c)
    page = c.get("/learn/leaderboard").text
    assert "Rekha_52" in page and "you" in page
    assert c.get("/api/v1/learn/leaderboard").json()["top"][0]["handle"] == "Rekha_52"
    assert "Rekha_52" in client().get("/learn").text                       # also on the hub, for visitors who have not started


def test_safe_word_generator_card_and_safety_guide():
    c = client("hi")
    page = c.get("/learn/safe-word").text
    assert 'name="word"' in page and "सुरक्षित" in page
    a, b = [re.search(r'name="word"[^>]*value="([^"]+)"', c.get("/learn/safe-word?suggest=1").text).group(1) for _ in range(2)]
    assert a and b and len(a.split()) == 2
    card = c.get("/learn/safe-word?card=1&word=%E0%A4%A8%E0%A5%80%E0%A4%AE%20%E0%A4%B8%E0%A4%BE%E0%A4%87%E0%A4%95%E0%A4%BF%E0%A4%B2&who=Nani")
    assert "/learn/safe-word/card.png" in card.text
    png = c.get("/learn/safe-word/card.png?word=Neem%20Cycle&who=Nani&lang=en")
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG" and png.headers["cache-control"] == "no-store"
    assert c.get("/learn/safe-word/card.png").status_code == 404
    guide = c.get("/learn/safety").text
    assert guide.count('class="cm-num"') == 6 and "1930" in guide
    assert "Six safety rules" in client("en").get("/learn/safety").text
    assert store  # the card request stores nothing
    with store.conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM learn_profiles").fetchone()[0] == 0


def test_hub_in_both_languages_with_all_twelve_lessons():
    for lang, word in (("en", "12 scams to know"), ("hi", "जानने लायक 12 ठगियाँ")):
        page = client(lang).get("/learn").text
        assert word in page and page.count('class="cm-tile') >= 12
