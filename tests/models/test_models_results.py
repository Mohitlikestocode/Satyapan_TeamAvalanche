"""/results shows only numbers from docs/results files or a live run, and says "not evaluated" otherwise."""
import json

from fastapi.testclient import TestClient

from satyapan.api.app import app
from satyapan.eval import results


def rate(k, n):
    from satyapan.eval.metrics import rate as r
    return r(k, n)


def test_empty_results_folder_says_not_evaluated_everywhere(tmp_path, monkeypatch):
    monkeypatch.setattr(results, "RESULTS_DIR", tmp_path)
    secs = results.sections()
    assert secs and all(s.status == "not_evaluated" and not s.rows for s in secs)
    html = TestClient(app).get("/results").text
    assert "Not evaluated" in html and "95% CI" not in html
    hi = TestClient(app, cookies={"sp_lang": "hi"}).get("/results").text
    assert "मापा नहीं गया" in hi and "Not evaluated" not in hi


def test_tamper_and_generic_files_become_tables_with_intervals(tmp_path, monkeypatch):
    (tmp_path / "tamper_test.json").write_text(json.dumps({
        "split": "test", "n": 40, "model": {"tpr": rate(15, 20), "fpr": rate(2, 20), "auroc": 0.91, "auroc_ci": [0.8, 0.97], "threshold": 0.4},
        "config": {"encoder": "resnet18"}, "epoch": 9, "hardware": "NVIDIA GeForce RTX 4060 Laptop GPU",
        "baseline_ela": {"tpr": rate(5, 20), "fpr": rate(4, 20), "auroc": 0.6}, "by_condition": {"jpeg_q40": {"tpr": rate(3, 5), "fpr": rate(1, 5)}},
        "failures": [{"kind": "missed", "text": "L6 amount same font"}]}), encoding="utf-8")
    (tmp_path / "voice_test.json").write_text(json.dumps({
        "schema": 1, "dataset": "x", "rows": [{"name": "Detector", "tpr": rate(8, 10), "fpr": rate(1, 10), "eer": 0.12}],
        "conditions": [{"name": "opus24k", "tpr": rate(6, 10), "fpr": rate(2, 10)}], "failures": []}), encoding="utf-8")
    monkeypatch.setattr(results, "RESULTS_DIR", tmp_path)
    by = {s.key: s for s in results.sections()}
    syn = by["screenshot_synthetic"]
    assert syn.status == "measured" and [r.baseline for r in syn.rows] == [False, True]
    assert syn.rows[0].tpr["k"] == 15 and syn.hardware.startswith("NVIDIA")
    assert by["voice"].rows[0].eer == 0.12 and by["screenshot_real"].status == "not_evaluated"
    html = TestClient(app).get("/results").text
    assert "15/20 = 75%" in html and "2/20 = 10%" in html and "EER 12.0%" in html
    assert "JPEG quality 40" in html and "L6 amount same font" in html and "RTX 4060" in html


def test_run_kit_button_measures_the_kit_live_with_a_rules_baseline():
    r = TestClient(app).post("/api/v1/models/run-kit")
    assert r.status_code == 200
    dev = r.json()["dev"]
    assert dev["rows"][0]["baseline"] is True and dev["rows"][0]["tpr"]["n"] > 0 and dev["rows"][0]["fpr"]["n"] > 0
    assert dev["held_out"] is False and "messages.jsonl" in dev["dataset"]


def test_results_is_in_the_menu_and_works_at_phone_width_markup():
    html = TestClient(app).get("/").text
    assert 'href="/results"' in html
    page = TestClient(app).get("/results").text
    assert "/static/css/models.css" in page and "tbl-wrap" in page and 'id="ml-run"' in page
