"""Generate a large, varied corpus of Indian payment-fraud messages and genuine messages (English, Hindi, Hinglish) for training.

usage: python tools/make_scam_corpus.py data/corpus [--per-template 4] [--seed 7]

Writes synth_scams.jsonl and synth_genuine.jsonl: {"text", "label", "lang", "family", "synthetic": true}.
Messages are built from templates with slots (amounts, names, brands, links, phone numbers, UPI ids) plus optional openers, closers and
SMS-style noise, so one template gives many different surface forms. Everything is invented; no real person, number or account appears.

Leakage guard: any message that shares a run of six consecutive words with a line of data/kit/*.jsonl (the dev kit and the held-out
files) is dropped, so the held-out sets stay unseen. The generator never reads those files for anything else.
"""
from __future__ import annotations

import argparse
import sys
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

# ---------------------------------------------------------------- slots
AMT = ["Rs 500", "Rs 1,200", "Rs 2,999", "Rs 4,500", "Rs 9,800", "Rs 15,000", "Rs 25,000", "Rs 38,540", "Rs 49,999", "Rs 90,000", "Rs 1,20,000",
       "₹750", "₹1,850", "₹6,400", "₹12,500", "₹21,600", "₹75,000", "INR 3,000", "INR 18,000", "Rs.2500", "Rs. 99,000", "Rs 5 lakh", "Rs 2 lakh"]
SMALL = ["Rs 1", "Rs 2", "Rs 10", "Rs 25", "Rs 49", "Rs 99", "Rs 150", "₹5", "₹30", "Rs 199"]
FEE = ["Rs 299", "Rs 499", "Rs 999", "Rs 1,500", "Rs 2,100", "Rs 3,500", "Rs 5,000", "Rs 7,500", "₹850", "₹1,999", "Rs 12,000"]
NAME_M = ["Rajesh", "Amit", "Sandeep", "Vikram", "Suresh", "Manoj", "Deepak", "Arun", "Rahul", "Imran", "Gurpreet", "Karthik", "Naveen", "Prakash", "Sunil"]
NAME_F = ["Priya", "Neha", "Sunita", "Anjali", "Kavita", "Meena", "Pooja", "Shweta", "Fatima", "Lakshmi", "Radha", "Divya", "Rekha", "Seema"]
SURN = ["Sharma", "Verma", "Singh", "Gupta", "Patel", "Khan", "Reddy", "Nair", "Iyer", "Das", "Mehta", "Joshi", "Yadav", "Mishra", "Kapoor"]
BANK = ["SBI", "HDFC Bank", "ICICI Bank", "Axis Bank", "Punjab National Bank", "Bank of Baroda", "Kotak Mahindra Bank", "Canara Bank", "Union Bank", "IDFC First Bank"]
APP = ["PhonePe", "Google Pay", "Paytm", "BHIM", "Amazon Pay", "WhatsApp Pay"]
COURIER = ["BlueDart", "India Post", "DTDC", "FedEx", "Delhivery", "DHL", "Amazon", "Flipkart", "Ecom Express"]
AUTH = ["CBI", "Delhi Police", "Mumbai Cyber Cell", "Narcotics Bureau", "Customs", "Enforcement Directorate", "TRAI", "Supreme Court", "RBI", "Income Tax"]
TLD = ["xyz", "top", "in", "co", "online", "shop", "info", "site", "club", "live", "icu", "vip"]
WORD = ["update", "verify", "secure", "claim", "refund", "kyc", "pay", "reward", "support", "login", "care", "link", "service", "alert", "check"]
BRANDS = ["sbi", "hdfc", "icici", "axis", "paytm", "phonepe", "amazon", "flipkart", "jio", "airtel", "irctc", "uidai", "incometax", "fedex", "bluedart", "lic"]
PHONE_PFX = ["98", "99", "97", "96", "88", "70", "80", "63", "62"]
CITY = ["Delhi", "Mumbai", "Pune", "Jaipur", "Lucknow", "Kolkata", "Chennai", "Bengaluru", "Indore", "Patna", "Hyderabad", "Surat"]
TIME = ["9:30 PM", "tonight", "in 2 hours", "today", "within 24 hours", "by 6 PM", "in 30 minutes", "before midnight", "tomorrow morning"]
TIME_HI = ["आज रात 9:30 बजे", "आज ही", "2 घंटे में", "24 घंटे के अंदर", "शाम 6 बजे तक", "आधे घंटे में", "आज रात"]
TIME_HG = ["aaj raat 9:30 baje", "aaj hi", "2 ghante me", "24 ghante ke andar", "shaam 6 baje tak", "aadhe ghante me", "aaj raat tak"]


def rnd_phone(r: random.Random) -> str:
    return r.choice(PHONE_PFX) + "".join(r.choice("0123456789") for _ in range(8))


def rnd_link(r: random.Random, brand: str | None = None) -> str:
    b = brand or r.choice(BRANDS)
    w = r.choice(WORD)
    d = r.choice(["{b}-{w}", "{w}-{b}", "{b}{w}", "{b}-{w}-in", "my{b}-{w}"]).format(b=b, w=w)
    path = r.choice(["", "/login", "/update", "/claim", "/pay", "/verify", "/kyc", "/refund"])
    short = r.random() < 0.18
    if short:
        return r.choice(["bit.ly/", "tinyurl.com/", "cutt.ly/", "t.ly/"]) + "".join(r.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(6))
    return r.choice(["http://", "https://", ""]) + d + "." + r.choice(TLD) + path


def rnd_upi(r: random.Random, kind: str = "scam") -> str:
    h = r.choice(["ybl", "oksbi", "okaxis", "okhdfcbank", "paytm", "ibl", "axl", "upi", "apl"])
    if kind == "scam":
        stem = r.choice(["claim", "refund", "support", "care", "reward", "kyc", "help", "pay", "desk", "agent", "trade", "gain", "offer"]) + r.choice([".", "_", ""]) + r.choice(["desk", "team", "help", "88", "77", "01", "pro", "india", "cell", str(r.randint(10, 99))])
    else:
        stem = r.choice(["swiggy", "zomato", "bigbasket", "irctc", "ravi.k", "meena.s", "shop.sharma", "dr.rao", "milkman", "rentpay", "school.fee", "cab.ola", "kirana"]) + (str(r.randint(1, 99)) if r.random() < 0.3 else "")
    return stem + "@" + h


def person(r: random.Random) -> str:
    return r.choice(NAME_M + NAME_F) + " " + r.choice(SURN)


class Slots(dict):
    """Lazy slot filler: {amt}, {fee}, {bank}, {link}, {brandlink}, {upi}, {phone}, {name}, {auth}, {courier}, {app}, {city}, {time}..."""

    def __init__(self, r: random.Random, lang: str):
        super().__init__()
        self.r, self.lang = r, lang

    def __missing__(self, k: str) -> str:
        r = self.r
        v = {
            "amt": lambda: r.choice(AMT), "small": lambda: r.choice(SMALL), "fee": lambda: r.choice(FEE), "bank": lambda: r.choice(BANK),
            "link": lambda: rnd_link(r), "upi": lambda: rnd_upi(r), "phone": lambda: rnd_phone(r), "name": lambda: r.choice(NAME_M + NAME_F),
            "person": lambda: person(r), "auth": lambda: r.choice(AUTH), "courier": lambda: r.choice(COURIER), "app": lambda: r.choice(APP),
            "city": lambda: r.choice(CITY), "pct": lambda: str(r.choice([3, 4, 5, 8, 10, 12, 15, 18, 20, 25, 40])),
            "days": lambda: str(r.choice([3, 5, 7, 10, 15, 30])), "times": lambda: str(r.choice([2, 3, 4, 5, 10])),
            "n": lambda: str(r.randint(10, 99)), "acct": lambda: "".join(r.choice("0123456789") for _ in range(r.choice([10, 12, 14]))),
            "otp": lambda: "".join(r.choice("0123456789") for _ in range(r.choice([4, 6]))), "ref": lambda: "".join(r.choice("0123456789") for _ in range(12)),
            "time": lambda: r.choice({"en": TIME, "hi": TIME_HI, "hinglish": TIME_HG}[self.lang]),
        }.get(k)
        if v is None:
            raise KeyError(k)
        self[k] = val = v()
        return val


def link_for(r: random.Random, brandword: str) -> str:
    return rnd_link(r, brandword)


# ---------------------------------------------------------------- scam families
# family -> lang -> list of templates
SCAM: dict[str, dict[str, list[str]]] = {
    "digital_arrest": {
        "en": ["This is {auth} calling. A parcel booked in your name was seized with illegal items and your Aadhaar is linked to money laundering. Stay on this video call, tell nobody, and transfer {amt} to our safe account for verification or you will be arrested.",
               "Officer {person} from {auth}: a case is registered against your mobile number. Do not disconnect the call and do not inform your family. Pay {amt} as a security deposit to clear your name, it will be refunded after the inquiry.",
               "Your SIM was used for illegal activity and a warrant is issued. You are under digital arrest until verification. Keep your camera on and move {amt} to the RBI verification account now."],
        "hi": ["यह {auth} की ओर से कॉल है। आपके नाम से एक पार्सल पकड़ा गया है जिसमें अवैध सामान मिला है। वीडियो कॉल पर बने रहें, किसी को न बताएँ और जाँच के लिए {amt} सुरक्षित खाते में भेजें, वरना गिरफ़्तारी होगी।",
               "आपके मोबाइल नंबर पर मनी लॉन्ड्रिंग का केस दर्ज हुआ है। कॉल न काटें और अपने परिवार को न बताएँ। नाम साफ़ करने के लिए {amt} जमानत राशि जमा करें, जाँच के बाद लौटा दी जाएगी।"],
        "hinglish": ["Main {auth} se bol raha hu. Aapke naam par ek parcel pakda gaya hai jisme illegal saaman hai. Video call par bane rahiye, kisi ko mat bataiye aur verification ke liye {amt} safe account me transfer kijiye warna arrest ho jayega.",
                     "Aapke Aadhaar se money laundering ka case bana hai. Call mat kaatna aur ghar walon ko mat batana. Case khatam karne ke liye {amt} jama karo, inquiry ke baad wapas mil jayega."],
    },
    "kyc_block": {
        "en": ["Dear customer, your {bank} account will be blocked {time} as KYC is pending. Update your PAN and Aadhaar now at {link} to avoid closure.",
               "{bank} ALERT: KYC expired. Your net banking is suspended. Complete verification immediately: {link}. Ignore and your account will be frozen.",
               "Your PAN card is deactivated. Click {link} to reactivate and enter your debit card number and PIN to confirm identity.",
               "Dear user, your Aadhaar is not linked with your bank. Link now at {link} or your account will be closed {time}."],
        "hi": ["प्रिय ग्राहक, आपका {bank} खाता केवाईसी अधूरी होने से {time} बंद हो जाएगा। अभी {link} पर पैन और आधार अपडेट करें।",
               "आपका पैन कार्ड निष्क्रिय हो गया है। दोबारा चालू करने के लिए {link} पर क्लिक करें और अपना डेबिट कार्ड नंबर और पिन डालें।"],
        "hinglish": ["Dear customer, aapka {bank} account KYC pending hone ki wajah se {time} block ho jayega. Abhi {link} par PAN aur Aadhaar update karein.",
                     "Aapka PAN card deactivate ho gaya hai. Dobara active karne ke liye {link} par click karke apna card number aur PIN daalein."],
    },
    "electricity_cut": {
        "en": ["Electricity dept: your last bill is unpaid and the connection will be cut {time}. Call {phone} immediately and pay through the app we send.",
               "Dear consumer, power supply to your meter will be disconnected {time} because bill details are not updated. Contact the officer on {phone} now."],
        "hi": ["बिजली विभाग: आपका पिछला बिल बाकी है और {time} कनेक्शन काट दिया जाएगा। तुरंत {phone} पर संपर्क करें और भेजे गए ऐप से भुगतान करें।"],
        "hinglish": ["Bijli vibhag se message: aapka pichla bill pending hai, {time} connection kat jayega. Turant {phone} par call karein aur diye gaye app se payment karein.",
                     "Dear consumer aapke meter ki supply {time} band hogi kyunki bill update nahi hai. Officer se {phone} par baat karein."],
    },
    "lottery_prize": {
        "en": ["Congratulations! You have won {amt} in the lucky draw. To claim, pay the processing fee of {fee} to {upi}.",
               "You are selected as a winner of a brand new car in the {brand} anniversary contest. Send {fee} as delivery and tax charges to receive it.",
               "Lucky winner! {amt} credited to your prize wallet. Pay {fee} GST to release the amount today."],
        "hi": ["बधाई हो! आपने लकी ड्रॉ में {amt} जीते हैं। इनाम पाने के लिए {fee} प्रोसेसिंग फीस {upi} पर भेजें।",
               "आप हमारी वर्षगांठ प्रतियोगिता में नई कार के विजेता चुने गए हैं। इसे पाने के लिए {fee} टैक्स और डिलीवरी शुल्क जमा करें।"],
        "hinglish": ["Mubarak ho! Aapne lucky draw me {amt} jeete hain. Claim karne ke liye {fee} processing fee {upi} par bhejein.",
                     "Aap ek naye mobile ke winner hain. Prize lene ke liye {fee} delivery aur tax charges bhejein, offer aaj hi khatam."],
    },
    "job_task": {
        "en": ["Part-time job: like and subscribe to videos and earn {amt} daily. Join our Telegram group, pay a refundable registration deposit of {fee} to start.",
               "Work from home data entry. Earn {amt} per day, no experience. Register by paying {fee} for your ID card and training kit.",
               "We are hiring for {brand}. Simple task, review products and get {amt} per task. WhatsApp +44 7{n} {n} {n} and send {fee} to activate your account."],
        "hi": ["पार्ट टाइम जॉब: वीडियो लाइक करके रोज़ {amt} कमाएँ। टेलीग्राम ग्रुप से जुड़ें और शुरू करने के लिए {fee} रजिस्ट्रेशन राशि जमा करें, बाद में वापस मिलेगी।",
               "घर बैठे डेटा एंट्री का काम, रोज़ {amt} कमाएँ। आईडी कार्ड और ट्रेनिंग किट के लिए {fee} भेजकर रजिस्टर करें।"],
        "hinglish": ["Part time job: videos like karke daily {amt} kamaiye. Telegram group join karo aur start karne ke liye {fee} refundable deposit bhejo.",
                     "Ghar baithe task karo, har task ka {amt}. Account activate karne ke liye pehle {fee} registration fee pay karni hogi."],
    },
    "loan_app": {
        "en": ["Instant personal loan up to {amt} without documents, no CIBIL check. Download our app, allow access to contacts, and pay {fee} insurance fee first to get approved.",
               "Your loan of {amt} is pre-approved. To release the amount pay {fee} processing charges first. Offer valid {time}.",
               "Loan approved! Send {fee} GST and file charge to {upi} and the money reaches your account in 10 minutes."],
        "hi": ["बिना दस्तावेज़ के {amt} तक का इंस्टेंट लोन, सिबिल की जाँच नहीं। हमारा ऐप डाउनलोड करें, कॉन्टैक्ट्स की अनुमति दें और मंज़ूरी के लिए पहले {fee} बीमा शुल्क भेजें।",
               "आपका {amt} का लोन पास हो गया है। राशि पाने के लिए पहले {fee} प्रोसेसिंग शुल्क जमा करें।"],
        "hinglish": ["Instant loan {amt} tak bina documents ke. App download karo, contacts access allow karo aur approval ke liye pehle {fee} insurance fees pay karo.",
                     "Aapka {amt} ka loan approve ho gaya hai. Paise lene ke liye {fee} processing charges pehle bhejiye."],
    },
    "relative_emergency": {
        "en": ["Hi, it's {name}. I lost my phone and I am using a friend's number. I need {amt} urgently for a hospital bill, please send to {upi} right now and don't tell dad.",
               "Mom my phone is broken, this is a new number. Please send {amt} to this account right away, I am in trouble and will explain later.",
               "Beta this is your uncle, I had an accident and I am in the hospital. Send {amt} immediately to {upi}, my phone is dead."],
        "hi": ["मम्मी, मेरा फ़ोन टूट गया है, यह नया नंबर है। अभी {amt} इसी नंबर पर फ़ोनपे कर दो, बहुत ज़रूरी है, पापा को मत बताना।",
               "बेटा मैं तुम्हारा चाचा बोल रहा हूँ, मेरा एक्सीडेंट हो गया है और मैं अस्पताल में हूँ। फ़ोन बंद है, तुरंत {amt} इस खाते में भेजो।"],
        "hinglish": ["Papa mera phone kho gaya hai, ye naya number hai. Abhi {amt} is number par bhej do, bahut zaruri hai, kisi ko mat batana.",
                     "Beta main tumhara mama bol raha hu, accident ho gaya hai hospital me hu. {amt} turant {upi} par bhejo, phone band hai."],
    },
    "olx_advance": {
        "en": ["Hi, I am interested in your listing. I am posted in the Army so I cannot come. I will pay {amt} advance by UPI. Scan the QR I am sending and enter your PIN to receive the money.",
               "I am CRPF officer {person}. Will buy your item, my transport person will collect. Send {small} to verify your account, then you will receive {amt}.",
               "Sir I liked your flat, I am abroad. Pay {fee} token now on {upi} to hold it, agreement will be mailed."],
        "hi": ["नमस्ते, मुझे आपका सामान पसंद आया। मैं सेना में तैनात हूँ इसलिए आ नहीं सकता। {amt} एडवांस भेज रहा हूँ, मेरा क्यूआर स्कैन करके अपना यूपीआई पिन डालिए, पैसे आ जाएँगे।"],
        "hinglish": ["Bhai main Army me hu, aapka saaman pasand aaya. {amt} advance bhej raha hu, bas QR scan karke apna UPI PIN daalo, paise aa jayenge.",
                     "Sir flat pasand aaya, main bahar hu. Hold karne ke liye abhi {upi} par {fee} token bhejiye, agreement mail kar dunga."],
    },
    "fake_support": {
        "en": ["Your computer shows a virus. This is {brand} support. Install AnyDesk and tell me the 9 digit code so I can remove it and process your refund.",
               "Customer care here. To process your refund of {amt}, install QuickSupport, share your screen and enter your UPI PIN when asked.",
               "Your {app} account will be blocked. Call support on {phone}, our agent will guide you, keep your phone with OTP ready."],
        "hi": ["आपके गैस कनेक्शन की सब्सिडी रुकी है। मदद के लिए एनीडेस्क ऐप डालें और स्क्रीन पर दिख रहा कोड हमारे एजेंट को बताएँ।",
               "कस्टमर केयर से बोल रहे हैं। {amt} का रिफंड देने के लिए टीमव्यूअर इंस्टॉल करें और स्क्रीन शेयर करें।"],
        "hinglish": ["Aapke computer me virus hai. Main {brand} support se hu. AnyDesk install karke 9 digit code bataiye, refund process kar dunga.",
                     "Customer care se bol rahe hain. {amt} ka refund dene ke liye QuickSupport app dalo aur screen share karo."],
    },
    "refund_trap": {
        "en": ["Your refund of {amt} is ready. Approve the collect request on your {app} and enter your UPI PIN to receive the money.",
               "Cashback of {amt} credited. To receive it scan this QR and enter your PIN, amount will be added to your wallet.",
               "Order cancelled, refund {amt} pending. Click {link}, enter your card number, expiry and OTP to get it back."],
        "hi": ["आपका {amt} का रिफंड तैयार है। अपने {app} पर कलेक्ट रिक्वेस्ट मंज़ूर करें और पैसे पाने के लिए यूपीआई पिन डालें।"],
        "hinglish": ["Aapka {amt} ka refund ready hai. {app} par collect request approve karo aur paise lene ke liye UPI PIN daalo.",
                     "Cashback {amt} aaya hai. Receive karne ke liye QR scan karo aur PIN enter karo."],
    },
    "investment_group": {
        "en": ["Join our VIP stock tips group. Guaranteed {pct}% monthly returns, last month members made {amt}. Deposit {fee} to {upi} to get in. Limited seats.",
               "Sure shot IPO allotment for selected members. Pay {amt} today to secure shares, returns {pct}0% before listing.",
               "Our trading expert gives daily profit of {pct}%. Download our app, deposit {amt} and withdraw double in {days} days."],
        "hi": ["हमारे वीआईपी शेयर टिप्स ग्रुप से जुड़ें। हर महीने {pct}% गारंटीड रिटर्न। {upi} पर {fee} जमा करें और शामिल हों, सीटें सीमित हैं।"],
        "hinglish": ["Hamare VIP stock tips group me judo. Guaranteed {pct}% monthly return. {upi} par {fee} jama karo, seats limited hain.",
                     "Trading expert roz {pct}% profit dete hain. App download karo, {amt} deposit karo aur {days} din me double nikalo."],
    },
    "fee_to_withdraw": {
        "en": ["Your profit of {amt} is ready. To withdraw you must first pay {pct}% tax, send {fee} to {upi}.",
               "Withdrawal blocked. Pay a release fee of {fee} to unlock your funds and withdraw today.",
               "Your trading balance {amt} is frozen by compliance. Deposit {fee} verification amount to unfreeze and withdraw."],
        "hi": ["आपका {amt} का मुनाफ़ा तैयार है। निकालने के लिए पहले {pct}% टैक्स यानी {fee} {upi} पर भेजना होगा।"],
        "hinglish": ["Aapka {amt} ka profit ready hai. Nikalne ke liye pehle {pct}% tax, yaani {fee}, {upi} par bhejna hoga.",
                     "Withdrawal rok diya gaya hai. Unlock karne ke liye {fee} release fee bhejiye."],
    },
    "crypto_double": {
        "en": ["Crypto giveaway! Send 0.1 BTC to our wallet and get 0.2 BTC back instantly. Offer valid one hour only.",
               "Bitcoin mining platform, invest {amt} and your money doubles in {days} days. Withdrawal after paying {pct}% tax to the account manager.",
               "USDT arbitrage group: members earned {pct}x in {days} days. Deposit {amt} on our platform, withdraw anytime."],
        "hi": ["बिटकॉइन माइनिंग प्लेटफ़ॉर्म में {amt} लगाएँ और {days} दिन में पैसा दोगुना पाएँ। निकासी के लिए पहले {pct}% टैक्स भेजना होगा।"],
        "hinglish": ["Bitcoin mining ke liye hamare platform me {amt} invest karo, {days} din me paisa double. Withdrawal ke liye pehle {pct}% tax bhejna padega."],
    },
    "parcel_fee": {
        "en": ["Your {courier} parcel is held at customs. Pay {small} clearance fee at {link} to release it today.",
               "{courier}: delivery failed, address incomplete. Update the address and pay {small} redelivery charge here: {link}.",
               "A gift parcel worth {amt} has arrived for you from abroad. Pay {fee} customs duty to our agent to receive it."],
        "hi": ["आपका {courier} पार्सल कस्टम में रुका है। आज छुड़वाने के लिए {link} पर {small} क्लियरेंस शुल्क भरें।"],
        "hinglish": ["Aapka courier undelivered hai. Address update karne ke liye {small} ka charge is link par pay karo: {link}",
                     "{courier}: parcel customs me ruka hai, {small} fees bharkar aaj hi chhudwayein: {link}"],
    },
    "fastag_challan": {
        "en": ["Your FASTag wallet balance is negative and your vehicle will be blacklisted at toll plazas. Recharge now through {link} to avoid a fine.",
               "E-challan pending against your vehicle. Pay {small} immediately at {link} or the fine increases to {amt}.",
               "RTO notice: traffic violation recorded. Download the {brand} app to see the challan and pay online."],
        "hi": ["आपके फास्टैग का बैलेंस माइनस है और गाड़ी टोल पर ब्लैकलिस्ट हो जाएगी। जुर्माने से बचने के लिए {link} से अभी रिचार्ज करें।"],
        "hinglish": ["Aapke vehicle par e-challan pending hai. {small} abhi {link} par bharein, warna fine {amt} ho jayega."],
    },
    "tax_refund": {
        "en": ["Income Tax Department: you are eligible for a refund of {amt}. Click {link} and enter your card details to receive it.",
               "GST refund of {amt} approved for your account. Submit bank details and OTP at {link} within 24 hours."],
        "hi": ["आयकर विभाग: आप {amt} के रिफंड के पात्र हैं। {link} पर क्लिक करके अपने कार्ड की जानकारी डालें और रिफंड पाएँ।"],
        "hinglish": ["Income Tax refund {amt} approved hai. Lene ke liye {link} par card details aur OTP daalein."],
    },
    "insurance_maturity": {
        "en": ["Your old LIC policy has matured with a bonus of {amt}. Pay {fee} processing fee and GST to release the maturity amount.",
               "Insurance claim of {amt} pending. Our officer {person} will help, send {fee} for documentation to get it credited."],
        "hi": ["आपकी पुरानी एलआईसी पॉलिसी मैच्योर हो गई है, {amt} का बोनस मिलेगा। राशि पाने के लिए {fee} प्रोसेसिंग और जीएसटी शुल्क जमा करें।"],
        "hinglish": ["Aapki purani policy mature ho gayi hai, {amt} bonus milega. Release karwane ke liye {fee} processing fee bhejiye."],
    },
    "sextortion": {
        "en": ["We have your private video. Pay {amt} or it will be sent to all your contacts and posted online. You have 2 hours.",
               "Your photos are with us. Send {amt} to {upi} to delete them, otherwise your family and office will see them."],
        "hi": ["हमारे पास आपका निजी वीडियो है। {amt} दें वरना यह आपके सभी कॉन्टैक्ट्स को भेज दिया जाएगा।"],
        "hinglish": ["Hamare paas aapka private video hai. {amt} bhejo warna sabhi contacts ko bhej denge, 2 ghante hain."],
    },
    "gift_abroad": {
        "en": ["Hello dear, I am a doctor posted abroad and I want to send you a gift parcel worth {amt}. You only pay the customs charge of {fee} to our agent.",
               "I am {name} from London, I fell in love with your profile. I sent you a valuable gift, pay {fee} clearance to the courier to receive it."],
        "hi": ["नमस्ते, मैं विदेश में डॉक्टर हूँ और आपको {amt} का उपहार भेजना चाहता हूँ। आपको सिर्फ़ एजेंट को {fee} कस्टम शुल्क देना है।"],
        "hinglish": ["Dear, main abroad me doctor hu aur aapko {amt} ka gift bhej raha hu. Bas agent ko {fee} customs charge dena hoga."],
    },
    "govt_subsidy": {
        "en": ["PM scheme: you are eligible for a subsidy of {amt}. Pay {fee} registration at {link} to get the amount in your bank today.",
               "Scholarship of {amt} sanctioned. Pay {fee} processing fee at {link} and share your bank OTP to receive it.",
               "Your cylinder subsidy of {amt} is pending. Send {small} to verify via {link}."],
        "hi": ["सरकारी योजना: आप {amt} की सब्सिडी के पात्र हैं। आज ही पैसे पाने के लिए {link} पर {fee} पंजीकरण शुल्क जमा करें।"],
        "hinglish": ["Scholarship {amt} sanction ho gayi hai. Lene ke liye {link} par {fee} processing fee bharein aur bank OTP share karein."],
    },
    "sim_trai": {
        "en": ["TRAI notice: your mobile number will be disconnected in 2 hours due to illegal activity. Press 9 to speak to the officer.",
               "Your SIM will be deactivated {time}. Verify with Aadhaar and share the OTP you receive to keep your number active."],
        "hi": ["ट्राई सूचना: अवैध गतिविधि के कारण आपका मोबाइल नंबर 2 घंटे में बंद कर दिया जाएगा। अधिकारी से बात करने के लिए 9 दबाएँ।"],
        "hinglish": ["TRAI notice: aapka number illegal activity ki wajah se 2 ghante me band ho jayega. Officer se baat karne ke liye 9 dabayein."],
    },
    "fake_payment_proof": {
        "en": ["Sir I have paid {amt} for the order, screenshot attached. My bank server is slow so you may not get the SMS. Please dispatch the goods.",
               "Payment done {amt}, see the screenshot. Money will show in your account in some time, please send the item today itself.",
               "I sent {amt} by mistake, please return {amt} to {upi}. Check the payment screenshot."],
        "hi": ["सर, मैंने ऑर्डर के {amt} भेज दिए हैं, स्क्रीनशॉट भेज रहा हूँ। मेरा बैंक सर्वर धीमा है इसलिए एसएमएस नहीं आया होगा, कृपया माल आज ही भेज दें।"],
        "hinglish": ["Sir maine {amt} bhej diye hain, screenshot attached hai. Bank server slow hai isliye SMS nahi aaya, maal aaj hi dispatch kar do."],
    },
    "changed_account": {
        "en": ["Our bank account has changed. Please pay the pending invoice of {amt} to the new account {acct}, IFSC ICIC0{n}0{n}. Regards, accounts team.",
               "Dear sir, update your records: from next month pay the rent to our new account {acct}. Old account is closed."],
        "hi": ["हमारा बैंक खाता बदल गया है। कृपया बकाया बिल {amt} नए खाते {acct} में भेजें। पुराना खाता बंद हो चुका है।"],
        "hinglish": ["Hamara bank account badal gaya hai. Pending invoice {amt} ab naye account {acct} me bhejiye, purana account band hai."],
    },
    "otp_return": {
        "en": ["Hi, I sent you a verification code by mistake on WhatsApp. Please send it back to me, it is urgent.",
               "Please share the 6 digit code you just received, I am verifying your delivery and it will be cancelled otherwise."],
        "hi": ["नमस्ते, मैंने गलती से आपको एक वेरिफ़िकेशन कोड भेज दिया है। कृपया उसे मुझे वापस भेज दीजिए, बहुत ज़रूरी है।"],
        "hinglish": ["Hi, galti se aapke number par ek verification code chala gaya hai. Please wo code mujhe wapas bhej do, urgent hai."],
    },
    "card_block": {
        "en": ["Your {bank} credit card is blocked. To unblock share your card number, expiry date and the OTP sent to your phone.",
               "Reward points worth {amt} expire today. Redeem now at {link} and enter your card number and CVV."],
        "hi": ["आपका {bank} एटीएम कार्ड ब्लॉक हो गया है। चालू करने के लिए अपना कार्ड नंबर, एक्सपायरी और ओटीपी बताएँ।"],
        "hinglish": ["Aapka {bank} card block ho gaya hai. Unblock karne ke liye card number, expiry aur OTP bataiye."],
    },
    "fake_apk": {
        "en": ["Your {bank} reward points will expire. Download the {bank} Rewards APK from {link} and install it to claim.",
               "Traffic challan app: install the RTO_Challan.apk sent here to view and pay your pending fine."],
        "hi": ["आपके {bank} रिवॉर्ड पॉइंट्स खत्म होने वाले हैं। {link} से एपीके डाउनलोड करके इंस्टॉल करें और पाएँ।"],
        "hinglish": ["Aapke {bank} reward points expire honge. {link} se APK download karke install karein aur claim karein."],
    },
    "subscription_expired": {
        "en": ["Your Netflix payment failed. Update billing information at {link} to avoid suspension.",
               "Your {brand} Prime membership expired. Renew for {small} at {link}, enter card details to continue."],
        "hi": ["आपका नेटफ्लिक्स भुगतान असफल रहा। सेवा बंद होने से बचने के लिए {link} पर बिलिंग जानकारी अपडेट करें।"],
        "hinglish": ["Aapka subscription payment fail ho gaya. Band hone se bachne ke liye {link} par billing details update karein."],
    },
    "fake_customer_number": {
        "en": ["Hello, I searched for {brand} customer care on Google and my refund is stuck. The number {phone} asked me to share an OTP. Please confirm.",
               "For refund of {amt} call our helpline {phone} immediately, our executive will take your card details and process it."],
        "hi": ["{amt} के रिफंड के लिए तुरंत हमारी हेल्पलाइन {phone} पर कॉल करें, हमारा कार्यकारी आपके कार्ड की जानकारी लेकर रिफंड करा देगा।"],
        "hinglish": ["Refund {amt} ke liye turant helpline {phone} par call karein, executive aapke card ki details lekar refund process karega."],
    },
    "betting_game": {
        "en": ["Cricket match fixing tip, 100% sure win tonight. Deposit {amt} on our betting app and get {pct}x returns.",
               "Online game bonus: add {fee} to your wallet and win {amt}. Withdraw instantly after {times} wins."],
        "hi": ["आज रात के मैच की सौ प्रतिशत पक्की टिप। हमारे बेटिंग ऐप में {amt} जमा करें और {pct} गुना पाएँ।"],
        "hinglish": ["Aaj ke match ki 100% sure tip. Hamare betting app me {amt} deposit karo aur {pct}x wapas pao."],
    },
    "pf_pension": {
        "en": ["EPFO: your PF of {amt} is ready for withdrawal. Pay {fee} service charge at {link} to process the claim.",
               "Pension stopped. Verify your life certificate at {link} and pay {small} to restart."],
        "hi": ["ईपीएफओ: आपका {amt} पीएफ निकासी के लिए तैयार है। क्लेम के लिए {link} पर {fee} सेवा शुल्क भरें।"],
        "hinglish": ["PF ka {amt} nikalne ke liye ready hai. Claim process ke liye {link} par {fee} service charge bharein."],
    },
    "booking_advance": {
        "en": ["Hotel booking confirmed at half price. Pay {fee} advance to {upi} within 30 minutes or the offer is cancelled.",
               "Tatkal train tickets available at 50% extra. Send {amt} to {upi} and we will WhatsApp the ticket."],
        "hi": ["आधी कीमत पर होटल बुकिंग पक्की। 30 मिनट में {upi} पर {fee} एडवांस भेजें वरना ऑफ़र रद्द।"],
        "hinglish": ["Half price par hotel booking confirm hai. 30 minute me {upi} par {fee} advance bhejo warna offer cancel."],
    },
    "charity_fake": {
        "en": ["Please donate for a child's heart surgery, hospital needs {amt} urgently. Send any amount to {upi}. God bless you.",
               "Flood relief fund: donate {fee} now to {upi}, tax certificate will be sent."],
        "hi": ["एक बच्चे की दिल की सर्जरी के लिए अस्पताल को तुरंत {amt} चाहिए। {upi} पर जो भी दे सकें भेजें।"],
        "hinglish": ["Ek bachche ki heart surgery ke liye hospital ko {amt} turant chahiye. {upi} par jo ho sake bhejein."],
    },
    "social_account": {
        "en": ["Your Instagram account violates policy and will be deleted in 24 hours. Verify at {link} with your password.",
               "Your WhatsApp will be banned. Verify your account by entering the code at {link}."],
        "hi": ["आपका इंस्टाग्राम खाता नीति तोड़ने पर 24 घंटे में हटा दिया जाएगा। {link} पर पासवर्ड डालकर सत्यापन करें।"],
        "hinglish": ["Aapka Instagram account 24 ghante me delete ho jayega. {link} par password daalkar verify karein."],
    },
    "wrong_transfer": {
        "en": ["I sent {amt} to your account by mistake. Please send it back to this number, I am very worried.",
               "Sorry, wrong transfer of {amt} to your account. Kindly return it to {upi} immediately."],
        "hi": ["गलती से आपके खाते में {amt} चले गए हैं। कृपया इसी नंबर पर वापस भेज दीजिए, मैं बहुत परेशान हूँ।"],
        "hinglish": ["Maine galti se aapke account me {amt} bhej diye. Please wapas bhej do is number par, main bahut pareshaan hu."],
    },
    "emi_waiver": {
        "en": ["Your credit card limit increased to {amt}. Pay {fee} activation fee at {link} to enable it.",
               "Loan EMI waiver for 3 months. Send {fee} to {upi} and we will waive your EMI."],
        "hi": ["आपके क्रेडिट कार्ड की सीमा {amt} बढ़ा दी गई है। चालू करने के लिए {link} पर {fee} एक्टिवेशन शुल्क दें।"],
        "hinglish": ["Aapke credit card ki limit {amt} badh gayi hai. Activate karne ke liye {link} par {fee} fee dein."],
    },
}

OPENERS = {"en": ["", "", "", "Dear customer, ", "Attention: ", "URGENT: ", "Important notice. ", "Hello sir, ", "Alert! "],
           "hi": ["", "", "", "प्रिय ग्राहक, ", "ज़रूरी सूचना: ", "सावधान: ", "नमस्कार, "],
           "hinglish": ["", "", "", "Dear customer, ", "Zaruri suchna: ", "URGENT: ", "Sir, ", "Hello, "]}
CLOSERS = {"en": ["", "", "", " Act now.", " Do not ignore this.", " Reply YES to confirm.", " Hurry.", " This is the last reminder.", " Call us on {phone}."],
           "hi": ["", "", "", " तुरंत कार्रवाई करें।", " इसे अनदेखा न करें।", " देर न करें।", " संपर्क करें: {phone}।"],
           "hinglish": ["", "", "", " Jaldi karein.", " Isse ignore mat karna.", " Der mat karo.", " Contact: {phone}."]}

# ---------------------------------------------------------------- genuine
GENUINE: dict[str, dict[str, list[str]]] = {
    "bank_alert": {
        "en": ["{amt}.00 debited from A/c XX{n}{n} on 22-10-26 to VPA {upi2}. If not you, call your bank. -{bankshort}",
               "Rs {amtn} credited to your account XX{n}{n} by NEFT from {company}. Avl bal Rs {amtn}. -{bankshort}",
               "Your {bank} debit card ending {n}{n} was used for {amt} at {shop}. Not you? Call the number on the back of your card.",
               "Your statement for card ending {n}{n} is ready. Minimum due {amt}, due date {date}. Pay using the official app."],
        "hi": ["आपके खाते XX{n}{n} से {amt} कट गए हैं। यह आप नहीं थे तो अपने बैंक को कॉल करें। -{bankshort}",
               "आपके खाते में {amt} जमा हुए हैं। उपलब्ध शेष राशि अपडेट हो गई है। -{bankshort}"],
        "hinglish": ["Aapke account XX{n}{n} se {amt} debit hue hain. Agar ye aap nahi the to bank ko call karein. -{bankshort}",
                     "Aapke account me {amt} credit hue hain. Balance update ho gaya hai. -{bankshort}"],
    },
    "otp_warning": {
        "en": ["Your OTP for login is {otp}. Do not share this with anyone, including bank staff. Valid for 10 minutes.",
               "{otp} is your one time password for the transaction of {amt}. Never share it. If not you, report immediately.",
               "Your cab is arriving in 3 minutes. OTP for the ride is {otp}. Share it only with the driver."],
        "hi": ["आपके लॉगिन का ओटीपी {otp} है। यह 10 मिनट तक मान्य है। इसे किसी को न बताएँ, बैंक के कर्मचारी को भी नहीं।"],
        "hinglish": ["Aapka login OTP {otp} hai. Ise kisi ke saath share na karein, bank wale ke saath bhi nahi. 10 minute tak valid."],
    },
    "delivery_update": {
        "en": ["Your {courier} order #{ref} has been shipped and will arrive by Friday. Track it in the app.",
               "Your order is out for delivery. Rider {name} will arrive in 10 minutes. Pay nothing at the door, it is prepaid.",
               "Delivered: your package was left at the security desk. Rate your experience in the app."],
        "hi": ["आपका ऑर्डर भेज दिया गया है और शुक्रवार तक पहुँच जाएगा। ऐप में ट्रैक करें।"],
        "hinglish": ["Aapka order deliver ho gaya hai. Koi dikkat ho to app me return request daal sakte hain.",
                     "Aapka order out for delivery hai, rider {name} 10 minute me pahunchega."],
    },
    "personal_chat": {
        "en": ["Hi, are we still on for lunch tomorrow at 1? I will book the table.", "Reached home safely. Will call you tomorrow morning.",
               "Can you pick up milk and bread on your way back? Also call mom, she was asking.", "Happy birthday! Wishing you a great year ahead. Dinner on me this weekend.",
               "Meeting moved to 4 PM, conference room B. Please bring the laptop."],
        "hi": ["माँ, मैं पहुँच गया हूँ। खाना खा लिया। कल सुबह फ़ोन करूँगा।", "आज शाम सात बजे सोसाइटी में बैठक है। सभी सदस्य कृपया उपस्थित रहें।",
               "कल घर आ जाना, चाय पर बात करेंगे।"],
        "hinglish": ["Bhai kal shaam 7 baje ghar aa jana, cake lekar. Mummy ne bola hai.", "Meeting 4 baje shift ho gayi hai, laptop leke aana.",
                     "Yaar maine tera Rs 500 UPI kar diya, check kar le. Kal chai pe milte hain."],
    },
    "friend_money_benign": {
        "en": ["Hey, can you send {small} for the auto fare? I will return it tonight.", "I sent the rent split, {amt}, via {app}. Can you confirm it showed up?",
               "Dad, can you transfer my college fee this week? The receipt is on the portal and I will check with the office first.",
               "Sending you {amt} for dinner, my UPI is {upi2}. No rush to pay back."],
        "hi": ["यार ऑटो के लिए {small} भेज देना, रात को लौटा दूँगा।", "पापा, इस हफ़्ते कॉलेज की फीस भेज दीजिए, रसीद पोर्टल पर है, मैं पहले दफ़्तर में पूछ लूँगा।"],
        "hinglish": ["Bhai auto ke liye {small} bhej dena, raat ko wapas kar dunga.", "Maine rent ka hissa {amt} {app} se bhej diya hai, dekh lena aa gaya ya nahi."],
    },
    "appointment_reminder": {
        "en": ["Reminder: your appointment with Dr. Rao is on Monday 10:30 AM at City Clinic. Reply C to confirm.",
               "Interview scheduled Thursday 11 AM at our office. Please carry your resume. No fee is charged at any stage.",
               "Your visa interview is on 3 Nov. Carry the printed confirmation and original passport."],
        "hi": ["कल की परीक्षा 10 बजे से है। प्रवेश पत्र साथ लाना न भूलें। शुभकामनाएँ।", "डॉ. राव के साथ आपकी अपॉइंटमेंट सोमवार सुबह 10:30 बजे है।"],
        "hinglish": ["Aapka appointment kal subah 10:30 baje hai, clinic me samay par aayein.", "Interview Thursday 11 baje hai, resume saath layein. Kisi bhi stage par koi fee nahi li jati."],
    },
    "utility_notice": {
        "en": ["Your electricity bill of {amt} is generated. Due date 30 Oct. Pay through the official app or website.",
               "The electricity department will carry out maintenance on Saturday 10am to 2pm in Sector {n}. Supply may be interrupted.",
               "Your gas cylinder will be delivered tomorrow morning. Share the OTP with the delivery person only after receiving it."],
        "hi": ["आपका बिजली का बिल {amt} बना है। अंतिम तिथि 30 अक्टूबर। भुगतान आधिकारिक ऐप से करें।"],
        "hinglish": ["Aapka gas cylinder kal subah deliver hoga. Delivery boy ko sirf cylinder haath me aane par OTP dena."],
    },
    "telecom_recharge": {
        "en": ["Your recharge of {amt} is successful. Validity till 20 Nov. Thank you.", "Your new SIM is activated. For KYC visit any store with your original Aadhaar. We never ask for OTP on call.",
               "Data pack of 2GB per day is active until {date}."],
        "hi": ["आपका {amt} का रिचार्ज सफल रहा। वैधता 20 नवंबर तक।"],
        "hinglish": ["Aapka {amt} ka recharge successful raha. Validity 20 Nov tak hai."],
    },
    "travel_ticket": {
        "en": ["Your bus ticket from Delhi to Jaipur is confirmed. Seat {n}, departure 9 PM.", "PNR {ref}: your train ticket is confirmed for 28 Oct. Carry a valid photo ID.",
               "Flight AI {n}{n} is on time. Web check-in opens 48 hours before departure."],
        "hi": ["आपकी ट्रेन का टिकट कन्फर्म हो गया है। यात्रा की तारीख 28 अक्टूबर। पहचान पत्र साथ रखें।"],
        "hinglish": ["Aapka bus ticket confirm hai, seat {n}, raat 9 baje departure."],
    },
    "shop_receipt": {
        "en": ["Thank you for your payment of {amt} to {shop}. Your invoice is attached in the email.", "Your refund of {amt} for the cancelled order has been initiated and will reach your bank in 5-7 days.",
               "Order #{ref} confirmed. {amt} paid via {app}. Estimated delivery in 3 days."],
        "hi": ["{shop} को {amt} के भुगतान के लिए धन्यवाद। आपका बिल ईमेल में है।"],
        "hinglish": ["{shop} ko {amt} ke payment ke liye thanks. Aapka invoice email me bhej diya gaya hai."],
    },
    "legit_promo": {
        "en": ["Flat 20% off on shoes this weekend at our store. Visit our website for deals.", "Free delivery on orders above Rs 499 this week. Terms apply.",
               "Our new branch opens on Saturday at 10 AM. Come and enjoy 10% off on all items."],
        "hi": ["इस हफ़्ते हमारे स्टोर पर जूतों पर 20% की छूट। अधिक जानकारी के लिए वेबसाइट देखें।"],
        "hinglish": ["Is weekend hamare store par shoes par flat 20% off hai. Deals ke liye website dekhein."],
    },
    "bank_kyc_genuine": {
        "en": ["Dear customer, your KYC update is due. Please visit your home branch with your Aadhaar and PAN. We never ask for OTP, PIN or card details by SMS or call.",
               "{bank}: never share your OTP, PIN or CVV with anyone. We will never call to ask for them. Report fraud at the number on your card.",
               "Your EMI of {amt} is due on {date}. Please maintain balance in your account. Pay through the official app."],
        "hi": ["प्रिय ग्राहक, आपकी केवाईसी अपडेट होनी है। कृपया आधार और पैन के साथ अपनी शाखा में आएँ। हम एसएमएस या कॉल पर ओटीपी या पिन कभी नहीं माँगते।"],
        "hinglish": ["Dear customer, KYC update baaki hai. Aadhaar aur PAN lekar apni branch aayein. Hum SMS ya call par OTP ya PIN kabhi nahi maangte."],
    },
    "school_office_notice": {
        "en": ["Dear parent, the school will remain closed on Monday for Diwali. Classes resume on Wednesday.", "Please submit your timesheet by Friday evening. HR will process salaries on the 1st.",
               "The society meeting is at 7 PM on Sunday. Agenda: water supply and lift repair."],
        "hi": ["प्रिय अभिभावक, दिवाली के कारण सोमवार को स्कूल बंद रहेगा। बुधवार से कक्षाएँ फिर शुरू होंगी।"],
        "hinglish": ["Dear parents, Diwali ki wajah se Monday ko school band rahega. Wednesday se classes shuru."],
    },
    "gov_notice_genuine": {
        "en": ["Your Aadhaar update request has been accepted. Check status at uidai.gov.in.", "Your passport appointment is on {date}. Carry original documents. No agent fee is required.",
               "Income tax return for AY 2026-27 is filed. Acknowledgement number {ref}. Visit incometax.gov.in for status."],
        "hi": ["आपका आधार अपडेट अनुरोध स्वीकार कर लिया गया है। स्थिति देखने के लिए uidai.gov.in पर जाएँ।"],
        "hinglish": ["Aapka Aadhaar update request accept ho gaya hai. Status uidai.gov.in par dekhein."],
    },
    "support_reply": {
        "en": ["We have received your complaint no. {ref}. Our team will contact you within 48 hours. -Customer Care", "Your password was changed successfully. If this was you, no action is needed. If not, contact support through the official app.",
               "Thanks for contacting us. Your refund of {amt} will be credited to the original payment method in 5 to 7 working days."],
        "hi": ["आपकी शिकायत संख्या {ref} दर्ज हो गई है। हमारी टीम 48 घंटों में संपर्क करेगी।"],
        "hinglish": ["Aapki complaint {ref} darj ho gayi hai. Hamari team 48 ghante me contact karegi."],
    },
    "mutual_fund_genuine": {
        "en": ["Your SIP of {amt} has been processed for October. Units allotted: {n}.{n}.", "Your fixed deposit of {amt} matures on {date}. Visit the branch or renew in the app."],
        "hi": ["आपका {amt} का एसआईपी अक्टूबर के लिए पूरा हो गया है।"],
        "hinglish": ["Aapka {amt} ka SIP October ke liye process ho gaya hai."],
    },
}

from scam_templates_extra import GENUINE_EXTRA, SCAM_EXTRA  # noqa: E402


def _merge(base: dict, extra: dict) -> None:
    for fam, langs in extra.items():
        for lang, templates in langs.items():
            base.setdefault(fam, {}).setdefault(lang, []).extend(templates)


_merge(SCAM, SCAM_EXTRA)
_merge(GENUINE, GENUINE_EXTRA)
from scam_templates_round2 import GENUINE_EXTRA2, SCAM_EXTRA2  # noqa: E402

_merge(SCAM, SCAM_EXTRA2)
_merge(GENUINE, GENUINE_EXTRA2)

SHOPS = ["Big Bazaar", "Reliance Digital", "Sharma Kirana", "City Medical", "Swiggy", "Zomato", "D-Mart", "Apollo Pharmacy", "Croma", "More Supermarket"]
COMPANIES = ["ACME PVT LTD", "TCS", "Infosys", "Reliance", "XYZ Traders"]
BANKSHORT = ["SBI", "HDFC Bank", "ICICI Bank", "Axis Bank", "PNB", "BoB", "Kotak"]
DATES = ["5 Nov", "12 Nov", "30 Oct", "15 Dec", "1 Nov", "20 Nov"]

SMS_NOISE = [lambda s, r: s, lambda s, r: s, lambda s, r: s, lambda s, r: s.lower() if r.random() < 0.5 else s,
             lambda s, r: s.replace(".", "") if r.random() < 0.5 else s, lambda s, r: s + " " + r.choice(["pls", "ASAP", "sir", "ji", "!!", "."]),
             lambda s, r: re.sub(r"\byou\b", "u", s) if r.random() < 0.4 else s, lambda s, r: s.replace("Rs ", "Rs.") if r.random() < 0.4 else s]


def expand(template: str, r: random.Random, lang: str, kind: str) -> str:
    sl = Slots(r, lang)
    if kind == "genuine":
        sl["upi2"] = rnd_upi(r, "genuine")
        sl["bankshort"] = r.choice(BANKSHORT)
        sl["shop"] = r.choice(SHOPS)
        sl["company"] = r.choice(COMPANIES)
        sl["date"] = r.choice(DATES)
        sl["amtn"] = r.choice(["15,000.00", "2,450.00", "62,310.00", "799.00", "1,24,000.00"])
        sl["ref"] = "".join(r.choice("0123456789") for _ in range(r.choice([6, 8, 12])))
    sl["brand"] = r.choice(["Amazon", "Flipkart", "Jio", "Airtel", "SBI", "Paytm", "HDFC", "Google"])
    text = template
    try:
        text = template.format_map(sl)
    except (KeyError, IndexError, ValueError):
        pass
    return text


def shingles(text: str, n: int = 6) -> set[tuple[str, ...]]:
    w = re.findall(r"\w+", text.lower())
    return {tuple(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


def banned_shingles() -> set[tuple[str, ...]]:
    out: set[tuple[str, ...]] = set()
    for f in sorted((ROOT / "data" / "kit").glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out |= shingles(json.loads(line)["text"])
    return out


def build(per_template: int, seed: int) -> tuple[list[dict], list[dict], int]:
    r = random.Random(seed)
    ban = banned_shingles()
    dropped = 0
    seen: set[str] = set()

    def make(kind: str, table: dict, label: str) -> list[dict]:
        nonlocal dropped
        rows: list[dict] = []
        for fam, langs in table.items():
            for lang, templates in langs.items():
                for t in templates:
                    for _ in range(per_template * (3 if kind == "genuine" else 1)):
                        text = expand(t, r, lang, kind)
                        if kind == "scam":
                            text = r.choice(OPENERS[lang]) + text + expand(r.choice(CLOSERS[lang]), r, lang, kind)
                        text = r.choice(SMS_NOISE)(text, r).strip()
                        key = re.sub(r"\W+", " ", text.lower()).strip()
                        if key in seen:
                            continue
                        if shingles(text) & ban:
                            dropped += 1
                            continue
                        seen.add(key)
                        rows.append({"text": text, "label": label, "lang": lang, "family": fam, "synthetic": True})
        return rows

    return make("scam", SCAM, "scam"), make("genuine", GENUINE, "benign"), dropped


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--per-template", type=int, default=4)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    scams, genuine, dropped = build(a.per_template, a.seed)
    a.out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("synth_scams.jsonl", scams), ("synth_genuine.jsonl", genuine)):
        (a.out / name).write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")
    fams = {x["family"] for x in scams}
    print(f"wrote {len(scams)} scams in {len(fams)} families and {len(genuine)} genuine; dropped {dropped} that overlapped the kit/held-out files")


if __name__ == "__main__":
    main()
