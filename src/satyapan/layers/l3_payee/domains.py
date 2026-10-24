"""Link checks: look-alikes of well-known bank/broker/marketplace domains, punycode and APK links."""
from __future__ import annotations

from urllib.parse import urlparse

# registered domain -> short label shown nowhere to the user; used only to decide "official"
OFFICIAL = {
    "hdfcbank.com", "icicibank.com", "sbi.co.in", "onlinesbi.sbi", "axisbank.com", "kotak.com", "pnbindia.in",
    "zerodha.com", "upstox.com", "groww.in", "angelone.in", "amazon.in", "amazon.com", "flipkart.com",
    "sebi.gov.in", "rbi.org.in", "npci.org.in", "paytm.com", "phonepe.com", "cybercrime.gov.in", "india.gov.in",
}
# brand keywords that should only ever appear on their own official domains
BRANDS = ["hdfc", "icici", "sbi", "axis", "kotak", "pnb", "zerodha", "upstox", "groww", "angel", "amazon", "flipkart",
          "sebi", "paytm", "phonepe", "npci"]
_TWO_LEVEL = {"co.in", "gov.in", "org.in", "bank.in", "net.in", "ac.in", "com.au", "co.uk"}


def hostname(url: str) -> str | None:
    try:
        h = urlparse(url).hostname
    except ValueError:
        return None
    return h.lower().rstrip(".") if h else None


def registered_domain(host: str) -> str:
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in _TWO_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def is_official(host: str) -> bool:
    return host.endswith(".bank.in") or registered_domain(host) in OFFICIAL


def lookalike(host: str) -> bool:
    """True when the host imitates a known brand: punycode, or a brand word on a domain that is not the brand's own."""
    if is_official(host):
        return False
    if "xn--" in host:
        return True
    label = registered_domain(host).split(".")[0].replace("-", "").replace("0", "o").replace("1", "l")
    full = host.replace("-", "").replace("0", "o").replace("1", "l")
    return any(b in label or b in full.split(".")[0] for b in BRANDS)
