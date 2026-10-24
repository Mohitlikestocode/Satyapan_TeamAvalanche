"""Score the tamper model on REAL screenshots: a folder of ones teammates edited and a folder of genuine ones.

usage (from the repo root):
  python training/tamper/evaluate_real.py --ckpt var/models/tamper.pt --edited data/real/edited --genuine data/real/genuine --json docs/results/tamper_real.json

This is the honest number. The synthetic test set only shows the model learned our generator. Use the checkpoint's own
threshold (chosen on synthetic validation styles); do not tune it on these files. Files stay local: never commit them.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from PIL import Image, ImageOps

from common import ScreenDataset, ela_score, summarise, threshold_at_fpr  # noqa: E402  (common fixes sys.path)
from satyapan.layers.l2_forensics.tamper_net import image_score, load_checkpoint, prepare  # noqa: E402

EXT = {".jpg", ".jpeg", ".png", ".webp"}


def score_dir(model, config: dict, folder: Path, device: str) -> list[tuple[str, float]]:
    out = []
    for p in sorted(x for x in folder.iterdir() if x.suffix.lower() in EXT):
        with torch.no_grad():
            img = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
            s = float(image_score(model(prepare(img, config).unsqueeze(0).to(device)))[0])
        out.append((p.name, s))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--edited", type=Path, required=True)
    ap.add_argument("--genuine", type=Path, required=True)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--data", type=Path, help="synthetic set (data/f1): adds the error-level-analysis baseline row")
    a = ap.parse_args()
    device = "cuda" if a.device == "auto" and torch.cuda.is_available() else ("cpu" if a.device == "auto" else a.device)
    model, ck = load_checkpoint(a.ckpt)
    model.to(device).eval()
    size = tuple(ck["config"]["size"])
    e, g = score_dir(model, ck["config"], a.edited, device), score_dir(model, ck["config"], a.genuine, device)
    thr = ck["threshold"]
    res = summarise([s for _, s in e] + [s for _, s in g], [True] * len(e) + [False] * len(g), thr)
    f = lambda r: f"{100 * r['rate']:.1f}% ({r['k']}/{r['n']}, 95% CI {100 * r['lo']:.0f}-{100 * r['hi']:.0f}%)"  # noqa: E731
    print(f"REAL screenshots: {len(e)} edited, {len(g)} genuine, threshold {thr:.3f}")
    print(f"  edited caught: {f(res['tpr'])}")
    print(f"  genuine wrongly flagged: {f(res['fpr'])}   AUROC {res['auroc']:.3f}")
    print("  missed edits:", [n for n, s in e if s <= thr][:20])
    print("  false alarms:", [n for n, s in g if s > thr][:20])
    extra: dict = {"hardware": torch.cuda.get_device_name(0) if device == "cuda" else "cpu", "n_edited": len(e), "n_genuine": len(g)}
    if a.data:  # baseline: error-level analysis with its threshold chosen on the synthetic validation split, same false-alarm target
        val = ScreenDataset(a.data, "val", size)
        v_neg = [ela_score(a.data / "images" / f"{r['id']}.jpg") for r in val.rows if not r["edited"]]
        bthr = threshold_at_fpr(v_neg, ck.get("target_fpr", 0.05))
        files = [a.edited / n for n, _ in e] + [a.genuine / n for n, _ in g]
        extra["baseline_ela"] = summarise([ela_score(p) for p in files], [True] * len(e) + [False] * len(g), bthr)
        print(f"  baseline (error-level analysis): caught {f(extra['baseline_ela']['tpr'])}  wrongly flagged {f(extra['baseline_ela']['fpr'])}")
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(json.dumps({**res, **extra, "missed": [n for n, s in e if s <= thr], "false_alarms": [n for n, s in g if s > thr]}, indent=1),
                          encoding="utf-8")


if __name__ == "__main__":
    main()
