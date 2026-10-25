"""Ground rules for the AI rule check: what genuine Indian banks, regulators and companies never do, and what scams always do.

Each rule says what to look for (given to the language model), how strong a sign it is, and where it comes from:
"official" = an Indian regulator or government advisory (source given), "pattern" = a well-documented scam pattern from
those bodies' fraud booklets and fact checks, "heuristic" = our own common-sense benchmark (said so, not attributed to anyone).
The model only says WHICH rules match and quotes the words; the reason text comes from reasons/ext/models.yaml (ML_GR_*).
"""
from __future__ import annotations

from dataclasses import dataclass

SEBI_TIPS = "https://www.business-standard.com/finance/personal-finance/sebi-circular-on-frauds-verify-registration-before-taking-investment-tips-125042000636_1.html"
SEBI_GUARANTEE = "https://businesstoday.in/story/sebi-busts-sms-whatsapp-based-investment-scam/1/206967.html"
RBI_BEAWARE = "https://website.rbi.org.in/documents/87730/39016390/BEAWARE07032022.pdf"
RBI_RAJU = "https://website.rbi.org.in/en/web/rbi/rbi-kehta-hai/raju-and-forty-thieves"
RBI_LOAN_APPS = "https://rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=50846"
NPCI_PIN = "https://moneylife.in/article/upi-frauds-top-apps-leading-banks-join-npcis-safetyshield-campaign/66552.html"
MHA_ARREST = "https://teamleaseregtech.com/updates/article/31906/mha-issued-alert-against-digital-arrests"
TRAI_DISCONNECT = "https://www.newsonair.gov.in/trai-warns-public-against-fake-calls-threatening-mobile-disconnection"
PIB_TAX = "https://outlookmoney.com/news/did-you-just-get-the-income-tax-refund-message-it-s-a-bait-clarifies-i-b-ministry-news-307861"
I4C_TASK = "https://ucobank.com/documents/d/guest/security-advisory-beware-of-task-based-job-scams"


@dataclass(frozen=True)
class Rule:
    id: str          # short id the model returns, e.g. "GR01"
    code: str        # reason code in reasons/ext/models.yaml
    group: str
    look_for: str    # instruction for the model (English; messages may be in any language)
    strong: bool     # strong sign when matched with high confidence; otherwise weak
    basis: str       # official | pattern | heuristic
    source: str      # URL, or "" for a heuristic


RULES: list[Rule] = [
    # ---- investment and returns --------------------------------------------------------------------------------
    Rule("GR01", "ML_GR_GUARANTEED_RETURN", "investment",
         "Promises GUARANTEED, assured, fixed, sure-shot, risk-free or 'no loss' returns or profit on an investment, trading, crypto, "
         "gold or deposit scheme.", True, "official", SEBI_GUARANTEE),
    Rule("GR02", "ML_GR_HIGH_RETURN", "investment",
         "Promises returns far above normal: any daily, weekly or monthly percentage return; more than about 15% a year; or money "
         "doubling/tripling in less than about 5 years (e.g. 'double in 15 days', '25% every month', '5% daily'). Normal Indian bank "
         "deposits pay roughly 6-8% a year.", True, "heuristic", ""),
    Rule("GR03", "ML_GR_UNREGISTERED_TIPS", "investment",
         "Offers stock, IPO, F&O, forex or crypto tips, 'VIP signals', 'sure-shot calls' or a trading group on WhatsApp/Telegram/social "
         "media, without giving a SEBI registration number.", False, "official", SEBI_TIPS),
    Rule("GR04", "ML_GR_IPO_QUOTA", "investment",
         "Claims a special IPO allotment, institutional or 'insider' quota, pre-listing shares, or an exclusive account that ordinary "
         "investors cannot get.", True, "official", SEBI_TIPS),
    Rule("GR05", "ML_GR_INVEST_PERSONAL_ACCOUNT", "investment",
         "Asks to send investment or trading money to a person's UPI ID or bank account, or to deposit on an unknown app/platform, "
         "instead of through a SEBI-registered broker's own app.", True, "official", SEBI_TIPS),
    Rule("GR06", "ML_GR_FEE_TO_WITHDRAW", "advance_fee",
         "Says you must first pay a tax, GST, fee, charge, deposit or 'unlock' amount to WITHDRAW profits, release funds, a loan, a "
         "refund, a policy bonus or a prize.", True, "pattern", RBI_BEAWARE),
    # ---- credentials and payment mechanics ---------------------------------------------------------------------
    Rule("GR07", "ML_GR_ASKS_SECRET", "credentials",
         "Asks the reader to SHARE or tell an OTP, UPI PIN, ATM PIN, CVV, card number, net-banking password or verification code. "
         "(A message that WARNS never to share an OTP does NOT match.)", True, "official", RBI_BEAWARE),
    Rule("GR08", "ML_GR_PIN_TO_RECEIVE", "credentials",
         "Says you must enter a UPI PIN, approve a request, or scan a QR code in order to RECEIVE money, a refund or cashback. "
         "A UPI PIN is only ever needed to send money.", True, "official", NPCI_PIN),
    Rule("GR09", "ML_GR_REMOTE_APP", "credentials",
         "Asks to install a screen-sharing or remote-control app (AnyDesk, TeamViewer, QuickSupport, RustDesk), an APK file, or an "
         "unknown app from a link, to fix, verify or refund something.", True, "pattern", RBI_RAJU),
    Rule("GR10", "ML_GR_KYC_LINK", "credentials",
         "Says a bank account, card, wallet, PAN, Aadhaar or SIM will be blocked or suspended unless KYC/PAN/Aadhaar details are "
         "updated through a link, a phone call or an app.", True, "official", RBI_BEAWARE),
    Rule("GR11", "ML_GR_SUSPICIOUS_LINK", "credentials",
         "Contains a link to log in, pay, update, verify or claim that is a URL shortener, a look-alike or misspelled brand domain, or "
         "a domain that is not the organisation's own official website.", False, "pattern", RBI_RAJU),
    # ---- pressure ----------------------------------------------------------------------------------------------
    Rule("GR12", "ML_GR_DEADLINE", "pressure",
         "Creates time pressure: act or pay within minutes or hours, 'today only', 'tonight at 9:30', 'last chance', 'offer ends soon', "
         "or something bad will happen if you do not act now.", False, "pattern", RBI_BEAWARE),
    Rule("GR13", "ML_GR_BLOCK_THREAT", "pressure",
         "Threatens that electricity, mobile number/SIM, FASTag, gas, bank account or card will be cut, disconnected, blocked or "
         "blacklisted, from a personal number or with a call/link to stop it. TRAI and discoms do not send such threats.",
         False, "official", TRAI_DISCONNECT),
    Rule("GR14", "ML_GR_SECRECY", "pressure",
         "Tells the reader to keep it secret, not to tell family, friends, the bank or the police, or not to disconnect the call.",
         True, "official", MHA_ARREST),
    # ---- impersonation -----------------------------------------------------------------------------------------
    Rule("GR15", "ML_GR_DIGITAL_ARREST", "impersonation",
         "Claims to be police, CBI, ED, customs, narcotics, cyber cell, a court, RBI or TRAI; says there is a case, FIR, warrant, "
         "parcel with drugs or money laundering in your name; mentions 'digital arrest' or a video-call investigation; or asks for "
         "money to settle or verify. Indian agencies do not arrest or collect money over video calls.", True, "official", MHA_ARREST),
    Rule("GR16", "ML_GR_TAX_REFUND", "impersonation",
         "Offers an income tax, GST or government refund, subsidy or scheme benefit through a link, or asks for bank details, card "
         "details or an OTP to release it. The Income Tax Department does not send refund links by SMS.", True, "official", PIB_TAX),
    Rule("GR17", "ML_GR_FAKE_SUPPORT", "impersonation",
         "Someone claiming to be customer care, bank staff, a delivery company or an app's support team contacts the reader first, or "
         "gives a personal mobile number as the 'helpline', to fix a failed payment, refund or account problem.", False, "pattern", RBI_RAJU),
    Rule("GR18", "ML_GR_NEW_NUMBER_RELATIVE", "impersonation",
         "Claims to be a relative, child, friend or boss writing from a NEW or borrowed number (phone broken, lost, in hospital, "
         "accident, stuck abroad) and asks for money urgently.", True, "pattern", RBI_RAJU),
    Rule("GR19", "ML_GR_BRAND_OR_OFFICIAL_NAME", "impersonation",
         "Uses the name of a bank, RBI, SEBI, NPCI, a government department, a well-known company or a celebrity to make an offer, "
         "demand or threat look official.", False, "pattern", RBI_BEAWARE),
    # ---- pay-to-receive and other money patterns ---------------------------------------------------------------
    Rule("GR20", "ML_GR_PAY_TO_GET", "advance_fee",
         "Asks for a registration, processing, joining, delivery, customs, insurance, file or verification fee BEFORE giving a job, "
         "loan, prize, gift, parcel, refund or other benefit.", True, "pattern", RBI_BEAWARE),
    Rule("GR21", "ML_GR_LOTTERY", "advance_fee",
         "Says you won a lottery, lucky draw, KBC prize, car, phone, gift or reward you never entered, or were 'selected' at random.",
         True, "pattern", RBI_RAJU),
    Rule("GR22", "ML_GR_TASK_JOB", "jobs",
         "Offers money for simple online tasks (liking videos, rating hotels or products, reviews, following pages, captcha), 'prepaid' "
         "or 'merchant' tasks, or a work-from-home job that needs a deposit. Genuine employers do not charge candidates.",
         True, "official", I4C_TASK),
    Rule("GR23", "ML_GR_LOAN_APP", "loans",
         "Offers an instant loan with no documents or no CIBIL check, through an app or link, especially one that needs access to "
         "contacts/photos or an upfront fee. Lenders must be RBI-regulated banks or NBFCs and name themselves.", True, "official", RBI_LOAN_APPS),
    Rule("GR24", "ML_GR_PARCEL_CUSTOMS", "parcel",
         "Says a parcel or courier is held, undelivered or seized (customs, wrong address, illegal items) and asks to pay a fee, update "
         "details through a link, or call an officer.", True, "pattern", RBI_RAJU),
    Rule("GR25", "ML_GR_MISTAKEN_TRANSFER", "refund",
         "Claims money was sent to the reader by mistake and asks them to return or refund it, or to accept a collect request.",
         False, "pattern", RBI_BEAWARE),
    Rule("GR26", "ML_GR_FAKE_PAYMENT_PROOF", "refund",
         "Says 'I have paid, see the screenshot', 'the money will reach you later because of a slow server', and asks the reader to "
         "hand over goods, refund the difference or trust the screenshot instead of checking their own bank or UPI app.",
         False, "official", NPCI_PIN),
    Rule("GR27", "ML_GR_ACCOUNT_CHANGED", "invoice",
         "A supplier, landlord, school, company or boss says their bank account or UPI ID has CHANGED and asks to pay the new one, "
         "often urgently or quietly.", True, "pattern", RBI_BEAWARE),
    Rule("GR28", "ML_GR_EXTORTION", "threat",
         "Threatens to leak private photos or videos, defame, or harm the reader unless money is paid.", True, "pattern", MHA_ARREST),
    Rule("GR29", "ML_GR_ADVANCE_TOKEN", "advance_fee",
         "Asks for a token, booking or advance amount for a flat, car, item for sale, wedding/matrimony match or service from someone "
         "the reader has not met, often 'out of station', 'army officer' or 'abroad'.", False, "pattern", RBI_RAJU),
    Rule("GR30", "ML_GR_TOO_GOOD", "heuristic",
         "Offers something clearly too good to be true: free iPhones, huge discounts that need payment first, money for nothing, "
         "free gifts from strangers abroad, or a refund/cashback the reader did not ask for.", False, "heuristic", ""),
    Rule("GR31", "ML_GR_OFF_PLATFORM", "heuristic",
         "Moves the conversation or payment off an official channel: 'pay directly to this number', 'contact on WhatsApp/Telegram', "
         "'do not use the app', or 'pay outside the platform'.", False, "pattern", RBI_RAJU),
    Rule("GR32", "ML_GR_CRYPTO_PLATFORM", "investment",
         "Asks to deposit money or USDT/crypto on an unknown trading, mining or investment platform or app with promised earnings.",
         True, "official", SEBI_TIPS),
    Rule("GR33", "ML_GR_SUBSIDY_FEE", "advance_fee",
         "Says a government scheme, subsidy, pension, scholarship, ration or LPG benefit needs a small payment, an OTP, or a remote "
         "app to be released. Government benefits do not charge a release fee.", True, "pattern", RBI_BEAWARE),
]
BY_ID = {r.id: r for r in RULES}
BY_CODE = {r.code: r for r in RULES}
