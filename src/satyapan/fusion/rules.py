"""Fusion: turn layer signals into a verdict tier. Monotone and auditable.

- HIGH RISK needs two independent layers that each have a strong signal, or a registry hit.
- Forensics (L2) alone caps at SUSPICIOUS. One weak signal never gives HIGH RISK.
- Failed quality gate or conflicting evidence gives CAN'T TELL.
- Nothing found gives NO RED FLAGS FOUND, which always carries the "not a guarantee" line.
"""
from __future__ import annotations

import yaml
from pathlib import Path

from ..contracts.models import FusionInput, FusionOutput, Layer, ReasonRef, Strength, Tier

_CAT = yaml.safe_load((Path(__file__).resolve().parents[1] / "reasons" / "catalogue.yaml").read_text(encoding="utf-8"))
PRIORITY = {code: v["priority"] for code, v in _CAT["codes"].items()}
CLAIM = {Layer.L3, Layer.L4}


def fuse(inp: FusionInput) -> FusionOutput:
    signals = [s for r in inp.results for s in r.signals]
    reasons: list[ReasonRef] = []
    notes: list[str] = []

    if inp.registry_matches:
        for m in inp.registry_matches:
            code = {"payee": "REG_PAYEE", "url": "REG_URL"}.get(m.kind, "REG_MEDIA")
            params = {"payee": m.value} if m.kind == "payee" else {"domain": m.value} if m.kind == "url" else {}
            reasons.append(ReasonRef(code=code, params=params))
        reasons += [ReasonRef(code=s.code, params=s.params) for s in signals if s.strength.suspicious]
        return FusionOutput(tier=Tier.REGISTRY_HIT, reasons=_order(reasons))

    if not inp.quality.usable_for_any:
        reasons = [ReasonRef(code=c) for c in inp.quality.reasons] or [ReasonRef(code="QUALITY_UNREADABLE")]
        return FusionOutput(tier=Tier.CANT_TELL, reasons=_order(reasons), manual_steps=True)

    strong_layers = {s.layer for s in signals if s.strength == Strength.STRONG_SUSPICIOUS}
    suspicious = [s for s in signals if s.strength.suspicious]
    authentic_strong = [s for s in signals if s.strength == Strength.STRONG_AUTHENTIC]
    claim_strong = strong_layers & CLAIM

    if suspicious and authentic_strong and not claim_strong:
        # strong authenticity evidence against weak suspicion: do not guess
        reasons = [ReasonRef(code="CONFLICT_MEDIA")] + [ReasonRef(code=s.code, params=s.params) for s in suspicious]
        return FusionOutput(tier=Tier.CANT_TELL, reasons=_order(reasons), manual_steps=True)

    if len(strong_layers) >= 2 and claim_strong:
        tier = Tier.HIGH_RISK
    elif strong_layers or len({s.code for s in suspicious}) >= 2 or (suspicious and inp.money_ask_present):
        tier = Tier.SUSPICIOUS
    else:
        tier = Tier.NO_RED_FLAGS

    reasons = [ReasonRef(code=s.code, params=s.params) for s in suspicious] if tier != Tier.NO_RED_FLAGS else []
    if tier == Tier.NO_RED_FLAGS:
        reasons += [ReasonRef(code=s.code, params=s.params) for s in signals if s.code in ("PAYEE_FORMAT_ONLY", "PAYEE_VALID_REGISTERED")]
        if not _has_payee(signals, inp):
            reasons.append(ReasonRef(code="NO_PAYEE_FOUND"))
        reasons.append(ReasonRef(code="NO_FLAGS_NOT_GUARANTEE"))
    elif inp.payees_confirmed_registered is False:
        reasons.append(ReasonRef(code="PAYEE_UNVERIFIED"))
    return FusionOutput(tier=tier, reasons=_order(reasons), notes=notes)


def _has_payee(signals, inp: FusionInput) -> bool:
    return inp.payees_confirmed_registered is not None or any(s.code.startswith("PAYEE_") for s in signals)


def _order(reasons: list[ReasonRef]) -> list[ReasonRef]:
    seen, out = set(), []
    for r in sorted(reasons, key=lambda r: PRIORITY.get(r.code, 99)):
        key = (r.code, tuple(sorted(r.params.items())))
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out
