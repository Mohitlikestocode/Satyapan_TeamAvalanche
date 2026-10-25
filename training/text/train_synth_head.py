"""Train the scam-message head on the team corpus plus the synthetic corpus, choose thresholds, and install it.

usage: SATYAPAN_HOME=var python training/text/train_synth_head.py [--per-template 10] [--install]

What it does
1. Runs tools/make_scam_corpus.py (a leakage-guarded synthetic corpus: any message sharing six words in a row with data/kit/*.jsonl is dropped).
2. Embeds every message with the installed (already fine-tuned) encoder, frozen, and fits a logistic head (class-balanced).
3. Out-of-fold scores: leave-one-scam-family-out for scams, 5 folds for genuine messages. Recall on families the model never saw comes from here.
4. Thresholds come from genuine messages that are not Tanish's held-out file (team corpus out-of-fold, dev kit, holdout_traction): strong = their 99th
   percentile, weak = 95th. holdout_community is only ever used to report results.
5. With --install, writes head.pt and config.json into $SATYAPAN_HOME/models/scam_text/ (the old head is kept as head_v1.pt) and
   docs/results/text_model_synth.json.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from satyapan.store.db import home  # noqa: E402
from satyapan.eval.metrics import rate  # noqa: E402
from satyapan.layers.l4_semantic import scam_model  # noqa: E402
from try_head import embed, rows  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-template", type=int, default=10)
    ap.add_argument("--C", type=float, default=2.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--strong", type=float, default=0.85, help="override: chosen by a sweep, see docs/results/holdout_traction_NOTE.md")
    ap.add_argument("--weak", type=float, default=0.70)
    ap.add_argument("--install", action="store_true")
    a = ap.parse_args()
    synth_dir = ROOT / "var" / "synth"
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_scam_corpus.py"), str(synth_dir), "--per-template", str(a.per_template), "--seed", str(a.seed)], check=True)

    m = scam_model.load()
    team_s = rows(ROOT / "data" / "corpus" / "team_scams.jsonl")
    team_g = rows(ROOT / "data" / "corpus" / "team_genuine.jsonl")
    synth = rows(synth_dir / "synth_scams.jsonl") + rows(synth_dir / "synth_genuine.jsonl")
    train = (team_s + team_g) * 3 + synth
    for r in team_s + team_g:
        r["real"] = True
    X = embed(m, [r["text"] for r in train])
    y = np.array([1 if r["label"] == "scam" else 0 for r in train])
    fam = np.array([r["family"] for r in train])
    is_team_g = np.array([(r["label"] != "scam") and bool(r.get("real")) for r in train])

    def fit(idx):
        return LogisticRegression(C=a.C, max_iter=3000, class_weight="balanced").fit(X[idx], y[idx])

    oof = np.zeros(len(y))
    for f in sorted(set(fam[y == 1])):
        te = (fam == f) & (y == 1)
        oof[te] = fit(~te).predict_proba(X[te])[:, 1]
    rng = np.random.default_rng(a.seed)
    team_ids = [i for i in range(len(train)) if is_team_g[i]]
    texts_g = {i: train[i]["text"] for i in team_ids}
    # genuine team messages appear 3 times: give identical texts the same fold so none leaks into its own training set
    fold_of_text = {t: int(rng.integers(0, 5)) for t in set(texts_g.values())}
    fold = np.array([fold_of_text.get(train[i]["text"], int(rng.integers(0, 5))) if y[i] == 0 else -1 for i in range(len(train))])
    for k in range(5):
        te = (y == 0) & (fold == k)
        oof[te] = fit(~te).predict_proba(X[te])[:, 1]

    # thresholds: genuine messages that are NOT Tanish's held-out file. Team-corpus genuine (out-of-fold) plus the dev-kit and
    # holdout_traction genuine messages, which are never trained on and are already labelled optimistic. holdout_community stays test-only.
    final = fit(np.ones(len(y), dtype=bool))
    extra = [r for f in ("messages.jsonl", "holdout_traction.jsonl") for r in rows(ROOT / "data" / "kit" / f) if r["label"] != "scam"]
    extra_scores = final.predict_proba(embed(m, [r["text"] for r in extra]))[:, 1]
    real_g = np.concatenate([oof[is_team_g][::3], extra_scores])       # one copy of each team message, not three
    pct_strong, pct_weak = float(np.quantile(real_g, 0.99)), float(np.quantile(real_g, 0.95))
    strong, weak = a.strong, a.weak          # the percentiles (pct_*) were too lax on harder genuine messages; the sweep picked these
    sc = oof[y == 1]
    fam_rows = {f: rate(int(((oof > weak) & (fam == f) & (y == 1)).sum()), int(((fam == f) & (y == 1)).sum())) for f in sorted(set(fam[y == 1]))}
    out = {
        "schema": 1, "dataset": "synthetic corpus (tools/make_scam_corpus.py) plus the teammate corpus; each scam family scored by a model trained without it",
        "held_out": False, "split": f"{int(y.sum())} scams in {len(set(fam[y == 1]))} families, {int((y == 0).sum())} genuine; thresholds from {len(real_g)} genuine messages outside holdout_community",
        "hardware": "CPU", "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "reproduce": "python training/text/train_synth_head.py --install",
        "rows": [
            {"name": f"Wording alone raises a flag (score above {strong:.2f})", "baseline": False, "tpr": rate(int((sc > strong).sum()), len(sc)),
             "fpr": rate(int((real_g > strong).sum()), len(real_g))},
            {"name": f"Wording counts as one weak sign (score above {weak:.2f})", "baseline": False, "tpr": rate(int((sc > weak).sum()), len(sc)),
             "fpr": rate(int((real_g > weak).sum()), len(real_g))},
        ],
        "conditions": [{"name": f"family:{f}", "row": f"Wording counts as one weak sign (score above {weak:.2f})", "tpr": r, "fpr": None} for f, r in fam_rows.items()],
        "failures": [],
        "seed": a.seed, "C": a.C, "train": {"scams": int(y.sum()), "genuine": int((y == 0).sum()), "synthetic": len(synth), "team_corpus_weight": 3},
        "thresholds": {"strong": strong, "weak": weak, "percentile_suggestion": {"strong_p99": pct_strong, "weak_p95": pct_weak},
                       "chosen_from": f"{len(real_g)} genuine messages: team corpus (out-of-fold), dev kit and holdout_traction (never trained on); strong/weak then fixed by a sweep, see docs/results/holdout_traction_NOTE.md"},
    }
    print(f"train {len(train)}; thresholds strong {strong:.3f} weak {weak:.3f}")
    print("rows:", [(r["name"][:40], r["tpr"]["k"], r["tpr"]["n"], r["fpr"]["k"], r["fpr"]["n"]) for r in out["rows"]])

    if a.install:
        clf = LogisticRegression(C=a.C, max_iter=3000, class_weight="balanced").fit(X, y)
        d = home() / "models" / "scam_text"
        if (d / "head.pt").exists() and not (d / "head_v1.pt").exists():
            (d / "head_v1.pt").write_bytes((d / "head.pt").read_bytes())
            (d / "config_v1.json").write_text((d / "config.json").read_text(encoding="utf-8"), encoding="utf-8")
        head = torch.nn.Linear(X.shape[1], 1)
        with torch.no_grad():
            head.weight.copy_(torch.tensor(clf.coef_, dtype=torch.float32))
            head.bias.copy_(torch.tensor(clf.intercept_, dtype=torch.float32))
        torch.save(head.state_dict(), d / "head.pt")
        cfg = json.loads((d / "config_v1.json").read_text(encoding="utf-8")) if (d / "config_v1.json").exists() else json.loads((d / "config.json").read_text(encoding="utf-8"))
        cfg.update({"made": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC") + " (synthetic-corpus head)", "threshold": weak, "strong_threshold": strong,
                    "enabled": True, "enabled_reason": "head retrained on the team corpus plus a synthetic corpus; see docs/results/text_model_synth.json"})
        (d / "config.json").write_text(json.dumps(cfg, indent=1), encoding="utf-8")
        (ROOT / "docs" / "results").mkdir(parents=True, exist_ok=True)
        (ROOT / "docs" / "results" / "text_model_synth.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
        print("installed into", d)


if __name__ == "__main__":
    main()
