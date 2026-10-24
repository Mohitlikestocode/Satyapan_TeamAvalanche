"""Score the engine on a held-out message file: python scripts/eval_holdout.py data/kit/holdout_traction.jsonl [--json out]"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PATH = Path(sys.argv[1])
rows = [json.loads(line) for line in PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
import os
os.environ["SATYAPAN_HOME"] = tempfile.mkdtemp()
from satyapan.service import analyse_text  # noqa: E402

hit = fa = 0
misses, falses = [], []
for r in rows:
    res = analyse_text(r["text"], kind="text", use_registry=False)
    flagged = res.tier.name in ("SUSPICIOUS", "HIGH_RISK", "REGISTRY_HIT")
    if r["label"] == "scam":
        hit += flagged
        if not flagged:
            misses.append(r["family"])
    else:
        fa += flagged
        if flagged:
            falses.append(r["text"][:60])
ns = sum(r["label"] == "scam" for r in rows)
nb = len(rows) - ns
out = {"file": PATH.name, "scams_flagged": hit, "scams": ns, "false_alarms": fa, "genuine": nb, "missed_families": misses, "false_alarm_examples": falses}
print(json.dumps(out, ensure_ascii=False, indent=1))
if "--json" in sys.argv:
    Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
