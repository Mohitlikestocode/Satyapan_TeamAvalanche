"""FastAPI app: serves the web front end and a demo check API.

The check endpoint is a stub: it accepts what the user submits, discards it, and points to the matching *sample* result
page. No detection runs yet. Files are never written to disk.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .schemas import MAX_UPLOAD_BYTES, SAMPLE_RESULTS, CheckKind, CheckReceipt, WrongResultReport

WEB = Path(__file__).resolve().parents[3] / "web"
templates = Jinja2Templates(directory=WEB / "templates")

NAV = [
    ("home", "/", "Home", "मुख्य पृष्ठ"),
    ("check", "/check", "Check now", "जाँच करें"),
    ("dashboard", "/dashboard", "My checks", "मेरी जाँचें"),
    ("tools", "/tools", "Is this real?", "असली है?"),
    ("learn", "/learn", "Learn", "सीखें"),
    ("help", "/already-paid", "If you paid", "पैसे भेज दिए?"),
    ("how", "/how-it-works", "How it works", "कैसे काम करता है"),
]
RELATED = {
    "home": [],
    "dashboard": [],
    "check": [("See a sample result", "/result"), ("Is this really Amazon?", "/tools"), ("My checks", "/dashboard"), ("Scam Drill", "/learn/drill")],
    "help": [("Evidence report", "/report"), ("Complaint draft", "/report/complaint"), ("Warn others", "/warn"), ("Wrong result?", "/wrong")],
    "tools": [("Check something", "/check"), ("Shopkeeper check", "/shopkeeper"), ("Helper mode", "/helper"), ("Safety guide", "/learn/safety")],
    "learn": [("Scam Drill", "/learn/drill"), ("Safety guide", "/learn/safety"), ("Family safe-word card", "/learn/safe-word"), ("Check something", "/check")],
    "how": [("How it works", "/how-it-works"), ("System states", "/states"), ("Check something", "/check")],
}

app = FastAPI(title="Satyapan", version="0.1.0")

# case id -> receipt. In memory only; holds no file content.
_CASES: dict[str, CheckReceipt] = {}


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/samples")
def samples() -> dict[str, str]:
    return {k.value: v for k, v in SAMPLE_RESULTS.items()}


@app.post("/api/v1/check", response_model=CheckReceipt)
async def start_check(
    kind: CheckKind = Form(...),
    topic: str = Form("", max_length=80),
    speak_aloud: bool = Form(False),
    text: str = Form("", max_length=4000),
    file: UploadFile | None = File(None),
) -> CheckReceipt:
    if kind in (CheckKind.LINK, CheckKind.MESSAGE):
        if not text.strip():
            raise HTTPException(422, "text is required for this kind of check")
    else:
        if file is None:
            raise HTTPException(422, "a file is required for this kind of check")
        size = 0
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                raise HTTPException(413, "file is too large")
        await file.close()  # the content is discarded: nothing is stored
    receipt = CheckReceipt(
        id=uuid.uuid4().hex[:12],
        kind=kind,
        speak_aloud=speak_aloud,
        result_url=SAMPLE_RESULTS[kind],
    )
    _CASES[receipt.id] = receipt
    return receipt


@app.get("/api/v1/check/{case_id}", response_model=CheckReceipt)
def get_check(case_id: str) -> CheckReceipt:
    if case_id not in _CASES:
        raise HTTPException(404, "unknown or deleted check")
    return _CASES[case_id]


@app.delete("/api/v1/check/{case_id}", status_code=204)
def delete_check(case_id: str) -> None:
    _CASES.pop(case_id, None)


_REVIEW_QUEUE: list[dict[str, object]] = []


@app.post("/api/v1/wrong-result", status_code=201)
def wrong_result(report: WrongResultReport) -> dict[str, str]:
    """"Wrong verdict?": queue a note for human review. Holds the note only, never the user's file."""
    ref = uuid.uuid4().hex[:8]
    _REVIEW_QUEUE.append({"id": ref, **report.model_dump()})
    return {"id": ref, "status": "waiting_for_review"}


app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")


def _page_route(meta: dict):
    def view(request: Request) -> HTMLResponse:
        ctx = {"page": meta, "nav": NAV, "related": RELATED.get(meta["section"], [])}
        return templates.TemplateResponse(request, meta["template"], ctx)

    return view


PAGES = json.loads((WEB / "pages.json").read_text(encoding="utf-8"))
for _meta in PAGES:
    app.add_api_route("/" + _meta["route"], _page_route(_meta), methods=["GET"], response_class=HTMLResponse,
                      include_in_schema=False, name="page:" + (_meta["route"] or "home"))
