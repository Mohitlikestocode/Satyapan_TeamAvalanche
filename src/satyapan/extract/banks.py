"""Bank names and IFSC codes. The first four letters of an IFSC identify the bank.

A small built-in table of large banks. It is replaced by the full open IFSC dataset when that snapshot is loaded.
"""
from __future__ import annotations

import re

IFSC_RE = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")
IFSC_LABELLED = re.compile(r"IFS\s*C(?:\s*code)?\s*[:\-]?\s*([A-Za-z0-9]{8,12})", re.IGNORECASE)

# lower-case name fragment -> IFSC bank code
NAME_TO_CODE: dict[str, str] = {
    "hdfc": "HDFC", "icici": "ICIC", "state bank of india": "SBIN", "sbi": "SBIN", "axis": "UTIB", "kotak": "KKBK",
    "punjab national": "PUNB", "pnb": "PUNB", "bank of baroda": "BARB", "canara": "CNRB", "idfc": "IDFB",
    "yes bank": "YESB", "indusind": "INDB", "union bank": "UBIN", "bank of india": "BKID", "federal bank": "FDRL",
    "idbi": "IBKL", "indian bank": "IDIB",
}


def bank_codes_named(text: str) -> dict[str, str]:
    """Map code -> the name fragment found, for every known bank mentioned in the text."""
    low = text.lower()
    out: dict[str, str] = {}
    for name, code in NAME_TO_CODE.items():
        if re.search(r"\b" + re.escape(name) + r"\b", low):
            out.setdefault(code, name.upper() if len(name) <= 5 else name.title())
    return out
