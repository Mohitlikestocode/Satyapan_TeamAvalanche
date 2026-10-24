"""Measure the whole screenshot check as deployed (OCR, payee and word rules, tamper model, fusion) on unseen test layouts.

usage (from the repo root): python training/tamper/evaluate_system.py [--n 200] [--seed 7]
"Flagged" = SUSPICIOUS or worse. Also counts how often the edit sign itself appears. Writes docs/results/screenshot_system.json.
Uses the installed $SATYAPAN_HOME/models/tamper.pt and whatever OCR engine the site would use.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from satyapan.contracts.models import Tier  # noqa: E402
from satyapan.eval.metrics import rate  # noqa: E402
from satyapan.extract.ocr import engine_name  # noqa: E402
from satyapan.plugins import load_plugins  # noqa: E402
from satyapan.service import analyse_image  # noqa: E402

FLAGGED = {Tier.SUSPICIOUS, Tier.HIGH_RISK, Tier.REGISTRY_HIT}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "f1")
    ap.add_argument("--n", type=int, default=200, help="images per class (edited, genuine)")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    load_plugins()
    rows = [json.loads(x) for x in (a.data / "meta.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    test = [r for r in rows if r["split"] == "test"]
    rnd = random.Random(a.seed)
    pick = rnd.sample([r for r in test if r["edited"]], a.n) + rnd.sample([r for r in test if not r["edited"]], a.n)
    stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    failures, t0 = [], time.time()
    for i, r in enumerate(pick, 1):
        res = analyse_image((a.data / "images" / f"{r['id']}.jpg").read_bytes())
        codes = res.verdicts["en"].reason_codes
        keys = ["all", f"jpeg_q{r['jpeg_q']}", f"scale_{r['scale']}"] + ([("edit_perfect" if r["perfect"] else "edit_with_traces")] if r["edited"] else [])
        for k in keys:
            s = stats[k]
            s["pos" if r["edited"] else "neg"] += 1
            s[("flag_" if res.tier in FLAGGED else "noflag_") + ("pos" if r["edited"] else "neg")] += 1
            s[("sign_" if "MEDIA_IMAGE_EDITED" in codes else "nosign_") + ("pos" if r["edited"] else "neg")] += 1
            if res.tier == Tier.CANT_TELL:
                s["cant_tell"] += 1
        if r["edited"] and res.tier not in FLAGGED:
            failures.append({"kind": "missed", "text": f"image {r['id']} ({r['field']} edited, layout {r['style']}, JPEG q{r['jpeg_q']}) -> {res.tier.value}"})
        elif not r["edited"] and res.tier in FLAGGED:
            failures.append({"kind": "false_alarm", "text": f"image {r['id']} (genuine, layout {r['style']}) -> {res.tier.value} {codes}"})
        if i % 50 == 0:
            print(f"  {i}/{len(pick)} ({time.time() - t0:.0f}s)", flush=True)
    al = stats["all"]
    out = {"schema": 1, "dataset": "generated screens, test layouts L6 and L7 (never seen in training)", "held_out": True,
           "split": f"{a.n} edited + {a.n} genuine, random sample (seed {a.seed}); OCR engine: {engine_name()}",
           "hardware": "CPU inference, as on the site", "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "reproduce": "python training/tamper/evaluate_system.py",
           "rows": [{"name": "Whole screenshot check as deployed (SUSPICIOUS or worse)", "baseline": False,
                     "tpr": rate(al["flag_pos"], al["pos"]), "fpr": rate(al["flag_neg"], al["neg"])},
                    {"name": "Edit sign shown (\"The image shows signs of editing\")", "baseline": False,
                     "tpr": rate(al["sign_pos"], al["pos"]), "fpr": rate(al["sign_neg"], al["neg"])}],
           "conditions": [{"name": k, "tpr": rate(s["flag_pos"], s["pos"]) if s["pos"] else None,
                           "fpr": rate(s["flag_neg"], s["neg"]) if s["neg"] else None} for k, s in sorted(stats.items()) if k != "all"],
           "cant_tell": rate(al["cant_tell"], al["pos"] + al["neg"]), "failures": failures[:60]}
    (ROOT / "docs" / "results" / "screenshot_system.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for r in out["rows"]:
        print(f"{r['name']}: edited {r['tpr']['k']}/{r['tpr']['n']}, genuine {r['fpr']['k']}/{r['fpr']['n']}")
    print(f"CAN'T TELL: {out['cant_tell']['k']}/{out['cant_tell']['n']}")


if __name__ == "__main__":
    main()
