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
    im.save(b, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


CSS = """
@page{size:A4;margin:0}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:210mm;background:#fff}
body{font-family:'Segoe UI','Noto Sans',Arial,sans-serif;font-size:8.6pt;line-height:1.25;color:#0B1F3A;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.page{width:210mm;height:296.5mm;overflow:hidden;position:relative;page-break-after:always}.page:last-child{page-break-after:auto}
.hd{background:#0B2A4A;color:#fff;padding:4mm 8mm 3mm;border-bottom:1.3mm solid #E8710A;display:flex;justify-content:space-between;align-items:flex-end}
.hd h1{font-size:23pt;line-height:1;letter-spacing:.2px}.hd h1 small{font-size:12pt;font-weight:400;opacity:.85;margin-left:2.5mm}
.hd .tag{font-size:9.6pt;margin-top:1mm;white-space:nowrap;color:#FFD9B0;font-weight:700;letter-spacing:.2px}
.hd .who{font-size:7pt;text-align:right;line-height:1.4;opacity:.95;white-space:nowrap}
.hero{display:flex;gap:4mm;padding:3.4mm 8mm 0;align-items:stretch}
.story{flex:0 0 62mm;display:flex;flex-direction:column;justify-content:space-between}
.story .q{font-size:8.2pt;line-height:1.3}
.story .q i{color:#344054}
.bigstat{background:#FFF4E5;border:.3mm solid #F0C27B;border-radius:2mm;padding:2mm 2.8mm}
.bigstat b{display:block;font-size:21pt;line-height:1;color:#B42318;font-weight:800}
.bigstat span{font-size:7.6pt;font-weight:600;display:block;margin-top:.8mm}
.shots{flex:1;display:flex;gap:2.4mm;height:64mm}
.shots figure{flex:1;border-radius:2mm;overflow:hidden;border:.3mm solid #D0D5DD;position:relative;background:#0B1F3A}
.shots img{width:100%;height:100%;object-fit:cover;object-position:center top;display:block}
.shots figcaption,.cell figcaption{position:absolute;left:0;right:0;bottom:0;background:rgba(11,42,74,.88);color:#fff;font-size:7.4pt;font-weight:700;padding:1mm 2mm}
.sec{padding:2.8mm 8mm 1.4mm;font-size:9pt;font-weight:800;letter-spacing:.5px;text-transform:uppercase;color:#1F4E8C}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:2.8mm;padding:0 8mm}
.cell{border:.3mm solid #D0D5DD;border-radius:2mm;overflow:hidden;background:#fff}
.cell .ph{position:relative;height:57mm;background:#0B1F3A}
.cell .ph img{width:100%;height:100%;object-fit:cover;display:block}
.cell .ph figcaption{font-size:8.6pt;font-style:italic;font-weight:600;padding:1.4mm 2.4mm}
.cell .tx{padding:1.3mm 2.4mm 1.6mm;font-size:8.2pt;font-weight:600;color:#0B2A4A;min-height:12mm;line-height:1.22}
.cell .tx small{display:block;font-size:6.8pt;font-weight:700;color:#B54708;letter-spacing:.3px;text-transform:uppercase}
.cell.g{border-color:#9ED5B1}.cell.g .tx{background:#EEF8F1}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:2.6mm;padding:2.6mm 8mm 0}
.tile{background:#0B2A4A;color:#fff;border-radius:2mm;padding:1.5mm 2.4mm;text-align:center}
.tile b{display:block;font-size:17pt;line-height:1.05;color:#FFD9B0}.tile span{font-size:7.2pt;line-height:1.25;opacity:.95;display:block}
.honest{padding:1.6mm 8mm 0;font-size:7.6pt;color:#475467;text-align:center}.honest b{color:#B42318}
.chips{display:grid;grid-template-columns:repeat(3,1fr);gap:2.4mm;padding:0 8mm}.fail{display:grid;grid-template-columns:repeat(3,1fr);gap:2.4mm;padding:0 8mm;font-size:9pt;line-height:1.3}.fail div{border:.3mm solid #F4B6B0;background:#FEF3F2;border-radius:2mm;padding:2.4mm 3mm}.fail b{color:#B42318}
.chip{border:.25mm solid #C7D5EA;background:#F2F6FC;border-radius:2mm;padding:2.6mm 3mm}
.chip b{display:block;font-size:10pt;margin-bottom:.6mm;color:#0B2A4A}.chip b i{font-style:normal;color:#B54708;margin-left:1mm}
.chip span{font-size:8.4pt;color:#344054;line-height:1.2}
.chip.s2{background:#EEF8F1;border-color:#BFE3CC}
.bonus{margin:4mm 8mm 0;background:#E8710A;color:#fff;border-radius:2mm;padding:1.8mm 3mm;font-size:8.2pt;font-weight:700;display:flex;gap:2mm;justify-content:space-between;align-items:center;flex-wrap:wrap}
.bonus em{font-style:normal;font-size:7.6pt;background:rgba(255,255,255,.18);padding:.5mm 2mm;border-radius:2mm;white-space:nowrap}
.flow{display:flex;gap:2mm;padding:0 8mm;align-items:stretch;font-size:8.6pt;line-height:1.3}.flow>div:not(.ar){flex:1;border:.3mm solid #C7D5EA;background:#F2F6FC;border-radius:2mm;padding:2.4mm 3mm}.flow small{display:block;font-size:7.4pt;font-weight:800;color:#B54708;text-transform:uppercase;letter-spacing:.4px;margin-bottom:.8mm}.flow .ar{align-self:center;font-size:16pt;color:#E8710A;font-weight:800}.doors{display:flex;gap:2mm;padding:2.4mm 8mm 0;flex-wrap:wrap}.doors em{font-style:normal;font-size:8.6pt;font-weight:700;background:#0B2A4A;color:#fff;border-radius:2mm;padding:1.2mm 3mm}.next{display:grid;grid-template-columns:repeat(3,1fr);gap:2.4mm;padding:0 8mm;font-size:8.6pt;line-height:1.3}.next div{border:.3mm solid #9ED5B1;background:#EEF8F1;border-radius:2mm;padding:2.4mm 3mm}.next b{display:block;font-size:10pt;color:#0B2A4A;margin-bottom:.6mm}.ft{position:absolute;left:0;right:0;bottom:0;display:flex;gap:4mm;align-items:center;padding:0 8mm 6mm;font-size:9.4pt;color:#344054}
.ft svg{width:30mm;height:30mm}.ft .t{flex:1;text-align:center;line-height:1.35}
"""


def build(photos: list[str], shots: list[str], community: str) -> str:
    amazon, security, leaders = photos
    tg, explain = shots
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Satyapan: final report</title><style>{CSS}</style></head><body><div class="page">
<div class="hd"><div><h1>Satyapan<small>सत्यापन · Verify before you pay</small></h1>
<div class="tag">Understand it. Verify it. Act on it. In your language, on any app.</div></div>
<div class="who"><b style="font-size:13pt;color:#FFD9B0;letter-spacing:.4px">TEAM AVALANCHE</b><br>Sai Mohit Kotta · Tanish Shitanshu · Ghana Polisetty<br>RAKSHAM AI Cybersecurity Hackathon<br>IIT Delhi × Amazon · Track 3 · Final report</div></div>

<div class="hero">
<div class="story">
<div class="q"><b>7:42 pm. Meena, 52,</b> runs a tiffin service and takes payments on PhonePe. A message says: <i>“Amazon Pay: your refund of ₹3,849 is approved. Pay a refundable charge of ₹49.”</i> The ₹49 is not the loss. The link behind it takes her PIN.</div>
<div class="bigstat"><b>₹22,845 crore</b><span>lost to cyber fraud in India in 2024 (Home Ministry, in Parliament): about ₹4 lakh every minute. About half of UPI-fraud victims never even complain.</span></div>
</div>
<div class="shots"><figure><img src="{tg}" alt=""><figcaption>Telegram: forward a scam, get the answer</figcaption></figure>
<figure><img src="{explain}" alt=""><figcaption>Understood first, in Telugu</figcaption></figure></div>
</div>

<div class="sec">We took it to real people. They asked, we built.</div>
<div class="grid">
<div class="cell"><div class="ph"><img src="{amazon}" alt=""><figcaption>“Can anyone, from anywhere, learn this?”</figcaption></div><div class="tx"><small>Amazon team member</small>11 Indian languages: a Kannada message, translated and read aloud by Sarvam voice.</div></div>
<div class="cell"><div class="ph"><img src="{community}" alt=""><figcaption>“Can it reach and warn people?”</figcaption></div><div class="tx"><small>Lawyer and mother</small>Scam Watch community, lessons, Scam Drill and shareable warning cards.</div></div>
<div class="cell"><div class="ph"><img src="{security}" alt=""><figcaption>“I want a call button if this happens to me.”</figcaption></div><div class="tx"><small>Security staff</small>One-tap Call 1930 and a complaint draft, on every page.</div></div>
<div class="cell g"><div class="ph"><img src="{leaders}" alt=""><figcaption>“Think beyond the app.”</figcaption></div><div class="tx"><small>Amazon, head of customer experience</small>Next: a partner API in refund and order flows, WhatsApp, SMS and voice.</div></div>
</div>

<div class="tiles">
<div class="tile"><b>33 / 40</b><span>unseen scam messages caught<br>0 / 40 genuine flagged</span></div>
<div class="tile"><b>89%</b><span>of scam families never seen in training caught as a warning sign</span></div>
<div class="tile"><b>1,980 / 1,980</b><span>cloned voices flagged<br>speakers held out</span></div>
<div class="tile"><b>415 · 42</b><span>tests and end-to-end checks, all passing</span></div>
</div>
<div class="honest" style="padding-top:3mm"><b>Try it now:</b> Telegram <b>@Satyapanbot</b> · Code: <b>github.com/Mohitlikestocode/Satyapan_TeamAvalanche</b> · details on page 2</div>
</div>

<div class="page">
<div class="hd"><div><h1>Satyapan<small>सत्यापन</small></h1><div class="tag">Team Avalanche · Proof, not promises</div></div><div class="who">Sai Mohit Kotta · Tanish Shitanshu · Ghana Polisetty<br>RAKSHAM · IIT Delhi × Amazon · Track 3</div></div>
<div class="sec" style="padding-top:5mm">Our failures, said out loud</div>
<div class="fail"><div><b>41%</b> of edited screenshots caught, <b>7%</b> false alarms</div><div><b>Not evaluated:</b> real phone screenshots</div><div><b>Optimistic:</b> our own test files. Bring yours: we publish the kit.</div></div>
<div class="sec">Against your rubric</div>
<div class="chips">
<div class="chip"><b>Working prototype<i>25</i></b><span>Judges pick the input: message, link, QR, PDF, voice, screenshot</span></div>
<div class="chip"><b>Measured accuracy<i>30</i></b><span>Held-out sets, false alarms and failures reported with the numbers</span></div>
<div class="chip"><b>Own engineering<i>15</i></b><span>Fine-tuned message classifier, own U-Net tamper model, own scam dataset</span></div>
<div class="chip"><b>Alert and response<i>15</i></b><span>One-tap Call 1930, human review of wrong results, delete on demand</span></div>
<div class="chip"><b>Delivery vs plan<i>15</i></b><span>Plan vs delivered written down; what we cut and why</span></div>
<div class="chip s2"><b>Problem and user<i>20</i></b><span>Meena, shopkeepers and helpers, tested with real people</span></div>
<div class="chip s2"><b>Deployability<i>15</i></b><span>One API behind web, Telegram, Chrome extension; pilot plan ready</span></div>
<div class="chip s2"><b>Communication, Q&amp;A<i>10</i></b><span>A written list of what we do not know yet</span></div>
<div class="chip s2"><b>Live user journey<i>25</i></b><span>Scam arrives, alert, Call 1930 or complaint draft, human review</span></div>
<div class="chip s2"><b>Adversarial robustness<i>20</i></b><span>/attack shows how we are beaten and what we fixed</span></div>
<div class="chip s2"><b>Responsible AI<i>10</i></b><span>Reasons shown, never “safe”, no raw data kept, consent first</span></div>
<div class="chip" style="background:#FFF4E5;border-color:#F0C27B"><b>Reproducible<i>test kit</i></b><span>415 tests, 42 end-to-end checks, eval scripts in the repo</span></div>
</div>

<div class="bonus"><span>BONUS</span><em>Fine-tuned classifier, own dataset</em><em>Custom U-Net tamper model</em><em>Boxed-in LLM: 33 regulator rules</em><em>Open-source stack</em></div>

<div class="sec" style="padding-top:5mm">One engine, many doors</div>
<div class="flow"><div><small>You send</small>Message · link · QR · payment screenshot · PDF · voice note · chat screenshot</div><div class="ar">→</div><div><small>Satyapan checks</small>Rules from regulator advisories · fine-tuned classifier · tamper model · payee check · voice model · boxed-in AI rule check</div><div class="ar">→</div><div><small>You get</small>Plain reasons in your language, never “safe”, one-tap Call 1930, complaint draft, human review</div></div>
<div class="doors"><em>Website</em><em>Telegram bot</em><em>Chrome extension</em><em>Shopkeeper tool</em><em>Helper tool</em><em>API</em></div>
<div class="sec">What we heard, what comes next</div>
<div class="next"><div><b>Partner API</b>Inside refund and order flows, where the scam message is born (Amazon, customer experience).</div><div><b>More doors</b>WhatsApp, SMS and voice, because people live in different apps.</div><div><b>Awareness after the incident</b>Scam Watch, lessons and Scam Drill, so one victim protects the next.</div></div>
<div class="ft"><div>{qr_svg(BOT)}</div><div class="t"><b style="font-size:12pt;color:#0B2A4A">Team Avalanche</b><br>Try it now: Telegram <b>@Satyapanbot</b> (left code)<br>Code, results, reproduction: <a href="https://github.com/Mohitlikestocode/Satyapan_TeamAvalanche" style="color:#1F4E8C;font-weight:800">github.com/Mohitlikestocode/Satyapan_TeamAvalanche</a> (right code)</div><div>{qr_svg(REPO)}</div></div>
</div></body></html>"""


def main() -> None:
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    amazon, security, leaders = sys.argv[2:5]
    photos = [img(amazon, 95 / 57, 0.4), img(security, 95 / 57, 0.1), img(leaders, 95 / 57, 0.12)]
    shots = [img(ROOT / "docs/img/telegram-bot.png", 1.0, 0.5, width=700), img(ROOT / "docs/img/explain-telugu.png", 1.0, 0.0, width=700)]
    community = img(ROOT / "docs/img/community.png", 95 / 57, 0.1)
    html = out / "Satyapan_Final_Report.html"
    html.write_text(build(photos, shots, community), encoding="utf-8")
    pdf = out / "Satyapan_Final_Report.pdf"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}", html.as_uri()],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    print("wrote", pdf)


if __name__ == "__main__":
    main()
