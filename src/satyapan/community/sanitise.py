"""Mask personal data in anything a visitor submits, before it is stored or shown.

What is kept: wording of the message, link *domains*, and UPI IDs that pass the validator (phone-like ones are partly masked).
What is masked: phone numbers, e-mail addresses, long digit runs (Aadhaar, account and card numbers), OTP/PIN/CVV values, PAN,
names after a greeting, and everything in a link after the domain (paths and query strings often carry tokens).

How: entities are lifted out into private-use placeholders in a fixed order (so one pattern cannot eat another's match), the rest is
masked, then placeholders are replaced by their safe display text. A last pass re-scans the result: if anything that still looks like
personal data survives, `clean` is False and the caller must not publish it automatically.

Best effort, not a guarantee: free-text names, addresses and unusual formats can slip through. Moderation and "delete my post"
exist for that, and docs/community.md says so.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import urlparse

from ..extract.entities import VPA_RE, parse_upi_uri
from ..layers.l3_payee.domains import hostname
from .profanity import contains_profanity

MAX_INPUT = 1000
MAX_EXCERPT = 600

_DEVANAGARI_DIGITS = {ord(c): str(i) for i, c in enumerate("०१२३४५६७८९")}
_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u202a\u202b\u202c\u202d\u202e"), None)

_UPI_URI = re.compile(r"upi://pay\?[^\s<>\"']+", re.I)
_URL = re.compile(r"\b(?:https?://|www\.)[^\s<>\"'\u0964]+", re.I)
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
_VPA = re.compile(r"(?<![\w.@/])([A-Za-z0-9][A-Za-z0-9._\-]{1,63}@[A-Za-z]{2,32})(?![\w@]|\.[A-Za-z])")
_TLDS = ("com|in|co\\.in|net|org|info|xyz|top|online|site|link|app|club|vip|live|shop|store|cc|me|ly|gl|to|tk|ml|ga|cf|gq|biz|io|ai|pw|icu|"
         "cyou|buzz|work|click|life|world|today|pro|cloud|fun|cam|rest|bond|sbs|digital|tech|website|space|co|us|uk|ly|page|help")
_BARE = re.compile(rf"(?<![\w.@/\-])((?:[A-Za-z0-9](?:[A-Za-z0-9\-]{{0,61}}[A-Za-z0-9])?\.)+(?:{_TLDS}))(?![\w@\-]|\.[A-Za-z0-9])(?:/[^\s<>\"'\u0964]*)?", re.I)
_PHONE = re.compile(r"(?<![\d])(?:(?:\+|00)?91[\s\-]?|0)?([6-9]\d{9}|[6-9]\d{4}[\s\-]\d{5}|[6-9]\d{2}[\s\-]\d{3}[\s\-]\d{4})(?!\d)")
_LONG = re.compile(r"(?<!\d)(?:\d{9,}|\d{4,6}(?:[ \-]\d{4,6}){2,4})(?!\d)")
_SECRET = re.compile(r"(?i:\b(?:otp|mpin|pin|cvv|cvc|password|passcode|code)\b|ओटीपी|पिन|पासवर्ड|कोड)([^\d\n]{0,16})(\d{3,8})(?!\d)")
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_GREET = re.compile(r"(?i:\b(?:dear|hello|hi|hey|namaste|namaskar|mr|mrs|ms|shri|shree|smt|sri)\b\.?)(\s+)([A-Z][a-z]{2,19})(?:(\s+)([A-Z][a-z]{2,19}))?")
_GREET_HI = re.compile(r"(?:प्रिय|श्री|श्रीमती|सुश्री|नमस्ते|हेलो)(\s+)([\u0900-\u0963\u0966-\u097F]{2,20})")
_MYNAME = re.compile(r"(?i:\bmy name is\b|\bmera naam\b|\bmera name\b)(\s+)([A-Z][a-z]{2,19})(?:(\s+)([A-Z][a-z]{2,19}))?")
_MYNAME_HI = re.compile(r"(मेरा नाम)(\s+)([\u0900-\u0963\u0966-\u097F]{2,20})")
_GENERIC = {"customer", "user", "sir", "madam", "friend", "valued", "account", "holder", "member", "investor", "applicant", "candidate",
            "sir/madam", "team", "all", "everyone", "there", "bhai", "dost", "beta", "uncle", "aunty", "ji", "sirji", "ग्राहक", "उपयोगकर्ता",
            "महोदय", "महोदया", "मित्र", "खाताधारक", "सर", "मैडम", "जी", "दोस्त", "भाई", "सदस्य", "निवेशक", "साथी"}
_RESIDUAL_PHONE = re.compile(r"(?<!\d)[6-9]\d{9}(?!\d)")
_RESIDUAL_LONG = re.compile(r"\d{9,}")
_MARK = re.compile("\ue000(\\d+)\ue001")


@dataclass
class Entity:
    kind: str          # "upi" | "domain" | "phone"
    value: str         # normalised value, used only in memory to build keyed hashes: NEVER stored or shown
    display: str       # safe text: what may be stored and shown


@dataclass
class Sanitised:
    excerpt: str
    clean: bool = True
    masked: dict[str, int] = field(default_factory=dict)
    entities: list[Entity] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    @property
    def total_masked(self) -> int:
        return sum(self.masked.values())

    def first(self, kind: str) -> Entity | None:
        return next((e for e in self.entities if e.kind == kind), None)

    def primary(self) -> Entity | None:
        """The identifier used to link duplicates: a payee first, then a link domain, then a phone number."""
        return self.first("upi") or self.first("domain") or self.first("phone")


def mask_digits(digits: str) -> str:
    return digits if len(digits) <= 4 else digits[:2] + "X" * (len(digits) - 4) + digits[-2:]


def display_upi(vpa: str) -> str:
    """UPI IDs that are really phone numbers or long numbers are partly masked; word-like ones are kept for awareness."""
    local, _, handle = vpa.partition("@")
    return re.sub(r"\d{6,}", lambda m: mask_digits(m.group(0)), local) + "@" + handle


def normalise(raw: str) -> str:
    t = unicodedata.normalize("NFKC", raw or "").translate(_ZERO_WIDTH).translate(_DEVANAGARI_DIGITS)
    t = "".join(ch for ch in t if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()[:MAX_INPUT]


def _domain_of(url: str) -> str | None:
    h = hostname(url if "://" in url else "http://" + url)
    if not h or len(h) > 100 or not re.fullmatch(r"[a-z0-9.\-]+", h) or "." not in h:
        return None
    return h[4:] if h.startswith("www.") and h.count(".") >= 2 else h


def sanitise(raw: str) -> Sanitised:
    text = normalise(raw)
    out = Sanitised(excerpt="")
    slots: list[str] = []
    seen: set[tuple[str, str]] = set()

    def bump(what: str) -> None:
        out.masked[what] = out.masked.get(what, 0) + 1

    def slot(display: str) -> str:
        slots.append(display)
        return f"\ue000{len(slots) - 1}\ue001"

    def add(kind: str, value: str, display: str) -> None:
        if (kind, value) not in seen:
            seen.add((kind, value))
            out.entities.append(Entity(kind, value, display))

    def upi_uri(m: re.Match) -> str:
        req = parse_upi_uri(m.group(0))
        if not req:
            bump("payment_link")
            return slot("[payment link hidden]")
        d = display_upi(req.vpa)
        add("upi", req.vpa.lower(), d)
        return slot(f"[UPI request: {d}]")

    def url(m: re.Match) -> str:
        raw_url = m.group(0).rstrip(".,);]")
        tail = m.group(0)[len(raw_url):]
        dom = _domain_of(raw_url)
        if not dom:
            bump("link")
            return slot("[link hidden]") + tail
        add("domain", dom, dom)
        if urlparse(raw_url if "://" in raw_url else "http://" + raw_url).path.strip("/") or "?" in raw_url:
            bump("link_details")
        return slot(f"[link: {dom}]") + tail

    def email(m: re.Match) -> str:
        bump("email")
        return slot("[email hidden]")

    def vpa(m: re.Match) -> str:
        v = m.group(1)
        if not VPA_RE.match(v):
            return m.group(0)
        d = display_upi(v)
        add("upi", v.lower(), d)
        return slot(d)

    def phone(m: re.Match) -> str:
        num = re.sub(r"\D", "", m.group(1))
        add("phone", num, f"{num[:2]}XXXXXX{num[-2:]}")
        bump("phone")
        return slot(f"{num[:2]}XXXXXX{num[-2:]}")

    def long_number(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if len(digits) < 9:                     # "25000 30000" style amounts are not identifiers
            return m.group(0)
        bump("long_number")
        return slot("[number hidden]")

    def secret(m: re.Match) -> str:
        bump("secret_code")
        return m.group(0)[: m.start(2) - m.start(0)] + slot("[hidden]")

    def greet(m: re.Match) -> str:
        if m.group(2).lower() in _GENERIC:
            return m.group(0)
        bump("name")
        head = m.group(0)[: m.start(1) - m.start(0)]
        return head + m.group(1) + slot("[name]")

    t = _UPI_URI.sub(upi_uri, text)
    t = _URL.sub(url, t)
    t = _EMAIL.sub(email, t)
    t = _VPA.sub(vpa, t)
    t = _BARE.sub(lambda m: (add("domain", d, d) or slot(f"[link: {d}]")) if (d := _domain_of(m.group(1))) else m.group(0), t)
    t = _PHONE.sub(phone, t)
    t = _SECRET.sub(secret, t)
    t = _PAN.sub(lambda m: (bump("pan"), slot("[PAN hidden]"))[1], t)
    t = _LONG.sub(long_number, t)
    t = _GREET.sub(greet, t)
    t = _GREET_HI.sub(lambda m: m.group(0) if m.group(2) in _GENERIC else (bump("name"), m.group(0)[: m.start(1) - m.start(0)] + m.group(1) + slot("[name]"))[1], t)
    t = _MYNAME.sub(lambda m: (bump("name"), m.group(0)[: m.start(1) - m.start(0)] + m.group(1) + slot("[name]"))[1], t)
    t = _MYNAME_HI.sub(lambda m: (bump("name"), m.group(1) + m.group(2) + slot("[name]"))[1], t)

    t = _MARK.sub(lambda m: slots[int(m.group(1))], t)
    out.excerpt = t[:MAX_EXCERPT].rstrip()

    if _RESIDUAL_PHONE.search(out.excerpt) or _RESIDUAL_LONG.search(out.excerpt) or _EMAIL.search(out.excerpt) or _PAN.search(out.excerpt):
        out.clean = False
        out.flags.append("personal_data_left")
    if contains_profanity(out.excerpt):
        out.clean = False
        out.flags.append("profanity")
    if "\ue000" in out.excerpt or "\ue001" in out.excerpt:
        out.clean = False
        out.flags.append("marker_left")
    return out


def sanitise_place(raw: str) -> str:
    """City or state: letters, spaces, comma and hyphen only (so a street address or number cannot be smuggled in), 40 characters."""
    t = unicodedata.normalize("NFKC", raw or "")
    t = re.sub(r"[^A-Za-z\u0900-\u0963\u0971-\u097F ,\-]", "", t)
    return re.sub(r"\s+", " ", t).strip()[:40]
