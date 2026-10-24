"""Generate fake payment-success screens, some edited, with a mask of the edited area. Training data for the tamper model (F1).

usage: python tools/make_payment_screens.py OUT_DIR [--n 2000] [--seed 7] [--holdout-styles 2]

Everything is synthetic: made-up app names, people, UPI IDs and reference numbers. No real brand, logo or person.
Output: OUT_DIR/images/<id>.jpg, OUT_DIR/masks/<id>.png (255 where the edit is), OUT_DIR/meta.jsonl.
Styles are split into train/val/test by *style*, so the test set shows layouts the model never saw.
"""
from __future__ import annotations

import argparse
import io
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_CANDIDATES = [
    "arial.ttf", "arialbd.ttf", "segoeui.ttf", "calibri.ttf", "verdana.ttf", "tahoma.ttf", "times.ttf", "trebuc.ttf",
    "DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Regular.ttf", "NotoSans-Regular.ttf",
]
NAMES = ["Sharma Kirana", "Meena Stores", "R K Traders", "Gupta Medicals", "Anil Kumar", "Sunita Devi", "Patel Dairy", "Vikram Singh",
         "Lakshmi Tiffin", "Joseph Fernandes", "Hassan Tailors", "Neha Verma"]
APPS = ["PayEasy", "QuickPay", "MoneyBee", "RupeeGo", "DhanPlus", "UPIWave"]
BANKS = ["ybl", "oksbi", "okaxis", "paytm", "ibl", "okicici"]
FIELDS = ["amount", "ref", "payee", "time"]


@dataclass
class Style:
    name: str
    bg: tuple
    card: tuple
    accent: tuple
    ink: tuple
    layout: int


STYLES = [
    Style("s0", (244, 246, 250), (255, 255, 255), (20, 140, 70), (22, 28, 40), 0),
    Style("s1", (18, 22, 34), (30, 36, 52), (80, 200, 140), (240, 244, 250), 1),
    Style("s2", (255, 244, 230), (255, 255, 255), (230, 120, 20), (50, 36, 20), 2),
    Style("s3", (233, 240, 255), (250, 252, 255), (40, 90, 200), (16, 30, 70), 0),
    Style("s4", (250, 250, 250), (255, 255, 255), (170, 40, 120), (40, 20, 40), 2),
    Style("s5", (26, 40, 34), (38, 58, 48), (240, 200, 60), (236, 246, 240), 1),
]


def fonts() -> list[str]:
    found = []
    for name in FONT_CANDIDATES:
        try:
            ImageFont.truetype(name, 20)
            found.append(name)
        except OSError:
            continue
    if not found:
        sys.exit("No TrueType fonts found. Install any system font (DejaVu, Liberation, Noto) and retry.")
    return found


def draw_check(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    d.line((cx - r // 2, cy, cx - r // 8, cy + r // 2, cx + r // 2, cy - r // 3), fill=(255, 255, 255), width=max(3, r // 6))


def make_values(rnd: random.Random) -> dict:
    amt = rnd.choice([rnd.randrange(20, 500), rnd.randrange(500, 5000), rnd.randrange(5000, 60000)])
    name = rnd.choice(NAMES)
    vpa = name.lower().replace(" ", ".") + "@" + rnd.choice(BANKS)
    ref = "".join(rnd.choice("0123456789") for _ in range(12))
    t = f"{rnd.randrange(1, 29):02d} Oct 2026, {rnd.randrange(1, 13):02d}:{rnd.randrange(0, 60):02d} {rnd.choice(['am', 'pm'])}"
    return {"amount": f"Rs {amt:,}", "payee": name, "vpa": vpa, "ref": f"UPI Ref: {ref[:4]} {ref[4:8]} {ref[8:]}", "time": t, "status": "Payment Successful"}


def render(style: Style, v: dict, font_name: str, rnd: random.Random):
    """Return (image, boxes) where boxes maps each editable field to its (x0, y0, x1, y1)."""
    W, H = 720, rnd.choice([1280, 1200, 1340])
    img = Image.new("RGB", (W, H), style.bg)
    d = ImageDraw.Draw(img)
    F = lambda s: ImageFont.truetype(font_name, s)  # noqa: E731
    top = rnd.randrange(90, 160)
    d.rounded_rectangle((36, top - 30, W - 36, top + 780), 24, fill=style.card)
    draw_check(d, W // 2, top + 40, 34, style.accent)
    boxes: dict[str, tuple] = {}

    def put(key: str, text: str, xy, size, fill, anchor="la"):
        f = F(size)
        d.text(xy, text, font=f, fill=fill, anchor=anchor)
        b = d.textbbox(xy, text, font=f, anchor=anchor)
        boxes[key] = (b[0] - 4, b[1] - 4, b[2] + 4, b[3] + 4)

    d.text((W // 2, top + 100), v["status"], font=F(30), fill=style.ink, anchor="ma")
    if style.layout == 0:
        put("amount", v["amount"], (W // 2, top + 160), 72, style.ink, "ma")
        put("payee", "To: " + v["payee"], (70, top + 300), 28, style.ink)
        d.text((70, top + 346), v["vpa"], font=F(24), fill=style.accent)
        put("time", v["time"], (70, top + 420), 24, style.ink)
        put("ref", v["ref"], (70, top + 470), 24, style.ink)
    elif style.layout == 1:
        put("payee", v["payee"], (W // 2, top + 160), 40, style.ink, "ma")
        put("amount", v["amount"], (W // 2, top + 230), 80, style.accent, "ma")
        put("time", v["time"], (W // 2, top + 360), 24, style.ink, "ma")
        put("ref", v["ref"], (W // 2, top + 410), 24, style.ink, "ma")
    else:
        put("time", v["time"], (70, top + 170), 22, style.ink)
        put("amount", v["amount"], (70, top + 220), 66, style.ink)
        put("payee", "Paid to " + v["payee"], (70, top + 340), 30, style.ink)
        put("ref", v["ref"], (70, top + 400), 22, style.accent)
    d.rounded_rectangle((70, top + 640, W - 70, top + 710), 18, fill=style.accent)
    d.text((W // 2, top + 675), "Done", font=F(28), fill=(255, 255, 255), anchor="mm")
    d.text((W // 2, H - 60), rnd.choice(APPS), font=F(22), fill=style.ink, anchor="ma")
    return img, boxes


def tamper(img: Image.Image, boxes: dict, v: dict, style: Style, fonts_: list[str], rnd: random.Random):
    """Paint over one field and write a different value in a slightly different way. Returns (image, mask, field)."""
    field = rnd.choice(FIELDS)
    x0, y0, x1, y1 = boxes[field]
    d = ImageDraw.Draw(img)
    d.rectangle((x0, y0, x1, y1), fill=style.card)  # erase the old value
    new = dict(v)
    if field == "amount":
        new["amount"] = f"Rs {rnd.choice([rnd.randrange(20, 900), rnd.randrange(1000, 90000)]):,}"
        text = new["amount"]
    elif field == "ref":
        r = "".join(rnd.choice("0123456789") for _ in range(12))
        text = f"UPI Ref: {r[:4]} {r[4:8]} {r[8:]}"
    elif field == "payee":
        text = ("To: " if "To:" in v["payee"] else "") + rnd.choice(NAMES)
    else:
        text = f"{rnd.randrange(1, 29):02d} Oct 2026, {rnd.randrange(1, 13):02d}:{rnd.randrange(0, 60):02d} {rnd.choice(['am', 'pm'])}"
    h = y1 - y0 - 8
    same_font = rnd.random() < 0.3  # harder case: same font, only position and size drift a little
    fname = fonts_[0] if same_font else rnd.choice(fonts_)
    size = max(14, int(h * rnd.uniform(0.62, 0.8) * (1.0 if same_font else rnd.uniform(0.9, 1.1))))
    f = ImageFont.truetype(fname, size)
    cx, cy = (x0 + x1) // 2 + rnd.randrange(-6, 7), (y0 + y1) // 2 + rnd.randrange(-4, 5)
    ink = tuple(max(0, min(255, c + rnd.randrange(-14, 15))) for c in style.ink)
    d.text((cx, cy), text, font=f, fill=ink, anchor="mm")
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rectangle((x0, y0, x1, y1), fill=255)
    if rnd.random() < 0.4:  # soften the edit edges
        region = img.crop((x0 - 6, y0 - 6, x1 + 6, y1 + 6)).filter(ImageFilter.GaussianBlur(0.6))
        img.paste(region, (x0 - 6, y0 - 6))
    return img, mask, field


def chat_copy(img: Image.Image, mask: Image.Image | None, rnd: random.Random):
    """Make it look like it went through a chat app: shrink, then JPEG at a random quality."""
    scale = rnd.choice([1.0, 1.0, 0.75, 0.6])
    if scale < 1:
        size = (int(img.width * scale), int(img.height * scale))
        img = img.resize(size, Image.BILINEAR)
        if mask is not None:
            mask = mask.resize(size, Image.NEAREST)
    q = rnd.choice([95, 85, 70, 55, 40])
    b = io.BytesIO()
    img.save(b, "JPEG", quality=q)
    return Image.open(io.BytesIO(b.getvalue())).convert("RGB"), mask, q


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--holdout-styles", type=int, default=2, help="styles kept out of training: one for val, the rest for test")
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    fl = fonts()
    (a.out / "images").mkdir(parents=True, exist_ok=True)
    (a.out / "masks").mkdir(parents=True, exist_ok=True)
    order = list(STYLES)
    held = order[-a.holdout_styles:] if a.holdout_styles else []
    split_of = {s.name: "train" for s in order}
    for i, s in enumerate(held):
        split_of[s.name] = "val" if i == 0 else "test"
    with (a.out / "meta.jsonl").open("w", encoding="utf-8") as meta:
        for i in range(a.n):
            style = rnd.choice(order)
            font = rnd.choice(fl)
            v = make_values(rnd)
            img, boxes = render(style, v, font, rnd)
            edited = rnd.random() < 0.5
            mask = Image.new("L", img.size, 0)
            field = None
            if edited:
                img, mask, field = tamper(img, boxes, v, style, fl, rnd)
            img, mask, q = chat_copy(img, mask, rnd)
            sid = f"{i:06d}"
            img.save(a.out / "images" / f"{sid}.jpg", quality=q)
            mask.save(a.out / "masks" / f"{sid}.png")
            meta.write(json.dumps({"id": sid, "style": style.name, "split": split_of[style.name], "edited": edited, "field": field,
                                   "font": font, "jpeg_q": q}) + "\n")
    print(f"wrote {a.n} images to {a.out} (held-out styles: {[s.name for s in held]})")


if __name__ == "__main__":
    main()
