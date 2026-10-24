"""Train the payment-screenshot tamper model on the synthetic set.

usage (from the repo root):
  python tools/make_payment_screens.py data/f1 --n 12000
  python training/tamper/train.py --data data/f1 --out var/models/tamper.pt --epochs 12

The checkpoint holds the weights, the config and the alarm threshold chosen on the *validation* styles so that at most
--target-fpr of genuine screenshots are flagged. Nothing is ever tuned on the test styles.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from common import ScreenDataset, summarise, threshold_at_fpr  # noqa: E402  (common fixes sys.path)
from evaluate import evaluate  # noqa: E402
from satyapan.layers.l2_forensics.tamper_net import DEFAULT_SIZE, build, image_score  # noqa: E402


def dice_bce(logits, mask):
    p = torch.sigmoid(logits)
    inter = (p * mask).flatten(1).sum(1)
    dice = 1 - (2 * inter + 1) / (p.flatten(1).sum(1) + mask.flatten(1).sum(1) + 1)
    return F.binary_cross_entropy_with_logits(logits, mask, pos_weight=torch.tensor(8.0, device=logits.device)) + dice.mean()


@torch.no_grad()
def val_scores(model, loader, device):
    model.eval()
    scores = []
    for x, _, _ in loader:
        scores += image_score(model(x.to(device))).cpu().tolist()
    return scores


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("var/models/tamper.pt"))
    ap.add_argument("--encoder", choices=["small", "resnet18"], default="small")
    ap.add_argument("--pretrained", action="store_true", help="resnet18 only: start from ImageNet weights (downloads them once)")
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--bs", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--size", type=int, nargs=2, default=list(DEFAULT_SIZE), metavar=("H", "W"))
    ap.add_argument("--target-fpr", type=float, default=0.05)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--max-train", type=int, default=0, help="use only the first N training images (smoke tests)")
    ap.add_argument("--no-augment", action="store_true", help="turn off training-time colour, crop and JPEG augmentation")
    a = ap.parse_args()

    random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)
    device = "cuda" if a.device == "auto" and torch.cuda.is_available() else ("cpu" if a.device == "auto" else a.device)
    size = tuple(a.size)
    train = ScreenDataset(a.data, "train", size, augment=not a.no_augment)
    if a.max_train:
        train.rows = train.rows[: a.max_train]
    val = ScreenDataset(a.data, "val", size)
    print(f"device={device} train={len(train)} val={len(val)} encoder={a.encoder} size={size}")
    tl = DataLoader(train, batch_size=a.bs, shuffle=True, num_workers=a.workers, drop_last=len(train) > a.bs, persistent_workers=a.workers > 0)
    vl = DataLoader(val, batch_size=a.bs, shuffle=False, num_workers=0)

    model = build(a.encoder, pretrained=a.pretrained).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=max(1, a.epochs * len(tl)))
    amp = device == "cuda"
    scaler = torch.amp.GradScaler(enabled=amp)
    best = {"auroc": -1.0}
    log = []
    a.out.parent.mkdir(parents=True, exist_ok=True)
    for ep in range(1, a.epochs + 1):
        model.train()
        t0, tot = time.time(), 0.0
        for x, m, _ in tl:
            x, m = x.to(device), m.to(device)
            with torch.autocast(device_type="cuda", enabled=amp):
                loss = dice_bce(model(x), m)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt); scaler.update(); sched.step()
            tot += loss.item()
        scores = val_scores(model, vl, device)
        edited = [r["edited"] for r in val.rows]
        thr = threshold_at_fpr([s for s, e in zip(scores, edited) if not e], a.target_fpr)
        s = summarise(scores, edited, thr)
        log.append({"epoch": ep, "loss": tot / max(1, len(tl)), "val_auroc": s["auroc"], "val_tpr": s["tpr"]["rate"], "val_fpr": s["fpr"]["rate"]})
        print(f"epoch {ep:2d}  loss {log[-1]['loss']:.4f}  val AUROC {s['auroc']:.3f}  TPR {s['tpr']['rate']:.2f} at FPR {s['fpr']['rate']:.2f}  ({time.time() - t0:.0f}s)")
        if s["auroc"] >= best["auroc"]:
            best = {"auroc": s["auroc"]}
            torch.save({"state_dict": model.state_dict(), "config": {"encoder": a.encoder, "size": list(size)}, "threshold": thr,
                        "target_fpr": a.target_fpr, "val": {k: v for k, v in s.items() if k != "threshold"}, "seed": a.seed, "epoch": ep}, a.out)
    print(f"best checkpoint saved to {a.out}")
    for split in ("val", "test"):
        if (ScreenDataset(a.data, split, size).rows):
            res = evaluate(a.out, a.data, split, device)
            path = a.out.with_name(f"tamper_{split}_metrics.json")
            path.write_text(json.dumps(res, indent=1), encoding="utf-8")
            print(f"[{split}] model TPR {res['model']['tpr']['rate']:.2f} FPR {res['model']['fpr']['rate']:.2f} AUROC {res['model']['auroc']:.3f} | "
                  f"ELA baseline AUROC {res['baseline_ela']['auroc']:.3f} | IoU {res['localisation_iou_on_edited']:.2f} -> {path}")
    (a.out.with_name("tamper_train_log.json")).write_text(json.dumps({"args": {k: str(v) for k, v in vars(a).items()}, "epochs": log}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
