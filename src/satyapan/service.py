"""Run a check end to end on text (a message, a pasted link, or text decoded from a QR code)."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .contracts.models import (FusionInput, Lang, Layer, LayerResult, QualityReport, Strength, Tier, Verdict)
from .extract.entities import Found, extract
from .fusion.rules import fuse
from .layers.l3_payee import layer as l3
from .layers.l4_rules import layer as l4
from .reasons.render import build_verdict

SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "data" / "sebi_snapshot.json"
MAX_TEXT = 4000


def load_snapshot() -> dict | None:
    """Dated offline copy of the SEBI broker/fund handle list. None until one is downloaded: then no handle is confirmed."""
    try:
        return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@dataclass
class CaseResult:
    case_id: str
    kind: str
    tier: Tier
    verdicts: dict[str, Verdict]
    payees: list[dict[str, str]] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    layers_run: list[str] = field(default_factory=list)


def analyse_text(text: str, kind: str = "message", topic: str = "", case_id: str | None = None) -> CaseResult:
    """Text is untrusted data. It is only matched against fixed patterns and never chooses a template or a tier."""
    case_id = case_id or uuid.uuid4().hex[:12]
    text = (text or "")[:MAX_TEXT]
    quality = QualityReport(usable_for_any=bool(text.strip()), reasons=[] if text.strip() else ["QUALITY_UNREADABLE"])
    found: Found = extract(text)
    snapshot = load_snapshot()

    l4res = l4.run(text)
    l3res = l3.run(text, found, l4res.signals, snapshot=snapshot, topic_investment=topic.strip().lower().startswith("investment"))
    payee_confirmed = None
    if found.upi:
        payee_confirmed = any(s.code == "PAYEE_VALID_REGISTERED" for s in l3res.signals)
    out = fuse(FusionInput(results=[l3res, l4res], quality=quality, media_present=False, payees_confirmed_registered=payee_confirmed))
    verdicts = {lang.value: build_verdict(case_id, out, lang) for lang in Lang}
    return CaseResult(
        case_id=case_id, kind=kind, tier=out.tier, verdicts=verdicts,
        payees=[{"upi": u.vpa, "name": u.name or "", "amount": u.amount or ""} for u in found.upi],
        links=found.urls[:5], phones=found.phones[:5], layers_run=["payee", "rules"],
    )
