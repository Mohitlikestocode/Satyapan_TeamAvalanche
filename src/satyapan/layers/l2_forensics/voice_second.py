"""Second-opinion voice detector: MelodyMachine/Deepfake-audio-detection-V2 (wav2vec2-base classifier, Apache-2.0).

Its training data is not documented by its authors, so it is used only as a second opinion: when it disagrees with the
primary detector, we say nothing about the voice. Score = logit(real) - logit(fake), averaged over up to MAX_WINDOWS
windows of WIN samples; higher = more like a real voice. The threshold is calibrated on our own dev split.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

WIN = 16000 * 4
MAX_WINDOWS = 2


class Second:
    name = "melody-deepfake-v2"

    def __init__(self, model, fe, device: str, real: int, fake: int):
        self.model, self.fe, self.device, self.real, self.fake = model, fe, device, real, fake

    def score(self, wav: np.ndarray) -> float:
        import torch
        n = max(1, min(MAX_WINDOWS, len(wav) // WIN))
        chunks = [wav[i * WIN:(i + 1) * WIN] for i in range(n)] if len(wav) >= WIN else [wav]
        inp = self.fe(chunks, sampling_rate=16000, return_tensors="pt", padding=True)
        with torch.inference_mode():
            logits = self.model(**{k: v.to(self.device) for k, v in inp.items()}).logits.float()
        return float((logits[:, self.real] - logits[:, self.fake]).mean())


def load(d: Path, device: str = "cpu") -> Second:
    from transformers import AutoFeatureExtractor, Wav2Vec2ForSequenceClassification
    model = Wav2Vec2ForSequenceClassification.from_pretrained(str(d)).to(device).eval()
    fe = AutoFeatureExtractor.from_pretrained(str(d))
    labels = {v.lower(): int(k) for k, v in model.config.id2label.items()}
    return Second(model, fe, device, labels["real"], labels["fake"])
