"""Measure the whole check on PDFs, chat screenshots and QR cards, with the AI rule check off and on.

usage: SATYAPAN_HOME=var python training/text/eval_ai_media.py   (needs the site's .env key; writes docs/results/ai_media_eval.json)
Everything is generated here and invented: no real person, number or account. The scam and genuine documents were written by the
integrator's assistant, so this is a small, optimistic, own-written set: it shows the feature works on these inputs and what it costs in
false alarms, not how it will do on the judges' files.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("SATYAPAN_HOME", str(ROOT / "var"))

import segno  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from satyapan.contracts.models import Tier  # noqa: E402
from satyapan.envfile import load_dotenv  # noqa: E402
from satyapan.eval.metrics import rate  # noqa: E402
from satyapan.layers.l4_semantic import llm_check  # noqa: E402
from satyapan.plugins import load_plugins  # noqa: E402
from satyapan.service import analyse_image, analyse_pdf  # noqa: E402

FLAGGED = {Tier.SUSPICIOUS, Tier.HIGH_RISK, Tier.REGISTRY_HIT}

PDF_SCAM = [
    ["WEALTH GROW ADVISORY - PREMIUM MEMBERSHIP", "Our SEBI registered expert gives guaranteed returns of 40% every month.", "Last month members earned Rs 1,20,000 on a Rs 50,000 deposit.",
     "Pay Rs 4,999 registration to join the VIP group today. Limited seats only."],
    ["Notice of Prize Award", "Dear winner, you have been selected for the lucky draw prize of Rs 25,00,000.", "To release the amount pay the processing fee of Rs 12,500 to the claims officer.",
     "Reply within 24 hours or the prize will be cancelled."],
    ["Pre-approved personal loan offer", "Loan amount Rs 5,00,000 approved with no CIBIL check and no documents.", "Pay Rs 7,500 insurance and processing fee in advance to release the loan.",
     "Download our app and allow access to your contacts."],
    ["Appointment letter - Amazon Work From Home", "You are selected for a part time job. Earn Rs 5,000 per day by rating products.", "Pay Rs 1,500 refundable registration deposit to activate your account.",
     "Join our Telegram group for daily tasks."],
    ["Directorate of Enforcement - Final Notice", "A money laundering case is registered against your Aadhaar and mobile number.", "You are under digital arrest. Do not tell anyone and stay available on video call.",
     "Transfer Rs 90,000 to the RBI verification account to close the case."],
    ["Income Tax Department - Refund Notice", "You are eligible for a tax refund of Rs 38,540.", "Click http://incometax-refund.top/claim and enter your card number, expiry and OTP to receive it today."],
    ["Crypto Mining Platform - Welcome", "Invest Rs 20,000 and your money doubles in 15 days. Guaranteed.", "To withdraw your profit first pay 15% tax to our account manager.",
     "Send the tax amount to profit.desk@ybl."],
    ["Important: Bank KYC expired", "Dear customer your SBI account will be blocked today because your KYC is pending.", "Update PAN and Aadhaar immediately at http://sbi-yono-kyc.in/update.",
     "Do not visit the branch. Share the OTP you receive to complete verification."],
    ["Tax invoice - Acme Traders", "Invoice INV-7731 for Rs 2,40,000 is overdue.", "Our bank account has changed. Please pay the invoice to the new account 7788990011, IFSC ICIC0000456.",
     "Old account is closed. Pay today to avoid penalty."],
    ["Customs clearance - Gift parcel from abroad", "A gift parcel worth 50,000 pounds has arrived for you.", "Pay the customs duty of Rs 20,000 to our clearing agent to receive the parcel.",
     "Parcel will be returned if not paid in 48 hours."],
]
PDF_GENUINE = [
    ["Electricity bill - October 2026", "Consumer number 4410032211. Units consumed 212. Amount due Rs 1,240.", "Due date 30 October. Pay through the official app or at the utility office.",
     "Supply may be interrupted for maintenance on Saturday 10 am to 2 pm in Sector 21."],
    ["Tax invoice - Sharma Stationers", "Invoice INV-2209 dated 14 October. Paper and pens, total Rs 3,450 including GST.", "Payment terms: 30 days. Bank details are the same as on previous invoices.",
     "Thank you for your business."],
    ["Fee receipt - City Public School", "Received with thanks from the parent of Class 7 the term fee of Rs 18,500.", "Receipt number 5521. Paid by cheque on 3 October.",
     "School will remain closed on Monday for Diwali."],
    ["LIC premium reminder", "Your premium of Rs 8,000 is due on 15 November.", "Please pay through the LIC website, the official app or at the branch. We never ask for OTP or card details by phone or SMS."],
    ["Hospital bill summary", "Patient admission 12 to 14 October. Consultation, room and medicines total Rs 22,600.", "Insurance claim number 88213 has been submitted. Balance payable at the billing counter Rs 2,600."],
    ["Bank statement notice", "Dear customer your monthly statement for October is ready.", "Minimum due Rs 1,200, due date 5 November. Pay using the official app.",
     "Never share your OTP, PIN or CVV with anyone, including bank staff."],
    ["Rent agreement summary", "Monthly rent Rs 12,000 payable on the first of each month to the account given in the agreement.", "Security deposit Rs 24,000 refundable at the end of the tenancy.",
     "Both parties have signed in the presence of two witnesses."],
    ["Interview invitation", "We are pleased to invite you for an interview on Thursday 11 am at our Gurgaon office.", "Please carry your resume and original certificates. No fee is charged at any stage of hiring."],
    ["Mutual fund SIP confirmation", "Your SIP of Rs 5,000 has been processed for October.", "Units allotted 112.34. The statement is available in the app.", "Mutual fund investments are subject to market risks."],
    ["Delivery note - Order 402-5521", "Your order has been shipped and will arrive by Friday.", "Track it in the app. Payment was made online, nothing to pay at the door.", "Thank you for shopping with us."],
]
CHAT_SCAM = [
    "Congratulations! You won Rs 25,00,000 in the KBC lucky draw. Pay Rs 12,500 processing fee to claim your prize today.",
    "Sir join our VIP stock tips group. Guaranteed 30 percent profit every month. Pay Rs 4,999 now to get in.",
    "Your SBI account is blocked due to pending KYC. Update PAN now at http://sbi-yono-kyc.in/update or it will be closed today.",
    "This is CBI. A parcel in your name has drugs. You are under digital arrest. Do not tell anyone. Transfer Rs 90,000 for verification.",
    "Part time job: like videos and earn Rs 5,000 daily. Pay Rs 1,500 registration deposit to start. Join our telegram group.",
    "Install AnyDesk and tell me the code so I can process your Rs 2,499 refund. Then enter your UPI PIN to receive the money.",
    "Hi mom this is my new number, phone broke. Please send Rs 15,000 urgently to this account, I will explain later. Dont tell dad.",
    "Your loan of Rs 50,000 is approved. Pay Rs 2,999 insurance fee first to release the amount. No documents needed.",
]
CHAT_GENUINE = [
    "Hi, are we still on for lunch tomorrow at 1? I will book the table. Also please bring the laptop to the 4 pm meeting.",
    "Your OTP for login is 482910. Do not share this with anyone including bank staff. Valid for 10 minutes.",
    "Mom I reached the hostel. Will call after dinner. Please do not worry. Exam went well.",
    "Your Amazon order has shipped and will arrive by Friday. Track it in the app. Nothing to pay at the door.",
    "Reminder: your appointment with Dr. Rao is on Monday 10:30 AM at City Clinic. Reply C to confirm.",
    "Dad can you transfer my college fee this week? The receipt is on the portal and I will check with the office first.",
    "Your monthly statement is ready. Minimum due Rs 1,200, due 5 November. Pay through the official app only.",
    "Happy birthday! Wishing you a wonderful year ahead. Dinner on me this weekend.",
]
QR_SCAM = ["SCAN TO RECEIVE YOUR REFUND OF Rs 4,999. Enter your UPI PIN to get the money.", "VIP STOCK TIPS: guaranteed 30% monthly profit. Scan to join and pay Rs 4,999.",
           "You won a lucky draw prize of Rs 5,00,000. Scan the QR and pay Rs 999 fee to claim.", "Part time job: earn Rs 5,000 a day. Scan to pay Rs 1,500 registration."]
QR_GENUINE = ["Sharma Kirana Store. Scan to pay.", "City Medical. Pay here with any UPI app.", "Please scan to pay the society maintenance for October.", "Hotel Annapurna. Scan to pay your bill."]


def font(size: int):
    for f in ("arial.ttf", "DejaVuSans.ttf", "calibri.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def pdf(lines: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 780
    for ln in lines:
        c.drawString(50, y, ln[:110])
        y -= 24
    c.save()
    return buf.getvalue()


def wrap(text: str, f, width: int, d) -> list[str]:
    out, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) > width and cur:
            out.append(cur)
            cur = w
        else:
            cur = t
    return out + ([cur] if cur else [])


def chat_png(text: str) -> bytes:
    im = Image.new("RGB", (720, 520), (229, 221, 213))
    d = ImageDraw.Draw(im)
    f = font(26)
    lines = wrap(text, f, 560, d)
    h = 30 + 36 * len(lines)
    d.rounded_rectangle((60, 60, 660, 60 + h), 18, fill=(255, 255, 255))
    for i, ln in enumerate(lines):
        d.text((84, 74 + 36 * i), ln, fill=(20, 20, 20), font=f)
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def qr_png(caption: str, payload: str) -> bytes:
    qb = io.BytesIO()
    segno.make(payload, error="m").save(qb, kind="png", scale=8, border=2)
    q = Image.open(io.BytesIO(qb.getvalue())).convert("RGB")
    im = Image.new("RGB", (max(q.width, 700), q.height + 190), (255, 255, 255))
    d = ImageDraw.Draw(im)
    f = font(26)
    for i, ln in enumerate(wrap(caption, f, 640, d)):
        d.text((30, 20 + 34 * i), ln, fill=(10, 10, 10), font=f)
    im.paste(q, ((im.width - q.width) // 2, 150))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def run(fn, items):
    res = []
    for it in items:
        t = fn(it)
        res.append(t.tier in FLAGGED)
    return res


def main() -> None:
    load_dotenv()
    load_plugins()
    if llm_check.config() is None:
        raise SystemExit("No AI provider key found (GROQ_API_KEY in .env).")
    sets = {
        "pdf": (lambda x: analyse_pdf(pdf(x)), PDF_SCAM, PDF_GENUINE),
        "chat_screenshot": (lambda x: analyse_image(chat_png(x), kind="screenshot"), CHAT_SCAM, CHAT_GENUINE),
        "qr_card": (lambda x: analyse_image(qr_png(x[0], x[1]), kind="qr"),
                    [(c, "https://example.com/pay") for c in QR_SCAM], [(c, "upi://pay?pa=shop@ybl&pn=Shop") for c in QR_GENUINE]),
    }
    out = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "provider": "groq", "reproduce": "python training/text/eval_ai_media.py",
           "note": "Invented, own-written, small: shows the feature works on these inputs and its false-alarm cost, not accuracy on the judges' files.", "sets": {}}
    for name, (fn, scam, genuine) in sets.items():
        row = {}
        for mode in ("without_ai", "with_ai"):
            os.environ["SATYAPAN_LLM"] = "0" if mode == "without_ai" else "1"
            t0 = time.time()
            s, g = run(fn, scam), run(fn, genuine)
            row[mode] = {"scams_flagged": rate(sum(s), len(s)), "genuine_flagged": rate(sum(g), len(g)), "seconds": round(time.time() - t0)}
            print(name, mode, f"scams {sum(s)}/{len(s)}  genuine flagged {sum(g)}/{len(g)}", flush=True)
        out["sets"][name] = row
    os.environ["SATYAPAN_LLM"] = "1"
    (ROOT / "docs" / "results" / "ai_media_eval.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
