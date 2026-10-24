"""Scam-message model as a text hook: adds a WEAK sign (ML_TEXT_SCAM_LIKE) when the wording is close to known scams.

Off unless $SATYAPAN_HOME/models/scam_text/config.json says "enabled": true, which training/text/decide.py sets only if the
model improved held-out results without more false alarms. It reads the text after the hidden-word clean-up.
"""
from __future__ import annotations

from ..contracts.models import Layer, LayerResult, Signal, Strength
from ..layers.l4_semantic import scam_model
from ..layers.l4_semantic.normalise import normalise

MIN_CHARS = 12


def scam_like(text: str, found) -> LayerResult | None:
    cfg = scam_model.config()
    if not cfg or not cfg.get("enabled") or len(text.strip()) < MIN_CHARS:
        return None
    m = scam_model.load()
    if m is None:
        return None
    p = m.prob([normalise(text).text[:2000]])[0]
    if p <= float(cfg["threshold"]):
        return None
    return LayerResult(layer=Layer.L4, signals=[Signal(layer=Layer.L4, code="ML_TEXT_SCAM_LIKE", strength=Strength.WEAK_SUSPICIOUS)],
                       model_versions={"scam_text": f"e5-small-{cfg.get('mode')}-{cfg.get('made')}"}, internal={"label_key": "ml_text", "p": p})


# trained on chat-style scam messages: on OCR text of payment screens, QR payloads, links and invoices it fires on ordinary payment wording
scam_like.skip_kinds = ("screenshot", "pdf", "qr", "link")


def setup(registry) -> None:
    registry.add_text_hook(scam_like, "ml_text", "Scam-message model (wording compared with known scams)",
                           "स्कैम-संदेश मॉडल (शब्दों की तुलना जाने-पहचाने स्कैम से)")
