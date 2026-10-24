"""Measure the check engine on a labelled text kit.

usage: python -m satyapan.eval.run data/kit/messages.jsonl [--json out.json]

Each line: {"text": str, "label": "scam" | "benign", "lang": "en"|"hi"|"hinglish", "family": str}
"flagged" means SUSPICIOUS or worse. "red" means HIGH RISK or REGISTRY HIT.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from ..contracts.models import Tier
from ..service import analyse_text
from .metrics import rate

FLAGGED = {Tier.SUSPICIOUS, Tier.HIGH_RISK, Tier.REGISTRY_HIT}
RED = {Tier.HIGH_RISK, Tier.REGISTRY_HIT}


def evaluate(rows: list[dict], use_plugins: bool = True) -> dict:
    """use_plugins=False measures the rules alone (the baseline); True measures the whole system as the site runs it."""
    stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    fails: list[dict] = []
    for r in rows:
        res = analyse_text(r["text"], topic=r.get("topic", ""), use_registry=False, use_plugins=use_plugins)
        scam = r["label"] == "scam"
        for key in ("all", f"lang:{r.get('lang', '?')}", f"family:{r.get('family', '?')}"):
            s = stats[key]
            s["scam" if scam else "benign"] += 1
            if res.tier in FLAGGED:
                s["flag_scam" if scam else "flag_benign"] += 1
            if res.tier in RED:
                s["red_scam" if scam else "red_benign"] += 1
        if (scam and res.tier not in FLAGGED) or (not scam and res.tier in FLAGGED):
            fails.append({"label": r["label"], "tier": res.tier.value, "lang": r.get("lang"), "text": r["text"][:160],
                          "codes": res.verdicts["en"].reason_codes})
    out: dict = {"groups": {}, "failures": fails}
    for key, s in sorted(stats.items()):
        out["groups"][key] = {
            "scam_n": s["scam"], "benign_n": s["benign"],
            "flag_rate_on_scams": rate(s["flag_scam"], s["scam"]),
            "red_rate_on_scams": rate(s["red_scam"], s["scam"]),
            "false_alarm_rate": rate(s["flag_benign"], s["benign"]),
            "red_false_alarm_rate": rate(s["red_benign"], s["benign"]),
        }
    return out


def fmt(r: dict) -> str:
    return f"{r['k']}/{r['n']} = {100 * r['rate']:.0f}% (95% CI {100 * r['lo']:.0f}-{100 * r['hi']:.0f}%)" if r["n"] else "n/a"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("kit", type=Path)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    rows = [json.loads(line) for line in a.kit.read_text(encoding="utf-8").splitlines() if line.strip()]
    out = evaluate(rows)
    for key, g in out["groups"].items():
        print(f"[{key}] scams={g['scam_n']} benign={g['benign_n']}")
        print(f"   scams flagged:      {fmt(g['flag_rate_on_scams'])}")
        print(f"   scams HIGH RISK:    {fmt(g['red_rate_on_scams'])}")
        print(f"   genuine flagged:    {fmt(g['false_alarm_rate'])}")
        print(f"   genuine HIGH RISK:  {fmt(g['red_false_alarm_rate'])}")
    print(f"\nFailures ({len(out['failures'])}):")
    for f in out["failures"]:
        print(f"  - {f['label']} -> {f['tier']} {f['codes']}: {f['text']}")
    if a.json:
        a.json.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
