"""Evaluate a tamper checkpoint on a split of the synthetic set, with a baseline row and per-condition breakdowns.

usage (from the repo root):
  python training/tamper/evaluate.py --ckpt var/models/tamper.pt --data data/f1 --split test --json docs/results/tamper_test.json
The threshold is the one stored in the checkpoint (chosen on the validation split), never re-tuned on the split being reported.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import torch

from common import ScreenDataset, ela_score, summarise, threshold_at_fpr  # noqa: E402  (common fixes sys.path)
from satyapan.layers.l2_forensics.tamper_net import image_score, load_checkpoint  # noqa: E402


@torch.no_grad()
def predict(model, ds: ScreenDataset, device: str, bs: int = 8):
    model.to(device).eval()
    scores, ious = [], []
    loader = torch.utils.data.DataLoader(ds, batch_size=bs, shuffle=False, num_workers=0)
    for x, m, _ in loader:
        logits = model(x.to(device))
        scores += image_score(logits).cpu().tolist()
        pred = (torch.sigmoid(logits) > 0.5).cpu()
        inter = (pred & (m > 0.5)).flatten(1).sum(1).float()
        union = (pred | (m > 0.5)).flatten(1).sum(1).float()
        ious += (inter / union.clamp(min=1)).tolist()
    return scores, ious


def evaluate(ckpt: Path, data: Path, split: str, device: str) -> dict:
    model, ck = load_checkpoint(ckpt)
    size = tuple(ck["config"]["size"])
    ds = ScreenDataset(data, split, size)
    scores, ious = predict(model, ds, device)
    edited = [r["edited"] for r in ds.rows]
    thr = ck["threshold"]
    out = {"split": split, "n": len(ds), "model": summarise(scores, edited, thr), "config": ck["config"], "threshold_from": "validation split"}
    out["localisation_iou_on_edited"] = float(sum(i for i, e in zip(ious, edited) if e) / max(1, sum(edited)))
    groups: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(ds.rows):
        groups[f"jpeg_q{r['jpeg_q']}"].append(i)
        groups[f"style_{r['style']}"].append(i)
        if r["edited"]:
            groups[f"field_{r['field']}"].append(i)
    out["by_condition"] = {k: summarise([scores[i] for i in ix], [edited[i] for i in ix], thr) for k, ix in sorted(groups.items()) if len(ix) >= 10}
    # baseline: error-level analysis, threshold chosen on the validation split at the same false-alarm rate
    val = ScreenDataset(data, "val", size)
    v_scores = [ela_score(data / "images" / f"{r['id']}.jpg") for r in val.rows]
    v_neg = [s for s, r in zip(v_scores, val.rows) if not r["edited"]]
    bthr = threshold_at_fpr(v_neg, ck.get("target_fpr", 0.05))
    b_scores = [ela_score(data / "images" / f"{r['id']}.jpg") for r in ds.rows]
    out["baseline_ela"] = summarise(b_scores, edited, bthr)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    device = "cuda" if a.device == "auto" and torch.cuda.is_available() else ("cpu" if a.device == "auto" else a.device)
    out = evaluate(a.ckpt, a.data, a.split, device)
    f = lambda r: f"{100 * r['rate']:.1f}% ({r['k']}/{r['n']}, 95% CI {100 * r['lo']:.0f}-{100 * r['hi']:.0f}%)"  # noqa: E731
    print(f"[{out['split']}] n={out['n']}  threshold={out['model']['threshold']:.3f} (from validation)")
    print(f"  model     edited caught: {f(out['model']['tpr'])}   genuine wrongly flagged: {f(out['model']['fpr'])}   AUROC {out['model']['auroc']:.3f}")
    print(f"  baseline  edited caught: {f(out['baseline_ela']['tpr'])}   genuine wrongly flagged: {f(out['baseline_ela']['fpr'])}   AUROC {out['baseline_ela']['auroc']:.3f}  (error-level analysis)")
    print(f"  localisation IoU on edited images: {out['localisation_iou_on_edited']:.2f}")
    for k, v in out["by_condition"].items():
        print(f"  {k:14s} caught {100 * v['tpr']['rate']:.0f}%  false alarms {100 * v['fpr']['rate']:.0f}%")
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
