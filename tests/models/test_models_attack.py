"""/attack applies real perturbations and re-runs the real checks; nothing is stored."""
import io

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from satyapan.api.app import app
from satyapan.eval import attacks

SCAM = "Guaranteed 30% profit every month. Pay Rs 25000 to alpha.gain88@ybl to join our VIP group."


def test_text_perturbations_do_what_they_say():
    assert attacks.homoglyph("pay") != "pay" and len(attacks.homoglyph("pay")) == 3
    assert "alpha.gain88@ybl" not in attacks.split_upi(SCAM) and "(at) ybl" in attacks.split_upi(SCAM)
    assert "g.u.a.r.a.n.t.e.e.d" in attacks.spacing(SCAM).lower()
    assert "garunteed" in attacks.hinglish(SCAM).lower()


def test_text_attack_runs_every_perturbation_through_the_checks():
    base, outs = attacks.attack_text(SCAM)
    assert base.tier.value in ("SUSPICIOUS", "HIGH_RISK")
    assert [o.key for o in outs] == ["spacing", "homoglyph", "hinglish", "split_upi", "all"]
    assert all(o.tier for o in outs) and any(o.preview != SCAM for o in outs)


def test_attack_page_shows_a_table_in_both_languages():
    c = TestClient(app)
    assert "Attack yourself" in c.get("/attack").text
    r = c.post("/attack/text", data={"text": SCAM})
    assert r.status_code == 200 and "Look-alike letters" in r.text and "Verdict after" in r.text
    hi = TestClient(app, cookies={"sp_lang": "hi"}).post("/attack/text", data={"text": SCAM}).text
    assert "हूबहू दिखने वाले दूसरे अक्षर" in hi


def test_image_attack_runs_six_changes():
    img = Image.new("RGB", (360, 700), "white")
    ImageDraw.Draw(img).text((30, 100), "Paid Rs 4,500 to meena.stores@ybl", fill="black")
    b = io.BytesIO()
    img.save(b, "PNG")
    r = TestClient(app).post("/attack/image", files={"file": ("s.png", b.getvalue(), "image/png")})
    assert r.status_code == 200 and r.text.count("<tr>") >= 7 and "Rotated by 3 degrees" in r.text
    assert TestClient(app).post("/attack/image", files={"file": ("x.png", b"nope", "image/png")}).status_code == 422


def test_sweep_measures_evasion_against_flagged_scams_only():
    rows = [{"text": SCAM, "label": "scam"}, {"text": "Your parcel is out for delivery today.", "label": "benign"}]
    res = attacks.sweep_text(rows)
    assert res["n_flagged_before"] == 1 and len(res["attacks"]) == 5
    assert all(a["evasion"]["n"] == 1 for a in res["attacks"])
