"""Decode QR codes from an uploaded image. The image is read in memory and never written to disk."""
from __future__ import annotations

import io

try:  # optional at import time so the rest of the app still runs without the decoder
    import zxingcpp
    from PIL import Image
except ImportError:  # pragma: no cover
    zxingcpp = None  # type: ignore[assignment]
    Image = None  # type: ignore[assignment]

MAX_PIXELS = 40_000_000


def decode_qr(data: bytes) -> list[str]:
    """Return the text of every QR code found, or [] when none is found or the file is not a readable image."""
    if zxingcpp is None or Image is None:
        return []
    try:
        img = Image.open(io.BytesIO(data))
        if img.width * img.height > MAX_PIXELS:
            return []
        img = img.convert("RGB")
        return [r.text for r in zxingcpp.read_barcodes(img) if r.text][:5]
    except Exception:  # corrupt or hostile image: treat as unreadable
        return []
