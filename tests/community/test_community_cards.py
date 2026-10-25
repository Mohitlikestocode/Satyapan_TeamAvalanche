"""Pictures and PDFs: warning cards, post cards, posters, the nav, and the Family Guardian trigger."""
from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image

from satyapan.api.app import app
from satyapan.community import cards, content

SCAM = "Join our VIP stock tips group. Guaranteed 30% profit every month. Pay Rs 25000 to alpha.gain88@ybl. Call 9876543210"


def client(lang: str = "en") -> TestClient:
    c = TestClient(app)
    c.cookies.set("sp_lang", lang)
    c.get("/community")
    return c


def png(resp):
    assert resp.status_code == 200 and resp.headers["content-type"] == "image/png"
    return Image.open(io.BytesIO(resp.content))


def test_every_lesson_has_a_card_and_a_poster_in_both_languages():
    c = client()
    for l in content.lessons():
        for lang in ("en", "hi"):
            assert png(c.get(f"/learn/cards/{l['slug']}.png?lang={lang}")).size == (1080, 1350)
            assert png(c.get(f"/warn/card.png?type={l['slug']}&lang={lang}")).size == (1080, 1350)
            assert cards.poster_png(l["slug"], lang, "https://x.example")
    assert c.get("/learn/cards/nope.png").status_code == 404 and c.get("/warn/card.png?type=nope").status_code == 404


def test_hindi_and_english_cards_differ():
    en, hi = cards.lesson_card("kyc-link", "en", "https://x.example"), cards.lesson_card("kyc-link", "hi", "https://x.example")
    assert en != hi


def test_post_card_uses_only_the_cleaned_public_post():
    c = client()
    c.post("/community/report", data={"kind": "message", "text": SCAM, "consent": "1"})
    assert png(c.get("/community/post/1/card.png?lang=hi")).size == (1080, 1350)
    assert png(c.get("/warn/card.png?post=1&lang=en")).size == (1080, 1350)
    assert b"9876543210" not in c.get("/community/post/1/card.png").content
    page = c.get("/warn?post=1").text
    assert "/warn/card.png?post=1" in page and "wa.me" in page
    # a post that is not public has no card
    c.post("/community/report", data={"kind": "message", "text": "Hello, your electricity bill of Rs 1200 is due on 30th. Please pay at the counter.", "consent": "1"})
    assert c.get("/community/post/2/card.png").status_code == 404


def test_warn_page_in_both_languages_and_with_defaults():
    assert "Make a warning card" in client("en").get("/warn").text
    page = client("hi").get("/warn").text
    assert "चेतावनी कार्ड बनाएँ" in page and 'value="hi" checked' in page
    assert "/warn/card.png?type=stock-tips-group" in client().get("/warn?type=stock-tips-group").text
    assert "/warn/card.png?type=stock-tips-group" in client().get("/warn?type=nonsense").text       # unknown types fall back to the first lesson


def test_posters_page_and_pdfs():
    c = client()
    page = c.get("/learn/posters").text
    assert page.count("/learn/posters/") >= 26
    one = c.get("/learn/posters/kyc-link.pdf?lang=hi")
    assert one.status_code == 200 and one.headers["content-type"] == "application/pdf" and one.content[:5] == b"%PDF-"
    allpdf = c.get("/learn/posters/all.pdf?lang=en").content
    assert allpdf.count(b"/Type /Page\n") + allpdf.count(b"/Type /Page ") >= 12 or allpdf.count(b"/Page") >= 12
    assert c.get("/learn/posters/nope.pdf").status_code == 404


def test_poster_has_a_qr_and_site_line_but_no_photo():
    img = Image.open(io.BytesIO(cards.poster_png("kyc-link", "en", "https://satyapan.example")))
    assert img.size == (1240, 1754) and img.info.get("dpi")
    footer = img.crop((0, 1754 - 250, 1240, 1754)).convert("L")
    assert min(footer.getdata()) < 50 and max(footer.getdata()) > 200             # dark band with light text and a QR in it


def test_certificate_and_safe_word_card_sizes():
    from datetime import datetime

    from satyapan.community import progress
    cert = Image.open(io.BytesIO(cards.certificate("Rekha_52", progress.level_for(130), "hi", datetime(2026, 10, 24), "https://x.example")))
    assert cert.size == (1600, 1131)
    assert Image.open(io.BytesIO(cards.safe_word_card("नीम साइकिल", "नानी", "hi", "https://x.example"))).size == (1240, 1754)
    assert Image.open(io.BytesIO(cards.safe_word_card("x" * 40, "", "en", "https://x.example"))).size == (1240, 1754)


def test_navigation_footer_and_related_links_are_registered():
    page = client().get("/learn").text
    assert 'href="/community"' in page and ">Community<" in page
    assert 'href="/me"' in page and 'href="/warn"' in page and 'href="/learn/posters"' in page


def test_asking_family_gives_the_family_guardian_badge_when_share_is_pressed():
    c = client()
    case = c.post("/api/v1/check", data={"kind": "message", "text": SCAM}).json()["id"]
    assert c.get(f"/guardian?case={case}").status_code == 200                      # only opening the page is not enough
    assert c.get("/api/v1/learn/me").json()["started"] is False
    c.post("/api/guardian/shared?case=does-not-exist")
    assert c.get("/api/v1/learn/me").json()["started"] is False                    # an unknown result earns nothing
    assert c.post(f"/api/guardian/shared?case={case}").status_code == 200          # the beacon the page sends on Share or Copy
    me = c.get("/api/v1/learn/me").json()
    assert me["started"] and "family_guardian" in me["badges"]


def test_scam_watcher_badge_after_first_published_report_and_after_moderation():
    c = client()
    c.post("/community/report", data={"kind": "message", "text": SCAM, "consent": "1"})
    assert "scam_watcher" in c.get("/api/v1/learn/me").json()["badges"]
    d, mod = client(), client()
    mod.cookies.set("sp_reviewer", "reviewer.03")
    d.post("/community/report", data={"kind": "message", "text": "Hello, your electricity bill of Rs 1200 is due on 30th. Please pay at the counter.", "consent": "1"})
    assert d.get("/api/v1/learn/me").json().get("started") is False                 # still waiting for a person
    mod.post("/community/moderate/2/approve")
    assert "scam_watcher" in d.get("/api/v1/learn/me").json()["badges"]
