"""Signed evidence pack: a canonical JSON summary of one check, hashed and signed with Ed25519.

The pack holds the verdict, the reasons, the validated payee details and what was not checked. It never holds the
user's file or the raw message. The signing key is created on first use under $SATYAPAN_HOME/keys (git-ignored).
Timestamps come from this server's clock unless a trusted time-stamp service is added.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ..store import db

IST = timezone(timedelta(hours=5, minutes=30))
SCHEMA_VERSION = 1


def _key() -> Ed25519PrivateKey:
    path = db.home() / "keys" / "ed25519.key"
    if path.exists():
        return serialization.load_pem_private_key(path.read_bytes(), password=None)  # type: ignore[return-value]
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return key


def public_key_id() -> str:
    raw = _key().public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()[:16]


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def report_id(case_id: str) -> str:
    return f"SP-{case_id[:4].upper()}-{case_id[4:8].upper()}"


def build_pack(case: db.StoredCase) -> dict:
    v = case.verdicts["en"]
    when = datetime.fromtimestamp(case.created, IST)
    return {
        "schema": SCHEMA_VERSION,
        "report_id": report_id(case.case_id),
        "created_ist": when.strftime("%d %b %Y, %H:%M IST"),
        "created_unix": case.created,
        "clock": "this server's clock (no trusted time-stamp service)",
        "kind": case.kind,
        "tier": case.tier.value,
        "headline": v.headline,
        "reasons": v.reasons_text,
        "reason_codes": v.reason_codes,
        "payees": case.payees,
        "links": case.links,
        "phones_masked": [p[:2] + "XXXXXX" + p[-2:] for p in case.phones],
        "checks_run": case.layers_run,
        "not_checked": "Images, voice and video forensics were not used for this result.",
        "reviewer_outcome": case.outcome or None,
        "audit_head": (db.audit_list(1) or [{"hash": ""}])[0]["hash"],
        "note": "Shows signs only; not proof. Advisory: nothing was blocked, paid or filed.",
    }


def sign_pack(pack: dict) -> dict:
    body = canonical(pack)
    sig = _key().sign(body)
    return {"pack": pack, "sha256": hashlib.sha256(body).hexdigest(), "algorithm": "Ed25519",
            "key_id": public_key_id(), "signature": base64.b64encode(sig).decode()}


def verify_signed(signed: dict) -> bool:
    try:
        body = canonical(signed["pack"])
        if hashlib.sha256(body).hexdigest() != signed["sha256"]:
            return False
        _key().public_key().verify(base64.b64decode(signed["signature"]), body)
        return True
    except (KeyError, ValueError, InvalidSignature):
        return False
