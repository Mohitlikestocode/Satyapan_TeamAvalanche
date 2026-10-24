"""Check API: run a check, read or delete the result, dispute a verdict, read the signed evidence pack."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..evidence.pack import build_pack, sign_pack, verify_signed
from ..extract.qr import decode_qr
from ..service import analyse_text
from ..store import db
from .schemas import MAX_UPLOAD_BYTES, SAMPLE_RESULTS, CheckKind, CheckReceipt, DisputeIn

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/samples")
def samples() -> dict[str, str]:
    return {k.value: v for k, v in SAMPLE_RESULTS.items()}


@router.post("/check", response_model=CheckReceipt)
async def start_check(
    kind: CheckKind = Form(...),
    topic: str = Form("", max_length=80),
    speak_aloud: bool = Form(False),
    text: str = Form("", max_length=4000),
    file: UploadFile | None = File(None),
) -> CheckReceipt:
    db.purge()
    case_id = uuid.uuid4().hex[:12]
    payload: str | None
    if kind in (CheckKind.LINK, CheckKind.MESSAGE):
        if not text.strip():
            raise HTTPException(422, "text is required for this kind of check")
        payload = text
    else:
        if file is None:
            raise HTTPException(422, "a file is required for this kind of check")
        data = bytearray()
        while chunk := await file.read(1024 * 1024):
            data += chunk
            if len(data) > MAX_UPLOAD_BYTES:
                raise HTTPException(413, "file is too large")
        await file.close()  # the content is discarded after this request: nothing is written to disk
        payload = None
        if kind == CheckKind.QR:
            payload = " ".join(decode_qr(bytes(data))) + (" " + text if text else "")
    if payload is None:  # screenshot, PDF and voice checks are not built yet: point to a labelled sample
        return CheckReceipt(id=case_id, kind=kind, speak_aloud=speak_aloud, result_url=SAMPLE_RESULTS[kind])
    res = analyse_text(payload, kind=kind.value, topic=topic, case_id=case_id)
    db.save_case(res, topic)
    return CheckReceipt(id=case_id, kind=kind, speak_aloud=speak_aloud, result_url=f"/case/{case_id}", mode="engine",
                        tier=res.tier.value, notice="Checked with the payee and red-flag rules.")


@router.get("/case/{case_id}")
def get_case(case_id: str) -> dict:
    c = db.get_case(case_id)
    if c is None:
        raise HTTPException(404, "unknown or deleted check")
    v = c.verdicts["en"]
    return {"id": c.case_id, "tier": c.tier.value, "headline": v.headline, "reasons": v.reasons_text,
            "reason_codes": v.reason_codes, "action": v.action_text, "outcome": c.outcome or None,
            "share_token": c.share_token}


@router.delete("/check/{case_id}", status_code=204)
def delete_check(case_id: str) -> None:
    db.delete_case(case_id)


@router.post("/wrong-result", status_code=201)
def wrong_result(report: DisputeIn) -> dict[str, str]:
    """"Wrong result?": send the case to a human reviewer. Reviewers see details only if the user agreed to share."""
    case_id = report.case_id if report.case_id and db.get_case(report.case_id) else None
    ref = db.create_review(case_id, report.reason, report.note, report.share_for_review)
    return {"id": ref, "status": "needs_review"}


@router.get("/review/{ref}")
def review_status(ref: str) -> dict:
    r = db.get_review(ref)
    if r is None:
        raise HTTPException(404, "unknown review")
    return {"ref": r["ref"], "status": r["status"], "decided": r["decided"]}


@router.get("/evidence/{case_id}")
def evidence(case_id: str) -> dict:
    c = db.get_case(case_id)
    if c is None:
        raise HTTPException(404, "unknown or deleted check")
    return sign_pack(build_pack(c))


@router.post("/evidence/verify")
def evidence_verify(signed: dict) -> dict[str, bool]:
    return {"valid": verify_signed(signed)}
