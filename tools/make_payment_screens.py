"""Generate fake payment-success screens, some edited, with a mask of the edited area. Training data for the tamper model (F1).

usage: python tools/make_payment_screens.py OUT_DIR [--n 2000] [--seed 7] [--holdout-styles 3]

Everything is synthetic: made-up app names, people, UPI IDs and reference numbers. No real brand, logo or person.
Output: OUT_DIR/images/<id>.jpg, OUT_DIR/masks/<id>.png (255 where the edit is), OUT_DIR/meta.jsonl.

A "style" is a layout family. Palettes, fonts, margins, extra elements and chat-app copies are random per image, so the model
cannot learn "what these few screens look like". Styles are split into train/val/test, so the test set shows layouts the model
never saw. Some fonts are also kept out of training and appear only in val/test images ("font_held": true).
"""
from __future__ import annotations

import argparse
import colorsys
import hashlib
import io
import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_CANDIDATES = [
    "arial.ttf", "arialbd.ttf", "segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "segoeuil.ttf", "calibri.ttf", "calibrib.ttf",
    "verdana.ttf", "verdanab.ttf", "tahoma.ttf", "tahomabd.ttf", "trebuc.ttf", "trebucbd.ttf", "framd.ttf", "micross.ttf",
    "candara.ttf", "Nirmala.ttf", "NirmalaB.ttf", "times.ttf",
    "DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf", "NotoSans-Regular.ttf",
]
# Fonts that never appear in training images: a test of "a font the model has not seen".
HELD_FONT_CANDIDATES = ["bahnschrift.ttf", "gadugi.ttf", "LeelawUI.ttf", "corbel.ttf", "ebrima.ttf", "DejaVuSerif.ttf"]
# Odd fonts an editor might pick for a careless edit (edits only).
EDIT_ONLY_FONTS = ["georgia.ttf", "consola.ttf", "pala.ttf", "constan.ttf"]

NAMES = ["Sharma Kirana", "Meena Stores", "R K Traders", "Gupta Medicals", "Anil Kumar", "Sunita Devi", "Patel Dairy", "Vikram Singh",
         "Lakshmi Tiffin", "Joseph Fernandes", "Hassan Tailors", "Neha Verma", "Balaji Mobiles", "Kaur Sweets", "Iqbal Hardware",
         "Priya Nair", "Das Fish Mart", "Om Sai Xerox", "Rahul Yadav", "Fatima Begum", "Shree Ganesh Bakery", "Arjun Reddy"]
APPS = ["PayEasy", "QuickPay", "MoneyBee", "RupeeGo", "DhanPlus", "UPIWave", "PaisaNow", "SwiftUPI", "KhataPay", "BharatSend"]
BANKS = ["ybl", "oksbi", "okaxis", "paytm", "ibl", "okicici", "okhdfcbank", "axl", "upi"]
FIELDS = ["amount", "ref", "payee", "time", "vpa"]
FIELD_WEIGHTS = [0.4, 0.15, 0.2, 0.15, 0.1]
N_LAYOUTS = 8


def usable_fonts(names: list[str]) -> list[str]:
    found = []
    for name in names:
        try:
            ImageFont.truetype(name, 20)
            found.append(name)
        except OSError:
            continue
    return found


# Full paths for macOS and Linux, where Pillow does not find fonts by file name alone.
SYSTEM_FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Verdana.ttf", "/System/Library/Fonts/Supplemental/Tahoma.ttf",
    "/System/Library/Fonts/Supplemental/Trebuchet MS.ttf", "/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/SFNS.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
]
# Last resort on any machine: the Noto Sans web fonts the site already ships (Unicode-range subsets; only those that can draw
# a payment screen are kept).
REPO_FONTS = Path(__file__).resolve().parents[1] / "web" / "static" / "fonts"
NEEDED = "Payment Successful Rs 0123456789,:.@ UPI Ref AM PM Oct"


def covers(font_name: str, text: str = NEEDED) -> bool:
    """True when the font draws every character in `text` (not the missing-glyph box)."""
    f = ImageFont.truetype(font_name, 24)

    def draw(ch: str) -> bytes:
        im = Image.new("L", (40, 40), 0)
        ImageDraw.Draw(im).text((4, 2), ch, font=f, fill=255)
        return im.tobytes()
    missing = draw("￿")
    return all(draw(ch) != missing for ch in set(text) if not ch.isspace())


def fonts() -> list[str]:
    found = usable_fonts(FONT_CANDIDATES) or usable_fonts([p for p in SYSTEM_FONT_PATHS if Path(p).exists()])
    if not found and REPO_FONTS.exists():
        found = [str(p) for p in sorted(REPO_FONTS.glob("*.woff2")) if usable_fonts([str(p)]) and covers(str(p))]
    if not found:
        sys.exit("No TrueType fonts found. Install any system font (DejaVu, Liberation, Noto) and retry.")
    return found


_RUPEE: dict[str, bool] = {}


def has_rupee(font_name: str) -> bool:
    """True when the font draws a real rupee sign rather than the missing-glyph box."""
    if font_name not in _RUPEE:
        f = ImageFont.truetype(font_name, 40)

        def draw(ch: str) -> bytes:
            im = Image.new("L", (60, 60), 0)
            ImageDraw.Draw(im).text((10, 5), ch, font=f, fill=255)
            return im.tobytes()
        _RUPEE[font_name] = draw("₹") != draw("￿")
    return _RUPEE[font_name]


# ---- values --------------------------------------------------------------------------------------------------

def indian(n: int) -> str:
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    return ",".join([head, *parts, tail]) if head else ",".join([*parts, tail])


def money(rnd: random.Random, font_name: str, n: int | None = None, cur: str | None = None) -> str:
    n = n if n is not None else rnd.choice([rnd.randrange(10, 500), rnd.randrange(500, 5000), rnd.randrange(5000, 90000), rnd.randrange(90000, 250000)])
    cur = cur or rnd.choice(["₹", "₹", "Rs ", "Rs. ", "INR "])
    if cur == "₹" and not has_rupee(font_name):
        cur = "Rs "
    body = indian(n) if rnd.random() < 0.7 else f"{n:,}"
    return f"{cur}{body}" + (".00" if rnd.random() < 0.3 else "")


def a_time(rnd: random.Random) -> str:
    d, m = rnd.randrange(1, 29), rnd.choice(["Oct", "Sep", "Nov"])
    h, mi = rnd.randrange(1, 13), rnd.randrange(0, 60)
    ap = rnd.choice(["am", "pm", "AM", "PM"])
    return rnd.choice([f"{d:02d} {m} 2026, {h:02d}:{mi:02d} {ap}", f"{h}:{mi:02d} {ap} on {d} {m} 2026", f"{d:02d}/10/2026 {h:02d}:{mi:02d} {ap}"])


def a_ref(rnd: random.Random, label: str) -> str:
    r = "".join(rnd.choice("0123456789") for _ in range(12))
    return label + (f"{r[:4]} {r[4:8]} {r[8:]}" if rnd.random() < 0.5 else r)


def make_values(rnd: random.Random, font_name: str) -> dict:
    name = rnd.choice(NAMES)
    vpa = name.lower().replace(" ", rnd.choice([".", "", "_"])) + str(rnd.choice(["", "", rnd.randrange(1, 99)])) + "@" + rnd.choice(BANKS)
    ref_label = rnd.choice(["UPI Ref: ", "UPI Ref No. ", "UTR: ", "Transaction ID: ", "Ref No: "])
    return {"amount": money(rnd, font_name), "payee": name, "vpa": vpa, "ref_label": ref_label, "ref": a_ref(rnd, ref_label),
            "time": a_time(rnd), "status": rnd.choice(["Payment Successful", "Paid successfully", "Money sent", "Transaction successful",
                                                       "Payment complete"])}


# ---- palette -------------------------------------------------------------------------------------------------

def hsv(h: float, s: float, v: float) -> tuple[int, int, int]:
    return tuple(int(255 * c) for c in colorsys.hsv_to_rgb(h % 1.0, max(0.0, min(1.0, s)), max(0.0, min(1.0, v))))


def make_palette(rnd: random.Random) -> dict:
    dark = rnd.random() < 0.3
    hue = rnd.random()
    accent = hsv(rnd.random(), rnd.uniform(0.5, 0.9), rnd.uniform(0.5, 0.85) if not dark else rnd.uniform(0.65, 0.95))
    if dark:
        bg = hsv(hue, rnd.uniform(0.0, 0.35), rnd.uniform(0.03, 0.16))
        card = hsv(hue, rnd.uniform(0.0, 0.3), rnd.uniform(0.12, 0.24))
        ink = hsv(hue, rnd.uniform(0.0, 0.08), rnd.uniform(0.88, 1.0))
        sub = hsv(hue, rnd.uniform(0.0, 0.1), rnd.uniform(0.55, 0.72))
    else:
        bg = hsv(hue, rnd.uniform(0.0, 0.14), rnd.uniform(0.9, 1.0))
        card = hsv(hue, rnd.uniform(0.0, 0.04), rnd.uniform(0.97, 1.0))
        ink = hsv(hue, rnd.uniform(0.0, 0.4), rnd.uniform(0.04, 0.28))
        sub = hsv(hue, rnd.uniform(0.0, 0.2), rnd.uniform(0.38, 0.55))
    if rnd.random() < 0.35:  # flat screens: no card
        card = bg
    return {"dark": dark, "bg": bg, "card": card, "accent": accent, "ink": ink, "sub": sub, "button_text": (255, 255, 255)}


# ---- rendering -----------------------------------------------------------------------------------------------

class Screen:
    """A drawn screen plus, for each editable field, how it was drawn (so an edit can imitate it)."""

    def __init__(self, img: Image.Image, font_name: str, rnd: random.Random):
        self.img, self.d, self.font_name, self.rnd = img, ImageDraw.Draw(img), font_name, rnd
        self.fields: dict[str, dict] = {}

    def F(self, size: int, name: str | None = None) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(name or self.font_name, size)

    def text(self, xy, text: str, size: int, fill, anchor: str = "la", key: str | None = None) -> None:
        f = self.F(size)
        self.d.text(xy, text, font=f, fill=fill, anchor=anchor)
        if key:
            b = self.d.textbbox(xy, text, font=f, anchor=anchor)
            self.fields[key] = {"box": (b[0] - 4, b[1] - 4, b[2] + 4, b[3] + 4), "xy": xy, "anchor": anchor, "size": size,
                                "fill": fill, "text": text}


def gradient(img: Image.Image, top, bottom) -> None:
    d = ImageDraw.Draw(img)
    for y in range(img.height):
        t = y / max(1, img.height - 1)
        d.line((0, y, img.width, y), fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))


def status_bar(s: Screen, p: dict, W: int) -> None:
    rnd = s.rnd
    s.d.text((28, 18), f"{rnd.randrange(1, 13)}:{rnd.randrange(0, 60):02d}", font=s.F(22), fill=p["ink"])
    x = W - 30
    s.d.rounded_rectangle((x - 40, 20, x, 38), 4, outline=p["ink"], width=2)
    s.d.rectangle((x - 37, 23, x - 37 + rnd.randrange(8, 34), 35), fill=p["ink"])
    for i in range(4):
        h = 6 + 4 * i
        s.d.rectangle((x - 90 + 8 * i, 38 - h, x - 85 + 8 * i, 38), fill=p["ink"])


def check_mark(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color, rnd: random.Random) -> None:
    if rnd.random() < 0.7:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
        d.line((cx - r // 2, cy, cx - r // 8, cy + r // 2, cx + r // 2, cy - r // 3), fill=(255, 255, 255), width=max(3, r // 6), joint="curve")
    else:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=max(3, r // 7))
        d.line((cx - r // 2, cy, cx - r // 8, cy + r // 2, cx + r // 2, cy - r // 3), fill=color, width=max(3, r // 6), joint="curve")


def logo(d: ImageDraw.ImageDraw, x: int, y: int, r: int, p: dict, letter_font, rnd: random.Random) -> None:
    """A made-up round logo with an initial. Not any real brand."""
    d.ellipse((x - r, y - r, x + r, y + r), fill=hsv(rnd.random(), 0.5, 0.75))
    d.text((x, y), rnd.choice("ABCDEFGHKMNPRSTV"), font=letter_font, fill=(255, 255, 255), anchor="mm")


def render(layout: int, p: dict, v: dict, font_name: str, rnd: random.Random) -> Screen:
    W, H = 720, rnd.choice([1280, 1360, 1440, 1520, 1600])
    img = Image.new("RGB", (W, H), p["bg"])
    if rnd.random() < 0.3:
        gradient(img, p["bg"], tuple(max(0, min(255, c + rnd.randrange(-18, 19))) for c in p["bg"]))
    s = Screen(img, font_name, rnd)
    d = s.d
    if rnd.random() < 0.8:
        status_bar(s, p, W)
    mx = rnd.randrange(24, 60)  # side margin
    top = rnd.randrange(90, 190)
    if p["card"] != p["bg"]:
        d.rounded_rectangle((mx, top - 30, W - mx, top + rnd.randrange(700, 900)), rnd.choice([8, 16, 24, 32]), fill=p["card"])
    left = mx + rnd.randrange(24, 50)
    sub, ink, acc = p["sub"], p["ink"], p["accent"]
    pay_to = rnd.choice(["To: ", "Paid to ", "", "Sent to "])
    if layout == 0:  # centred, big amount
        check_mark(d, W // 2, top + 40, rnd.randrange(28, 44), acc, rnd)
        s.text((W // 2, top + 100), v["status"], rnd.randrange(26, 34), ink, "ma")
        s.text((W // 2, top + 160), v["amount"], rnd.randrange(60, 84), ink, "ma", key="amount")
        s.text((left, top + 300), pay_to + v["payee"], rnd.randrange(26, 32), ink, key="payee")
        s.text((left, top + 346), v["vpa"], rnd.randrange(20, 26), sub, key="vpa")
        s.text((left, top + 420), v["time"], rnd.randrange(20, 26), ink, key="time")
        s.text((left, top + 470), v["ref"], rnd.randrange(20, 26), ink, key="ref")
    elif layout == 1:  # payee first, centred
        logo(d, W // 2, top + 40, 40, p, s.F(36), rnd)
        s.text((W // 2, top + 110), v["payee"], rnd.randrange(34, 44), ink, "ma", key="payee")
        s.text((W // 2, top + 165), v["vpa"], rnd.randrange(20, 26), sub, "ma", key="vpa")
        s.text((W // 2, top + 220), v["amount"], rnd.randrange(66, 90), acc, "ma", key="amount")
        s.text((W // 2, top + 340), v["status"], rnd.randrange(24, 30), ink, "ma")
        s.text((W // 2, top + 390), v["time"], rnd.randrange(20, 26), sub, "ma", key="time")
        s.text((W // 2, top + 440), v["ref"], rnd.randrange(20, 26), sub, "ma", key="ref")
    elif layout == 2:  # left aligned, time first
        s.text((left, top + 20), v["status"], rnd.randrange(28, 36), acc)
        s.text((left, top + 90), v["time"], rnd.randrange(20, 24), sub, key="time")
        s.text((left, top + 140), v["amount"], rnd.randrange(58, 76), ink, key="amount")
        s.text((left, top + 260), pay_to + v["payee"], rnd.randrange(28, 32), ink, key="payee")
        s.text((left, top + 305), v["vpa"], rnd.randrange(20, 24), sub, key="vpa")
        s.text((left, top + 370), v["ref"], rnd.randrange(20, 24), acc, key="ref")
    elif layout == 3:  # receipt table: labels left, values right
        check_mark(d, W // 2, top + 40, 32, acc, rnd)
        s.text((W // 2, top + 95), v["status"], rnd.randrange(28, 34), ink, "ma")
        right = W - left
        rows = [("Amount", "amount"), ("To", "payee"), ("UPI ID", "vpa"), ("Date", "time"), ("Reference", "ref")]
        y = top + 180
        for label, key in rows:
            d.text((left, y), label, font=s.F(22), fill=sub, anchor="la")
            val = v[key].replace(v["ref_label"], "") if key == "ref" else v[key]
            s.text((right, y), val, 34 if key == "amount" else 22, ink, "ra", key=key)
            y += 70 if key == "amount" else 58
            if rnd.random() < 0.6:
                d.line((left, y - 16, right, y - 16), fill=sub, width=1)
    elif layout == 4:  # coloured banner with amount, details below
        bh = rnd.randrange(300, 380)
        d.rectangle((0, 0, W, bh + top // 2), fill=acc)
        s.text((W // 2, top), v["status"], rnd.randrange(26, 32), p["button_text"], "ma")
        s.text((W // 2, top + 60), v["amount"], rnd.randrange(64, 82), p["button_text"], "ma", key="amount")
        y = bh + top // 2 + 50
        s.text((left, y), pay_to + v["payee"], rnd.randrange(26, 32), ink, key="payee")
        s.text((left, y + 46), v["vpa"], 22, sub, key="vpa")
        s.text((left, y + 120), v["time"], 22, ink, key="time")
        s.text((left, y + 170), v["ref"], 22, ink, key="ref")
    elif layout == 5:  # stacked list: small grey label above each value
        s.text((left, top), v["status"], rnd.randrange(30, 38), ink)
        check_mark(d, W - left - 30, top + 20, 26, acc, rnd)
        y = top + 90
        for label, key, size in [("Amount paid", "amount", rnd.randrange(48, 64)), ("Paid to", "payee", 28), ("UPI ID", "vpa", 22),
                                 ("Date and time", "time", 22), ("Transaction reference", "ref", 22)]:
            d.text((left, y), label, font=s.F(20), fill=sub)
            val = v[key].replace(v["ref_label"], "") if key == "ref" else v[key]
            s.text((left, y + 30), val, size, ink, key=key)
            y += 50 + size + 26
    elif layout == 6:  # compact row: payee left, amount right on one line
        check_mark(d, left + 26, top + 26, 26, acc, rnd)
        s.text((left + 70, top + 10), v["status"], rnd.randrange(26, 32), ink)
        logo(d, left + 30, top + 140, 30, p, s.F(28), rnd)
        s.text((left + 76, top + 118), v["payee"], rnd.randrange(24, 30), ink, key="payee")
        s.text((left + 76, top + 156), v["vpa"], 20, sub, key="vpa")
        s.text((W - left, top + 120), v["amount"], rnd.randrange(34, 44), ink, "ra", key="amount")
        d.line((left, top + 220, W - left, top + 220), fill=sub, width=1)
        s.text((left, top + 250), v["time"], 22, sub, key="time")
        s.text((left, top + 300), v["ref"], 22, sub, key="ref")
    else:  # full-bleed, amount huge on the left, details in two columns
        s.text((left, top), v["amount"], rnd.randrange(80, 100), acc, key="amount")
        s.text((left, top + 130), v["status"], rnd.randrange(24, 30), ink)
        s.text((left, top + 220), v["payee"], rnd.randrange(26, 30), ink, key="payee")
        s.text((left, top + 262), v["vpa"], 20, sub, key="vpa")
        col = W // 2 + 10
        d.text((left, top + 340), "When", font=s.F(18), fill=sub)
        s.text((left, top + 366), v["time"].split(",")[0], 22, ink, key="time")
        d.text((col, top + 340), "Reference", font=s.F(18), fill=sub)
        s.text((col, top + 366), v["ref"].replace(v["ref_label"], ""), 22, ink, key="ref")
    # common extras below the fields, never edited
    by = top + rnd.randrange(600, 700)
    if rnd.random() < 0.5:
        d.text((left, by - 80), rnd.choice(["Note: ", "Message: ", ""]) + rnd.choice(["rent", "milk", "for groceries", "thanks!", "advance"]),
               font=s.F(20), fill=sub)
    if rnd.random() < 0.85:
        bw = rnd.choice([W - 2 * left, (W - 2 * left) // 2 - 10])
        d.rounded_rectangle((left, by, left + bw, by + 64), rnd.choice([8, 18, 32]), fill=acc)
        d.text((left + bw // 2, by + 32), rnd.choice(["Done", "Share", "Back to home"]), font=s.F(26), fill=p["button_text"], anchor="mm")
        if bw < W - 2 * left:
            d.rounded_rectangle((W - left - bw, by, W - left, by + 64), 18, outline=acc, width=2)
            d.text((W - left - bw // 2, by + 32), "Share", font=s.F(26), fill=acc, anchor="mm")
    d.text((W // 2, H - rnd.randrange(50, 90)), rnd.choice(APPS), font=s.F(rnd.randrange(18, 26)), fill=sub, anchor="ma")
    return s


# ---- editing -------------------------------------------------------------------------------------------------

def outside_colour(img: Image.Image, box) -> tuple:
    x0, y0, x1, y1 = box
    px = [img.getpixel((min(img.width - 1, max(0, x), ), min(img.height - 1, max(0, y)))) for x, y in
          ((x0 - 3, y0 - 3), (x1 + 3, y0 - 3), (x0 - 3, y1 + 3), (x1 + 3, y1 + 3))]
    return tuple(sorted(c[i] for c in px)[1] for i in range(3))


def new_value(field: str, v: dict, rnd: random.Random, font_name: str, old: str) -> str:
    if field == "amount":
        cur = next((c for c in ("₹", "Rs. ", "Rs ", "INR ") if old.startswith(c)), "Rs ")
        return money(rnd, font_name, cur=cur)
    if field == "ref":
        return a_ref(rnd, v["ref_label"] if old.startswith(v["ref_label"]) else "")
    if field == "payee":
        prefix = next((p for p in ("To: ", "Paid to ", "Sent to ") if old.startswith(p)), "")
        return prefix + rnd.choice([n for n in NAMES if n not in old])
    if field == "vpa":
        name = rnd.choice(NAMES)
        return name.lower().replace(" ", ".") + "@" + rnd.choice(BANKS)
    t = a_time(rnd)
    return t.split(",")[0] if "," not in old else t


def tamper(s: Screen, v: dict, p: dict, edit_fonts: list[str], rnd: random.Random):
    """Erase one field and write a different value, the way a person in a photo editor would. Returns (mask, info)."""
    img = s.img
    keys = [k for k in FIELDS if k in s.fields]
    field = rnd.choices(keys, weights=[FIELD_WEIGHTS[FIELDS.index(k)] for k in keys])[0]
    f = s.fields[field]
    x0, y0, x1, y1 = f["box"]
    d = ImageDraw.Draw(img)
    # Real edits leave small traces; about 15% are "perfect" (exact colour, size and place), the hard case we report separately.
    perfect = rnd.random() < 0.15
    method = "fill"
    if rnd.random() < 0.35:  # clone a nearby strip of background instead of a flat fill
        w = x1 - x0
        src_x = x1 + 8 if x1 + 8 + w < img.width else x0 - 8 - w
        if src_x >= 0:
            img.paste(img.crop((src_x, y0, src_x + w, y1)), (x0, y0))
            method = "clone"
    if method == "fill":
        col = outside_colour(img, (x0, y0, x1, y1))
        if not perfect:  # an eyedropper on a compressed screenshot picks a slightly different colour
            col = tuple(max(0, min(255, c + rnd.choice([-1, 1]) * rnd.randrange(2, 9))) for c in col)
        d.rectangle((x0, y0, x1, y1), fill=col)
    text = new_value(field, v, rnd, s.font_name, f["text"])
    same_font = rnd.random() < 0.5  # harder case: same font, only a small drift in size and place
    fname = s.font_name if same_font else rnd.choice(edit_fonts)
    if perfect:
        size, jit, ink_j = f["size"], 0, 0
    elif same_font:
        size, jit, ink_j = f["size"] + rnd.choice([-2, -1, 1, 2]), 3, 8
    else:
        size, jit, ink_j = max(12, int(f["size"] * rnd.uniform(0.85, 1.12))), 6, 16
    xy = (f["xy"][0] + rnd.randrange(-jit, jit + 1), f["xy"][1] + rnd.randrange(-jit, jit + 1))
    ink = tuple(max(0, min(255, c + rnd.randrange(-ink_j, ink_j + 1))) for c in f["fill"])
    if rnd.random() < 0.15:
        d.fontmode = "1"  # some editors draw text without anti-aliasing
    font = ImageFont.truetype(fname, size)
    d.text(xy, text, font=font, fill=ink, anchor=f["anchor"])
    nb = d.textbbox(xy, text, font=font, anchor=f["anchor"])
    box = (min(x0, nb[0] - 3), min(y0, nb[1] - 3), max(x1, nb[2] + 3), max(y1, nb[3] + 3))
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rectangle(box, fill=255)
    soft = rnd.random() < 0.3
    if soft:  # soften the edit edges
        bx = (max(0, box[0] - 6), max(0, box[1] - 6), min(img.width, box[2] + 6), min(img.height, box[3] + 6))
        img.paste(img.crop(bx).filter(ImageFilter.GaussianBlur(rnd.uniform(0.4, 0.9))), bx[:2])
    return mask, {"field": field, "method": method, "same_font": same_font, "edit_font": fname, "soft": soft, "perfect": perfect}


def jpeg(img: Image.Image, q: int) -> Image.Image:
    b = io.BytesIO()
    img.save(b, "JPEG", quality=q)
    return Image.open(io.BytesIO(b.getvalue())).convert("RGB")


def chat_copy(img: Image.Image, mask: Image.Image, rnd: random.Random):
    """Make it look like it went through a chat app: shrink, then JPEG at a random quality, sometimes twice."""
    scale = rnd.choice([1.0, 1.0, 0.85, 0.75, 0.6, 0.5])
    if scale < 1:
        size = (int(img.width * scale), int(img.height * scale))
        img = img.resize(size, rnd.choice([Image.BILINEAR, Image.BICUBIC, Image.LANCZOS]))
        mask = mask.resize(size, Image.NEAREST)
    double = rnd.random() < 0.25
    if double:
        img = jpeg(img, rnd.choice([90, 80, 70]))
    q = rnd.choice([95, 90, 85, 70, 55, 40])
    b = io.BytesIO()
    img.save(b, "JPEG", quality=q)
    return b.getvalue(), mask, q, scale, double


def split_of_layouts(holdout: int) -> dict[int, str]:
    split = {i: "train" for i in range(N_LAYOUTS)}
    held = list(range(N_LAYOUTS))[-holdout:] if holdout else []
    for i, lay in enumerate(held):
        split[lay] = "val" if i == 0 else "test"
    return split


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--holdout-styles", type=int, default=3, help="layout families kept out of training: one for val, the rest for test")
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    train_fonts = fonts()
    held_fonts = [f for f in usable_fonts(HELD_FONT_CANDIDATES) if f not in train_fonts]
    odd_fonts = usable_fonts(EDIT_ONLY_FONTS)
    (a.out / "images").mkdir(parents=True, exist_ok=True)
    (a.out / "masks").mkdir(parents=True, exist_ok=True)
    split_of = split_of_layouts(a.holdout_styles)
    with (a.out / "meta.jsonl").open("w", encoding="utf-8") as meta:
        for i in range(a.n):
            layout = rnd.randrange(N_LAYOUTS)
            split = split_of[layout]
            font_held = split != "train" and bool(held_fonts) and rnd.random() < 0.5
            font = rnd.choice(held_fonts if font_held else train_fonts)
            pool = train_fonts + odd_fonts + (held_fonts if split != "train" else [])
            p = make_palette(rnd)
            v = make_values(rnd, font)
            s = render(layout, p, v, font, rnd)
            pre_jpeg = rnd.random() < 0.6  # the screenshot was already a chat copy before anyone touched it (common)
            if pre_jpeg:
                s.img = jpeg(s.img, rnd.choice([95, 85, 75]))
                s.d = ImageDraw.Draw(s.img)
            edited = rnd.random() < 0.5
            mask = Image.new("L", s.img.size, 0)
            info: dict = {"field": None, "method": None, "same_font": None, "edit_font": None, "soft": None, "perfect": None}
            if edited:
                mask, info = tamper(s, v, p, pool, rnd)
            elif rnd.random() < 0.2:  # genuine look-alike: one field slightly softened, not edited
                k = rnd.choice(list(s.fields))
                bx = s.fields[k]["box"]
                s.img.paste(s.img.crop(bx).filter(ImageFilter.GaussianBlur(rnd.uniform(0.3, 0.7))), bx[:2])
                info["soft"] = True
            data, mask, q, scale, double = chat_copy(s.img, mask, rnd)
            sid = f"{i:06d}"
            (a.out / "images" / f"{sid}.jpg").write_bytes(data)
            mask.save(a.out / "masks" / f"{sid}.png")
            meta.write(json.dumps({"id": sid, "style": f"L{layout}", "split": split, "edited": edited, **info, "font": font,
                                   "font_held": font_held, "dark": p["dark"], "flat": p["card"] == p["bg"], "pre_jpeg": pre_jpeg,
                                   "jpeg_q": q, "scale": scale, "double_jpeg": double}) + "\n")
    held = sorted(f"L{k}" for k, sp in split_of.items() if sp != "train")

    splits = {"generator": "tools/make_payment_screens.py v3", "seed": a.seed, "n": a.n,
              "layouts": {sp: sorted(f"L{k}" for k, s2 in split_of.items() if s2 == sp) for sp in ("train", "val", "test")},
              "fonts": {"train": train_fonts, "val_test_only": held_fonts, "edit_only": odd_fonts},
              "meta_sha256": hashlib.sha256((a.out / "meta.jsonl").read_bytes()).hexdigest()}
    (a.out / "splits.json").write_text(json.dumps(splits, indent=1), encoding="utf-8")
    print(f"wrote {a.n} images to {a.out} (held-out layouts: {held}; held-out fonts: {held_fonts})")


if __name__ == "__main__":
    main()
