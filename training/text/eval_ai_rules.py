"""Measure the AI rule check: whole system with and without it, on every message set, plus extra genuine messages.

usage: python training/text/eval_ai_rules.py
Writes docs/results/ai_rules_eval.json. Honesty note recorded in the file: the 33 ground rules were written after we had read
the held-out misses, so held-out numbers for this component are optimistic; false alarms on genuine messages are the key number.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from satyapan.eval.metrics import rate  # noqa: E402
from satyapan.eval.report import read_jsonl  # noqa: E402
from satyapan.eval.run import FLAGGED  # noqa: E402
from satyapan.layers.l4_semantic import llm_check  # noqa: E402
from satyapan.plugins import load_plugins  # noqa: E402
from satyapan.service import analyse_text  # noqa: E402

KIT = ROOT / "data" / "kit"
SETS = {"holdout_tanish": [KIT / "holdout_community.jsonl"], "extra_genuine_team_corpus": [ROOT / "data" / "corpus" / "team_genuine.jsonl"],
        "dev_kit": [KIT / "messages.jsonl"], "holdout_mohit_tuned_on": [KIT / "holdout_traction.jsonl"]}
WAIT_TRIES = 8


def ask_until_answered(text: str) -> bool:
    """Free-tier rate limits make a call fall back silently; for a fair measurement we wait and ask again (fills the cache)."""
    from satyapan.layers.l4_semantic.normalise import normalise
    for i in range(WAIT_TRIES):
        if llm_check.check(normalise(text).text) is not None:
            return True
        time.sleep(4 + 2 * i)
    return False


def run(rows: list[dict], with_ai: bool) -> tuple[dict, list[dict]]:
    os.environ["SATYAPAN_LLM"] = "1" if with_ai else "0"
    s = {"scam": 0, "benign": 0, "flag_scam": 0, "flag_benign": 0}
    fails = []
    unanswered = 0
    for r in rows:
        if with_ai and len(r["text"].strip()) >= 12 and not ask_until_answered(r["text"]):
            unanswered += 1
        res = analyse_text(r["text"], use_registry=False)
        scam = r["label"] == "scam"
        s["scam" if scam else "benign"] += 1
        hit = res.tier in FLAGGED
        if hit:
            s["flag_scam" if scam else "flag_benign"] += 1
        if scam != hit:
            fails.append({"kind": "missed" if scam else "false_alarm", "text": r["text"][:160], "tier": res.tier.value,
                          "codes": res.verdicts["en"].reason_codes})
    return {"tpr": rate(s["flag_scam"], s["scam"]) if s["scam"] else None, "fpr": rate(s["flag_benign"], s["benign"]) if s["benign"] else None,
            "ai_unanswered": unanswered}, fails


def main() -> None:
    load_plugins()
    cfg = llm_check.config()
    if cfg is None:
        sys.exit("no LLM configured (GROQ_API_KEY in .env)")
    out = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "provider": cfg.provider, "model": cfg.model, "sets": {},
           "note": "The 33 ground rules were written after reading the held-out misses, so held-out numbers for the AI rule check are "
                   "optimistic. Mohit's set was also used to tune the India rules. False alarms on genuine messages are the key number."}
    for name, paths in SETS.items():
        rows = read_jsonl([p for p in paths if p.exists()])
        if not rows:
            continue
        t0 = time.time()
        without, _ = run(rows, with_ai=False)
        with_, fails = run(rows, with_ai=True)
        out["sets"][name] = {"n": len(rows), "without_ai": without, "with_ai": with_, "failures": fails, "seconds": round(time.time() - t0)}
        f = lambda r: f"{r['k']}/{r['n']}" if r else "-"  # noqa: E731
        print(f"{name:28s} scams {f(without['tpr'])} -> {f(with_['tpr'])}   genuine flagged {f(without['fpr'])} -> {f(with_['fpr'])}", flush=True)
    (ROOT / "docs" / "results" / "ai_rules_eval.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
