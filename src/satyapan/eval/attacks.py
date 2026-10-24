"""Attack yourself: real perturbations an attacker could use, run through the real checks, to see what changes.

Text: extra spacing and punctuation, look-alike (homoglyph) letters, Hinglish respelling of key words, a UPI ID split across lines.
Image: JPEG quality drop, resize, crop, brightness, noise, rotation.
Audio: chat-app re-encoding (Opus, AAC, 8 kHz telephone), pitch shift, background noise.
Nothing is stored. `sweep_text` measures how often each text perturbation makes a flagged kit scam slip through.
"""
from __future__ import annotations

import io
import json
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ..contracts.models import Tier
from ..service import CaseResult, analyse_image, analyse_text

FLAGGED = {Tier.SUSPICIOUS, Tier.HIGH_RISK, Tier.REGISTRY_HIT}
ROOT = Path(__file__).resolve().parents[3]

# ---- text --------------------------------------------------------------------------------------------------------

HOMOGLYPHS = {"a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "x": "х", "i": "і", "y": "у",
              "A": "А", "E": "Е", "O": "О", "P": "Р", "C": "С", "K": "Κ", "T": "Τ", "B": "Β"}
KEYWORDS = ["guaranteed", "guarantee", "profit", "returns", "return", "invest", "investment", "pay", "payment", "refund", "kyc", "otp",
            "pin", "link", "click", "urgent", "lottery", "winner", "prize", "fee", "tax", "withdraw", "account", "blocked", "verify",
            "update", "sebi", "registered", "daily", "monthly", "risk", "bonus", "task", "job", "parcel", "customs", "support"]
HINGLISH = {"guaranteed": "garunteed", "guarantee": "garanti", "profit": "prophit", "returns": "ritarns", "return": "ritarn",
            "investment": "invesment", "invest": "inwest", "payment": "pement", "pay": "pey", "refund": "rifund", "kyc": "k y c",
            "otp": "o.t.p", "link": "lnk", "click": "klik", "urgent": "arjent", "lottery": "lotri", "winner": "vinnar", "prize": "praij",
            "fee": "phee", "tax": "tacks", "withdraw": "vidraw", "account": "akount", "blocked": "blok", "verify": "verifai",
            "update": "apdet", "daily": "deli", "monthly": "mahina", "risk": "rissk", "bonus": "bonas", "registered": "rajistard",
            "customs": "kastam", "support": "saport", "job": "jobb", "task": "taask"}
UPI_RE = re.compile(r"([A-Za-z0-9._-]{2,})@([A-Za-z][A-Za-z0-9]{1,})")


def _kw_re() -> re.Pattern:
    return re.compile(r"\b(" + "|".join(sorted(map(re.escape, KEYWORDS), key=len, reverse=True)) + r")\b", re.IGNORECASE)


KW = _kw_re()


def spacing(t: str) -> str:
    """Letters of key words spread out with dots and spaces: 'g.u.a.r.a.n.t.e.e.d', doubled spaces, extra punctuation."""
    t = KW.sub(lambda m: ".".join(m.group(0)), t)
    return re.sub(r" ", "  ", t).replace(",", " ,").replace("!", " !!")


def homoglyph(t: str) -> str:
    """Latin letters swapped for Cyrillic or Greek letters that look the same."""
    return "".join(HOMOGLYPHS.get(ch, ch) for ch in t)


def hinglish(t: str) -> str:
    """Key words respelled the way people type them in Hinglish."""
    def rep(m: re.Match) -> str:
        w = m.group(0)
        r = HINGLISH.get(w.lower(), w)
        return r.upper() if w.isupper() else r
    return KW.sub(rep, t)


def split_upi(t: str) -> str:
    """The UPI ID broken across lines and written with 'at': 'alpha.gain88\\n(at) ybl'."""
    return UPI_RE.sub(lambda m: f"{m.group(1)}\n(at) {m.group(2)}", t)


def everything(t: str) -> str:
    return homoglyph(hinglish(spacing(split_upi(t))))


TEXT_ATTACKS = [("spacing", "Spacing and punctuation", "अक्षरों के बीच जगह और विराम चिह्न", spacing),
                ("homoglyph", "Look-alike letters", "हूबहू दिखने वाले दूसरे अक्षर", homoglyph),
                ("hinglish", "Hinglish respelling", "हिंग्लिश में अलग स्पेलिंग", hinglish),
                ("split_upi", "UPI ID split across lines", "UPI ID कई लाइनों में तोड़ी", split_upi),
                ("all", "All of the above together", "ऊपर के सभी एक साथ", everything)]


# ---- image -------------------------------------------------------------------------------------------------------

def _img(data: bytes):
    from PIL import Image, ImageOps
    return ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")


def _jpeg(img, q: int = 90) -> bytes:
    b = io.BytesIO()
    img.save(b, "JPEG", quality=q)
    return b.getvalue()


def img_jpeg(data: bytes) -> bytes:
    return _jpeg(_img(data), 25)


def img_resize(data: bytes) -> bytes:
    im = _img(data)
    return _jpeg(im.resize((max(1, im.width // 2), max(1, im.height // 2))))


def img_crop(data: bytes) -> bytes:
    im = _img(data)
    dx, dy = im.width // 10, im.height // 10
    return _jpeg(im.crop((dx, dy, im.width - dx, im.height - dy)))


def img_bright(data: bytes) -> bytes:
    from PIL import ImageEnhance
    return _jpeg(ImageEnhance.Brightness(_img(data)).enhance(1.35))


def img_noise(data: bytes) -> bytes:
    from PIL import Image
    a = np.asarray(_img(data), dtype=np.float32)
    a += np.random.default_rng(0).normal(0, 10, a.shape)
    return _jpeg(Image.fromarray(np.clip(a, 0, 255).astype("uint8")))


def img_rotate(data: bytes) -> bytes:
    return _jpeg(_img(data).rotate(3, expand=True, fillcolor=(255, 255, 255)))


IMAGE_ATTACKS = [("jpeg25", "JPEG quality 25", "JPEG गुणवत्ता 25", img_jpeg), ("resize50", "Shrunk to half size", "आधे आकार में छोटा", img_resize),
                 ("crop10", "Edges cropped by 10%", "किनारे 10% काटे", img_crop), ("bright", "Brighter by 35%", "35% ज़्यादा चमक", img_bright),
                 ("noise", "Grain (noise) added", "दाने (नॉइज़) जोड़े", img_noise), ("rotate3", "Rotated by 3 degrees", "3 डिग्री घुमाया", img_rotate)]


# ---- audio -------------------------------------------------------------------------------------------------------

def _reencode(wav: np.ndarray, codec: str) -> np.ndarray | None:
    from ..layers.l2_forensics import audio
    enc = audio.encode(wav, codec)
    return audio.decode(enc) if enc else None


def au_opus(w):
    return _reencode(w, "opus24k")


def au_aac(w):
    return _reencode(w, "aac64k")


def au_tel(w):
    return _reencode(w, "tel8k")


def au_pitch(w: np.ndarray) -> np.ndarray:
    """Pitch up about 2 semitones by resampling, keeping the length (speed changes slightly)."""
    f = 2 ** (2 / 12)
    idx = np.arange(0, len(w), f)
    return np.interp(idx, np.arange(len(w)), w).astype(np.float32)


def au_noise(w: np.ndarray) -> np.ndarray:
    """Background noise at about 20 dB signal-to-noise."""
    p = float(np.mean(w ** 2)) or 1e-8
    n = np.random.default_rng(0).normal(0, np.sqrt(p / 100), len(w)).astype(np.float32)
    return np.clip(w + n, -1, 1)


AUDIO_ATTACKS = [("opus24k", "WhatsApp-like Opus 24 kbps", "WhatsApp जैसा Opus 24 kbps", au_opus), ("aac64k", "AAC 64 kbps", "AAC 64 kbps", au_aac),
                 ("tel8k", "8 kHz phone line", "8 kHz फ़ोन लाइन", au_tel), ("pitch", "Pitch shifted up", "आवाज़ की पिच ऊँची", au_pitch),
                 ("noise", "Background noise added", "पीछे का शोर जोड़ा", au_noise)]


# ---- running -----------------------------------------------------------------------------------------------------

@dataclass
class Outcome:
    key: str
    label: tuple[str, str]
    tier: str | None
    changed: bool
    codes: list[str] = field(default_factory=list)
    lost: list[str] = field(default_factory=list)      # reason codes the original had and this one lost
    gained: list[str] = field(default_factory=list)
    preview: str = ""                                  # the perturbed text (text attacks only)
    note: str = ""                                     # extra measured fact, e.g. "voice sign lost"


def _codes(res: CaseResult) -> list[str]:
    return list(res.verdicts["en"].reason_codes)


def compare(base: CaseResult, key: str, label: tuple[str, str], res: CaseResult | None, preview: str = "", note: str = "") -> Outcome:
    if res is None:
        return Outcome(key, label, None, True, note=note or "unreadable after this change")
    b, c = set(_codes(base)), _codes(res)
    return Outcome(key, label, res.tier.value, res.tier != base.tier, c, sorted(b - set(c)), sorted(set(c) - b), preview, note)


def attack_text(text: str) -> tuple[CaseResult, list[Outcome]]:
    base = analyse_text(text, use_registry=False)
    out = []
    for key, en, hi, fn in TEXT_ATTACKS:
        t = fn(text)
        out.append(compare(base, key, (en, hi), analyse_text(t, use_registry=False), preview=t[:600]))
    return base, out


def attack_image(data: bytes) -> tuple[CaseResult, list[Outcome]]:
    base = analyse_image(data)
    base_edit = "MEDIA_IMAGE_EDITED" in _codes(base)
    out = []
    for key, en, hi, fn in IMAGE_ATTACKS:
        try:
            res = analyse_image(fn(data))
        except Exception:
            res = None
        note = ""
        if res is not None and base_edit != ("MEDIA_IMAGE_EDITED" in _codes(res)):
            note = "edit sign lost" if base_edit else "edit sign appeared"
        out.append(compare(base, key, (en, hi), res, note=note))
    return base, out


def attack_audio(data: bytes) -> tuple[CaseResult | None, list[Outcome], dict]:
    """Perturb the decoded audio and re-run the voice check. Returns (base, outcomes, info) where info has the base transcript."""
    from ..layers.l2_forensics import audio
    from ..plugins.models_voice import check_voice
    wav = audio.decode(data)
    if wav is None:
        return None, [], {}
    t = audio.transcribe(wav)
    base_text = t[0] if t else ""
    base = check_voice(b"", transcript=base_text, layer=audio.voice_layer(wav))
    base_band = audio.voice_layer(wav).internal.get("band")
    out = []
    for key, en, hi, fn in AUDIO_ATTACKS:
        w = fn(wav)
        if w is None:
            out.append(compare(base, key, (en, hi), None))
            continue
        layer = audio.voice_layer(w)
        tt = audio.transcribe(w)
        text = tt[0] if tt else ""
        res = check_voice(b"", transcript=text, layer=layer)
        notes = []
        if layer.internal.get("band") != base_band:
            notes.append(f"voice: {base_band} -> {layer.internal.get('band')}")
        if text.strip() != base_text.strip():
            from rapidfuzz import fuzz
            notes.append(f"words {fuzz.ratio(text, base_text):.0f}% the same")
        out.append(compare(base, key, (en, hi), res, preview=text[:300], note="; ".join(notes)))
    return base, out, {"transcript": base_text, "band": base_band}


def sweep_text(rows: list[dict], use_plugins: bool = True) -> dict:
    """For each text attack: of the kit scams the checks flag, how many are no longer flagged after it (evasion rate).
    use_plugins=False measures the rules alone; True measures the site as deployed (rules plus our hooks and models)."""
    from ..plugins import load_plugins
    from .metrics import rate
    load_plugins()  # no-op when the app already loaded them

    def flagged_(t: str) -> bool:
        return analyse_text(t, use_registry=False, use_plugins=use_plugins).tier in FLAGGED
    scams = [r for r in rows if r["label"] == "scam"]
    flagged = [r for r in scams if flagged_(r["text"])]
    benign = [r for r in rows if r["label"] != "scam"]
    fa_before = sum(flagged_(r["text"]) for r in benign)
    out = {"n_scams": len(scams), "n_flagged_before": len(flagged), "attacks": []}
    for key, en, hi, fn in TEXT_ATTACKS:
        slipped = [r for r in flagged if not flagged_(fn(r["text"]))]
        fa_after = sum(flagged_(fn(r["text"])) for r in benign)
        out["attacks"].append({"key": key, "label_en": en, "label_hi": hi, "evasion": rate(len(slipped), len(flagged)),
                               "genuine_flagged_before": rate(fa_before, len(benign)), "genuine_flagged_after": rate(fa_after, len(benign)),
                               "examples": [r["text"][:120] for r in slipped[:3]]})
    return out


def main() -> None:
    """python -m satyapan.eval.attacks: write docs/results/attack_text.json from every kit file."""
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "results" / "attack_text.json")
    a = ap.parse_args()
    files = sorted(p for p in (ROOT / "data" / "kit").glob("*.jsonl") if "missed" not in p.stem)
    rows = [json.loads(x) for p in files for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    res = sweep_text(rows, use_plugins=True)
    res |= {"dataset": ", ".join(p.relative_to(ROOT).as_posix() for p in files), "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "reproduce": "python -m satyapan.eval.attacks", "rules_only": sweep_text(rows, use_plugins=False),
            "note": "The hidden-word check was written after the rules-only sweep showed these gaps, using the same kit, so the as-deployed "
                    "numbers are optimistic; the held-out kit files are the fair test."}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for name, r in (("rules only", res["rules_only"]), ("as deployed", res)):
        for x in r["attacks"]:
            e = x["evasion"]
            print(f"{name:12s} {x['key']:10s} slipped through: {e['k']}/{e['n']}   genuine flagged {x['genuine_flagged_before']['k']} -> "
                  f"{x['genuine_flagged_after']['k']}")


if __name__ == "__main__":
    random.seed(0)
    main()
