"""Dataset and metrics shared by train.py and evaluate.py."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402
from torch.utils.data import Dataset  # noqa: E402

from satyapan.eval.metrics import rate  # noqa: E402
from satyapan.layers.l2_forensics.tamper_net import to_tensor  # noqa: E402


def read_meta(data: Path, split: str) -> list[dict]:
    rows = [json.loads(line) for line in (data / "meta.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if r["split"] == split]


class ScreenDataset(Dataset):
    def __init__(self, data: Path, split: str, size: tuple[int, int]):
        self.data, self.size, self.rows = Path(data), size, read_meta(Path(data), split)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, i: int):
        r = self.rows[i]
        img = Image.open(self.data / "images" / f"{r['id']}.jpg")
        m = Image.open(self.data / "masks" / f"{r['id']}.png").resize((self.size[1], self.size[0]), Image.NEAREST)
        mask = torch.from_numpy((np.asarray(m, dtype="float32") > 127).astype("float32")).unsqueeze(0)
        return to_tensor(img, self.size), mask, i


def auroc(pos: list[float], neg: list[float]) -> float:
    """Probability that a random edited image scores above a random genuine one (ties count half)."""
    if not pos or not neg:
        return float("nan")
    p, n = np.asarray(pos), np.asarray(neg)
    gt = (p[:, None] > n[None, :]).mean()
    eq = (p[:, None] == n[None, :]).mean()
    return float(gt + 0.5 * eq)


def threshold_at_fpr(neg: list[float], target_fpr: float) -> float:
    """Smallest threshold whose false-alarm rate on genuine images is at most target_fpr."""
    if not neg:
        return 0.5
    s = np.sort(np.asarray(neg))
    k = int(np.ceil((1 - target_fpr) * len(s))) - 1
    return float(s[min(max(k, 0), len(s) - 1)]) + 1e-9


def summarise(scores: list[float], edited: list[bool], thr: float) -> dict:
    pos = [s for s, e in zip(scores, edited) if e]
    neg = [s for s, e in zip(scores, edited) if not e]
    return {"tpr": rate(sum(s > thr for s in pos), len(pos)), "fpr": rate(sum(s > thr for s in neg), len(neg)),
            "auroc": auroc(pos, neg), "threshold": thr}


def ela_score(path: Path) -> float:
    """Baseline: error-level analysis. Re-save at JPEG 90 and take the largest 16x16 block difference."""
    img = Image.open(path).convert("RGB")
    b = io.BytesIO()
    img.save(b, "JPEG", quality=90)
    d = np.abs(np.asarray(img, dtype="float32") - np.asarray(Image.open(io.BytesIO(b.getvalue())).convert("RGB"), dtype="float32")).mean(axis=2)
    h, w = (d.shape[0] // 16) * 16, (d.shape[1] // 16) * 16
    blocks = d[:h, :w].reshape(h // 16, 16, w // 16, 16).mean(axis=(1, 3))
    return float(blocks.max())
