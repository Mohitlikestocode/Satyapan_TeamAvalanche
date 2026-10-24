"""After training: evaluate every run on the held-out test layouts, pick one, install it, write the Results files.

usage (from the repo root): python training/tamper/finalize.py [--runs var/models/runs] [--data data/f1]

Choice rule (from the team brief): pick by the TEST split, never by validation. We take the highest test AUROC; the
threshold inside each checkpoint was fixed on validation and is not changed. Writes docs/results/tamper_test.json (chosen)
and docs/results/tamper_test_<run>.json (others), copies the chosen checkpoint to $SATYAPAN_HOME/models/tamper.pt.
Note for the Results page: choosing between runs on test makes the chosen test number slightly optimistic. All of it is
synthetic, held-out styles; not evaluated on real phone screenshots.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT  # noqa: E402  (also fixes sys.path)
from evaluate import evaluate  # noqa: E402

from satyapan.store import db  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, default=ROOT / "var" / "models" / "runs")
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "f1")
    a = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    results = {}
    for ck in sorted(a.runs.glob("*/tamper.pt")):
        name = ck.parent.name
        if name == "probe":
            continue
        print(f"evaluating {name} on the test layouts ...", flush=True)
        res = evaluate(ck, a.data, "test", device)
        res["run"] = name
        res["train_log"] = json.loads((ck.parent / "tamper_train_log.json").read_text(encoding="utf-8")) if (ck.parent / "tamper_train_log.json").exists() else None
        results[name] = res
        m = res["model"]
        print(f"  {name}: AUROC {m['auroc']:.3f}  caught {m['tpr']['k']}/{m['tpr']['n']}  wrongly flagged {m['fpr']['k']}/{m['fpr']['n']}  "
              f"IoU {res['localisation_iou_on_edited']:.2f}  | ELA baseline AUROC {res['baseline_ela']['auroc']:.3f}")
    if not results:
        sys.exit("no runs found")
    best = max(results, key=lambda k: results[k]["model"]["auroc"])
    out = ROOT / "docs" / "results"
    out.mkdir(parents=True, exist_ok=True)
    for name, res in results.items():
        res["chosen"] = name == best
        res["choice_rule"] = "highest AUROC on the test layouts (threshold fixed on validation)"
        (out / ("tamper_test.json" if name == best else f"tamper_test_{name}.json")).write_text(json.dumps(res, indent=1), encoding="utf-8")
    dest = db.home() / "models" / "tamper.pt"
    shutil.copy(a.runs / best / "tamper.pt", dest)
    print(f"chosen: {best} -> {dest}")


if __name__ == "__main__":
    main()
