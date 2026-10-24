"""L3: who is asking for the money? Deterministic checks on UPI payees, links and claimed names."""
from __future__ import annotations

import re

from rapidfuzz import fuzz

from ...contracts.models import Layer, LayerResult, Signal, Strength
from ...extract.banks import bank_codes_named
from ...extract.entities import Found, UpiRequest
from ..l4_rules import layer as l4_rules
from .domains import hostname, lookalike

# SEBI-registered brokers (.brk) and mutual-fund distributors (.mf) collect only on @valid<bank> handles.
VALID_FORMAT = re.compile(r"^[a-z0-9._\-]+\.(brk|mf)$")
TRIGGER_ORDER = ["guaranteed_returns", "fixed_periodic_return", "fee_to_withdraw", "vip_group"]


def _is_valid_handle(req: UpiRequest) -> bool:
    return req.handle.startswith("valid") and bool(VALID_FORMAT.match(req.local))


def run(text: str, found: Found, l4_signals: list[Signal], snapshot: dict | None = None, topic_investment: bool = False) -> LayerResult:
    """`l4_signals` supplies the offer words (the trigger in a payee reason); `snapshot` is the dated SEBI list, if loaded."""
    signals: list[Signal] = []
    triggers = [s.params["trigger"] for s in l4_signals if s.params.get("trigger")]
    trigger = next((t for t in TRIGGER_ORDER if t in triggers), None)
    invest = topic_investment or l4_rules.investment_context(text) or bool(trigger) or bool(found.claimed)
    urgent = any(s.code == "OFFER_URGENCY" for s in l4_signals)

    for req in found.upi:
        listed = bool(snapshot) and req.vpa.lower() in {h.lower() for h in snapshot.get("handles", [])}
        if _is_valid_handle(req):
            if listed:
                signals.append(Signal(layer=Layer.L3, code="PAYEE_VALID_REGISTERED", strength=Strength.WEAK_AUTHENTIC,
                                      params={"payee": req.vpa, "snapshot_date": snapshot["date"]}))
            elif snapshot:
                signals.append(Signal(layer=Layer.L3, code="PAYEE_FAKE_VALID_HANDLE", strength=Strength.STRONG_SUSPICIOUS,
                                      params={"payee": req.vpa, "snapshot_date": snapshot["date"]}))
            else:
                signals.append(Signal(layer=Layer.L3, code="PAYEE_FORMAT_ONLY", strength=Strength.NONE, params={"payee": req.vpa}))
        elif req.handle.startswith("valid"):
            # looks like an @valid handle but is not a .brk/.mf broker or fund handle
            signals.append(Signal(layer=Layer.L3, code="PAYEE_FORMAT_ONLY", strength=Strength.NONE, params={"payee": req.vpa}))
        elif invest:
            if trigger:
                signals.append(Signal(layer=Layer.L3, code="PAYEE_NOT_VALID_HANDLE", strength=Strength.STRONG_SUSPICIOUS,
                                      params={"payee": req.vpa, "trigger": trigger}))
            else:
                signals.append(Signal(layer=Layer.L3, code="PAYEE_PERSONAL_ACCOUNT", strength=Strength.WEAK_SUSPICIOUS,
                                      params={"payee": req.vpa}))
        if req.name and found.claimed and fuzz.token_set_ratio(req.name.lower(), found.claimed.lower()) < 60:
            signals.append(Signal(layer=Layer.L3, code="PAYEE_NAME_MISMATCH", strength=Strength.WEAK_SUSPICIOUS,
                                  params={"claimed": found.claimed, "payee_name": req.name}))
        if req.amount and urgent:
            signals.append(Signal(layer=Layer.L3, code="PAYEE_PREFILLED_URGENCY", strength=Strength.WEAK_SUSPICIOUS))

    if l4_rules.has_collect_trap(text):
        signals.append(Signal(layer=Layer.L3, code="PAYEE_COLLECT_TRAP", strength=Strength.STRONG_SUSPICIOUS))

    for url in found.urls:
        host = hostname(url)
        if not host:
            continue
        if lookalike(host):
            signals.append(Signal(layer=Layer.L3, code="LINK_LOOKALIKE_DOMAIN", strength=Strength.STRONG_SUSPICIOUS,
                                  params={"domain": host[:60]}))
        if url.lower().split("?")[0].endswith(".apk"):
            signals.append(Signal(layer=Layer.L3, code="LINK_APK", strength=Strength.STRONG_SUSPICIOUS))
    if l4_rules.has_apk(text) and not any(s.code == "LINK_APK" for s in signals):
        signals.append(Signal(layer=Layer.L3, code="LINK_APK", strength=Strength.STRONG_SUSPICIOUS))

    named = bank_codes_named(text)
    for ifsc in found.ifsc:
        if named and ifsc[:4] not in named:
            signals.append(Signal(layer=Layer.L3, code="INVOICE_IFSC_MISMATCH", strength=Strength.STRONG_SUSPICIOUS,
                                  params={"ifsc": ifsc, "bank": ", ".join(sorted(named.values()))[:40]}))
    for bad in found.ifsc_invalid:
        signals.append(Signal(layer=Layer.L3, code="INVOICE_IFSC_INVALID", strength=Strength.WEAK_SUSPICIOUS, params={"ifsc": bad}))
    for ref in found.utr_invalid:
        signals.append(Signal(layer=Layer.L3, code="PAYMENT_UTR_FORMAT", strength=Strength.WEAK_SUSPICIOUS))
        break

    seen: set[tuple[str, str]] = set()
    unique = []
    for s in signals:
        key = (s.code, str(sorted(s.params.items())))
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return LayerResult(layer=Layer.L3, signals=unique, model_versions={"payee": "rules-1"})
