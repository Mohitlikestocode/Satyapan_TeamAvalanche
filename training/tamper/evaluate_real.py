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
from PIL import Image

from common import summarise  # noqa: E402  (common fixes sys.path)
from satyapan.layers.l2_forensics.tamper_net import image_score, load_checkpoint, to_tensor  # noqa: E402

EXT = {".jpg", ".jpeg", ".png", ".webp"}


def score_dir(model, size, folder: Path, device: str) -> list[tuple[str, float]]:
    out = []
    for p in sorted(x for x in folder.iterdir() if x.suffix.lower() in EXT):
        with torch.no_grad():
            s = float(image_score(model(to_tensor(Image.open(p), size).unsqueeze(0).to(device)))[0])
        out.append((p.name, s))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--edited", type=Path, required=True)
    ap.add_argument("--genuine", type=Path, required=True)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    device = "cuda" if a.device == "auto" and torch.cuda.is_available() else ("cpu" if a.device == "auto" else a.device)
    model, ck = load_checkpoint(a.ckpt)
    model.to(device).eval()
    size = tuple(ck["config"]["size"])
    e, g = score_dir(model, size, a.edited, device), score_dir(model, size, a.genuine, device)
    thr = ck["threshold"]
    res = summarise([s for _, s in e] + [s for _, s in g], [True] * len(e) + [False] * len(g), thr)
    f = lambda r: f"{100 * r['rate']:.1f}% ({r['k']}/{r['n']}, 95% CI {100 * r['lo']:.0f}-{100 * r['hi']:.0f}%)"  # noqa: E731
    print(f"REAL screenshots: {len(e)} edited, {len(g)} genuine, threshold {thr:.3f}")
    print(f"  edited caught: {f(res['tpr'])}")
    print(f"  genuine wrongly flagged: {f(res['fpr'])}   AUROC {res['auroc']:.3f}")
    print("  missed edits:", [n for n, s in e if s <= thr][:20])
    print("  false alarms:", [n for n, s in g if s > thr][:20])
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(json.dumps({**res, "missed": [n for n, s in e if s <= thr], "false_alarms": [n for n, s in g if s > thr]}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
