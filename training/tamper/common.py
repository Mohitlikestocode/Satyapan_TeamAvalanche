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
from satyapan.layers.l2_forensics.tamper_net import to_tensor, to_tensor_native  # noqa: E402


def read_meta(data: Path, split: str) -> list[dict]:
    rows = [json.loads(line) for line in (data / "meta.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if r["split"] == split]


def augment(img: Image.Image, m: Image.Image, rng: np.random.Generator) -> tuple[Image.Image, Image.Image]:
    """Training-only changes that keep the edit where it is: colour channel swap, brightness, crop, one more JPEG pass."""
    img = img.convert("RGB")
    if rng.random() < 0.5:
        img = Image.merge("RGB", [img.split()[k] for k in rng.permutation(3)])
    if rng.random() < 0.3:
        a = np.asarray(img, dtype="float32") * rng.uniform(0.85, 1.15) + rng.uniform(-20, 20)
        img = Image.fromarray(np.clip(a, 0, 255).astype("uint8"))
    if rng.random() < 0.3:
        w, h = img.size
        cw, ch = int(w * rng.uniform(0.8, 1.0)), int(h * rng.uniform(0.8, 1.0))
        x0, y0 = int(rng.integers(0, w - cw + 1)), int(rng.integers(0, h - ch + 1))
        img, m = img.crop((x0, y0, x0 + cw, y0 + ch)), m.crop((x0, y0, x0 + cw, y0 + ch))
    if rng.random() < 0.3:
        b = io.BytesIO()
        img.save(b, "JPEG", quality=int(rng.integers(40, 96)))
        img = Image.open(io.BytesIO(b.getvalue())).convert("RGB")
    return img, m


def _mask_tensor(m: Image.Image) -> torch.Tensor:
    return torch.from_numpy((np.asarray(m, dtype="float32") > 127).astype("float32")).unsqueeze(0)


def native_pair(img: Image.Image, m: Image.Image, max_side: int) -> tuple[torch.Tensor, torch.Tensor]:
    """Image and mask exactly as to_tensor_native prepares an image at inference (shrink only if huge, crop to a multiple of 16)."""
    x = to_tensor_native(img, max_side)
    s = min(1.0, max_side / max(img.size))
    if s < 1.0:
        m = m.resize((max(16, int(img.width * s)), max(16, int(img.height * s))), Image.NEAREST)
    m = m.crop((0, 0, x.shape[2], x.shape[1]))
    return x, _mask_tensor(m)


def random_crop(img: Image.Image, m: Image.Image, crop: tuple[int, int], rng: np.random.Generator) -> tuple[Image.Image, Image.Image]:
    """A crop of `crop` (h, w) pixels at native resolution. For edited images, 60% of crops contain the edit."""
    ch, cw = crop
    if img.width < cw or img.height < ch:  # pad small images with their own edge colour
        canvas = Image.new("RGB", (max(cw, img.width), max(ch, img.height)), img.getpixel((0, 0)))
        canvas.paste(img, (0, 0))
        mc = Image.new("L", canvas.size, 0)
        mc.paste(m, (0, 0))
        img, m = canvas, mc
    bb = m.getbbox()
    if bb and rng.random() < 0.6:
        def pick(lo: int, hi: int) -> int:
            lo, hi = max(0, lo), max(0, hi)
            return int(rng.integers(min(lo, hi), max(lo, hi) + 1))
        cx = pick(bb[2] - cw, min(bb[0], img.width - cw))
        cy = pick(bb[3] - ch, min(bb[1], img.height - ch))
    else:
        cx, cy = int(rng.integers(0, img.width - cw + 1)), int(rng.integers(0, img.height - ch + 1))
    cx, cy = min(max(0, cx), img.width - cw), min(max(0, cy), img.height - ch)
    return img.crop((cx, cy, cx + cw, cy + ch)), m.crop((cx, cy, cx + cw, cy + ch))


class ScreenDataset(Dataset):
    """size: fixed (h, w) input, the image is resized. native=True: native resolution (whole image at eval, `crop` patches in training)."""

    def __init__(self, data: Path, split: str, size: tuple[int, int], augment: bool = False, native: bool = False,
                 crop: tuple[int, int] | None = None, max_side: int = 1600):
        self.data, self.size, self.rows, self.augment = Path(data), size, read_meta(Path(data), split), augment
        self.native, self.crop, self.max_side = native, crop, max_side

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, i: int):
        r = self.rows[i]
        img = Image.open(self.data / "images" / f"{r['id']}.jpg").convert("RGB")
        m = Image.open(self.data / "masks" / f"{r['id']}.png")
        # torch seeds each loader worker from the run seed, so this stays reproducible
        rng = np.random.default_rng(int(torch.randint(0, 2**31 - 1, (1,))))
        if self.augment:
            img, m = augment(img, m, rng)
        if self.native:
            if self.crop:
                img, m = random_crop(img, m, self.crop, rng)
                x = to_tensor_native(img, max_side=10**6)
                return x, _mask_tensor(m.crop((0, 0, x.shape[2], x.shape[1]))), i
            x, mt = native_pair(img, m, self.max_side)
            return x, mt, i
        m = m.resize((self.size[1], self.size[0]), Image.NEAREST)
        return to_tensor(img, self.size), _mask_tensor(m), i


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


def auroc_ci(pos: list[float], neg: list[float], n_boot: int = 500, seed: int = 0) -> tuple[float, float]:
    """Bootstrap 95% interval for AUROC, resampling edited and genuine images separately."""
    if len(pos) < 2 or len(neg) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    p, n = np.asarray(pos), np.asarray(neg)
    vals = [auroc(list(rng.choice(p, len(p))), list(rng.choice(n, len(n)))) for _ in range(n_boot)]
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def summarise(scores: list[float], edited: list[bool], thr: float, ci: bool = False) -> dict:
    pos = [s for s, e in zip(scores, edited) if e]
    neg = [s for s, e in zip(scores, edited) if not e]
    out = {"tpr": rate(sum(s > thr for s in pos), len(pos)), "fpr": rate(sum(s > thr for s in neg), len(neg)),
           "auroc": auroc(pos, neg), "threshold": thr}
    if ci:
        out["auroc_ci"] = auroc_ci(pos, neg)
    return out


def ela_score(path: Path) -> float:
    """Baseline: error-level analysis. Re-save at JPEG 90 and take the largest 16x16 block difference."""
    img = Image.open(path).convert("RGB")
    b = io.BytesIO()
    img.save(b, "JPEG", quality=90)
    d = np.abs(np.asarray(img, dtype="float32") - np.asarray(Image.open(io.BytesIO(b.getvalue())).convert("RGB"), dtype="float32")).mean(axis=2)
    h, w = (d.shape[0] // 16) * 16, (d.shape[1] // 16) * 16
    blocks = d[:h, :w].reshape(h // 16, 16, w // 16, 16).mean(axis=(1, 3))
    return float(blocks.max())
