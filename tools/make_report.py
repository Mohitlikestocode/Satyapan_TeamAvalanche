"""Build the one-page final report (A4 PDF) for the submission.

usage: python tools/make_report.py <out_dir> [photo1 photo2 photo3]
Photos of people are NOT stored in the repository: pass their paths on the command line (they are embedded in the PDF only).
Needs Chrome (headless print to PDF) and `segno` for the QR codes.
"""
from __future__ import annotations

import base64
import io
import subprocess
import sys
from pathlib import Path

import segno
from PIL import Image

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
REPO = "https://github.com/Mohitlikestocode/Satyapan_TeamAvalanche"
BOT = "https://t.me/Satyapanbot"


def qr_svg(url: str) -> str:
    b = io.BytesIO()
    segno.make(url, error="m").save(b, kind="svg", scale=3, border=1, dark="#0B2A4A", xmldecl=False, svgns=True, nl=False)
    return b.getvalue().decode()


def photo(path: str, ratio: float = 4 / 3, box: tuple[float, float] | None = None) -> str:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    target_h = int(w / ratio)
    if target_h <= h:
        top = int((h - target_h) * (box[1] if box else 0.5))
        im = im.crop((0, top, w, top + target_h))
    else:
        tw = int(h * ratio)
        im = im.crop(((w - tw) // 2, 0, (w - tw) // 2 + tw, h))
    im = im.resize((520, int(520 / ratio)))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=72)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


CSS = """
@page{size:A4;margin:0}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:210mm;background:#fff}
body{font-family:'Segoe UI','Noto Sans',Arial,sans-serif;font-size:7.3pt;line-height:1.25;color:#0B1F3A;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.page{width:210mm;height:296.5mm;overflow:hidden}
.hd{background:#0B2A4A;color:#fff;padding:4mm 7mm 3mm;border-bottom:1.1mm solid #E8710A;display:flex;justify-content:space-between;gap:5mm}
.hd h1{font-size:17pt;line-height:1.05}.hd h1 span{font-weight:400;opacity:.85;font-size:11.5pt;margin-left:2mm}
.hd .tag{font-size:8pt;margin-top:1mm;color:#FFD9B0;font-weight:600}
.hd .who{font-size:6.6pt;text-align:right;opacity:.93;line-height:1.35;white-space:nowrap}
.main{padding:2.2mm 7mm 0}
.row{display:flex;gap:2.4mm;margin-bottom:2mm}
.box{border:.25mm solid #D0D5DD;border-radius:1.2mm;padding:1.6mm 2.2mm;flex:1;background:#fff}
.box h2{font-size:7.6pt;text-transform:uppercase;letter-spacing:.3px;color:#1F4E8C;margin-bottom:.7mm}
.stat{background:#FFF4E5;border-color:#F0C27B}
.big{font-size:16pt;font-weight:800;color:#B42318;line-height:1.05}
.big small{display:block;font-size:7pt;color:#0B1F3A;font-weight:600;margin-top:.6mm}
.three{display:flex;gap:2mm}
.step{flex:1;border-left:1mm solid #1F4E8C;padding-left:1.8mm}
.step>b:first-child{display:block;font-size:7.6pt;color:#0B2A4A}
.chips span{display:inline-block;background:#EEF3FA;border:.2mm solid #C7D5EA;border-radius:2mm;padding:0 1.3mm;margin:.4mm .3mm 0 0;font-size:6.2pt;font-weight:600;color:#1F4E8C}
.field{display:flex;gap:2.4mm}
.cards{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:1.4mm}
.card{border:.25mm solid #D0D5DD;border-radius:1.2mm;padding:1.6mm 2mm;background:#F8FAFC}
.card q{display:block;font-style:italic;color:#475467;font-size:7.5pt;quotes:none;margin-bottom:.4mm}
.card q:before{content:"“"}.card q:after{content:"”"}
.card .who{font-weight:700;font-size:7.6pt;color:#0B2A4A;margin-bottom:.3mm}
.card .a{font-size:7.5pt;line-height:1.3}
.card.future{background:#EEF8F1;border-color:#9ED5B1}
.photos{width:25mm;display:flex;flex-direction:column;gap:1mm}
.photos img{width:100%;border-radius:.9mm;display:block}
.tiles{display:grid;grid-template-columns:repeat(6,1fr);gap:1.4mm;margin-bottom:2mm}
.tile{border:.25mm solid #D0D5DD;border-radius:1.2mm;padding:1.1mm 1.4mm;text-align:center;background:#fff}
.tile b{display:block;font-size:10.5pt;color:#0B2A4A;line-height:1.1}.tile span{font-size:6.2pt;color:#475467;line-height:1.18;display:block}
.cols{display:flex;gap:2.4mm;margin-bottom:2mm}
table{width:100%;border-collapse:collapse;font-size:6.8pt}
th{background:#0B2A4A;color:#fff;text-align:left;padding:.9mm 1.4mm;font-size:7pt}
th.s2{background:#1F4E8C}
td{border-bottom:.2mm solid #E4E7EC;padding:.7mm 1.4mm;vertical-align:top}
td.c{width:21mm;font-weight:700;color:#0B2A4A}td.c i{display:block;font-weight:600;font-style:normal;color:#B54708;font-size:5.9pt}
.bonus{background:#0B2A4A;color:#fff;border-color:#0B2A4A;padding:1.6mm 2.4mm}.bonus h2{color:#FFD9B0}
.bonus .g{display:grid;grid-template-columns:1fr 1fr;gap:.8mm 3mm;font-size:6.6pt}.bonus b{color:#FFD9B0}
.ft{display:flex;gap:3mm;align-items:center;padding:1.2mm 7mm 0;font-size:6.5pt;color:#344054}
.ft svg{width:13mm;height:13mm}.ft .t{flex:1}code{background:#F2F4F7;padding:0 .7mm;border-radius:.6mm;font-size:6pt;color:#0B1F3A}
.bonus code{background:#1F4E8C;color:#fff}
"""


def build(photos: list[str]) -> str:
    imgs = "".join(f'<img src="{p}" alt="">' for p in photos)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Satyapan: final report</title><style>{CSS}</style></head><body><div class="page">
<div class="hd"><div><h1>Satyapan<span>सत्यापन · Verify before you pay</span></h1>
<div class="tag">Understand it. Verify it. Act on it: in your own language, on whichever app the scam arrives.</div></div>
<div class="who"><b>Team Avalanche</b><br>Sai Mohit Kotta · Tanish Shitanshu · Ghana Polisetty<br>RAKSHAM AI Cybersecurity Hackathon, IIT Delhi × Amazon<br>Track 3 · Final report · 25 Oct 2026</div></div>
<div class="main">

<div class="row">
<div class="box" style="flex:1.7"><h2>The problem, and the person it hurts</h2>
7:42 pm. <b>Meena, 52, runs a tiffin service</b> from her kitchen and takes payments on PhonePe. She is expecting a refund, and a message says <i>“Amazon Pay: your refund of ₹3,849 is approved. Pay a refundable processing charge of ₹49.”</i> The ₹49 is not the loss: the link behind it takes her PIN. Victims are busy and trusting, not careless. Shopkeepers are shown fake “payment successful” screens, small businesses get “our bank account has changed” invoices, and most people read these messages in a language other than English.</div>
<div class="box stat" style="flex:1"><div class="big">₹22,845 crore<small>lost to cyber fraud in India in 2024 (Home Ministry, in Parliament): about ₹4 lakh every minute</small></div>
<div style="margin-top:.8mm"><b>About half</b> of UPI-fraud victims never file a complaint (LocalCircles survey), so the true loss is higher.</div></div>
</div>

<div class="row"><div class="box"><h2>What we built: one brain, many doors</h2>
<div class="three">
<div class="step"><b>1 · UNDERSTAND first</b>Before any verdict we show <b>what the message actually says</b>, explain it in the user’s own language (11 Indian languages, Sarvam translation) and read it aloud (Sarvam voice). A suggestion, never a certainty.</div>
<div class="step"><b>2 · VERIFY</b>Message, link, QR, screenshot, PDF and voice note, all live: rules, fine-tuned models, payee and link checks and an AI check against 33 regulator-advisory rules, fused by a plain rule set. Reasons come from reviewed templates.</div>
<div class="step"><b>3 · ACT</b><b>One-tap Call 1930</b> and a cybercrime.gov.in complaint draft, <b>Ask family</b>, a signed evidence report, <b>Wrong result?</b> to a human reviewer, and instant delete.</div></div>
<div class="chips" style="margin-top:.8mm"><span>Website</span><span>Telegram @Satyapanbot</span><span>Browser right-click extension</span><span>Shopkeeper check</span><span>Helper mode for bank staff and volunteers</span><span>“Is this really them?” company check</span><span>Shop QR poster</span><span>Scam Watch community</span><span>Scam Drill</span></div></div></div>

<div class="row field"><div class="box" style="flex:1"><h2>We took it to real people, and built what they asked for</h2>
<div class="cards">
<div class="card"><q>Can anyone, from anywhere, learn this?</q><div class="who">Amazon team member</div><div class="a">→ <b>Understand-first in 11 languages.</b> A Kannada message is translated and read aloud in Kannada by Sarvam voice, so the person understands it before deciding.</div></div>
<div class="card"><q>Can it reach people and raise awareness?</q><div class="who">Lawyer and mother</div><div class="a">→ <b>Scam Watch community</b> (reports cleaned of names and numbers, discussion), 12 lessons, Scam Drill with streaks, shareable warning cards, shop posters.</div></div>
<div class="card"><q>I want a call button if this happens to me.</q><div class="who">Security staff member</div><div class="a">→ <b>Call-to-action on every page:</b> one tap to the national cyber-crime helpline 1930, plus a ready complaint draft for cybercrime.gov.in.</div></div>
<div class="card future"><q>Think beyond the app.</q><div class="who">Amazon, head of customer experience</div><div class="a">→ Today: Telegram, the call button, post-incident awareness. <b>Next:</b> a partner API in customer-experience flows (refund and order messages), brand-impersonation reporting, WhatsApp, SMS and voice (IVR).</div></div>
</div></div><div class="photos">{imgs}</div></div>

<div class="tiles">
<div class="tile"><b>33 / 40</b><span>unseen scam messages caught, 0 / 40 genuine flagged (40 / 40 with the AI check; own files, optimistic)</span></div>
<div class="tile"><b>66% · 89%</b><span>scam families never seen in training: alone · as one weak sign (0.7% · 2.2% genuine flagged)</span></div>
<div class="tile"><b>41% · 7%</b><span>edited screenshots caught · genuine wrongly flagged (generated screens, unseen layouts)</span></div>
<div class="tile"><b>1,980 / 1,980</b><span>cloned voices flagged; 4.1% of real voices wrongly flagged (speakers held out)</span></div>
<div class="tile"><b>415 · 42</b><span>automated tests · end-to-end feature checks, all passing</span></div>
<div class="tile"><b style="font-size:9pt">Not evaluated</b><span>real phone screenshots: we use nobody’s payment data without permission. /results says so.</span></div>
</div>

<div class="cols">
<div style="flex:1"><table><thead><tr><th colspan="2">STAGE 1 · SHORTLIST</th></tr></thead><tbody>
<tr><td class="c">Working prototype<i>25</i></td><td>Live on the judge’s own input, end to end (input → detection → alert → action): six input types, Telegram and the extension. <b>42 / 42</b> end-to-end checks.</td></tr>
<tr><td class="c">Measured accuracy<i>30</i></td><td>Every number on <b>/results</b> is read from a file, with false positives and named failures; “not evaluated” where unmeasured. Own PDF, chat and QR sets: 10/10, 8/8, 4/4 caught; at most 1/10 genuine flagged.</td></tr>
<tr><td class="c">Own engineering<i>15 + bonus</i></td><td>Fine-tuned and custom models, our own datasets, fused signals, a custom pipeline (blue box below). Each of us can explain any part.</td></tr>
<tr><td class="c">Alert and response<i>15</i></td><td>Alert with reasons → <b>Call 1930</b> · Ask family · signed evidence pack · <b>Wrong result? → human reviewer</b> · real deletion. Running safeguards: files in memory only, 24 h expiry, personal numbers masked before any AI call.</td></tr>
<tr><td class="c">Delivery vs plan<i>15</i></td><td>Cut on purpose, with reasons: video deepfakes, lip-sync, Docker. Added after mentor feedback: community, traction, Telegram, extension. See <code>docs/DEVIATIONS.md</code>.</td></tr>
</tbody></table></div>
<div style="flex:1"><table><thead><tr><th class="s2" colspan="2">STAGE 2 · FINAL PRESENTATION</th></tr></thead><tbody>
<tr><td class="c">Problem and user<i>20</i></td><td>Meena (payer), the shopkeeper (payee) and the small business (invoice fraud), grounded in the ₹22,845 crore figure and how UPI scams really run.</td></tr>
<tr><td class="c">Deployability<i>15</i></td><td>One API, many doors: a link or QR inside a UPI or bank app, an API call when a payee is added, Helper mode for branch staff, signed packs for cyber cells. One 4 GB server, about 5.8 checks/s measured on a laptop; cost per 1,000 not yet computed.</td></tr>
<tr><td class="c">Communication, Q&amp;A<i>10</i></td><td>Short answers and an honest “we don’t know” list: real screenshots, cost at national scale, languages beyond Hindi, English and Hinglish.</td></tr>
<tr><td class="c">Live user journey<i>25</i></td><td>Scam arrives (web, Telegram, extension) → understood in the user’s language → verdict → their action → review or report. The jury varies every input.</td></tr>
<tr><td class="c">Adversarial robustness<i>20</i></td><td><b>/attack</b>: look-alike letters let 84% of flagged scams past our rules; a clean-up step now stops them (0/50) but raises false alarms (up to 14/73). Smart paraphrases are untested.</td></tr>
<tr><td class="c">Responsible AI<i>10</i></td><td>A wrongly flagged genuine user gets a reference number, a human decision and a status page. Alerts say why; “no red flags” never means safe.</td></tr>
</tbody></table></div>
</div>

<div class="row"><div class="box bonus"><h2>Bonus: engineering depth (fine-tuning, custom models, open source)</h2><div class="g">
<div><b>Fine-tuned</b> multilingual-e5-small scam classifier on <b>our own dataset</b>: a generator we wrote for 41 Indian scam families plus genuine message types (English, Hindi, Hinglish) with a guard that drops anything overlapping the held-out test files.</div>
<div><b>Custom U-Net</b> payment-screenshot tamper model trained by us on 20,000 generated screens and tested on unseen layouts; calibrated cloned-voice detector (Spectra-AASIST3) and faster-whisper speech to text on our own server.</div>
<div><b>Boxed-in AI check:</b> an open model (gpt-oss on Groq) may only name which of <b>33 RBI, SEBI, NPCI, TRAI and MHA advisory rules</b> a message breaks and quote the words. A match counts only if the quote is real; reasons come from our templates; it can only add warnings, so prompt injection cannot clear a scam.</div>
<div><b>Open and platform-independent:</b> RapidOCR/Tesseract, zxing, faster-whisper, Spectra-AASIST3, e5, gpt-oss. A plugin architecture let three people build in parallel with zero merge conflicts. Reproduce: <code>pip install -e .</code> · <code>python -m pytest -q</code> · <code>python scripts/final_check.py</code> · <code>python -m satyapan.eval.report</code></div></div></div></div>

</div>
<div class="ft"><div>{qr_svg(BOT)}</div><div class="t"><b>Try it:</b> Telegram <b>@Satyapanbot</b> (left code) · code, results and reproduction steps: <b>github.com/Mohitlikestocode/Satyapan_TeamAvalanche</b> (right code). Our own test files are optimistic and we invite the jury’s kit.</div><div>{qr_svg(REPO)}</div></div>
</div></body></html>"""


def main() -> None:
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    paths = sys.argv[2:5]
    imgs = [photo(p, 4 / 3) for p in paths]
    html = out / "Satyapan_Final_Report.html"
    html.write_text(build(imgs), encoding="utf-8")
    pdf = out / "Satyapan_Final_Report.pdf"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}", html.as_uri()],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    print("wrote", pdf)


if __name__ == "__main__":
    main()
