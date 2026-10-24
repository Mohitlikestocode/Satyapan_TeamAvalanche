"""A small, honest word filter. It catches the obvious, not everything: moderation and abuse reports cover the rest.

Strong words are matched anywhere in the normalised text; short or ambiguous ones only as whole words, so "class" and "Scunthorpe"
are not blocked.
"""
from __future__ import annotations

import re
import unicodedata

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i"})

STRONG = {
    "fuck", "bitch", "bastard", "asshole", "whore", "nigger", "faggot", "motherfucker",
    "madarchod", "maderchod", "bhenchod", "behenchod", "bhosdi", "bhosda", "chutiya", "chutiye", "gandu", "harami",
    "haramkhor", "kamina", "gaandu", "bhadwa", "bhadwe", "raand", "chodu", "hijda",
    "मादरचोद", "बहनचोद", "भोसड़ी", "भोसडी", "चूतिया", "चुतिया", "गांडू", "रंडी", "हरामी", "हरामखोर", "कमीना", "लौड़ा", "भड़वा", "हिजड़ा",
}
WHOLE = {"ass", "dick", "cock", "tit", "tits", "mc", "bc", "bkl", "mkc", "sex", "xxx", "gand", "gaand", "pussy", "damn", "crap", "shit",
         "shitty", "cunt", "slut", "porn", "nazi", "randi", "lund", "lauda", "chod", "tatte"}
RESERVED = {"admin", "administrator", "moderator", "satyapan", "support", "official", "police", "cyberpolice", "helpline", "sebi", "rbi", "npci"}


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).lower().translate(_LEET)
    return re.sub(r"(.)\1{2,}", r"\1\1", t)           # "fuuuck" -> "fuuck"


def contains_profanity(text: str) -> bool:
    t = _norm(text)
    squashed = re.sub(r"[\W_]+", "", t)
    if any(w in squashed for w in STRONG):
        return True
    words = set(re.findall(r"[^\W_]+", t))
    return bool(words & WHOLE)


def is_reserved(text: str) -> bool:
    squashed = re.sub(r"[\W_]+", "", _norm(text))
    return any(r in squashed for r in RESERVED)
