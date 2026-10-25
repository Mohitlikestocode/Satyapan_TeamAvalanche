"""The Back button: loaded on every public page, and its rules (where it shows, what it does) are in the script."""
from __future__ import annotations

from fastapi.testclient import TestClient

from satyapan.api.app import app

PAGES = ["/", "/check", "/dashboard", "/learn", "/learn/kyc-link", "/learn/drill", "/community", "/community/report", "/me", "/warn", "/how-it-works",
         "/already-paid", "/report", "/tools", "/shopkeeper", "/console"]


def test_every_public_page_loads_the_back_button_script_and_style():
    c = TestClient(app)
    for p in PAGES:
        html = c.get(p).text
        assert "/static/js/community_back.js" in html and "/static/css/community_back.css" in html, p
    assert c.get("/static/js/community_back.js").status_code == 200 and c.get("/static/css/community_back.css").status_code == 200


def test_script_rules_both_languages_and_where_it_stays_away():
    js = TestClient(app).get("/static/js/community_back.js").text
    assert 'en: "Back"' in js and 'hi: "वापस"' in js and "पिछले पृष्ठ पर वापस जाएँ" in js          # labels and tooltip in both languages
    for skipped in ('path === "/"', '"/console"', '"/check/progress"'):
        assert skipped in js                                                                   # home, reviewer console, a running check
    for form in ("/community/report", "/drill/play", "/check"):
        assert form in js                                                                      # never "back" into an empty form or an old question
    assert "history.back()" in js and "referrer" in js and "r.origin !== location.origin" in js    # only within this site
    assert "data-cm-back" in js                                                                # added once, never twice


def test_style_makes_a_large_enough_tap_target_and_hides_for_print():
    css = TestClient(app).get("/static/css/community_back.css").text
    assert "min-height:44px" in css and "@media print" in css and ":focus-visible" in css
