"""Scam-message classifier: multilingual-e5-small with a classification head (training/text/train_classifier.py).

It only ever adds a WEAK sign (ML_TEXT_SCAM_LIKE); the rules, the payee check and fusion still decide the verdict.
Installed at $SATYAPAN_HOME/models/scam_text/ (config.json + weights). The config says whether it is enabled: it is
switched on only if it improved held-out results without more false alarms (see docs/models.md).
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from ...store import db

log = logging.getLogger("satyapan.scam_model")
MAX_LEN = 128
_LOCK = threading.Lock()
_CACHE: dict = {}


def model_dir() -> Path:
    return db.home() / "models" / "scam_text"


def config() -> dict | None:
    try:
        return json.loads((model_dir() / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class ScamModel:
    def __init__(self, enc, tok, head, device: str, mode: str):
        self.enc, self.tok, self.head, self.device, self.mode = enc, tok, head, device, mode

    def embed(self, texts: list[str]):
        import torch
        b = self.tok(["query: " + t for t in texts], padding=True, truncation=True, max_length=MAX_LEN, return_tensors="pt").to(self.device)
        out = self.enc(**b).last_hidden_state
        m = b["attention_mask"].unsqueeze(-1).float()
        e = (out * m).sum(1) / m.sum(1).clamp(min=1)
        return torch.nn.functional.normalize(e, dim=-1)

    def prob(self, texts: list[str]) -> list[float]:
        import torch
        with torch.inference_mode():
            return torch.sigmoid(self.head(self.embed(texts)).squeeze(-1)).float().cpu().tolist()


def load(d: Path | None = None, device: str | None = None) -> ScamModel | None:
    d = d or model_dir()
    cfg = config() if d == model_dir() else json.loads((d / "config.json").read_text(encoding="utf-8"))
    if not cfg:
        return None
    key = (str(d), cfg.get("made"))
    with _LOCK:
        if key not in _CACHE:
            try:
                import torch
                from transformers import AutoModel, AutoTokenizer
                dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
                base = Path(cfg["encoder_dir"]) if cfg.get("mode") == "head" else d / "encoder"
                if not base.is_absolute():
                    base = db.home() / "models" / base
                tok = AutoTokenizer.from_pretrained(str(base))
                enc = AutoModel.from_pretrained(str(base)).to(dev).eval()
                head = torch.nn.Linear(enc.config.hidden_size, 1)
                head.load_state_dict(torch.load(d / "head.pt", map_location="cpu", weights_only=True))
                _CACHE.clear()
                _CACHE[key] = ScamModel(enc, tok, head.to(dev).eval(), dev, cfg.get("mode", "head"))
            except Exception:
                log.exception("could not load the scam-message model")
                return None
        return _CACHE[key]
