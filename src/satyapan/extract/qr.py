"""Decode QR codes from an uploaded image. The image is read in memory and never written to disk.

Phone photos and chat-compressed screenshots are often noisy, small or blurred, so a failed first read is retried on
cleaned-up copies of the image (median filter, enlargement, contrast stretch) before giving up.
"""
from __future__ import annotations

import io
from collections.abc import Callable, Iterator

try:  # optional at import time so the rest of the app still runs without the decoder
    import zxingcpp
    from PIL import Image, ImageFilter, ImageOps
except ImportError:  # pragma: no cover
    zxingcpp = None  # type: ignore[assignment]
    Image = ImageFilter = ImageOps = None  # type: ignore[assignment]

MAX_PIXELS = 40_000_000
MAX_SIDE = 3000


def _variants(img: "Image.Image") -> Iterator["Image.Image"]:
    """Cleaned-up copies, cheapest first."""
    yield img
    gray = ImageOps.grayscale(img)
    steps: list[Callable[["Image.Image"], "Image.Image"]] = [
        lambda g: g.filter(ImageFilter.MedianFilter(3)),
        lambda g: ImageOps.autocontrast(g, cutoff=2),
        lambda g: g.filter(ImageFilter.MedianFilter(5)),
        lambda g: g.resize((g.width * 2, g.height * 2), Image.BICUBIC) if max(g.size) <= 1200 else g,
        lambda g: g.resize((g.width * 2, g.height * 2), Image.BICUBIC).filter(ImageFilter.MedianFilter(3)) if max(g.size) <= 1200 else g,
        lambda g: ImageOps.autocontrast(g).point(lambda p: 255 if p > 128 else 0),
    ]
    for step in steps:
        yield step(gray)


def decode_qr(data: bytes) -> list[str]:
    """Return the text of every QR code found, or [] when none is found or the file is not a readable image."""
    if zxingcpp is None or Image is None:
        return []
    try:
        img = Image.open(io.BytesIO(data))
        if img.width * img.height > MAX_PIXELS:
            return []
        img = ImageOps.exif_transpose(img).convert("RGB")
        if max(img.size) > MAX_SIDE:
            img.thumbnail((MAX_SIDE, MAX_SIDE))
        for variant in _variants(img):
            found = [r.text for r in zxingcpp.read_barcodes(variant, formats=zxingcpp.BarcodeFormat.QRCode) if r.text]
            if found:
                return list(dict.fromkeys(found))[:5]
    except Exception:  # corrupt or hostile image: treat as unreadable
        return []
    return []
