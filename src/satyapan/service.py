"""Run a check end to end on text (a message, a pasted link, or text decoded from a QR code, a PDF or an image)."""
from __future__ import annotations

import json
import logging
import re
import uuid
from urllib.parse import unquote
from dataclasses import dataclass, field
from pathlib import Path

from .contracts.models import FusionInput, Lang, LayerResult, QualityReport, Tier, Verdict
from .extract.entities import Found, extract
from .fusion.rules import fuse
from .layers.l3_payee import layer as l3
from .layers.l4_rules import layer as l4
from .plugins import REGISTRY
from .reasons.render import build_verdict

log = logging.getLogger("satyapan.service")
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
    text_read: str = ""       # what the check read from the input; handed to the visitor's own browser only, never saved


def _run_hooks(hooks, *args) -> list[LayerResult]:
    out = []
    for fn in hooks:
        try:
            r = fn(*args)
        except Exception:  # a broken plugin must not break a check
            log.exception("hook %s failed", getattr(fn, "__name__", fn))
            continue
        if r is not None:
            out.append(r)
    return out


def analyse_text(text: str, kind: str = "message", topic: str = "", case_id: str | None = None, use_registry: bool = True,
                 extra_layers: list[LayerResult] | None = None, readable: bool = True, extra_names: list[str] | None = None,
                 use_plugins: bool = True, receipt: bool = False) -> CaseResult:
    """Text is untrusted data. It is only matched against fixed patterns and never chooses a template or a tier."""
    case_id = case_id or uuid.uuid4().hex[:12]
    text = (text or "")[:MAX_TEXT]
    usable = bool(text.strip()) and readable
    quality = QualityReport(usable_for_any=usable, reasons=[] if usable else ["QUALITY_UNREADABLE"])
    found: Found = extract(text)
    snapshot = load_snapshot()

    l4res = l4.run(text)
    l3res = l3.run(text, found, l4res.signals, snapshot=snapshot, topic_investment=topic.strip().lower().startswith("investment"))
    if receipt:
        # a payment receipt shows who WAS paid; it is not a request to pay, so the recipient alone must not flag it
        l3res = l3res.model_copy(update={"signals": [x for x in l3res.signals if x.code != "PAYEE_PERSONAL_ACCOUNT"]})
    payee_confirmed = None
    if found.upi:
        payee_confirmed = any(s.code == "PAYEE_VALID_REGISTERED" for s in l3res.signals)
    matches = []
    if use_registry:
        from .layers.l3_payee.domains import hostname
        from .store import db
        matches = db.registry_matches([u.vpa for u in found.upi], [h for h in (hostname(u) for u in found.urls) if h])
    # a hook can opt out of some kinds with `skip_kinds` (the scam-message model was trained on messages, not on payment screens or QR payloads)
    hooks = [h for h in REGISTRY.text_hooks if kind not in getattr(h, "skip_kinds", ()) and not (receipt and getattr(h, "skip_receipt", False))]
    hooked = _run_hooks(hooks, text, found) if (use_plugins and usable) else []
    out = fuse(FusionInput(results=[l3res, l4res, *(extra_layers or []), *hooked], registry_matches=matches, quality=quality, media_present=False,
                           payees_confirmed_registered=payee_confirmed, money_ask_present=bool(found.upi or found.ifsc or found.urls)))
    verdicts = {lang.value: build_verdict(case_id, out, lang) for lang in Lang}
    names = ["payee", "rules"] + list(extra_names or []) + [r.internal.get("label_key", "") for r in hooked if r.internal.get("label_key")]
    return CaseResult(
        case_id=case_id, kind=kind, tier=out.tier, verdicts=verdicts,
        payees=[{"upi": u.vpa, "name": u.name or "", "amount": u.amount or ""} for u in found.upi],
        links=found.urls[:5], phones=found.phones[:5], layers_run=names, text_read=text[:3000],
    )


def analyse_pdf(data: bytes, topic: str = "", case_id: str | None = None) -> CaseResult:
    """Read the PDF's text and look for signs of editing, then run the same payee and word checks as for a message."""
    from .layers.l2_forensics.pdf import analyse_pdf as read_pdf
    info = read_pdf(data)
    return analyse_text(info.text, kind="pdf", topic=topic or "invoice", case_id=case_id, extra_layers=[info.result], readable=info.readable,
                        extra_names=["pdf"])


RECEIPT_RE = re.compile(
    r"(payment|paid|transfer|transaction|txn)\s*(is\s+)?(successful|success|completed?|done)|paid\s+to|debited\s+from|utr|upi\s*(ref|transaction)|transaction\s*id|txn\s*id|भुगतान\s*सफल",
    re.IGNORECASE)
REQUEST_RE = re.compile(r"(pay\s+now|scan\s+(to|the)\s+pay|collect\s+request|approve\s+the\s+request|enter\s+(your\s+)?(upi\s+)?pin)", re.IGNORECASE)


def looks_like_receipt(text: str) -> bool:
    """Payment-success wording and no request to pay."""
    return bool(RECEIPT_RE.search(text)) and not REQUEST_RE.search(text)


def analyse_image(data: bytes, kind: str = "screenshot", topic: str = "", case_id: str | None = None) -> CaseResult:
    """Decode any QR code, read the text, and run the picture checks (tamper model and any image hooks)."""
    from .extract.ocr import read_text
    from .extract.qr import decode_qr
    qr = decode_qr(data)
    ocr = read_text(data)  # the words printed next to a QR ("scan to receive", "enter PIN") matter as much as the code
    parts = [unquote(q) for q in qr] + ([ocr] if ocr else [])  # %20 and friends hide the words in a UPI note from the rules
    layers: list[LayerResult] = []
    names: list[str] = []
    if kind != "qr":
        from .layers.l2_forensics import screenshot
        forensic = screenshot.run(data)
        if forensic is not None:
            layers.append(forensic)
            names.append("image")
        for r in _run_hooks(REGISTRY.image_hooks, data):
            layers.append(r)
            if r.internal.get("label_key"):
                names.append(r.internal["label_key"])
    joined = "\n".join(parts)
    return analyse_text(joined, kind=kind, topic=topic, case_id=case_id, readable=bool(parts),
                        extra_layers=layers or None, extra_names=names or None,
                        receipt=(kind == "screenshot" and looks_like_receipt(joined)))
