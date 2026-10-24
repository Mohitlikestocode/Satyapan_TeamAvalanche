"""Write a small kit of *real, scannable* QR images (synthetic payees only) with phone-style damage.

usage: python tools/make_qr_kit.py <out_dir>

Every payee below is made up. Nothing here points to a real account.
"""
from __future__ import annotations

import io
import random
import sys
from pathlib import Path

import segno
from PIL import Image, ImageDraw, ImageFilter

PAYLOADS = {
    "stock_tips_personal": "upi://pay?pa=alpha.gain88@ybl&pn=Ramesh%20K&am=25000&tn=VIP%20profits",
    "broker_valid": "upi://pay?pa=acme.brk@validhdfc&pn=Acme%20Broking&mc=6211",
    "plain_link": "https://hdfc-bank-kyc-update.example/login",
    "collect_trap": "upi://pay?pa=refund.desk77@paytm&pn=Refund%20Desk&am=4999&tn=Enter%20PIN%20to%20receive",
}


def base_qr(text: str, scale: int = 8) -> Image.Image:
    buf = io.BytesIO()
    segno.make(text, error="m").save(buf, kind="png", scale=scale, border=4)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def degrade(img: Image.Image, how: str, seed: int = 1) -> Image.Image:
    rnd = random.Random(seed)
    if how == "clean":
        return img
    if how == "rotated":
        return img.rotate(17, expand=True, fillcolor=(255, 255, 255), resample=Image.BICUBIC)
    if how == "small":
        return img.resize((max(110, img.width // 3), max(110, img.height // 3)), Image.BILINEAR)
    if how == "blurred":
        return img.filter(ImageFilter.GaussianBlur(1.4))
    if how == "jpeg":
        b = io.BytesIO(); img.save(b, "JPEG", quality=25); return Image.open(io.BytesIO(b.getvalue())).convert("RGB")
    if how == "noisy":
        px = img.load()
        for _ in range(img.width * img.height // 25):
            x, y = rnd.randrange(img.width), rnd.randrange(img.height)
            v = rnd.randrange(256); px[x, y] = (v, v, v)
        return img
    if how == "on_screen":  # QR inside a phone-screenshot-like page, with text and a grey background
        page = Image.new("RGB", (720, 1280), (236, 238, 242))
        d = ImageDraw.Draw(page)
        d.rectangle((40, 80, 680, 220), fill=(255, 255, 255))
        d.text((60, 120), "VIP Profits Club - scan to pay", fill=(20, 20, 20))
        q = img.resize((420, 420), Image.NEAREST)
        page.paste(q, (150, 320))
        return page.filter(ImageFilter.GaussianBlur(0.6))
    raise ValueError(how)


CONDITIONS = ["clean", "rotated", "small", "blurred", "jpeg", "noisy", "on_screen"]


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, text in PAYLOADS.items():
        for how in CONDITIONS:
            degrade(base_qr(text), how).save(out / f"{name}__{how}.png")
    print(f"wrote {len(PAYLOADS) * len(CONDITIONS)} images to {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
