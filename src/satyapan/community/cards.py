"""Server-made pictures: warning cards, the Scam-Aware certificate, the family safe-word card, and A4 posters.

Drawn with Pillow using the Noto Sans fonts already shipped in web/static/fonts (SIL Open Font License; Latin and Devanagari files).
Hindi is shaped by Pillow's Raqm layout, so conjuncts and vowel signs come out right. No photographs, no logos, nobody's face:
only text, flat colour and, on posters, a QR code that points to the site address.
Posters are embedded as pictures in a reportlab PDF because reportlab cannot shape Devanagari text itself.
"""
from __future__ import annotations

import io
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import content

FONTS = Path(__file__).resolve().parents[3] / "web" / "static" / "fonts"
LATIN, DEVA = "c916a8117b.woff2", "e31c9bb4f7.woff2"
NAVY, SAFFRON, RED, GREEN, INK, MUTED, LINE, PAPER, TINT = "#0B2A4A", "#E8760A", "#B42318", "#146C2E", "#16202C", "#4A5566", "#C9D1DC", "#FFFFFF", "#F3F5F8"
_DEV = re.compile("[ऀ-ॿ‌‍]")
HELPLINE = {"en": "Lost money? Call 1930 or report at cybercrime.gov.in", "hi": "पैसे चले गए? 1930 पर कॉल करें या cybercrime.gov.in पर शिकायत करें"}
CHECK_LINE = {"en": "Check before you pay", "hi": "पैसे भेजने से पहले जाँचें"}
DISCLAIMER = {"en": "Satyapan Scam-Aware, a learning certificate, not an official qualification.",
              "hi": "सत्यापन स्कैम-सजग, सीखने का प्रमाणपत्र है, कोई सरकारी या आधिकारिक योग्यता नहीं।"}


@lru_cache(maxsize=64)
def font(size: int, bold: bool = False, deva: bool = False) -> ImageFont.FreeTypeFont:
    try:
        f = ImageFont.truetype(str(FONTS / (DEVA if deva else LATIN)), size)
        f.set_variation_by_axes([700 if bold else 400])
        return f
    except (OSError, ValueError):
        return ImageFont.load_default(size)


def _runs(text: str) -> list[tuple[str, bool]]:
    out: list[tuple[str, bool]] = []
    for ch in text:
        d = bool(_DEV.match(ch))
        if out and out[-1][1] == d:
            out[-1] = (out[-1][0] + ch, d)
        else:
            out.append((ch, d))
    return out


@lru_cache(maxsize=20000)
def _len(text: str, size: int, bold: bool, deva: bool) -> float:
    return font(size, bold, deva).getlength(text)


def width(text: str, size: int, bold: bool = False) -> float:
    return sum(_len(t, size, bold, d) for t, d in _runs(text))


def put(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, size: int, fill: str = INK, bold: bool = False) -> float:
    """Draw one line, switching font per script. Returns the x where it ended."""
    x, y = xy
    for t, d in _runs(text):
        f = font(size, bold, d)
        draw.text((x, y), t, font=f, fill=fill, anchor="ls")
        x += f.getlength(t)
    return x


def wrap(text: str, size: int, max_w: int, bold: bool = False) -> list[str]:
    """Greedy line breaking on spaces. Word widths are measured once each, which is far cheaper than re-shaping every trial line."""
    space = width(" ", size, bold)
    lines: list[str] = []
    for para in text.split("\n"):
        cur, cur_w = "", 0.0
        for word in para.split(" "):
            w = width(word, size, bold)
            if cur and cur_w + space + w > max_w:
                lines.append(cur)
                cur, cur_w = word, w
            else:
                cur, cur_w = (cur + " " + word if cur else word), (cur_w + space + w if cur else w)
        lines.append(cur)
    return lines


class _Dry:
    """Stands in for ImageDraw while only measuring how tall the text will be."""

    def __getattr__(self, _name):
        return lambda *a, **k: None


class Sheet:
    """A page of flowing text. `y` is the baseline of the next line. With dry=True nothing is drawn: used to pick a text size that fits."""

    def __init__(self, w: int, h: int, margin: int, bg: str = PAPER, dry: bool = False):
        self.img = Image.new("RGB", (8, 8) if dry else (w, h), bg)
        self.d = _Dry() if dry else ImageDraw.Draw(self.img)
        self.w, self.h, self.m, self.y = w, h, margin, margin

    def text(self, text: str, size: int, fill: str = INK, bold: bool = False, gap: float = 0.5, indent: int = 0, center: bool = False) -> None:
        lead = int(size * 1.42)
        for line in wrap(text, size, self.w - 2 * self.m - indent, bold):
            self.y += lead
            x = (self.w - width(line, size, bold)) / 2 if center else self.m + indent
            put(self.d, (x, self.y), line, size, fill, bold)
        self.y += int(size * gap)

    def bullets(self, items: list[str], size: int, fill: str = INK, mark: str = SAFFRON) -> None:
        lead = int(size * 1.42)
        for it in items:
            lines = wrap(it, size, self.w - 2 * self.m - size * 1.4)
            for i, line in enumerate(lines):
                self.y += lead
                if i == 0:
                    r = size * 0.18
                    cy = self.y - size * 0.32
                    self.d.ellipse((self.m + size * 0.2 - r, cy - r, self.m + size * 0.2 + r, cy + r), fill=mark)
                put(self.d, (self.m + size * 1.1, self.y), line, size, fill)
            self.y += int(size * 0.25)
        self.y += int(size * 0.3)

    def numbered(self, items: list[str], size: int) -> None:
        lead = int(size * 1.42)
        for n, it in enumerate(items, 1):
            lines = wrap(it, size, self.w - 2 * self.m - size * 1.6)
            top = self.y + lead - size
            self.d.ellipse((self.m, top, self.m + size * 1.1, top + size * 1.1), fill=NAVY)
            put(self.d, (self.m + size * 0.36, top + size * 0.88), str(n), int(size * 0.8), PAPER, True)
            for line in lines:
                self.y += lead
                put(self.d, (self.m + size * 1.5, self.y), line, size)
            self.y += int(size * 0.3)
        self.y += int(size * 0.3)

    def band(self, y0: int, y1: int, fill: str) -> None:
        self.d.rectangle((0, y0, self.w, y1), fill=fill)

    def png(self, dpi: int | None = None) -> bytes:
        buf = io.BytesIO()
        self.img.save(buf, "PNG", optimize=True, **({"dpi": (dpi, dpi)} if dpi else {}))
        return buf.getvalue()


def _qr(url: str, size: int) -> Image.Image | None:
    try:
        import segno
    except ImportError:
        return None
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="png", scale=8, border=2)
    return Image.open(buf).convert("RGB").resize((size, size), Image.NEAREST)


def _header(s: Sheet, lang: str, label: str, color: str, h: int = 130) -> None:
    s.band(0, h, NAVY)
    s.band(h, h + 10, SAFFRON)
    put(s.d, (s.m, h * 0.62), "Satyapan  सत्यापन", int(h * 0.42), PAPER, True)
    tw = width(label, int(h * 0.24), True)
    s.d.rectangle((s.w - s.m - tw - 40, h * 0.22, s.w - s.m, h * 0.78), fill=color)
    put(s.d, (s.w - s.m - tw - 20, h * 0.6), label, int(h * 0.24), PAPER, True)
    s.y = h + 20


def _footer(s: Sheet, lang: str, site: str, qr: bool = False) -> None:
    top = s.h - 250
    s.band(top, s.h, NAVY)
    put(s.d, (s.m, top + 85), CHECK_LINE[lang], 54, PAPER, True)
    put(s.d, (s.m, top + 145), site.replace("https://", "").replace("http://", ""), 40, "#FFD7A8", True)
    put(s.d, (s.m, top + 205), HELPLINE[lang], 28 if lang == "hi" else 30, "#CFDAE8")
    if qr and (img := _qr(site, 170)):
        s.img.paste(img, (s.w - s.m - 170, top + 40))


# ---- warning cards ----------------------------------------------------------------------------------------
LABEL = {"en": "SCAM WARNING", "hi": "स्कैम से सावधान"}
SIGNS = {"en": "Signs to look for", "hi": "ये संकेत देखें"}
WHAT = {"en": "What to do", "hi": "क्या करें"}
PEOPLE = {"en": "reported by people on Satyapan", "hi": "सत्यापन पर लोगों ने बताया"}


def _fit(build, limit: int, scales=(1.35, 1.25, 1.15, 1.05, 1.0, 0.92, 0.85)) -> Sheet:
    """Pick the largest text size whose measured height still leaves room for the footer, then draw once at that size."""
    for k in scales:
        if build(k, True).y <= limit:
            return build(k, False)
    return build(scales[-1], False)


@lru_cache(maxsize=96)
def lesson_card(slug: str, lang: str, site: str) -> bytes | None:
    l = content.lesson(slug)
    if not l:
        return None
    lang = "hi" if lang == "hi" else "en"

    def build(k: float, dry: bool) -> Sheet:
        s = Sheet(1080, 1350, 64, dry=dry)
        _header(s, lang, LABEL[lang], RED)
        s.text(l["title"][lang], int(52 * k), NAVY, True, 0.4)
        s.text(l["summary"][lang], int(32 * k), INK, False, 0.6)
        s.d.rectangle((s.m, s.y, s.w - s.m, s.y + 4), fill=LINE)
        s.y += 24
        s.text(SIGNS[lang], int(36 * k), RED, True, 0.2)
        s.bullets(l["flags"][lang][:4], int(31 * k))
        s.text(WHAT[lang], int(36 * k), GREEN, True, 0.2)
        s.bullets(l["do"][lang][:2], int(31 * k), mark=GREEN)
        return s

    s = _fit(build, 1350 - 250 - 20)
    _footer(s, lang, site)
    return s.png()


def post_card(post: dict, lang: str, site: str) -> bytes:
    """`post` is a view from community.posts.get: its text is already sanitised."""
    lang = "hi" if lang == "hi" else "en"
    s = Sheet(1080, 1350, 64)
    _header(s, lang, LABEL[lang], RED)
    s.text(post["tier_label"], 52, RED if post["tier_class"] in ("r", "a") else NAVY, True, 0.2)
    s.text(f"{post['sightings']} " + {"en": "people saw this", "hi": "लोगों ने यह देखा"}[lang] if post.get("sightings") else PEOPLE[lang], 30, MUTED, False, 0.6)
    s.d.rectangle((s.m, s.y, s.m + 8, s.y + 330), fill=SAFFRON)
    start = s.y
    s.text(post["excerpt"][:330] + ("…" if len(post["excerpt"]) > 330 else ""), 36, INK, False, 0.4, indent=28)
    s.y = max(s.y, start)
    if post.get("entity"):
        s.text(post["entity"], 40, NAVY, True, 0.5, indent=28)
    s.text(SIGNS[lang], 36, RED, True, 0.1)
    s.bullets([r for r in post["reasons"][:3]], 29)
    _footer(s, lang, site)
    return s.png()


# ---- certificate ------------------------------------------------------------------------------------------
LEVEL_WORD = {"en": "Level", "hi": "स्तर"}


def certificate(handle: str, level: dict, lang: str, when: datetime, site: str) -> bytes:
    lang = "hi" if lang == "hi" else "en"
    s = Sheet(1600, 1131, 90)
    s.d.rectangle((24, 24, s.w - 24, s.h - 24), outline=NAVY, width=8)
    s.d.rectangle((44, 44, s.w - 44, s.h - 44), outline=SAFFRON, width=3)
    s.y = 150
    s.text("Satyapan  सत्यापन", 44, NAVY, True, 0.3, center=True)
    s.text({"en": "Scam-Aware", "hi": "स्कैम-सजग"}[lang], 110, NAVY, True, 0.2, center=True)
    s.text({"en": "Learning certificate", "hi": "सीखने का प्रमाणपत्र"}[lang], 44, SAFFRON, True, 0.8, center=True)
    s.text({"en": "This is to say that", "hi": "यह बताता है कि"}[lang], 34, MUTED, False, 0.2, center=True)
    s.text(handle, 84, INK, True, 0.2, center=True)
    s.text({"en": "read all 12 scam lessons and finished 3 Scam Drill rounds.", "hi": "ने स्कैम के सारे 12 पाठ पढ़े और स्कैम ड्रिल के 3 राउंड पूरे किए।"}[lang], 36, INK, False, 0.5, center=True)
    name = level["name_hi"] if lang == "hi" else level["name_en"]
    s.text(f"{LEVEL_WORD[lang]} {level['level']} · {name}", 42, NAVY, True, 0.3, center=True)
    s.text(when.strftime("%d %B %Y") if lang == "en" else when.strftime("%d-%m-%Y"), 34, MUTED, False, 0.5, center=True)
    s.text(DISCLAIMER[lang], 28, RED, False, 0.2, center=True)
    s.text(site.replace("https://", "").replace("http://", ""), 30, NAVY, True, 0, center=True)
    return s.png()


# ---- family safe-word card (A4 at 150 dpi) ----------------------------------------------------------------
SAFE = {
    "en": {"title": "Our family safe word", "for": "For", "word": "The word", "how": "How to use it",
           "steps": ["If someone phones, in a voice you know, and asks for money, ask for the safe word.",
                     "Say it only when they have said it first. Never say it on a call you did not expect.",
                     "No word, or the wrong word? Hang up and call the person on the number you already have.",
                     "Do not write it in a message or post it online. Change it if it is ever shared."]},
    "hi": {"title": "हमारे परिवार का सुरक्षित शब्द", "for": "किसके लिए", "word": "शब्द", "how": "इसका इस्तेमाल कैसे करें",
           "steps": ["अगर कोई जानी-पहचानी आवाज़ में फ़ोन करके पैसे माँगे, तो उससे सुरक्षित शब्द पूछिए।",
                     "आप तब बोलिए जब वे पहले बोल दें। जिस कॉल की उम्मीद नहीं थी, उस पर कभी न बोलें।",
                     "शब्द नहीं आया या ग़लत आया? कॉल काटिए और उस व्यक्ति को उसी नंबर पर फ़ोन कीजिए जो आपके पास पहले से है।",
                     "इसे संदेश में न लिखें और ऑनलाइन न डालें। अगर कभी किसी को पता चल जाए तो बदल दें।"]},
}


def safe_word_card(word: str, who: str, lang: str, site: str) -> bytes:
    lang = "hi" if lang == "hi" else "en"
    t = SAFE[lang]
    s = Sheet(1240, 1754, 90)
    s.d.rectangle((30, 30, s.w - 30, s.h - 30), outline=NAVY, width=6)
    s.d.rectangle((54, 54, s.w - 54, s.h - 54), outline=LINE, width=2)
    s.y = 100
    s.text("Satyapan  सत्यापन", 36, MUTED, True, 0.2, center=True)
    s.text(t["title"], 64, NAVY, True, 0.6, center=True)
    if who:
        s.text(f"{t['for']}: {who}", 44, INK, True, 0.5, center=True)
    s.text(t["word"], 34, MUTED, False, 0.1, center=True)
    size = 150
    while width(word, size, True) > s.w - 2 * s.m - 40 and size > 50:
        size -= 6
    top = s.y + 20
    box_h = int(size * 1.6)
    s.d.rectangle((s.m, top, s.w - s.m, top + box_h), fill=TINT, outline=NAVY, width=5)
    put(s.d, ((s.w - width(word, size, True)) / 2, top + box_h * 0.68), word, size, NAVY, True)       # centred in the box
    s.y = top + box_h + 30
    s.text(t["how"], 44, SAFFRON, True, 0.3)
    s.numbered(t["steps"], 36)
    s.d.rectangle((s.m, s.h - 330, s.w - s.m, s.h - 215), fill=RED)
    put(s.d, (s.m + 30, s.h - 255), HELPLINE[lang], 34 if lang == "en" else 30, PAPER, True)
    put(s.d, (s.m, s.h - 130), site.replace("https://", "").replace("http://", ""), 38, NAVY, True)
    return s.png(150)


# ---- A4 posters -------------------------------------------------------------------------------------------
HOW = {"en": "How it works", "hi": "यह कैसे होता है"}


@lru_cache(maxsize=96)
def poster_png(slug: str, lang: str, site: str) -> bytes | None:
    l = content.lesson(slug)
    if not l:
        return None
    lang = "hi" if lang == "hi" else "en"

    def build(k: float, dry: bool) -> Sheet:
        s = Sheet(1240, 1754, 72, dry=dry)
        _header(s, lang, LABEL[lang], RED, 150)
        s.text(l["title"][lang], int(60 * k), NAVY, True, 0.3)
        s.text(l["summary"][lang], int(34 * k), INK, False, 0.4)
        s.text(HOW[lang], int(40 * k), NAVY, True, 0.1)
        s.numbered(l["how"][lang], int(31 * k))
        s.text(SIGNS[lang], int(40 * k), RED, True, 0.1)
        s.bullets(l["flags"][lang][:4], int(31 * k))
        s.text(WHAT[lang], int(40 * k), GREEN, True, 0.1)
        s.bullets(l["do"][lang][:3], int(31 * k), mark=GREEN)
        return s

    s = _fit(build, 1754 - 250 - 30)
    _footer(s, lang, site, qr=True)
    return s.png(150)


def poster_pdf(lang: str, site: str, slug: str | None = None) -> bytes:
    """One A4 page per scam (all 12, or just `slug`), as a PDF ready to print for a shop or a housing society notice board."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    pdf.setTitle("Satyapan scam posters" if lang == "en" else "सत्यापन स्कैम पोस्टर")
    slugs = [slug] if slug else [l["slug"] for l in content.lessons()]
    for sl in slugs:
        png = poster_png(sl, lang, site)
        if png:
            pdf.drawImage(ImageReader(io.BytesIO(png)), 0, 0, width=A4[0], height=A4[1])
            pdf.showPage()
    pdf.save()
    return buf.getvalue()
