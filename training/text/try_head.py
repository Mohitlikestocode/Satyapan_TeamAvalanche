"""Experiment: a new linear head over the (frozen) installed encoder, trained on the team corpus plus the synthetic corpus.

usage: SATYAPAN_HOME=var python training/text/try_head.py [--synth var/synth]
Prints AUROC and recall at fixed false-alarm levels on the three message files, and a leave-one-family-out estimate on the training data.
The held-out files are used only to report numbers here, never to fit anything.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sklearn.linear_model import LogisticRegression  # noqa: E402

from satyapan.layers.l4_semantic import scam_model  # noqa: E402
from satyapan.layers.l4_semantic.normalise import normalise  # noqa: E402


def rows(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def embed(m, texts: list[str]) -> np.ndarray:
    import torch
    out = []
    with torch.inference_mode():
        for i in range(0, len(texts), 64):
            out.append(m.embed([normalise(t).text[:2000] for t in texts[i:i + 64]]).float().cpu().numpy())
    return np.concatenate(out)


def auroc(pos, neg) -> float:
    pos, neg = np.array(pos), np.array(neg)
    return float(np.mean([(p > neg).mean() + 0.5 * (p == neg).mean() for p in pos]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synth", type=Path, default=ROOT / "var" / "synth")
    ap.add_argument("--C", type=float, default=2.0)
    a = ap.parse_args()
    m = scam_model.load()
    team = rows(ROOT / "data" / "corpus" / "team_scams.jsonl") + rows(ROOT / "data" / "corpus" / "team_genuine.jsonl")
    synth = rows(a.synth / "synth_scams.jsonl") + rows(a.synth / "synth_genuine.jsonl")
    train = team * 3 + synth
    X = embed(m, [r["text"] for r in train])
    y = np.array([1 if r["label"] == "scam" else 0 for r in train])
    fam = np.array([r["family"] for r in train])
    clf = LogisticRegression(C=a.C, max_iter=2000, class_weight="balanced").fit(X, y)

    # leave-one-family-out on the scam side, genuine split by random fold
    oof = np.zeros(len(y))
    fams = sorted(set(fam[y == 1]))
    rng = np.random.default_rng(7)
    gen_fold = rng.integers(0, 5, size=len(y))
    for f in fams:
        te = (fam == f) & (y == 1)
        tr = ~te
        c = LogisticRegression(C=a.C, max_iter=2000, class_weight="balanced").fit(X[tr], y[tr])
        oof[te] = c.predict_proba(X[te])[:, 1]
    for k in range(5):
        te = (y == 0) & (gen_fold == k)
        c = LogisticRegression(C=a.C, max_iter=2000, class_weight="balanced").fit(X[~te], y[~te])
        oof[te] = c.predict_proba(X[te])[:, 1]
    gen_oof = oof[y == 0]
    thr = float(np.quantile(gen_oof, 0.98))
    print(f"train {len(train)} (scam {int(y.sum())}); leave-one-family-out recall at 2% false alarms (thr {thr:.3f}): {(oof[y == 1] > thr).mean():.2f}")

    for name in ("holdout_community", "holdout_traction", "messages"):
        r = rows(ROOT / "data" / "kit" / f"{name}.jsonl")
        p = clf.predict_proba(embed(m, [x["text"] for x in r]))[:, 1]
        s = [v for v, x in zip(p, r) if x["label"] == "scam"]
        g = [v for v, x in zip(p, r) if x["label"] != "scam"]
        line = f"{name}: AUROC {auroc(s, g):.3f}  "
        for fa in (0.0, 0.025, 0.05, 0.10):
            t = np.quantile(g, 1 - fa) if fa else max(g)
            line += f"| FA<={fa:.3f}: {sum(v > t for v in s)}/{len(s)} "
        line += f"| at oof-thr: {sum(v > thr for v in s)}/{len(s)} scams, {sum(v > thr for v in g)}/{len(g)} genuine"
        print(line)


if __name__ == "__main__":
    main()

