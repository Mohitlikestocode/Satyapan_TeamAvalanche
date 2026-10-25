"""Claimed-company check: "this message says it is from Amazon / SBI / a courier". Compare its links and phone numbers with that company's
real official web addresses from a small built-in list of well-known companies.

Honest limits: the list is short and hand-made from each company's own public site, so a company not on it gets no brand check (only the
general checks). A phone number is never confirmed or denied as official: we can only say a personal mobile number is not how these companies
give support. Official addresses can change, so this is a sign, not proof.
"""
from __future__ import annotations

from ...contracts.models import Layer, LayerResult, Signal, Strength
from ...extract.entities import extract
from .domains import hostname

# key -> (display name, official web domains). Subdomains of these count as official.
COMPANIES: dict[str, tuple[str, tuple[str, ...]]] = {
    "amazon": ("Amazon", ("amazon.in", "amazon.com", "amzn.in", "amzn.to", "a.co", "amazonpay.in")),
    "sbi": ("State Bank of India", ("sbi.co.in", "onlinesbi.sbi", "sbi.bank.in", "yonosbi.com", "sbicard.com")),
    "hdfc": ("HDFC Bank", ("hdfcbank.com", "hdfcbank.net", "hdfc.com")),
    "icici": ("ICICI Bank", ("icicibank.com", "icicibank.co.in")),
    "axis": ("Axis Bank", ("axisbank.com",)),
    "flipkart": ("Flipkart", ("flipkart.com", "fkrt.it", "fkrt.cc")),
    "paytm": ("Paytm", ("paytm.com", "paytm.in", "paytmbank.com")),
    "phonepe": ("PhonePe", ("phonepe.com",)),
    "gpay": ("Google Pay", ("pay.google.com", "google.com", "gpay.app.goo.gl")),
    "jio": ("Jio", ("jio.com", "jiopay.com")),
    "airtel": ("Airtel", ("airtel.in", "airtel.com")),
    "courier": ("a courier company", ("bluedart.com", "indiapost.gov.in", "dtdc.com", "dtdc.in", "delhivery.com", "fedex.com", "dhl.com",
                                       "ecomexpress.in", "xpressbees.com", "shadowfax.in")),
    "govt": ("a government service", ("uidai.gov.in", "incometax.gov.in", "incometaxindia.gov.in", "irctc.co.in", "epfindia.gov.in",
                                       "india.gov.in", "digilocker.gov.in")),
}
# companies asked for in the form but with no fixed website list (electricity boards differ by state): general checks only
NO_LIST = {"electricity", "other"}
SHORTENERS = ("bit.ly", "tinyurl.com", "cutt.ly", "t.ly", "goo.gl", "is.gd", "rb.gy", "rebrand.ly")


def is_official(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def is_personal_mobile(number: str) -> bool:
    digits = "".join(ch for ch in number if ch.isdigit())[-10:]
    return len(digits) == 10 and digits[0] in "6789"


def check(company_key: str, text: str) -> LayerResult | None:
    """Signals for a message that claims to come from `company_key`. None when the company is unknown or nothing stands out."""
    entry = COMPANIES.get(company_key)
    if entry is None:
        return None
    name, domains = entry
    found = extract(text)
    signals: list[Signal] = []
    for url in found.urls:
        host = hostname(url)
        if not host:
            continue
        if host in SHORTENERS or any(host.endswith("." + s) for s in SHORTENERS):
            signals.append(Signal(layer=Layer.L3, code="LINK_HIDES_DESTINATION", strength=Strength.WEAK_SUSPICIOUS, params={"company": name}))
        elif not is_official(host, domains):
            signals.append(Signal(layer=Layer.L3, code="LINK_NOT_OFFICIAL_FOR_BRAND", strength=Strength.STRONG_SUSPICIOUS,
                                  params={"domain": host[:60], "company": name}))
    if any(is_personal_mobile(p) for p in found.phones):
        # delivery agents genuinely call from personal mobiles, so for couriers it is only a weak sign
        strength = Strength.WEAK_SUSPICIOUS if company_key == "courier" else Strength.STRONG_SUSPICIOUS
        signals.append(Signal(layer=Layer.L3, code="SUPPORT_NUMBER_PERSONAL", strength=strength, params={"company": name}))
    return LayerResult(layer=Layer.L3, signals=signals, model_versions={"brand_claim": "1"}) if signals else None
