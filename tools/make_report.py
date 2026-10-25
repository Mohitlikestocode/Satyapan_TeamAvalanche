"""Build the two-page final report (A4 PDF) for the submission.

usage: python tools/make_report.py <out_dir> <amazon_team_photo> <security_staff_photo> <amazon_leaders_photo>
Photos of people are NOT stored in the repository: pass their paths on the command line (they are embedded in the PDF only).
Product screenshots come from docs/img. Needs Chrome (headless print to PDF) and `segno` for the QR codes.
"""
from __future__ import annotations

import base64
import io
import subprocess
import sys
from pathlib import Path

import segno
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
REPO = "https://github.com/Mohitlikestocode/Satyapan_TeamAvalanche"
BOT = "https://t.me/Satyapanbot"


def qr_svg(url: str) -> str:
    b = io.BytesIO()
    segno.make(url, error="m").save(b, kind="svg", scale=3, border=1, dark="#0B2A4A", xmldecl=False, svgns=True, nl=False)
    return b.getvalue().decode()


def img(path: str | Path, ratio: float | None = None, frac: float = 0.5, width: int = 900) -> str:
    """Embed an image as a data URI, optionally cropped to a width:height ratio (frac = how far down the crop sits)."""
    im = Image.open(path).convert("RGB")
    w, h = im.size
    if ratio:
        th = int(w / ratio)
        if th <= h:
            top = int((h - th) * frac)
            im = im.crop((0, top, w, top + th))
        else:
            tw = int(h * ratio)
            left = int((w - tw) * 0.5)
            im = im.crop((left, 0, left + tw, h))
    im = im.resize((width, int(width * im.size[1] / im.size[0])))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


CSS = """
@page{size:A4;margin:0}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:210mm;background:#fff}
body{font-family:'Segoe UI','Noto Sans',Arial,sans-serif;font-size:9pt;line-height:1.32;color:#1D2939;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.page{width:210mm;height:296.5mm;overflow:hidden;position:relative;page-break-after:always;padding:0 11mm}
.page:last-child{page-break-after:auto}
.top{display:flex;justify-content:space-between;align-items:flex-end;padding:8mm 0 3mm;border-bottom:.35mm solid #0B2A4A}
.top h1{font-size:25pt;line-height:1;color:#0B2A4A;font-weight:800}.top h1 small{font-size:12pt;font-weight:400;color:#667085;margin-left:2.5mm}
.top .tm{text-align:right;font-size:7.4pt;color:#667085;line-height:1.4}.top .tm b{display:block;font-size:11.5pt;letter-spacing:1.2px;color:#0B2A4A}
.intro{padding:4mm 0 0;font-size:10.4pt;line-height:1.38;color:#0B2A4A}.intro b{color:#B54708}
.intro .sub{display:block;margin-top:1.4mm;font-size:8.6pt;color:#667085}
.hero{display:flex;gap:4.5mm;padding-top:4mm;align-items:stretch}
.story{flex:0 0 66mm;display:flex;flex-direction:column;justify-content:space-between;gap:3mm}
.story .q{font-size:8.6pt;color:#344054}.story .q b{color:#0B2A4A}
.bigstat{border-left:1.2mm solid #E8710A;padding:.4mm 0 .4mm 3mm}
.bigstat b{display:block;font-size:22pt;line-height:1;color:#0B2A4A;font-weight:800}
.bigstat span{display:block;font-size:7.8pt;color:#475467;margin-top:1mm}
.shots{flex:1;display:flex;gap:3mm;height:58mm}
.shots figure{flex:1;border-radius:2.4mm;overflow:hidden;border:.3mm solid #D0D5DD;position:relative;background:#0B1F3A}
.shots img{width:100%;height:100%;object-fit:contain;object-position:center top;display:block}
.shots figcaption{position:absolute;left:0;right:0;bottom:0;background:rgba(11,42,74,.9);color:#fff;font-size:7.4pt;font-weight:700;padding:1.1mm 2.2mm}
.sec{padding:5mm 0 2.2mm;font-size:8pt;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;color:#B54708}
.sec.first{padding-top:4mm}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:4mm 4.5mm}
.card figure{height:53mm;border-radius:2.4mm;overflow:hidden;background:#0B1F3A;border:.3mm solid #D0D5DD}
.card img{width:100%;height:100%;object-fit:cover;display:block}
.card .cap{padding:2mm 0 0}
.card q{display:block;font-size:10.6pt;font-style:italic;font-weight:700;color:#0B2A4A;quotes:none;line-height:1.25}
.card .who{font-size:7pt;font-weight:800;letter-spacing:.8px;text-transform:uppercase;color:#B54708;margin-top:1.1mm}
.card p{font-size:8.6pt;color:#344054;margin-top:.4mm}
.foot1{position:absolute;left:11mm;right:11mm;bottom:6mm;font-size:8pt;color:#667085;text-align:center;border-top:.25mm solid #D0D5DD;padding-top:2mm}.foot1 b{color:#0B2A4A}
.feat{display:grid;grid-template-columns:repeat(3,1fr);gap:3mm}
.f{border:.3mm solid #D0D5DD;border-radius:2.2mm;padding:2.6mm 3mm;background:#fff}
.f h3{font-size:9.6pt;color:#0B2A4A;margin-bottom:1mm}.f h3 i{font-style:normal;display:inline-block;width:1.8mm;height:1.8mm;border-radius:50%;background:#E8710A;margin-right:1.6mm;vertical-align:middle}
.f p{font-size:8.2pt;color:#475467;line-height:1.35}.f p b{color:#0B2A4A;font-weight:700}
.models{display:flex;gap:3mm}
.m{flex:1;border-radius:2.2mm;background:#0B2A4A;color:#fff;padding:2.4mm 3mm;font-size:8pt;line-height:1.3}.m b{display:block;color:#FFD9B0;font-size:9.2pt;margin-bottom:.6mm}
.nums{display:grid;grid-template-columns:repeat(4,1fr);gap:3mm}
.n{border-top:.9mm solid #E8710A;padding-top:1.6mm}.n b{display:block;font-size:17pt;line-height:1.05;color:#0B2A4A}.n span{font-size:7.8pt;color:#475467;display:block;line-height:1.3}
.fails{margin-top:3mm;border:.3mm solid #F4B6B0;background:#FEF3F2;border-radius:2.2mm;padding:2.2mm 3.2mm;font-size:8.4pt;color:#344054}.fails b{color:#B42318}
.rub{display:flex;flex-wrap:wrap;font-size:8.4pt;color:#344054;line-height:1.6}.rub span{white-space:nowrap;margin-right:1mm}.rub span:after{content:" · ";color:#E8710A;font-weight:800}.rub span:last-child:after{content:""}
.next{display:grid;grid-template-columns:repeat(3,1fr);gap:3mm}
.next div{border-left:1mm solid #12B76A;background:#F6FEF9;padding:2mm 3mm;font-size:8.4pt;color:#344054}.next b{display:block;font-size:9.4pt;color:#0B2A4A}
.ft{position:absolute;left:11mm;right:11mm;bottom:7mm;display:flex;gap:4mm;align-items:center;font-size:9pt;color:#344054;border-top:.35mm solid #0B2A4A;padding-top:3mm}
.ft svg{width:25mm;height:25mm}.ft .t{flex:1;text-align:center;line-height:1.45}
"""


def build(photos: list[str], shots: list[str], community: str) -> str:
    amazon, security, leaders = photos
    tg, explain = shots
    gh = "github.com/Mohitlikestocode/Satyapan_TeamAvalanche"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Satyapan: final report</title><style>{CSS}</style></head><body>
<div class="page">
<div class="top"><h1>Satyapan<small>सत्यापन · Verify before you pay</small></h1><div class="tm"><b>TEAM AVALANCHE</b>Sai Mohit Kotta · Tanish Shitanshu · Ghana Polisetty<br>RAKSHAM AI Cybersecurity Hackathon · IIT Delhi × Amazon · Track 3</div></div>
<div class="intro"><b>Satyapan</b> helps anyone check a suspicious payment message <b>before</b> they pay. Send it a message, link, QR code, payment screenshot, PDF or voice note on the website, Telegram or Chrome. It explains what it says in your own language, shows plain reasons, and tells you what to do next: <b>call 1930</b> or ask someone you trust. It never says “safe” and never moves money.<span class="sub">Understand it. Verify it. Act on it. In your language, on any app.</span></div>

<div class="hero">
<div class="story"><div class="q"><b>7:42 pm. Meena, 52,</b> runs a tiffin service and takes payments on PhonePe. A message says: <i>“Amazon Pay: your refund of ₹3,849 is approved. Pay a refundable charge of ₹49.”</i> The ₹49 is not the loss. The link behind it takes her PIN.</div>
<div class="bigstat"><b>₹22,845 crore</b><span>lost to cyber fraud in India in 2024 (Home Ministry, in Parliament): about ₹4 lakh every minute. About half of UPI-fraud victims never even complain.</span></div></div>
<div class="shots"><figure><img src="{tg}" alt=""><figcaption>Telegram: forward a scam, get the answer</figcaption></figure>
<figure style="background:#fff"><img src="{explain}" alt=""><figcaption>Understood first, in Telugu</figcaption></figure></div>
</div>

<div class="sec">We took it to real people. They asked, we built.</div>
<div class="grid">
<div class="card"><figure><img src="{amazon}" alt=""></figure><div class="cap"><q>“Can anyone, from anywhere, learn this?”</q><div class="who">Amazon team member</div><p>Built: Explain in my language, 11 Indian languages, read aloud with Sarvam voice.</p></div></div>
<div class="card"><figure><img src="{community}" alt=""></figure><div class="cap"><q>“Can it reach and warn people?”</q><div class="who">Lawyer and mother</div><p>Built: Scam Watch community, Lessons, Scam Drill and shareable warning cards.</p></div></div>
<div class="card"><figure><img src="{security}" alt=""></figure><div class="cap"><q>“I want a call button if this happens to me.”</q><div class="who">Security staff</div><p>Built: one-tap Call 1930 and a complaint draft on every page.</p></div></div>
<div class="card"><figure><img src="{leaders}" alt=""></figure><div class="cap"><q>“Think beyond the app.”</q><div class="who">Amazon, head of customer experience</div><p>Built: Telegram bot, Chrome extension, one API. Next: refund flows, WhatsApp, SMS.</p></div></div>
</div>
<div class="foot1"><b>Page 2:</b> what is inside, what we measured, where we fail · <b>{gh}</b></div>
</div>

<div class="page">
<div class="top"><h1>Satyapan<small>What is inside</small></h1><div class="tm"><b>TEAM AVALANCHE</b>Proof, not promises</div></div>

<div class="sec first">Features, by name</div>
<div class="feat">
<div class="f"><h3><i></i>Check now</h3><p>Message, link, QR, payment screenshot, PDF, voice note, chat screenshot. One verdict: High risk, Suspicious, Can’t tell, No red flags found.</p></div>
<div class="f"><h3><i></i>Explain in my language</h3><p>11 Indian languages through Sarvam translation, with <b>Listen</b> voice. Only on your click; nothing stored.</p></div>
<div class="f"><h3><i></i>Is this real?</h3><p>Reads what the message says first, then the verdict. Reasons come from reviewed templates, in English and Hindi.</p></div>
<div class="f"><h3><i></i>If you paid</h3><p>One-tap <b>Call 1930</b>, complaint draft, and a ready message to forward to family.</p></div>
<div class="f"><h3><i></i>Wrong result?</h3><p>You choose whether a human reviewer sees it. Ticket, status page, <b>Delete my result</b> at any time.</p></div>
<div class="f"><h3><i></i>Telegram bot and Chrome extension</h3><p><b>@Satyapanbot</b>: forward anything. Extension: right-click selected text and check it where you read it.</p></div>
<div class="f"><h3><i></i>Scam Watch, Lessons, Scam Drill</h3><p>Community reports with phone numbers cleaned, short lessons and a practice drill, so one victim protects the next.</p></div>
<div class="f"><h3><i></i>For shops and Helper</h3><p>Shopkeeper tool for fake payment screenshots and look-alike payees; Helper mode to check for a parent or customer.</p></div>
<div class="f"><h3><i></i>Attack lab and Results</h3><p><b>/attack</b> shows how we are beaten and what we fixed. <b>/results</b> shows measured numbers and failures.</p></div>
</div>

<div class="sec">Models we built and trained</div>
<div class="models">
<div class="m"><b>Scam-message classifier</b>Fine-tuned e5 encoder with our own head, trained on our own synthetic scam corpus.</div>
<div class="m"><b>Tamper U-Net</b>Our own screenshot-edit detector for payment receipts.</div>
<div class="m"><b>Voice check</b>Whisper speech-to-text plus a cloned-voice detector, calibrated by us.</div>
<div class="m"><b>Boxed-in AI check</b>An LLM limited to 33 regulator-advisory rules, quote-verified, can only add warnings.</div>
</div>

<div class="sec">Measured, not claimed</div>
<div class="nums">
<div class="n"><b>33 / 40</b><span>unseen scam messages caught; 0 of 40 genuine flagged</span></div>
<div class="n"><b>89%</b><span>of scam families never seen in training caught as a warning sign</span></div>
<div class="n"><b>1,980 / 1,980</b><span>cloned voices flagged; speakers held out; 4.1% real voices flagged</span></div>
<div class="n"><b>415 · 42</b><span>tests and end-to-end checks, all passing</span></div>
</div>
<div class="fails"><b>Where we fail:</b> edited screenshots 41% caught with 7% false alarms · look-alike letters beat rules-only 84% of the time, fixed to 0 of 50 after our hook (more false alarms, listed) · real phone screenshots <b>not evaluated</b> · our own test files are optimistic, so bring yours: the kit is public.</div>

<div class="sec">Against the evaluation</div>
<div class="rub"><span>Working prototype</span><span>Measured accuracy</span><span>Own engineering</span><span>Alert and response</span><span>Delivery vs plan</span><span>Problem and user</span><span>Deployability</span><span>Communication and Q&amp;A</span><span>Live user journey</span><span>Adversarial robustness</span><span>Responsible AI</span><span>Bonus: fine-tuned and custom models, open source</span></div>

<div class="sec">What we heard, what comes next</div>
<div class="next"><div><b>Partner API</b>Inside refund and order flows, where the scam message is born.</div><div><b>More doors</b>WhatsApp, SMS and voice calls.</div><div><b>Real phone screenshots</b>Evaluate and improve on them with volunteers.</div></div>

<div class="ft"><div>{qr_svg(BOT)}</div><div class="t"><b style="font-size:12pt;color:#0B2A4A">Team Avalanche</b><br>Try it now: Telegram <b>@Satyapanbot</b> (left code)<br>Code, results, reproduction: <a href="https://github.com/Mohitlikestocode/Satyapan_TeamAvalanche" style="color:#1F4E8C;font-weight:800">{gh}</a> (right code)</div><div>{qr_svg(REPO)}</div></div>
</div></body></html>"""


def main() -> None:
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    amazon, security, leaders = sys.argv[2:5]
    photos = [img(amazon, 90 / 53, 0.4), img(security, 90 / 53, 0.1), img(leaders, 90 / 53, 0.12)]
    shots = [img(ROOT / "docs/img/telegram-bot.png", None, width=800), img(ROOT / "docs/img/explain-telugu.png", None, width=800)]
    community = img(ROOT / "docs/img/community.png", 90 / 53, 0.1)
    html = out / "Satyapan_Final_Report.html"
    html.write_text(build(photos, shots, community), encoding="utf-8")
    pdf = out / "Satyapan_Final_Report.pdf"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}", html.as_uri()],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    print("wrote", pdf)


if __name__ == "__main__":
    main()
