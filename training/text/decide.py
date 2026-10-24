"""Decide whether the scam-message model ships: compare the site with and without it on messages it never trained on.

usage: python training/text/decide.py

Test sets: data/kit/holdout_*.jsonl (written by teammates who did not read the rules: the deciding set when present) and
data/kit/messages.jsonl (never used for training; the rules were written against it). The model ships only if, on the deciding
set, it flags more scams AND does not flag more genuine messages. The decision and the numbers are written to
docs/results/text_model_decision.json and into the model's config ("enabled": true or false).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from satyapan.eval.report import kit_files, read_jsonl  # noqa: E402
from satyapan.eval.run import evaluate  # noqa: E402
from satyapan.layers.l4_semantic import scam_model  # noqa: E402


def set_enabled(on: bool, reason: str) -> None:
    p = scam_model.model_dir() / "config.json"
    cfg = json.loads(p.read_text(encoding="utf-8"))
    cfg["enabled"], cfg["enabled_reason"] = on, reason
    p.write_text(json.dumps(cfg, indent=1), encoding="utf-8")


def measure(rows: list[dict]) -> dict:
    g = evaluate(rows, use_plugins=True)["groups"]["all"]
    return {"scams_flagged": g["flag_rate_on_scams"], "genuine_flagged": g["false_alarm_rate"]}


def main() -> None:
    if scam_model.config() is None:
        sys.exit("no model: run training/text/train_classifier.py first")
    dev, held = kit_files()
    sets = {"holdout": read_jsonl(held)} if held else {}
    sets["dev_kit"] = read_jsonl(dev)
    out: dict = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "sets": {}}
    for name, rows in sets.items():
        set_enabled(False, "measuring")
        without = measure(rows)
        set_enabled(True, "measuring")
        with_ = measure(rows)
        out["sets"][name] = {"n": len(rows), "without_model": without, "with_model": with_}
    decide_on = "holdout" if "holdout" in out["sets"] else "dev_kit"
    s = out["sets"][decide_on]
    more_caught = s["with_model"]["scams_flagged"]["k"] > s["without_model"]["scams_flagged"]["k"]
    no_more_fa = s["with_model"]["genuine_flagged"]["k"] <= s["without_model"]["genuine_flagged"]["k"]
    ship = more_caught and no_more_fa
    why = (f"on {decide_on}: scams flagged {s['without_model']['scams_flagged']['k']} -> {s['with_model']['scams_flagged']['k']} "
           f"of {s['with_model']['scams_flagged']['n']}, genuine flagged {s['without_model']['genuine_flagged']['k']} -> "
           f"{s['with_model']['genuine_flagged']['k']} of {s['with_model']['genuine_flagged']['n']}")
    if decide_on == "dev_kit":
        why += " (no held-out files yet: decided on the development kit, which is weaker evidence)"
    set_enabled(ship, why)
    out |= {"decided_on": decide_on, "ship": ship, "why": why}
    (ROOT / "docs" / "results" / "text_model_decision.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(("SHIP: " if ship else "KEEP OFF: ") + why)


if __name__ == "__main__":
    main()
