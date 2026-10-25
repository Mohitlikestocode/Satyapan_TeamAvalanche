"""The Call 1930 block under risky verdicts: loaded on the verdict pages, and its rules are fixed in the script."""
from __future__ import annotations

from fastapi.testclient import TestClient

from satyapan.api.app import app

RISKY = "Join our VIP stock tips group. Guaranteed 30% profit every month. Pay Rs 25000 to alpha.gain88@ybl"


def test_script_and_style_are_loaded_on_every_verdict_page():
    c = TestClient(app)
    c.get("/community")
    case = c.post("/api/v1/check", data={"kind": "message", "text": RISKY}).json()
    token = c.get("/api/v1/case/" + case["id"]).json()["share_token"]
    for url in (f"/case/{case['id']}", f"/guardian?case={case['id']}", f"/g/{token}", f"/report?case={case['id']}", "/learn", "/"):
        html = c.get(url).text
        assert "/static/js/community_helpline.js" in html and "/static/css/community_helpline.css" in html, url


def test_the_script_calls_1930_only_for_risky_verdicts_in_both_languages():
    c = TestClient(app)
    js = c.get("/static/js/community_helpline.js").text
    assert "section.vbanner.vb-r" in js and "section.vbanner.vb-a" in js            # high risk, registry hit, suspicious
    for not_added in ("vb-g", "vb-n"):                                              # no red flags, can't tell
        assert not_added not in js
    assert 'href="tel:1930"' in js and "cybercrime.gov.in" in js and "data-cm-helpline" in js
    assert "Call 1930 now" in js and "अभी 1930 पर कॉल करें" in js and "पहले घंटे में कॉल करें" in js
    assert "data-variant" in js                                                      # the result page holds an English and a Hindi copy
    css = c.get("/static/css/community_helpline.css").text
    assert "min-height:56px" in css and "@media print" in css and ":focus-visible" in css


def test_community_posts_with_a_risky_verdict_have_a_verdict_banner_the_script_can_find():
    c = TestClient(app)
    c.get("/community")
    r = c.post("/community/report", data={"kind": "message", "text": RISKY, "consent": "1"}, follow_redirects=False)
    html = c.get(r.headers["location"]).text
    assert '<section class="vbanner vb-r"' in html and "/static/js/community_helpline.js" in html
