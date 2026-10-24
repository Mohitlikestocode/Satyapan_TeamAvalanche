"""Screenshot edit check: runs the trained tamper model if a checkpoint is installed, otherwise does nothing.

Install a checkpoint by copying it to $SATYAPAN_HOME/models/tamper.pt (default ./var/models/tamper.pt) and restarting.
The model is a sign-finder. A clean result never proves a payment happened, and an alarm is not proof of editing.
"""
from __future__ import annotations

import io
from pathlib import Path

from ...contracts.models import Layer, LayerResult, Signal, Strength
from ...store import db

STRONG_SCORE = 0.9


def checkpoint_path() -> Path:
    return db.home() / "models" / "tamper.pt"


_CACHE: dict[tuple[str, float], tuple] = {}


def _load():
    p = checkpoint_path()
    if not p.exists():
        return None
    key = (str(p), p.stat().st_mtime)
    if key not in _CACHE:
        try:
            import torch
            from .tamper_net import load_checkpoint
            torch.set_num_threads(max(1, min(4, torch.get_num_threads())))
            _CACHE.clear()
            _CACHE[key] = load_checkpoint(str(p))
        except Exception:  # torch missing or a broken file: behave as if no model is installed
            return None
    return _CACHE[key]


def available() -> bool:
    return _load() is not None


def run(data: bytes) -> LayerResult | None:
    """Return a forensics result, or None when no model is installed or the image cannot be read."""
    loaded = _load()
    if loaded is None:
        return None
    try:
        import torch
        from PIL import Image, ImageOps
        from .tamper_net import image_score, prepare
        model, ck = loaded
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        with torch.no_grad():
            logits = model(prepare(img, ck["config"]).unsqueeze(0))
        score = float(image_score(logits)[0])
        thr = float(ck["threshold"])
    except Exception:
        return None
    signals: list[Signal] = []
    box = None
    if score > thr:
        prob = torch.sigmoid(logits)[0, 0]
        ys, xs = torch.where(prob > 0.5)
        if len(xs):
            h, w = prob.shape
            sx, sy = img.width / w, img.height / h
            box = (int(xs.min() * sx), int(ys.min() * sy), int(xs.max() * sx), int(ys.max() * sy))
        signals.append(Signal(layer=Layer.L2, code="MEDIA_IMAGE_EDITED",
                              strength=Strength.STRONG_SUSPICIOUS if score >= STRONG_SCORE else Strength.WEAK_SUSPICIOUS,
                              evidence_ref=("box:%d,%d,%d,%d" % box) if box else None))
    return LayerResult(layer=Layer.L2, signals=signals, model_versions={"tamper": f"unet-{ck['config']['encoder']}-ep{ck.get('epoch', '?')}"},
                       internal={"score": score, "threshold": thr, "box": box})
