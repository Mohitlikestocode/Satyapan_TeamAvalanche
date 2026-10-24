"""Pull payees, links and phone numbers out of untrusted text. Text is data: nothing here follows instructions in it."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote, urlparse

VPA_RE = re.compile(r"^[A-Za-z0-9._\-]{2,64}@[A-Za-z]{2,32}$")
_VPA_FIND = re.compile(r"(?<![\w.@/])([A-Za-z0-9][A-Za-z0-9._\-]{1,63}@[A-Za-z]{2,32})(?![\w@]|\.[A-Za-z])")
_UPI_URI = re.compile(r"upi://pay\?[^\s<>\"']+", re.IGNORECASE)
_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\d)(?:\+91[\s-]?|0)?([6-9]\d{4}[\s-]?\d{5})(?!\d)")
_NAME_OK = re.compile(r"^[A-Za-z0-9 .&'\-]{1,40}$")
_CLAIMED = re.compile(
    r"\b([A-Z][\w&]*(?:[ \t]+[A-Z][\w&]*){0,3}[ \t]+(?:Securities|Capital|Wealth|Advisors?|Advisory|Broking|Investments?|"
    r"Traders?|Finance|Research|Equity|Stocks?|Markets?|Gains?|Profits?))\b"
)


@dataclass(frozen=True)
class UpiRequest:
    vpa: str
    name: str | None = None
    amount: str | None = None
    note: str | None = None
    mcc: str | None = None

    @property
    def handle(self) -> str:
        return self.vpa.rsplit("@", 1)[1].lower()

    @property
    def local(self) -> str:
        return self.vpa.rsplit("@", 1)[0].lower()


@dataclass
class Found:
    upi: list[UpiRequest] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    claimed: str | None = None


def parse_upi_uri(uri: str) -> UpiRequest | None:
    """Parse upi://pay?pa=&pn=&am=&tn=&mc=. Returns None unless the payee address is well formed."""
    q = parse_qs(urlparse(uri).query, keep_blank_values=False)

    def one(k: str) -> str | None:
        v = q.get(k)
        return unquote(v[0]).strip() if v else None

    pa = one("pa")
    if not pa or not VPA_RE.match(pa):
        return None
    pn = one("pn")
    if pn is not None and not _NAME_OK.match(pn):
        pn = None  # keep only simple names; anything else is not shown
    am = one("am")
    if am is not None and not re.fullmatch(r"\d{1,9}(\.\d{1,2})?", am):
        am = None
    mc = one("mc")
    if mc is not None and not re.fullmatch(r"\d{4}", mc):
        mc = None
    return UpiRequest(vpa=pa, name=pn, amount=am, note=(one("tn") or None) and one("tn")[:60], mcc=mc)


def extract(text: str) -> Found:
    found = Found()
    seen: set[str] = set()
    for m in _UPI_URI.finditer(text):
        req = parse_upi_uri(m.group(0))
        if req and req.vpa.lower() not in seen:
            seen.add(req.vpa.lower())
            found.upi.append(req)
    for m in _VPA_FIND.finditer(text):
        vpa = m.group(1)
        if vpa.lower() not in seen and VPA_RE.match(vpa):
            seen.add(vpa.lower())
            found.upi.append(UpiRequest(vpa=vpa))
    for m in _URL.finditer(text):
        u = m.group(0).rstrip(".,);]")
        if not u.lower().startswith("upi://") and u not in found.urls:
            found.urls.append(u)
    found.phones = list(dict.fromkeys(re.sub(r"[\s-]", "", m.group(1)) for m in _PHONE.finditer(text)))
    c = _CLAIMED.search(text)
    if c:
        found.claimed = c.group(1).strip()[:40]
    return found
