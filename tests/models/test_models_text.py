"""The scam-message model hook is silent unless installed and enabled, and only ever adds a WEAK sign."""
import json
import os
from pathlib import Path

from satyapan.contracts.models import Strength
from satyapan.layers.l4_semantic import scam_model
from satyapan.plugins import models_text


class Stub:
    def __init__(self, p):
        self.p = p

    def prob(self, texts):
        return [self.p] * len(texts)


def install(enabled: bool, threshold: float = 0.8) -> None:
    d = Path(os.environ["SATYAPAN_HOME"]) / "models" / "scam_text"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text(json.dumps({"made": "t", "mode": "head", "threshold": threshold, "enabled": enabled}), encoding="utf-8")


def test_silent_without_a_model_or_when_disabled(monkeypatch):
    assert models_text.scam_like("Pay now to claim your prize money today", None) is None
    install(enabled=False)
    monkeypatch.setattr(scam_model, "load", lambda *a, **k: Stub(0.99))
    assert models_text.scam_like("Pay now to claim your prize money today", None) is None


def test_enabled_model_adds_only_a_weak_sign_above_its_threshold(monkeypatch):
    install(enabled=True, threshold=0.8)
    monkeypatch.setattr(scam_model, "load", lambda *a, **k: Stub(0.95))   # the model call is replaced; the hook logic is real
    r = models_text.scam_like("Pay now to claim your prize money today", None)
    assert r is not None and [s.code for s in r.signals] == ["ML_TEXT_SCAM_LIKE"] and r.signals[0].strength == Strength.WEAK_SUSPICIOUS
    assert r.internal["label_key"] == "ml_text"
    monkeypatch.setattr(scam_model, "load", lambda *a, **k: Stub(0.5))
    assert models_text.scam_like("Pay now to claim your prize money today", None) is None
    assert models_text.scam_like("hi", None) is None                                      # too short to judge


def test_cross_validation_file_shows_on_results(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from satyapan.api.app import app
    from satyapan.eval import results
    from satyapan.eval.metrics import rate
    (tmp_path / "text_model_cv.json").write_text(json.dumps({
        "protocol": "leave-one-scam-family-out", "chosen": "full", "hardware": "GPU", "date": "d",
        "modes": {"full": {"recall_unseen_family": rate(60, 79), "genuine_flagged_oof": rate(1, 62), "per_family": {"lottery": rate(5, 6)}}}}),
        encoding="utf-8")
    monkeypatch.setattr(results, "RESULTS_DIR", tmp_path)
    html = TestClient(app).get("/results").text
    assert "60/79 = 76%" in html and "Whole encoder fine-tuned (chosen)" in html and "lottery" in html
