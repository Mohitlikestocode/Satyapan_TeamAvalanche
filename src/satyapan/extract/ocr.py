"""Read text from an image. Uses Tesseract (English + Hindi) when it is installed, else RapidOCR, else reports "unavailable".

Everything stays in memory. The text that comes back is untrusted data: it is matched against fixed patterns only.
"""
from __future__ import annotations

import io
import shutil
from functools import lru_cache

MAX_CHARS = 8000


@lru_cache(maxsize=1)
def _rapid():
    try:
        from rapidocr_onnxruntime import RapidOCR
        return RapidOCR()
    except Exception:  # not installed, or the runtime failed to start
        return None


def engine_name() -> str | None:
    if shutil.which("tesseract"):
        try:
            import pytesseract  # noqa: F401
            return "tesseract"
        except ImportError:
            pass
    return "rapidocr" if _rapid() is not None else None


def read_text(data: bytes) -> str | None:
    """Return the text found in the image, "" if none, or None when no OCR engine is available."""
    name = engine_name()
    if name is None:
        return None
    try:
        from PIL import Image, ImageOps
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        if max(img.size) > 3000:
            img.thumbnail((3000, 3000))
        if name == "tesseract":
            import pytesseract
            langs = pytesseract.get_languages(config="")
            lang = "+".join(x for x in ("eng", "hin") if x in langs) or "eng"
            return pytesseract.image_to_string(img, lang=lang)[:MAX_CHARS]
        import numpy as np
        result, _ = _rapid()(np.array(img))
        return "\n".join(r[1] for r in (result or []))[:MAX_CHARS]
    except Exception:  # unreadable or hostile image
        return ""
