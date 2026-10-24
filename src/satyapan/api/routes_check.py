"""Check API: run a check, read or delete the result, dispute a verdict, read the signed evidence pack."""
from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ..evidence.pack import build_pack, sign_pack, verify_signed
from ..extract.qr import decode_qr
from ..plugins import REGISTRY
from ..service import analyse_image, analyse_pdf, analyse_text
from ..store import db
from .schemas import MAX_UPLOAD_BYTES, SAMPLE_RESULTS, CheckKind, CheckReceipt, DisputeIn

router = APIRouter(prefix="/api/v1")


def res_text(data: bytes, typed: str) -> str:
    """Text from the image (QR payloads and OCR) joined with what the user typed."""
    from ..extract.ocr import read_text
    qr = decode_qr(data)
    return "\n".join([*qr, read_text(data) or "", typed])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/samples")
def samples() -> dict[str, str]:
    return {k.value: v for k, v in SAMPLE_RESULTS.items()}


@router.post("/check", response_model=CheckReceipt)
async def start_check(
    request: Request,
    kind: CheckKind = Form(...),
    topic: str = Form("", max_length=80),
    speak_aloud: bool = Form(False),
    text: str = Form("", max_length=4000),
    channel: str = Form("web", max_length=20),
    file: UploadFile | None = File(None),
) -> CheckReceipt:
    t0 = time.perf_counter()
    db.purge()
    case_id = uuid.uuid4().hex[:12]
    res = None
    if kind in (CheckKind.LINK, CheckKind.MESSAGE):
        if not text.strip():
            raise HTTPException(422, "text is required for this kind of check")
        res = analyse_text(text, kind=kind.value, topic=topic, case_id=case_id)
    else:
        if file is None:
            raise HTTPException(422, "a file is required for this kind of check")
        data = bytearray()
        while chunk := await file.read(1024 * 1024):
            data += chunk
            if len(data) > MAX_UPLOAD_BYTES:
                raise HTTPException(413, "file is too large")
        await file.close()  # the content is discarded after this request: nothing is written to disk
        handler = REGISTRY.handlers.get(kind.value)
        if handler is not None:  # a plugin owns this kind, for example "voice"
            res = handler(bytes(data), topic, case_id)
        elif kind == CheckKind.PDF:
            res = analyse_pdf(bytes(data), topic=topic, case_id=case_id)
        elif kind in (CheckKind.QR, CheckKind.SCREENSHOT):
            res = analyse_image(bytes(data), kind=kind.value, topic=topic, case_id=case_id)
            if text.strip():  # words the user typed alongside the picture are checked too
                res = analyse_text(res_text(bytes(data), text), kind=kind.value, topic=topic, case_id=case_id)
    elapsed = int((time.perf_counter() - t0) * 1000)
    event = {"case_id": case_id, "kind": kind.value, "channel": channel, "elapsed_ms": elapsed,
             "device": request.cookies.get("sp_dev"), "internal": request.cookies.get("sp_internal") == "1"}
    if res is None:  # voice checks without a handler: point to a labelled sample
        REGISTRY.emit("check", {**event, "mode": "demo-sample", "tier": None})
        return CheckReceipt(id=case_id, kind=kind, speak_aloud=speak_aloud, result_url=SAMPLE_RESULTS[kind])
    db.save_case(res, topic)
    REGISTRY.emit("check", {**event, "mode": "engine", "tier": res.tier.value})
    return CheckReceipt(id=case_id, kind=kind, speak_aloud=speak_aloud, result_url=f"/case/{case_id}", mode="engine",
                        tier=res.tier.value, notice="Checked with the payee and red-flag rules.", text_read=res.text_read or None)


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
    if db.delete_case(case_id):
        REGISTRY.emit("delete", {"case_id": case_id})


@router.post("/wrong-result", status_code=201)
def wrong_result(report: DisputeIn) -> dict[str, str]:
    """"Wrong result?": send the case to a human reviewer. Reviewers see details only if the user agreed to share."""
    case_id = report.case_id if report.case_id and db.get_case(report.case_id) else None
    ref = db.create_review(case_id, report.reason, report.note, report.share_for_review)
    REGISTRY.emit("dispute", {"ref": ref, "case_id": case_id})
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
