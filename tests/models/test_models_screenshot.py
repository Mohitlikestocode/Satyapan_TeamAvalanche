"""/models/screenshot runs the full check, circles the suspected edit in memory, and stores only the verdict."""
import io
import os
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from satyapan.api.app import app
from satyapan.contracts.models import Layer, LayerResult, Signal, Strength
from satyapan.layers.l2_forensics import screenshot


def screen_png() -> bytes:
    img = Image.new("RGB", (360, 700), (250, 250, 250))
    d = ImageDraw.Draw(img)
    d.text((40, 120), "Payment Successful", fill=(20, 20, 20))
    d.text((40, 180), "Rs 4,500 to meena.stores@ybl", fill=(20, 20, 20))
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def test_form_renders_in_both_languages_and_is_in_the_footer():
    c = TestClient(app)
    html = c.get("/models/screenshot").text
    assert 'name="file"' in html and "never proves a payment" in html
    assert 'href="/models/screenshot"' in c.get("/").text
    hi = TestClient(app, cookies={"sp_lang": "hi"}).get("/models/screenshot").text
    assert "पेमेंट स्क्रीनशॉट जाँचें" in hi


def test_upload_without_a_model_still_gives_a_verdict_and_a_picture_but_saves_no_file():
    home = Path(os.environ["SATYAPAN_HOME"])
    before = {p for p in home.rglob("*") if p.is_file()} if home.exists() else set()
    r = TestClient(app).post("/models/screenshot", files={"file": ("s.png", screen_png(), "image/png")})
    assert r.status_code == 200
    assert "data:image/jpeg;base64," in r.text and "/case/" in r.text
    case_id = r.text.split('href="/case/')[1].split('"')[0]
    assert TestClient(app).get(f"/api/v1/case/{case_id}").status_code == 200   # the verdict is kept like a normal check
    after = {p for p in home.rglob("*") if p.is_file()}
    assert not {p.suffix.lower() for p in after - before} & {".png", ".jpg", ".jpeg", ".webp", ".bin"}   # no image written


def test_a_suspected_edit_is_circled(monkeypatch):
    def fake_run(data):  # the model call is replaced; the drawing and the page are real
        return LayerResult(layer=Layer.L2, signals=[Signal(layer=Layer.L2, code="MEDIA_IMAGE_EDITED", strength=Strength.WEAK_SUSPICIOUS,
                                                           evidence_ref="box:40,175,250,195")], internal={"box": (40, 175, 250, 195), "score": 0.7})
    monkeypatch.setattr(screenshot, "run", fake_run)
    r = TestClient(app).post("/models/screenshot", files={"file": ("s.png", screen_png(), "image/png")})
    assert r.status_code == 200 and "Red circle" in r.text
    from satyapan.api.ext.models_screenshot import annotate
    import base64
    url = annotate(screen_png(), (40, 175, 250, 195))
    img = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).convert("RGB")
    reds = sum(1 for p in img.getdata() if p[0] > 150 and p[1] < 80 and p[2] < 90)
    assert reds > 200


def test_unreadable_and_oversized_files_get_clear_errors():
    c = TestClient(app)
    r = c.post("/models/screenshot", files={"file": ("x.png", b"not an image", "image/png")})
    assert r.status_code == 422 and "could not read" in r.text
    r = c.post("/models/screenshot", files={"file": ("x.png", b"0" * (10 * 1024 * 1024 + 10), "image/png")})
    assert r.status_code == 413 and "too large" in r.text
