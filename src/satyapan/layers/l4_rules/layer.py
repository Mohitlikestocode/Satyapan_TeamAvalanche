"""L4: bilingual (English / Hindi / Hinglish) red-flag rules over the words used in a message.

Deterministic patterns only. A hit is a *sign*, never proof; strengths are fixed per rule.
"""
from __future__ import annotations

import re

from ...contracts.models import Layer, LayerResult, Signal, Strength

I = re.IGNORECASE
# code -> (strength, trigger id for payee templates or None, patterns)
RULES: list[tuple[str, Strength, str | None, list[re.Pattern[str]]]] = [
    ("OFFER_GUARANTEED_RETURNS", Strength.STRONG_SUSPICIOUS, "guaranteed_returns", [
        re.compile(r"\b(guarantee[ds]?(?!\s+by\b)|assured|sure[- ]?shot|risk[- ]?free|100\s*%\s*(safe|sure|profit))\b", I),
        re.compile(r"\b(pakka|pakka\s+munafa|fixed\s+munafa)\b", I),
        re.compile(r"(गारंटी|गारंटीड|पक्का\s*मुनाफ़?ा|निश्चित\s*मुनाफ़?ा|जोखिम\s*मुक्त)"),
    ]),
    ("OFFER_FIXED_PERIODIC_RETURN", Strength.STRONG_SUSPICIOUS, "fixed_periodic_return", [
        re.compile(r"\b\d{1,3}\s*%\s*(?:/|per|a|every|each|ka|har|hr|ye)?\s*(day|daily|week|weekly|month|monthly|mahina|mahine|din|hafte)", I),
        re.compile(r"\b(daily|weekly|monthly)\s+(profit|return|income)s?\s+(of\s+)?\d{1,3}\s*%", I),
        re.compile(r"(हर|प्रति)\s*(दिन|सप्ताह|महीने|माह)\s*\d{1,3}\s*%"),
        re.compile(r"\d{1,3}\s*%\s*(हर|प्रति)\s*(दिन|सप्ताह|महीने|माह)"),
    ]),
    ("OFFER_FEE_TO_WITHDRAW", Strength.STRONG_SUSPICIOUS, "fee_to_withdraw", [
        re.compile(r"\b(pay|deposit|send)\b[^.\n]{0,40}\b(tax|fee|charges?|commission|gst)\b[^.\n]{0,50}\b(withdraw|release|unlock|receive|claim)", I),
        re.compile(r"\b(withdraw|nikal(ne|na)|paise\s+nikalne)\b[^.\n]{0,30}\b(pehle|ke\s+liye)\b[^.\n]{0,30}\b(charges?|tax|fee|commission)\b", I),
        re.compile(r"\b(tax|fee|charges?|gst)\b[^.\n]{0,40}\b(before|to)\b[^.\n]{0,20}\b(withdraw|withdrawal|release)", I),
        re.compile(r"(निकालने|विड्रॉ|withdraw)[^.\n]{0,40}(टैक्स|शुल्क|फीस|चार्ज)"),
    ]),
    ("OFFER_REMOTE_ACCESS", Strength.STRONG_SUSPICIOUS, None, [
        re.compile(r"\b(anydesk|teamviewer|quick\s*support|rustdesk|ultraviewer|screen\s*shar\w*)\b", I),
        re.compile(r"\b(share|tell|read\s+out|give)\b[^.\n]{0,20}\b(the\s+)?(code|screen)\b[^.\n]{0,30}\b(fix|help|verify|support)", I),
    ]),
    ("OFFER_BANK_DETAILS_CHANGED", Strength.WEAK_SUSPICIOUS, None, [
        re.compile(r"\b(our|the|my)\s+(bank\s+)?(account|bank\s+details?)\s+(has|have)\s+(been\s+)?(changed|updated|moved)\b", I),
        re.compile(r"\b(new|changed|updated)\s+(bank\s+)?(account|bank\s+details?)\b[^.\n]{0,40}\b(pay|transfer|send|use)\b", I),
        re.compile(r"\bpay\s+(to|into)\s+the\s+new\s+(bank\s+)?account\b", I),
        re.compile(r"(खाता|बैंक\s*डिटेल)[^.\n]{0,15}(बदल|नया)"),
    ]),
    ("OFFER_URGENCY", Strength.WEAK_SUSPICIOUS, None, [
        re.compile(r"\b(today\s+only|last\s+chance|limited\s+(seats|slots|time)|hurry|immediately|right\s+now|within\s+\d+\s*(min|hour)s?|abhi\s+(pay|bhejo|join)|jaldi)\b", I),
        re.compile(r"(आज\s*ही|अभी\s*(भेजें|जुड़ें|पैसे)|जल्दी|आख़िरी\s*मौका|सीमित\s*सीटें)"),
    ]),
    ("OFFER_VIP_GROUP", Strength.WEAK_SUSPICIOUS, "vip_group", [
        re.compile(r"\b(vip|premium|paid|elite)\s+(group|tips|channel|members?)\b", I),
        re.compile(r"\b(join|add)\b[^.\n]{0,30}\b(vip|premium)\b", I),
        re.compile(r"(वीआईपी|VIP)\s*(ग्रुप|चैनल|टिप्स)"),
    ]),
    ("OFFER_OFFPLATFORM", Strength.WEAK_SUSPICIOUS, None, [
        re.compile(r"\b(whatsapp|telegram|signal)\b[^.\n]{0,40}\b(group|channel|number|dm|inbox|join|contact)\b", I),
        re.compile(r"\b(dm|message)\s+me\b|\bt\.me/", I),
        re.compile(r"(व्हाट्सएप|टेलीग्राम)\s*(ग्रुप|चैनल)"),
    ]),
    ("OFFER_REGULATOR_IMPERSONATION", Strength.WEAK_SUSPICIOUS, None, [
        re.compile(r"\b(sebi|rbi|nse|bse)\s+(registered|approved|certified|authori[sz]ed|licen[sc]ed)\b", I),
        re.compile(r"(सेबी|आरबीआई)\s*(पंजीकृत|मान्यता|अनुमोदित)"),
    ]),
]
APK_RE = re.compile(r"\.apk\b|install\s+(the\s+)?(app|apk)|ऐप\s*इंस्टॉल|apk\s*(download|install)|apk[^.\n]{0,12}(इंस्टॉल|डाउनलोड)", I)
STORE_RE = re.compile(r"play\s*store|app\s*store|official\s+app|प्ले\s*स्टोर|ऐप\s*स्टोर", I)
COLLECT_TRAP_RE = re.compile(
    r"(enter|put|type|share|give)\s+(your\s+)?(upi\s+)?(pin|otp)\b[^.\n]{0,50}\b(receive|get|credit|refund|claim|collect)|"
    r"\b(receive|get|credit|refund|claim|collect)\b[^.\n]{0,40}\b(enter|put|type|share|give)\s+(your\s+)?(upi\s+)?(pin|otp)|"
    r"(पैसे\s*(पाने|लेने)\s*के\s*लिए)[^.\n]{0,30}(पिन|ओटीपी)|(पिन|ओटीपी)\s*(डालें|डालिए|बताएँ)[^.\n]{0,40}(पैसे|रिफंड)|"
    r"\b(refund|paise)\s+(lene|pane)\s+ke\s+liye\b[^.\n]{0,30}\b(pin|otp)\b",
    I,
)
INVEST_CONTEXT_RE = re.compile(
    r"\b(invest\w*|stocks?|shares?|trading|trade|ipo|sebi|demat|mutual\s+fund|returns?|profits?|portfolio|crypto|forex|intraday|nifty|sensex)\b|"
    r"(निवेश|शेयर|मुनाफ़?ा|ट्रेडिंग|क्रिप्टो)",
    I,
)


def run(text: str) -> LayerResult:
    signals: list[Signal] = []
    for code, strength, trigger, patterns in RULES:
        if any(p.search(text) for p in patterns):
            params = {"trigger": trigger} if trigger else {}
            signals.append(Signal(layer=Layer.L4, code=code, strength=strength, params=params))
    return LayerResult(layer=Layer.L4, signals=signals, model_versions={"rules": "lexicon-1"})


def has_apk(text: str) -> bool:
    """An app install outside the stores. Naming a store or the official app clears it."""
    return bool(APK_RE.search(text)) and not STORE_RE.search(text)


def has_collect_trap(text: str) -> bool:
    return bool(COLLECT_TRAP_RE.search(text))


def investment_context(text: str) -> bool:
    return bool(INVEST_CONTEXT_RE.search(text))
