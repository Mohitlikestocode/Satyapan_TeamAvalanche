"""PDF checks: the text inside, and signs the file was changed after it was made.

Signs are weak on their own. Chat apps, printers and "save as" also rewrite PDFs, so a sign only counts together with a
payee or bank code in the same file (see fusion).
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from pypdf import PdfReader

from ...contracts.models import Layer, LayerResult, Signal, Strength

MAX_PAGES = 20
MAX_CHARS = 20000
EDIT_TOOLS = re.compile(r"ilovepdf|smallpdf|sejda|pdfescape|pdf24|soda\s*pdf|pdfcandy|pdf-candy|pdfelement|wondershare|nitro|photoshop|illustrator|canva", re.IGNORECASE)


@dataclass
class PdfInfo:
    text: str = ""
    pages: int = 0
    readable: bool = False
    result: LayerResult = field(default_factory=lambda: LayerResult(layer=Layer.L2))
    producer: str = ""


def analyse_pdf(data: bytes) -> PdfInfo:
    info = PdfInfo()
    if not data.startswith(b"%PDF"):
        return info
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted and not reader.decrypt(""):
            return info
        info.pages = len(reader.pages)
        text = []
        for page in reader.pages[:MAX_PAGES]:
            text.append(page.extract_text() or "")
            if sum(map(len, text)) > MAX_CHARS:
                break
        info.text = "\n".join(text)[:MAX_CHARS]
        info.readable = bool(info.text.strip())
        meta = reader.metadata
    except Exception:  # malformed or hostile file
        return info

    reasons: list[str] = []
    producer = f"{getattr(meta, 'producer', '') or ''} {getattr(meta, 'creator', '') or ''}" if meta else ""
    info.producer = producer.strip()[:80]
    if EDIT_TOOLS.search(producer):
        reasons.append("edit_tool")
    try:
        created, modified = (meta.creation_date, meta.modification_date) if meta else (None, None)
        if created and modified and (modified - created).total_seconds() > 60:
            reasons.append("modified_later")
    except Exception:  # unparseable date strings are common
        pass
    if data.count(b"%%EOF") >= 2:
        reasons.append("incremental_update")
    signals = [Signal(layer=Layer.L2, code="PDF_EDIT_TRACES", strength=Strength.WEAK_SUSPICIOUS, params={})] if reasons else []
    info.result = LayerResult(layer=Layer.L2, signals=signals, model_versions={"pdf": "pypdf-rules-1"},
                              internal={"reasons": reasons})
    return info
