"""Measure the message checks and write the Results-page files.

usage: python -m satyapan.eval.report [--out docs/results]

Writes text_kit.json (data/kit/messages.jsonl, which the rules were written against: optimistic) and, when teammates' held-out
files exist, text_holdout.json (data/kit/holdout_community.jsonl: the honest number). Each has a rules-only baseline row and a row for the
whole system as the site runs it (rules plus any installed text models). "Flagged" means SUSPICIOUS or worse.
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

from .run import evaluate

ROOT = Path(__file__).resolve().parents[3]
KIT = ROOT / "data" / "kit"


def read_jsonl(paths: list[Path]) -> list[dict]:
    rows = []
    for p in paths:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def hardware() -> str:
    cpu = platform.processor() or platform.machine()
    return f"CPU: {cpu} ({platform.system()})"


def measure(paths: list[Path], held_out: bool) -> dict:
    """Run the kit twice (rules only, whole system) and return the generic results shape."""
    rows = read_jsonl(paths)
    t0 = time.perf_counter()
    base = evaluate(rows, use_plugins=False)
    full = evaluate(rows, use_plugins=True)
    elapsed = time.perf_counter() - t0
    same = json.dumps(base["groups"], sort_keys=True) == json.dumps(full["groups"], sort_keys=True)
    out_rows = [{"name": "Rules only (baseline)", "baseline": True, "tpr": base["groups"]["all"]["flag_rate_on_scams"],
                 "fpr": base["groups"]["all"]["false_alarm_rate"]}]
    out_rows.append({"name": "Whole system as deployed" + (" (same numbers as rules only on these messages)" if same else ""), "baseline": False,
                     "tpr": full["groups"]["all"]["flag_rate_on_scams"], "fpr": full["groups"]["all"]["false_alarm_rate"]})
    out_rows.append({"name": "Whole system: HIGH RISK only", "baseline": False, "tpr": full["groups"]["all"]["red_rate_on_scams"],
                     "fpr": full["groups"]["all"]["red_false_alarm_rate"]})
    conditions = [{"name": k, "row": "Whole system as deployed", "tpr": g["flag_rate_on_scams"] if g["scam_n"] else None,
                   "fpr": g["false_alarm_rate"] if g["benign_n"] else None}
                  for k, g in full["groups"].items() if k != "all"]
    failures = [{"kind": "missed" if f["label"] == "scam" else "false_alarm", "text": f["text"], "tier": f["tier"], "codes": f["codes"]}
                for f in full["failures"]]
    return {"schema": 1, "dataset": ", ".join(p.relative_to(ROOT).as_posix() for p in paths), "split": f"{len(rows)} messages",
            "held_out": held_out, "hardware": hardware(), "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "elapsed_s": round(elapsed, 2), "reproduce": "python -m satyapan.eval.report", "rows": out_rows, "conditions": conditions,
            "failures": failures}


def kit_files() -> tuple[list[Path], list[Path]]:
    """(development kit, held-out files). Derived lists such as holdout_*_missed.jsonl repeat messages and are skipped."""
    # holdout_traction.jsonl was drafted by the same assistant that wrote the rules, so it counts as optimistic, with the development kit
    held = sorted(p for p in KIT.glob("holdout_*.jsonl") if "missed" not in p.stem and p.stem != "holdout_traction")
    return [KIT / "messages.jsonl", KIT / "holdout_traction.jsonl"], held


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "results")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    dev, held = kit_files()
    for name, paths, is_held in (("text_kit.json", dev, False), ("text_holdout.json", held, True)):
        if not paths:
            print(f"{name}: no files, not evaluated")
            continue
        res = measure(paths, is_held)
        (a.out / name).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        for r in res["rows"]:
            t, f = r["tpr"], r["fpr"]
            print(f"{name}  {r['name']}: scams flagged {t['k']}/{t['n']}, genuine flagged {f['k']}/{f['n']}")


if __name__ == "__main__":
    main()
