"""Request/response shapes for the check API."""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class CheckKind(StrEnum):
    SCREENSHOT = "screenshot"
    PDF = "pdf"
    QR = "qr"
    LINK = "link"
    MESSAGE = "message"
    VOICE = "voice"


# Demo wiring only: which sample result page each kind of check points to until real detection exists.
SAMPLE_RESULTS: dict[CheckKind, str] = {
    CheckKind.SCREENSHOT: "/result/screenshot",
    CheckKind.PDF: "/result/invoice",
    CheckKind.QR: "/result/qr",
    CheckKind.LINK: "/result/qr",
    CheckKind.MESSAGE: "/tools/result",
    CheckKind.VOICE: "/check/voice",
}


class WrongResultReport(BaseModel):
    reason: str = Field("", max_length=200)
    note: str = Field("", max_length=2000)
    share_for_review: bool = False


class CheckReceipt(BaseModel):
    id: str
    kind: CheckKind
    speak_aloud: bool = False
    result_url: str
    mode: str = "demo-sample"  # "engine" when the real checks ran
    tier: str | None = None
    notice: str = "Demo: no detection has run. This points to a sample result."
