"""Red-flag rules for scam types that are common in India: authority threats, advance fees, prize claims, card and PIN grabs.

Same contract as `layer.RULES`: (code, strength, payee trigger id or None, patterns). A hit is a sign, never proof.
Negations ("do not share your OTP") are handled with fixed-width look-behinds so real bank warnings do not trip the rules.
"""
from __future__ import annotations

import re

from ...contracts.models import Strength

I = re.IGNORECASE
NOT = r"(?<!not )(?<!never )(?<!n't )(?<!mat )(?<!kabhi )(?<!न )(?<!na )"
FEE = r"(processing|clearance|registration|insurance|interview|shipping|customs|training|verification|settlement|joining|release|token|refundable|security)"

RULES_INDIA: list[tuple[str, Strength, str | None, list[re.Pattern[str]]]] = [
    ("OFFER_AUTHORITY_THREAT", Strength.STRONG_SUSPICIOUS, None, [
        re.compile(r"\bdigital\s+arrest\b", I),
        re.compile(r"\b(do\s*n[o']t|don't)\s+(disconnect|hang\s*up|tell|inform)\b[^.\n]{0,40}\b(call|anyone|anybody|family|police)\b", I),
        re.compile(r"\b(cbi|ncb|trai|enforcement\s+directorate|cyber\s*cell|customs)\b[^.\n]{0,80}\b(arrest|illegal|drugs?|disconnect\w*|warrant|case\s+against|money\s+laundering)\b", I),
        re.compile(r"\b(arrest|warrant)\b[^.\n]{0,50}\b(nikal|issue[ds]?|will\s+be|hoga|jayega)\b", I),
        re.compile(r"(गिरफ़्तार|गिरफ्तार)|सीबीआई|साइबर\s*सेल[^.\n]{0,40}(कॉल|नोटिस)"),
        re.compile(r"\b(court|police)\s+notice\b[^.\n]{0,60}\b(pay|bhej\w*|settle\w*|fee)\b", I),
    ]),
    ("OFFER_ADVANCE_FEE", Strength.STRONG_SUSPICIOUS, "fee_to_withdraw", [
        re.compile(r"\b(pay|send|deposit|transfer|bhej\w*|de\s+do)\b[^.\n]{0,40}\b" + FEE + r"\b[^.\n]{0,12}\b(fee|fees|charges?|deposit|kit|amount)\b", I),
        re.compile(r"\b" + FEE + r"\s+(fee|fees|charges?|deposit)\b[^.\n]{0,40}\b(rs\.?|inr|₹)\s*[\d,]+", I),
        re.compile(r"\b(rs\.?|inr|₹)\s*[\d,]+\s+(as\s+)?" + FEE + r"\s+(fee|charges?|deposit)\b", I),
        re.compile(r"\b(pay|send|deposit)\b[^.\n]{0,30}\b(fee|charges?)\b[^.\n]{0,30}\b(first|before|to\s+(claim|release|receive|get|start|join))\b", I),
        re.compile(r"(प्रोसेसिंग|रजिस्ट्रेशन|क्लियरेंस|बीमा|शिपिंग|सिक्योरिटी)\s*(शुल्क|फीस|फ़ीस|चार्ज)|(डिलीवरी|इनाम|लोन)\s*के\s*लिए\s*[\d,]+\s*रुपये?\s*(इस|भेजें)"),
    ]),
    ("OFFER_PRIZE_CLAIM", Strength.WEAK_SUSPICIOUS, None, [
        re.compile(r"\b(you\s+(have\s+)?won|lucky\s+(draw|coupon|winner)|lottery|kbc|congratulations[^.\n]{0,40}(won|selected|shortlisted))\b", I),
        re.compile(r"\b(jeet\w*|lucky\s+draw)\b[^.\n]{0,40}\b(lakh|crore|iphone|car|rs)\b", I),
        re.compile(r"(बधाई\s*हो|आपने)[^.\n]{0,40}(जीता|जीते|इनाम)|लकी\s*ड्रॉ"),
    ]),
    ("OFFER_CREDENTIAL_REQUEST", Strength.STRONG_SUSPICIOUS, None, [
        re.compile(NOT + r"\b(share|tell|give|send|enter|provide|bata\w*|read\s+out)\b[^.\n]{0,25}\b(your\s+|the\s+|apna\s+)?(otp|cvv|upi\s*pin|atm\s*pin|card\s+(number|details)|net\s*banking\s+(password|id)|password|aadhaar\s+otp)\b", I),
        re.compile(r"\b(otp|cvv|pin|password)\b(?:(?!\bna\b|\bmat\b|\bnahi\b)[^.\n]){0,20}\b(daal\w*|bata\w*|bhej\w*)\b", I),
        re.compile(r"(कार्ड\s*नंबर|सीवीवी|एक्सपायरी)[^.\n]{0,40}(ओटीपी|OTP|बताएँ|बताइए|डालें)|(ओटीपी|OTP)\s*(डालें|बताएँ|बताइए|शेयर\s*करें)"),
    ]),
    ("OFFER_APPROVE_TO_RECEIVE", Strength.STRONG_SUSPICIOUS, None, [
        re.compile(r"\b(scan|approve|accept)\b[^.\n]{0,40}\b(qr|collect\s+request|request)\b[^.\n]{0,60}\b(receive|get|credit|recharge|cashback|refund|pin)\b", I),
        re.compile(r"\bcollect\b[^.\n]{0,30}\b(approve|accept)\b[^.\n]{0,40}\b(pin|receive)\b", I),
        re.compile(r"\b(qr)\b[^.\n]{0,30}\b(scan)\b[^.\n]{0,50}\b(pin)\b", I),
    ]),
    ("OFFER_EARN_FOR_TASKS", Strength.STRONG_SUSPICIOUS, None, [
        re.compile(r"\bearn\b[^.\n]{0,15}\b(rs\.?|inr|₹)\s*[\d,]+\s*(per|a|every|daily|/)\s*(task|day|hour|video|order)\b", I),
        re.compile(r"\b(rs\.?|inr|₹)\s*[\d,]+\s*(per|a)\s*(task|hour)\b|\b(liking|like)\s+(youtube\s+)?videos?\b[^.\n]{0,40}\b(earn|rs|daily)\b", I),
        re.compile(r"\b(part[- ]time|work\s+from\s+home)\b[^.\n]{0,60}\b(earn|rs\.?|daily|per\s+hour)\b", I),
    ]),
    ("OFFER_FAMILY_EMERGENCY", Strength.STRONG_SUSPICIOUS, None, [
        re.compile(r"\b(lost|broke|broken)\s+(my\s+)?phone\b[^.\n]{0,60}\b(send|transfer|pay)\b", I),
        re.compile(r"\b(accident|hospital|operation|surgery)\b[^.\n]{0,60}\b(send|transfer|pay|bhej\w*)\b[^.\n]{0,40}\b(urgent\w*|now|immediately|account|rs\.?)\b", I),
        re.compile(r"(एक्सीडेंट|अस्पताल|ऑपरेशन)[^.\n]{0,60}(भेजें|ट्रांसफर)|(भेजें|ट्रांसफर)[^.\n]{0,40}(ऑपरेशन|अस्पताल)"),
    ]),
    ("OFFER_WRONG_TRANSFER_RETURN", Strength.STRONG_SUSPICIOUS, None, [
        re.compile(r"\b(by\s+mistake|galti\s+se|accidentally)\b[^.\n]{0,60}\b(sent|transferred|bhej\w*)\b[^.\n]{0,60}\b(back|return|wapas|refund)\b", I),
        re.compile(r"\b(wapas|back)\s+(bhej|send|transfer)\b", I),
        re.compile(r"गलती\s*से[^.\n]{0,60}(वापस|लौटा)"),
    ]),
    ("OFFER_CRYPTO_DOUBLE", Strength.STRONG_SUSPICIOUS, None, [
        re.compile(r"\b(send|transfer|deposit)\b[^.\n]{0,25}\b(btc|eth|usdt|bitcoin)\b[^.\n]{0,50}\b(get|receive)\b[^.\n]{0,25}\b(back|double|2x|\d+x)\b", I),
        re.compile(r"\bgiveaway\b[^.\n]{0,60}\b(send|wallet)\b", I),
        re.compile(r"\b(double|2x|3x|5x)\s+(your\s+)?(money|investment|btc)\b", I),
    ]),
    ("OFFER_FORCES_ADVANCE", Strength.STRONG_SUSPICIOUS, None, [
        re.compile(r"\b(army|crpf|cisf|bsf|posted\s+(in|abroad)|doctor\s+posted|working\s+abroad)\b[^.\n]{0,100}\b(advance|token|qr|upi|gift|parcel|pay)\b", I),
        re.compile(r"\b(advance|token)\b[^.\n]{0,60}\b(qr|upi)\b[^.\n]{0,40}\b(pin|scan)\b", I),
        re.compile(r"(आर्मी|सेना)[^.\n]{0,60}(एडवांस|क्यूआर|UPI)"),
    ]),
    ("OFFER_ACCOUNT_THREAT", Strength.WEAK_SUSPICIOUS, None, [
        re.compile(r"\b(account|card|sim|pan|aadhaar|connection|number|policy)\b[^.\n]{0,40}\b(blocked|block|closed|deactivated|suspended|disconnected|deleted|banned|cut|kat\s+jayega|band\s+ho)\b[^.\n]{0,40}\b(today|tonight|hours?|immediately|now|aaj|abhi|24|2)\b", I),
        re.compile(r"\b(warna|otherwise|or\s+else|वरना)\b[^.\n]{0,40}\b(block|close|cut|band|disconnect|कट|बंद|ब्लॉक)\w*", I),
        re.compile(r"(खाता|कार्ड|सिम|कनेक्शन)[^.\n]{0,30}(बंद|ब्लॉक|कट)[^.\n]{0,30}(आज|अभी|तुरंत)|(आज|अभी|तुरंत)[^.\n]{0,30}(बंद|ब्लॉक|कट)\s*(हो|कर)"),
        re.compile(r"(?:pending|incomplete|expired)\s+kyc\b|kyc\b[^.\n]{0,30}\b(expired|pending|incomplete|update\s+now)\b", I),
    ]),
    ("OFFER_VERIFY_LINK", Strength.WEAK_SUSPICIOUS, None, [
        re.compile(r"\b(click|tap)\b[^.\n]{0,30}\b(here|link|https?://\S+|bit\.ly\S*|\S+\.(top|xyz|shop|co|in|net)/\S+)", I),
        re.compile(r"\b(verify|update|reactivate|re-?activate|claim|redeem)\b[^.\n]{0,40}\b(at|via|on)\b[^.\n]{0,10}(https?://\S+|bit\.ly\S*|\S+\.(top|xyz|shop|net)\b)", I),
        re.compile(r"(लिंक\s*पर\s*क्लिक|इस\s*लिंक)"),
    ]),
    ("OFFER_AUTHORITY_REFUND_CLAIM", Strength.WEAK_SUSPICIOUS, None, [
        re.compile(r"\b(income\s+tax|it\s+department|tax\s+refund|subsidy|scholarship|cashback|reward\s+points)\b[^.\n]{0,60}\b(refund|eligible|sanction\w*|pending|expire\w*|credited|aaya)\b", I),
    ]),
]
