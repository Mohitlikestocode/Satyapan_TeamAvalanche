"""Load and run Spectra-AASIST3 (lab260/Spectra-AASIST3, Apache-2.0) the way its model card describes.

Input: float32 mono 16 kHz. Pre-emphasis 0.97, then windows of 64,600 samples (about 4 s; a short clip is tiled to fill one).
The model card scores only the first window. A voice note is longer, so we score up to MAX_WINDOWS consecutive windows and
average the bona-fide logits. Our threshold is calibrated on our own dev split with this same rule (training/voice/calibrate.py).
Output: the bona-fide logit, higher = more like a real voice.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

WIN = 64600
MAX_WINDOWS = 4


def windows(wav: np.ndarray, max_windows: int = MAX_WINDOWS) -> np.ndarray:
    x = np.append(wav[:1], wav[1:] - 0.97 * wav[:-1]).astype(np.float32)
    if len(x) < WIN:
        x = np.tile(x, int(np.ceil(WIN / max(1, len(x)))))[:WIN]
    n = max(1, min(max_windows, len(x) // WIN))
    return np.stack([x[i * WIN:(i + 1) * WIN] for i in range(n)])


class Spectra:
    name = "spectra-aasist3"

    def __init__(self, net, device: str):
        self.net, self.device = net, device

    def score(self, wav: np.ndarray) -> float:
        import torch
        x = torch.from_numpy(windows(wav)).to(self.device)
        with torch.inference_mode(), torch.autocast(device_type="cuda", enabled=self.device == "cuda"):
            logits = self.net(x).float()
        return float(logits[:, 1].mean())

    def score_batch(self, wavs: list[np.ndarray]) -> list[float]:
        return [self.score(w) for w in wavs]


def load(d: Path, device: str = "cpu") -> Spectra:
    from safetensors.torch import load_file
    from transformers import Wav2Vec2Config

    from .spectra_aasist3_net import SpectraAASIST3
    cfg = Wav2Vec2Config.from_json_file(str(Path(d) / "ssl_config.json"))
    net = SpectraAASIST3(ssl_config=cfg)
    missing, unexpected = net.load_state_dict(load_file(str(Path(d) / "model.safetensors")), strict=False)
    if missing:  # every weight must come from the checkpoint; a missing one means a wrong file
        raise RuntimeError(f"Spectra-AASIST3 checkpoint is missing {len(missing)} weights, e.g. {missing[:3]}")
    return Spectra(net.to(device).eval(), device)
