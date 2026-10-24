"""Regression guard on the dev kit: do not let a rule change quietly raise false alarms or lose recall."""
import json
from pathlib import Path

from satyapan.eval.run import evaluate

KIT = Path(__file__).resolve().parents[1] / "data" / "kit" / "messages.jsonl"


def test_dev_kit_floor():
    rows = [json.loads(line) for line in KIT.read_text(encoding="utf-8").splitlines() if line.strip()]
    out = evaluate(rows)["groups"]["all"]
    assert out["false_alarm_rate"]["rate"] <= 0.05      # genuine messages wrongly flagged
    assert out["red_false_alarm_rate"]["k"] == 0        # genuine messages called HIGH RISK
    assert out["flag_rate_on_scams"]["rate"] >= 0.90
