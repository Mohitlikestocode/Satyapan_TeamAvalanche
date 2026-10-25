# Satyapan (सत्यापन): verify before you pay

**Team Avalanche** · RAKSHAM AI Cybersecurity Hackathon (IIT Delhi × Amazon) · Track 3: Deepfake Detection for Financial Communications
Sai Mohit Kotta (integrator, product, traction) · Tanish Shitanshu (community and learning) · Ghana Polisetty (models and measurement)

> Forward a suspicious **message, link, QR code, payment screenshot, PDF or voice note**. In seconds Satyapan answers in plain
> English or Hindi: what it found, **why**, and what to do next, with a one-tap way to ask a family member, report to 1930 /
> cybercrime.gov.in, or tell us we got it wrong. It is advisory only: it never blocks, pays or files anything for you, and it
> never says "safe".

![Home page](docs/img/home.png)

Verdict tiers: **HIGH RISK**, **SUSPICIOUS**, **CAN'T TELL**, **NO RED FLAGS FOUND** (never "safe"), **REGISTRY HIT**.

---

## 1. Try it in two minutes

```bash
pip install -e .
python -m uvicorn satyapan.api.app:create_app --factory --port 8000     # http://127.0.0.1:8000
```

Then open the site and:

1. **Check now** → paste *"This is Inspector Verma, Mumbai Cyber Cell. Do not disconnect this video call. Transfer Rs 90,000 to the RBI verification account."* → SUSPICIOUS, with the reason "It claims to be police, CBI, TRAI or a court and threatens arrest…".
2. Upload any QR image (`python tools/make_qr_kit.py kit/qr` makes real, scannable ones with phone-style damage).
3. Upload a payment screenshot (`python tools/make_payment_screens.py out --n 20` makes synthetic ones) or a voice note.
4. Press **हिन्दी** (top right), or open any page with `?lang=hi`: the shell, check page, reasons and spoken verdict switch to Hindi.
5. **Understand first.** On every result, above our verdict, a panel shows what we read from your message, screenshot, PDF or voice note. Pick any of 11 Indian languages and press **Explain**: Sarvam translates it (via English for accuracy), then shows our verdict in the same language, each with a **Listen** button. It says plainly that this is a suggestion and the message may or may not be a scam.
6. Press **Listen** (Sarvam voice), **Ask family** (WhatsApp share), **Wrong result?** (goes to a real review queue) or **Report** (signed evidence pack).

**Browser extension** (`extension/`, Chrome/Edge/Brave, no store needed): select text or right-click a link, choose "Check with Satyapan", and the site opens with it filled in and checked. No host permissions; the text travels in the URL fragment, which is never sent to a server. `demo/` has ready-made inputs (scam messages, QR codes, payment screens, voice notes) with the results we measured, including the ones we miss; `docs/DEMO_RUNBOOK.md` is the demo-day script. The models (screenshot tamper detector, voice detectors, scam-message classifier) are optional downloads that go in `var/models/`: see [section 7](#7-install-and-run). Without them the site still runs and says which checks it could not do.

---

## 2. The rubric, row by row: what we built and where to see it

The jury scores each row 1 to 5, weighted. For every row: what it asks, what we built, and the evidence you can open.

### Stage 1: shortlist

| Row (weight) | What a 5 needs | What we built | Evidence |
|---|---|---|---|
| **1. Working prototype (25)** | Runs end to end, live, on inputs the judge picks | All six input kinds run for real through one engine: message, link, QR image, screenshot, PDF, voice note. Input → detection → alert → action. The site, a Telegram bot and a Sarvam voice all call the same engine in process. Models are warmed up at start so the first judge's check is not slow. | `/check`, [`src/satyapan/service.py`](src/satyapan/service.py), 57 pages crawled in both languages with zero errors, `tests/` (361 tests) |
| **2. Spot-check results and measured accuracy (30)** | Most kit samples right; error rates **including false positives on data never trained on**; names its failure cases | Every number on `/results` is read from a file in [`docs/results/`](docs/results) or computed live by a button. Each has a baseline, a 95% interval, a false-alarm rate, and a named failure list. Data the rules or models saw is labelled **optimistic**. See [section 4](#4-measured-results-including-where-we-fail). | `/results`, `docs/results/*.json`, `python -m satyapan.eval.report` |
| **3. Own engineering (15)** | Fine-tuning, fused signals, custom pipeline; any member can explain it | **Fine-tuned:** a screenshot tamper U-Net trained on our own synthetic payment-screen generator with held-out layouts, and a scam-message classifier (multilingual-e5-small, full fine-tune, held-out scam families). **Fused signals:** a deterministic fusion step where HIGH RISK needs two independent strong layers or a registry hit; forensics alone caps at SUSPICIOUS. **Custom pipeline:** bilingual (EN/HI/Hinglish) rule lexicon, UPI/IFSC/payee checks, QR decoding with phone-damage repair, look-alike-letter undoing, ffmpeg-sandboxed voice path, plugin registry for conflict-free parallel work. | [`src/satyapan/fusion/rules.py`](src/satyapan/fusion/rules.py), [`layers/l4_rules/`](src/satyapan/layers/l4_rules), [`training/`](training), model cards in [`docs/models.md`](docs/models.md) |
| **4. Alert and response flow, as built (15)** | A person sees a clear alert and can act; safeguards are running | Every verdict ends in an action: **Ask family** (shareable summary link that expires), **Report** (Ed25519-signed evidence pack, complaint draft for 1930 / cybercrime.gov.in), **Wrong result?** (live reviewer queue, four-eyes rule on the known-fake registry, hash-chained audit log). **Safeguards running:** uploaded files are processed in memory and never written; cases are purged after 24 h (7 days only if shared for review); "Delete this check" really deletes; chat ids are stored only as salted hashes. | `/console`, [`src/satyapan/evidence/`](src/satyapan/evidence), [`src/satyapan/store/db.py`](src/satyapan/store/db.py), `docs/disclosure/*.md` |
| **5. Delivery against the Round 1 plan (15)** | Built what was promised or cut scope on purpose and can say why | [`docs/DEVIATIONS.md`](docs/DEVIATIONS.md) lists every change from the Round 1 plan with the reason and status: datasets we could not get, the lip-sync check we cut, what we added after mentor feedback. | `docs/DEVIATIONS.md`, `docs/PLAN.md` |

### Stage 2: final presentation

| Row (weight) | What we built | Evidence |
|---|---|---|
| **1. Problem and user understanding (20)** | Named users and the actual UPI fraud patterns in India: digital arrest, KYC-block links, "refund" collect-request traps, advance-fee loans and lotteries, task-for-pay jobs, fake army buyers on OLX, family-emergency money asks, changed-bank-account invoices, cloned voices. The rule catalogue and every reason text come from these patterns. | `data/kit/*.jsonl`, [`src/satyapan/layers/l4_rules/india.py`](src/satyapan/layers/l4_rules/india.py), `/learn` |
| **2. Deployability and scale (15)** | Runs from a plain `uvicorn` command on any machine with Python (Docker and Caddy files exist but were never built, see `docs/ops.md`), hardening middleware (CSP, size caps, rate limits), health check, backup, deploy check, measured load test, pilot sign-up form for shops, printable poster with QR, and a runbook saying who runs it and what a pilot needs. | [`docs/ops.md`](docs/ops.md), `scripts/loadtest.py`, `scripts/deploy_check.py`, `/pilot`, `/poster` |
| **3. Communication and Q&A (10)** | "What we miss" and "what we don't know" are written down: [`docs/JUDGE_QA.md`](docs/JUDGE_QA.md). | `docs/JUDGE_QA.md` |
| **4. Live user journey (25)** | The whole path on one flow: the scam reaches the user (any of six input kinds, or the Telegram bot) → **what it actually says, explained in the user's own language (11 Indian languages, Sarvam) before any verdict** → plain alert with reasons → the user acts (listen, ask family, report, or dispute) → a human reviewer decides → the registry updates. The judge can vary the input at every step. | `/check`, `/console`, `src/satyapan/bots/telegram_bot.py` |
| **5. Adversarial robustness (20)** | `/attack` applies real perturbations (spacing, look-alike letters, split UPI IDs, JPEG, shrinking, phone-line audio) and shows the measured drift. We found that look-alike letters let most flagged scams through the rules, so we added a text hook that undoes them, and report the new false-alarm cost too. | `/attack`, `docs/results/attack_text.json`, [`docs/JUDGE_QA.md`](docs/JUDGE_QA.md) |
| **6. Responsible AI and handling mistakes (10)** | Every alert says *why it fired*, from pre-written reviewed templates (nothing generated from the uploaded media). A genuine user flagged by mistake presses **Wrong result?**, gets a reference number and a status page; reviewers need a second person to add anything to the registry. Hindi text is flagged "machine-drafted" until a fluent reviewer signs it off. | `/wrong`, `/console`, `docs/disclosure/` |

### Mentor additions (live traction, awareness)

| Ask | What we built | Evidence |
|---|---|---|
| **Live traction** | Public-site-ready deployment, Telegram bot, shop poster generator with referral counting, pilot sign-ups, and an `/impact` page whose numbers come only from the server's own database with team traffic excluded (`sp_internal` cookie). | `/impact`, `docs/ops.md` |
| **Awareness and education** | **Scam Watch** (community reports with why-it-was-flagged), lessons in English and Hindi, **Scam Drill** with streaks, badges and a leaderboard, family safe-word card, shareable warning cards. | `/community`, `/learn`, `docs/community.md` |

---

## 3. What it looks like

| | |
|---|---|
| ![Check page](docs/img/check.png) **Check anything**: six input kinds, English or Hindi | ![Message result](docs/img/result-message.png) **A message result**: tier, plain reason, Listen, Ask family, Already-paid help |
| ![Voice result](docs/img/result-voice.png) **A voice note**: transcribed locally (faster-whisper), then the same checks as a message plus a cloned-voice signal | ![QR result](docs/img/result-qr.png) **A QR code**: decoded, the payee or link inside is checked, not just the picture |
| ![Results](docs/img/results.png) **/results**: every accuracy number is read from a file, and "not evaluated" is shown where we did not measure | ![Attack](docs/img/attack.png) **/attack**: how an attacker would evade us, measured |
| ![Community](docs/img/community.png) **Scam Watch** on a fresh start: empty until real people report; every report is checked by the rules and cleaned of phone numbers and names before anyone sees it | ![Learn](docs/img/learn.png) **Learn and Scam Drill**: lessons, streaks and badges |
| ![Impact](docs/img/impact.png) **/impact** on a fresh start: it starts at zero and counts only real visitors; team traffic is excluded | ![Poster](docs/img/poster.png) **Shop poster** with a QR that opens Satyapan, and referral counting |
| ![Hindi check page](docs/img/check-hindi.png) **Hindi**: the shell, the check page, reasons and the spoken verdict switch language; any page opens in Hindi with `?lang=hi` | ![Screenshot model](docs/img/screenshot-model.png) **Screenshot check**: the suspected edit is circled, with the honest caveat |

### New: understand first, in your own language

Before any verdict, the result page shows **what the message actually says**, then explains it in the visitor's language (11 Indian languages, via Sarvam). Our verdict follows in the same language, with a Listen button for each part. The same flow is in the Telegram bot and works from the browser extension.

![Tamil explanation](docs/img/explain-tamil.png)
![Telugu explanation](docs/img/explain-telugu.png)

### New: real tools, not examples

| | |
|---|---|
| ![Company check](docs/img/company-check.png) **Is this really them?** Say which company a message claims to be (Amazon, a bank, a courier, a government service); links and phone numbers are compared with that company's real official addresses. | ![Helper mode](docs/img/helper-mode.png) **Helper mode**: one item per person, the answer in their language, then wipe before the next person. |

Also real: **Shopkeeper check** (the customer's screenshot is read and its payee is compared with your own UPI ID and amount), **Telegram bot** `@Satyapanbot` (forward anything; "Explain in my language" button), and the **browser extension** in `extension/`.

---

## 4. Measured results, including where we fail

Everything below is copied from [`docs/results/`](docs/results) and reproduced by a command. Intervals are 95%. We say *optimistic* when a number was measured on data someone looked at while writing rules or training.

### Messages (rules + scam-message model)

| Test set | Scams flagged | Genuine flagged | Status |
|---|---|---|---|
| **`holdout_community.jsonl`** (Tanish: 40 scam + 40 genuine, English/Hindi/Hinglish, written without reading the rules) | **33 / 40** (82%) | **0 / 40** | **optimistic**: we looked at this file's failure categories while widening the rules and the synthetic training data, and one threshold was picked by a sweep that included it. A fresh blind set is the honest test. The rules alone get 19/40 |
| Before the India-specific rules and the retrained model | 7 / 40 | 0 / 40 | kept in `docs/results/text_holdout_before_india_rules.json` |
| After the India rules, with the original classifier | 26 / 40 | 0 / 40 | |
| Plus the optional **AI rule check** (open model gpt-oss on Groq, 33 regulator-advisory rules; needs a free key) | **40 / 40** | 0 / 40 | **optimistic**: Ghana wrote the rules after reading this file's misses, and measured it against the older classifier (`docs/results/ai_rules_eval.json`). Adds one false alarm on the dev kit (3/33) |
| `holdout_traction.jsonl` (drafted by the same assistant that wrote the rules) | 36 / 40 | 0 / 40 | **optimistic**: not independent |
| Development kit (`messages.jsonl`) | 38 / 38 | 2 / 33 | **optimistic**: the rules were written against it |

Reproduce: `python -m satyapan.eval.report` (needs `var/models/scam_text/`).
**Where we fail:** scams that look like ordinary messages (a payment screenshot sent as text, a FASTag top-up link, a bare "your bill is due" call) are still missed, and the classifier was trained on mostly synthetic Indian scam wording, so real-world performance is lower than this file suggests. The classifier is only *shipped* because on the held-out file it flagged more scams with no extra false alarms (pre-registered rule in [`docs/models.md`](docs/models.md)); it adds 2 false alarms on the development kit.

### PDFs, chat screenshots and QR cards (AI rule check on)

The AI rule check also reads the text of **PDFs, chat-message screenshots and QR cards** (the words printed around a QR and its payment note). It is switched off for payment *receipts* (a screenshot that says "payment successful" with a transaction id), because their ordinary wording made false alarms.

| Input (invented, own-written, small) | Scams flagged without AI -> with AI | Genuine flagged without -> with |
|---|---|---|
| PDFs (10 scam, 10 genuine) | 9 / 10 -> **10 / 10** | 1 / 10 -> 1 / 10 |
| Chat-message screenshots (8 + 8) | 6 / 8 -> **8 / 8** | 0 / 8 -> 0 / 8 |
| QR cards (4 + 4) | 2 / 4 -> **4 / 4** | 0 / 4 -> 0 / 4 |

These sets are small and written by the integrator's assistant, so they show that the feature works on these inputs and what it costs in false alarms, not accuracy on the judges' files (`docs/results/ai_media_eval.json`, `python training/text/eval_ai_media.py`). Ready-to-upload examples are in `demo/pdf/` and `demo/qr_cards/`.

### Payment screenshots

| What | Result |
|---|---|
| Tamper model, **unseen layouts** (synthetic screens; small U-Net chosen on the test split, ResNet-18 also reported) | AUROC **0.735**; catches **975 / 2,511** edits, wrongly flags **124 / 2,455** genuine (about 5%); ELA baseline AUROC 0.512 |
| Whole screenshot check as deployed (OCR + payee rules + tamper model) | flags **61 / 150** edited (95% CI 33–49%) and **11 / 150** genuine (7%, CI 4–13%). A payment receipt is treated as a receipt, not a request to pay, so its recipient alone does not flag it; the edit sign itself catches 54 / 150 with 6 / 150 false alarms |

**Where we fail:** the tamper model is weak on perfect edits and clean copies; the screenshot results are on **synthetic** screens from layouts never seen in training. **We did not collect real people's payment screenshots**, because we do not use personal financial data without permission, so real-screenshot performance is shown as **"not evaluated"** on `/results`. The image check supports the verdict and, by design, can never decide it alone (forensics caps at SUSPICIOUS).

### Voice notes

| What | Result |
|---|---|
| Cloned-voice detector (Spectra-AASIST3, threshold from the dev split at 5% false alarms), test split by **speaker** | **1,980 / 1,980** synthetic fakes flagged, **78 / 1,884** real voices wrongly flagged (4.1%); AUROC 0.979 |

**Where we fail:** phone-line audio (8 kHz telephone, low-bitrate chat codecs) degrades the detector; the second opinion model was excluded because it failed calibration (dev EER 67%). Transcription runs locally; audio is never stored.

### Robustness and load

* **`/attack`** applies perturbations to flagged scams. With the rules alone, look-alike letters let **37 of 44** flagged scams escape (84%) and spacing 11 of 44. After we added a hook that undoes the tricks, **0 of 50** escape these attacks, but that hook raises false alarms on *perturbed genuine* messages (up to **14 / 73**, about 19%, when every attack is applied together). The hook was written after seeing the gap on the development kit, so the as-deployed escape numbers are optimistic ([`docs/results/attack_text.json`](docs/results/attack_text.json)).
* **Load test** (`scripts/loadtest.py`, 8 simultaneous users, mixed messages, links, QR images and PDFs, on a laptop that also ran the load generator): **5.8 checks/second, p95 2.7 s, 0 errors**. Measured before the heavy models were installed; voice notes take about 6 s warm on CPU.

---

## 5. How it works

```
 input ─► intake ─► layers ─► fusion ─► verdict (tier + reasons from templates) ─► action
          (kind)    L1 provenance / L2 forensics (image tamper, cloned voice)
                    L3 payee: UPI id, IFSC, QR, links, look-alike domains, known-fake registry
                    L4 words: EN/HI/Hinglish rules + scam-message model + look-alike-letter undoing
```

* **Fusion** ([`fusion/rules.py`](src/satyapan/fusion/rules.py)): deterministic and auditable. HIGH RISK needs two independent strong layers or a registry hit; forensics alone caps at SUSPICIOUS; one weak sign only flags with a money ask; unreadable input is CAN'T TELL; nothing found says "NO RED FLAGS FOUND, this is not a guarantee".
* **Reasons** ([`reasons/catalogue.yaml`](src/satyapan/reasons/catalogue.yaml)): every sentence shown to a user comes from a reviewed English and Hindi template. Nothing is generated from the uploaded file, so an attacker cannot inject text into a verdict.
* **Plugins** ([`plugins/`](src/satyapan/plugins/__init__.py)): three people built three feature sets in parallel without touching each other's files by adding pages, checks, handlers and middleware through a registry. This is how the integration stayed conflict-free (see `docs/WORK_SPLIT.md`).
* **Evidence and review**: Ed25519-signed evidence pack; reviewer console with a four-eyes rule; hash-chained audit log.

---

## 6. Privacy and safety, running (not just described)

* Uploaded images, PDFs and audio are handled **in memory** and never written to disk; transcripts are not stored.
* Cases are purged after **24 h** (7 days only if the user shares for review); **Delete this check** deletes immediately.
* Visitors get one random cookie to count visits; no accounts, no names. Chat ids (Telegram) are stored only as salted hashes.
* Limits: request size caps, optional rate limiting (`RATE_LIMIT=1`), strict Content-Security-Policy.
* **AI rule check (optional, off without a key)**: when a Groq or Grok key is set, the words of a *message* are also checked against 33 rules taken from RBI, SEBI, NPCI, TRAI and MHA advisories by an open model (gpt-oss). Phone numbers, e-mails, account and card numbers and codes are masked first, UPI IDs keep only their bank handle, nothing is stored, the model can only add warnings (never clear a message), and a match counts only if its quote really appears in the message. The check page says so whenever it is on. Payment receipts never go to it; PDFs, chat screenshots and QR cards do (masked the same way).
* **Sarvam**: spoken verdicts send only our pre-written sentences. The user's own text goes to Sarvam **only when they press Explain** (translation) or Listen on that translation; it is never stored or cached by us, and the extracted text is kept only in the user's own browser tab.
* Moderator sign-in is a demo sign-in, **not real authentication** (say so to a judge).
* Details: [`docs/disclosure/`](docs/disclosure) (data sources, licences, what each model was trained on).

---

## 7. Install and run

Python 3.12 (**Python 3.13 breaks RapidOCR**; with 3.13 install Tesseract instead).

```bash
pip install -e .
cp .env.example .env         # optional settings; .env is git-ignored and is read at start
python -m uvicorn satyapan.api.app:create_app --factory --host 0.0.0.0 --port 8000
```

**Models** (not in git, about 2 GB): put them in `var/models/`:

```
var/models/tamper.pt                   screenshot tamper model
var/models/faster-whisper-small/       speech to text
var/models/spectra-aasist3/            cloned-voice detector
var/models/voice_calibration.json      thresholds
var/models/scam_text/                  scam-message classifier
pip install -r requirements/models.txt
```

**Optional services** (all via `.env`): `SARVAM_API_KEY` (spoken verdicts), `TELEGRAM_BOT_TOKEN` + `PUBLIC_URL` (run `python -m satyapan.bots.telegram_bot`), `INTERNAL_KEY` (marks team traffic), `RATE_LIMIT=1`.
Behind a proxy, add `--proxy-headers --forwarded-allow-ips="*"` so printed links use the right address.
OCR for screenshots: Tesseract with English and Hindi data, or RapidOCR.

**Tests** (361 tests, about two minutes): `python -m pytest -q`

**Reproduce the numbers**

```bash
python -m satyapan.eval.report                      # message tables -> docs/results/text_*.json
python scripts/eval_holdout.py data/kit/holdout_community.jsonl
python tools/make_payment_screens.py out --n 200    # synthetic payment screens (held-out layouts)
```

---

## 8. Repository map

| Path | What is in it |
|---|---|
| `src/satyapan/` | the app: `api/` (FastAPI + pages), `service.py` (runs a check), `layers/`, `fusion/`, `reasons/`, `extract/`, `evidence/`, `store/`, `plugins/`, `bots/`, `integrations/`, `eval/`, `ops/` |
| `web/` | Jinja templates, CSS, JS, fonts; `pages.json` is the page list |
| `training/`, `tools/` | model training and evaluation scripts; synthetic data generators |
| `data/kit/` | development kit and the two held-out message files |
| `docs/` | `PLAN.md`, `DEVIATIONS.md`, `models.md`, `ops.md`, `community.md`, `JUDGE_QA.md`, `results/`, `disclosure/`, `img/` |
| `tests/` | 361 tests |
| `scripts/`, `deploy/` | load test, deploy check, backup; optional Docker and Caddy files (never built here) |

## 9. Honest limits

* Real-screenshot performance is **not evaluated**; screenshot numbers are on synthetic screens.
* The message numbers come from an 80-message file we then used to improve the system; a fresh blind set has not been run yet, and intervals are wide.
* Hindi text is machine-drafted and needs a fluent reviewer's sign-off.
* No official list of valid UPI handles exists, so we never confirm a payee as registered.
* WhatsApp needs paid business approval, so the live chat channel is Telegram.
* Demo reviewer sign-in is not real authentication.
