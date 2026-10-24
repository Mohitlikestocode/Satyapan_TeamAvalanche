"""Undo the text tricks scammers use to slip past word filters, so the same rules can see the real words.

Measured on our kit (docs/results/attack_text.json): look-alike Cyrillic or Greek letters let 32 of 37 flagged scams through the
rules, spaced-out letters 10 of 37, a UPI ID split across lines 4 of 37. This module folds those back:
- look-alike letters inside Latin words (Cyrillic and Greek only; Devanagari and other scripts are never touched),
- zero-width characters,
- letters spread out with dots, dashes or spaces ("g.u.a.r.a.n.t.e.e.d", "o t p"),
- a UPI ID written as "name (at) bank", "name [at] bank", "name @ bank" or broken across lines.
It does not undo Hinglish respellings: guessing those would only memorise our own attack list.
Text is data: it is only rewritten with fixed tables and patterns, never interpreted.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

CONFUSABLES = {
    # Cyrillic
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "і": "i", "у": "y", "ѕ": "s",
    "ј": "j", "ԁ": "d", "һ": "h", "ӏ": "l", "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M",
    "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T", "Х": "X", "І": "I", "Ѕ": "S", "Ј": "J",
    # Greek
    "ο": "o", "α": "a", "ν": "v", "ρ": "p", "τ": "t", "κ": "k", "ι": "i", "Α": "A", "Β": "B",
    "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O", "Ρ": "P",
    "Τ": "T", "Υ": "Y", "Χ": "X",
}
ZERO_WIDTH = re.compile("[​⁠﻿­]|(?<=[A-Za-z0-9])[‌‍]+(?=[A-Za-z0-9])")  # ZWJ/ZWNJ are real in Devanagari
MIN_SPREAD_WORD = 5  # "g.u.a.r.a.n.t.e.e.d" is a trick; "U.S.A" or "K.Y.C" is ordinary writing (still joined, not counted as a trick)
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
# three or more single letters joined by dots, dashes, stars, underscores or single spaces: g.u.a.r.a.n.t.e.e.d, o t p, K-Y-C
_SPREAD = re.compile(r"(?<![A-Za-z])(?:[A-Za-z](?:[.\-*_]|\s(?=[A-Za-z](?:[.\-*_\s]|$|[^A-Za-z]))|[.\-*_]\s)){2,}[A-Za-z](?![A-Za-z])")
# "(at)", "[at]", "{at}" are deliberate; a stray space or line break around "@" is usually OCR noise (10% of our OCR'd
# screenshots), so it is joined for the payee check but not counted as a trick.
_UPI_SPLIT = re.compile(r"([A-Za-z0-9][A-Za-z0-9._\-]{1,63})\s*(?:\(\s*at\s*\)|\[\s*at\s*\]|\{\s*at\s*\})\s*([A-Za-z]{2,32})(?![\w@])",
                        re.IGNORECASE)
_UPI_SPACED = re.compile(r"([A-Za-z0-9][A-Za-z0-9._\-]{1,63})(?:\s+@\s*|@\s+)([A-Za-z]{2,32})(?![\w@])")


@dataclass
class Normalised:
    original: str
    text: str
    tricks: list[str] = field(default_factory=list)  # which tricks were found: lookalike, zero_width, spread_letters, split_upi

    @property
    def changed(self) -> bool:
        return self.text != self.original


def _is_latin(ch: str) -> bool:
    return "LATIN" in unicodedata.name(ch, "")


def fold_lookalikes(text: str) -> tuple[str, bool]:
    """Replace look-alike letters only inside words that also contain Latin letters (mixed-script words)."""
    found = False

    def fix(m: re.Match) -> str:
        nonlocal found
        w = m.group(0)
        if any(c in CONFUSABLES for c in w) and (any(_is_latin(c) for c in w) or all(c in CONFUSABLES for c in w)):
            found = True
            return "".join(CONFUSABLES.get(c, c) for c in w)
        return w
    return _WORD.sub(fix, text), found


def normalise(text: str) -> Normalised:
    out = Normalised(original=text, text=text)
    t = unicodedata.normalize("NFKC", text)
    t2 = ZERO_WIDTH.sub("", t)
    if t2 != t:
        out.tricks.append("zero_width")
    t, hit = fold_lookalikes(t2)
    if hit:
        out.tricks.append("lookalike")
    long_spread = False

    def join(m: re.Match) -> str:
        nonlocal long_spread
        w = re.sub(r"[.\-*_\s]", "", m.group(0))
        long_spread |= len(w) >= MIN_SPREAD_WORD
        return w
    t = _SPREAD.sub(join, t)
    if long_spread:
        out.tricks.append("spread_letters")
    t2 = _UPI_SPLIT.sub(lambda m: f"{m.group(1)}@{m.group(2)}", t)
    if t2 != t:
        out.tricks.append("split_upi")
    out.text = _UPI_SPACED.sub(lambda m: f"{m.group(1)}@{m.group(2)}", t2)
    return out
