# Pitch pack: Satyapan, "verify before you pay"

For the 30 → 10 session (about 12 minutes per team, no slides needed, the judges use the product and ask questions) and the final (6 minutes + 3 minutes of questions, demo inside). Everything here is something the product really does today. If you cannot show it live, do not say it.

**Rule for the whole pitch: the customer first, the technology second.** The jury told us so. Open with a person, not a model.

---

## 0. The idea in one breath (say this three times in different words)

> **A person who is about to pay someone they cannot verify gets, in seconds, the answer to two questions: "what does this actually say?" in their own language, and "is it likely a scam, and why?". Then one tap to act: ask family, report, or get a human to look. It works wherever the scam reaches them: a website, Telegram, a browser right-click, a shopkeeper's counter.**

Three words to repeat: **understand, verify, act.**

---

## 1. The opening: make the judges the victim (60 to 90 seconds)

Do not start with "Hello, we are Team Avalanche". Hand over a phone (or a printed card) and say:

> "It is 7:42 in the evening. Meena is 52. She runs a tiffin service from her kitchen in Jaipur and takes payments on PhonePe. Last week she returned a pressure cooker, so she is expecting a refund. This message arrives. **You have ten seconds. Do you pay the ₹49?**"

The card, exactly as it appears in our Telegram demo:

> *Amazon Pay: Your refund of ₹3,849 has been approved but could not be credited due to a settlement issue. Pay a refundable processing charge of ₹49 to complete the transfer.*

Let them answer. Most will hesitate. Then:

> "It looks small and it looks like a refund. The ₹49 is not the loss. The link behind it collects her PIN, and that is how ₹49 becomes ₹49,000. Meena is not careless. She is busy, trusting, and alone with a phone."

**Then the statistic** (say it slowly, with the source):

> "India's Home Ministry told Parliament that people lost **more than ₹22,845 crore to cyber fraud in 2024 alone**. And in a national survey, **about half of the people hit by UPI fraud never filed a complaint at all**. Most victims do not just lose money. They lose it silently."

*Sources (have them open in a tab in case a judge asks):* MoS Home Affairs written reply, as reported by [IANS](https://ianslive.in/indians-lose-over-rs-52976-crore-to-cyber-frauds-over-six-years-report--20260103154943) and [CyberPeace's analysis of the Rajya Sabha reply](https://cyberpeace.org/resources/blogs/cyberpeace-analysis-indias-cybercrime-surge-signals-a-growing-digital-security-challenge-an-assessment-based-on-rajya-sabha-proceedings-and-mha-data); LocalCircles survey (51% did not file a complaint) via [Business Standard](https://www.business-standard.com/finance/news/upi-transaction-fraud-india-survey-one-in-five-users-hit-localcircles-125062601141_1.html). **Check the figures once more before 11 AM; do not quote the 2025 numbers, the sources disagree.**

Why this opening scores: it is the rubric's "names a specific user and a UPI scam grounded in how fraud actually happens in India" (Problem and user, 20), and it makes the jury feel the problem, which the mentors said is the most important thing.

---

## 2. The 12-minute run sheet (30 → 10 session)

| Time | What | Who | Where it earns marks |
|---|---|---|---|
| 0:00 to 1:30 | The opening above. Meena, the ₹49 message, the statistic | Mohit | Problem and user understanding |
| 1:30 to 2:15 | "This is Satyapan." The three words. One brain, many doors: website, Telegram, browser right-click, shopkeeper counter. Platform-agnostic | Mohit | Deployability, own engineering |
| 2:15 to 7:30 | **Live demo the judge drives** (script in section 3). Let the judge type their own message in any language | Mohit drives, Tanish narrates safeguards | Working prototype 25, live user journey 25 |
| 7:30 to 9:30 | How we built and measured it (section 4): our own data, our models, the Groq helper, the numbers, **and where we fail** | Ghana | Own engineering 15, accuracy 30 |
| 9:30 to 10:30 | Customer traction and community (section 6) | Tanish | Mentor asks: traction, awareness |
| 10:30 to 12:00 | Questions. Offer to help the technical team run the code | All | Communication and Q&A |

If the judges start using the product themselves in the first two minutes, **let them**. Narrate what they are doing. Jump to the section that matches.

### Final presentation (6 + 3 minutes)
| Time | Content |
|---|---|
| 0:00 to 0:50 | Meena and the statistic |
| 0:50 to 1:20 | The idea in one breath |
| 1:20 to 3:50 | **Live demo, judge-varied**: one judge's message → what it says in their language → verdict and reasons → Ask family → "Wrong result?" → human review |
| 3:50 to 4:40 | Why you can trust it: measured numbers, named failures, "attack yourself" |
| 4:40 to 5:30 | Path into a bank or UPI app: who runs it, what it costs, what a pilot needs. Why us |
| 5:30 to 6:00 | The ask: a pilot with real users |
| 6:00 to 9:00 | Questions. Use "we do not know" when true |

---

## 3. The live demo script (everything below has been tested live)

Open the site on the laptop **and** on a phone (Telegram open to `@Satyapanbot`). Start each step by asking the judge for an input. Fallback inputs are in `demo/`.

1. **Their message (the money step).** Ask: *"Type or paste any message you think a scammer would send, in any language."* Press **Check now**.
   - Show the first thing on the page: **"First, what does this say?"** with what we read from their message.
   - Say: *"Many people are more confident in their own language than in English. Before we tell them anything, we make sure they understand exactly what the message says."* Ask the judge for a language, pick it, press **Explain**. We translate what it says, **then** show our verdict in that language, then **Listen**.
   - Read out one reason. Point at the line: *"This is only a suggestion. It may or may not be a scam."* (Responsible AI: we do not claim certainty.)
2. **Same message on a phone, through Telegram.** Forward it to `@Satyapanbot`. The same verdict arrives in the chat. Press **Explain in my language**. *"We did not build a website. We built a brain, and it lives wherever the scam arrives."* (Platform agnostic.)
3. **The browser extension.** On any page, select text, right-click, **Check with Satyapan**. It opens the check, already running.
4. **A QR code.** Upload `demo/qr/collect_trap__clean.png`. *"The picture of a QR says nothing. We read what is inside it: a payment note that says 'Enter PIN to receive'. Receiving money never needs a PIN, so this one takes money out."*
5. **A shopkeeper with a screenshot.** `/shopkeeper`, save a UPI ID, upload `demo/screens/genuine_000000.jpg`. With a different shop UPI ID it says **the money went to someone else**. Then upload an edited one and show the circled area. *"This is the second Meena: the person selling, not paying."*
6. **A PDF.** Upload `demo/pdf/scam_changed_bank_invoice.pdf` (the "our bank account has changed" invoice fraud that hits small businesses).
7. **A voice note.** Upload `demo/voice/scam_hi.wav`. We show **what we heard (speech to text)**, then the verdict. If the transcription is a little off, show **"Heard something wrong? Edit the words and check again."**
8. **The part that is about people, not models.** Press **Ask family** (a short result to forward). Then **Wrong result?** on a genuine message that we flagged, and show: it gives a reference number, a human reviewer decides, and the user can see the status. Then **Delete now** and the real deletion receipt. *"If we are wrong about a genuine message, nobody is blocked and nobody is stuck. We never block or pay anything."*

**Do not demo:** the "EXAMPLE ONLY" pages as if they were live results; anything in Hindi voice over a phone line (our weak spot); the community page if it is empty (say "it fills with real reports").

---

## 4. The technical walkthrough (what Ghana says, in plain words)

*"Seven checks, one decision."*

1. **Read it.** OCR (English and Hindi), QR decoding, PDF text and metadata, speech to text on our own server (faster-whisper).
2. **Who is asking for the money.** UPI ID format, IFSC and bank code, look-alike links, collect-request traps, personal accounts asked for investments.
3. **What the words say.** A rule lexicon in English, Hindi and Hinglish (arrest threats, advance fees, PIN grabs, remote-access apps). Plus a **fine-tuned multilingual classifier** (e5-small) trained on **our own dataset**: a generator we wrote that produces 41 families of Indian scam and genuine messages, with a guard that throws away anything that overlaps the held-out test files.
4. **Is the picture edited.** A **small U-Net we trained** on **payment screens we generated ourselves**, tested on layouts it never saw.
5. **Is the voice synthetic.** A cloned-voice detector (Spectra-AASIST3), calibrated by us and tested on speakers we kept out.
6. **An AI check, deliberately boxed in.** Groq runs an open model (gpt-oss). It may do exactly one thing: say which of **33 rules taken from RBI, SEBI, NPCI, TRAI and MHA advisories** a message breaks, and quote the words. **We keep a match only if the quote is really in the message, the reasons come from our own templates, and the model can only add warnings, never clear a message**, so a prompt injection cannot make a scam look safe. Phone numbers and account numbers are masked first. Without a key nothing is sent.
7. **Fusion.** A short, readable rule set: HIGH RISK needs two independent strong signs or a registry hit; a picture check alone can never decide; one weak sign never raises an alarm on its own; nothing is ever called "safe".

*"Open source, platform agnostic."* Every model is open: Tesseract/RapidOCR, zxing, faster-whisper, Spectra-AASIST3, e5-small, gpt-oss. The brain is an API (`/api/v1/check`) that the website, Telegram, the extension and the shopkeeper page all call. It runs on a laptop with no cloud account.

*"What is ours, written at the finale":* the payment-screen generator and the tamper model, the scam-message corpus generator and classifier, the rule lexicon, the fusion step, the plugin architecture that let three people build in parallel with zero merge conflicts, the Understand-first flow, the shopkeeper, helper and company checks, the Telegram bot, the extension, and 415 automated tests plus a 42-check end-to-end script.

### The numbers to say out loud (all in `/results` and `docs/results/`)

| What | Number | How to say it |
|---|---|---|
| Scam messages, Tanish's file, never used in training | **33 of 40 caught, 0 of 40 genuine wrongly flagged** (rules alone: 19 of 40) | "Optimistic: we used its failure categories afterwards. Here is the honest way we will test it: you give us 40 new ones." |
| With the optional AI check | 40 of 40, 0 of 40 genuine flagged | "Optimistic for the same reason." |
| Scam types the classifier never saw (held out by family) | **66% on its own, 89% as one weak sign**; 0.7% and 2.2% of genuine flagged | "On synthetic and teammate-written data." |
| Edited payment screenshots (generated, layouts never seen) | **41% caught, 7% of genuine wrongly flagged** | "Weak, and we say so. It supports the verdict and can never decide alone." |
| Cloned voices | **1,980 of 1,980 flagged, 4.1% of real voices wrongly flagged** | "Test split by speaker. Phone-line audio is weaker." |
| Speed | first answer in about a second for text; voice about 6 to 10 s on a laptop CPU | |
| Tests | 415 automated tests; 42 end-to-end feature checks pass | |

**Test kit for the technical team (reproducibility, as the brief asks):** `pip install -e .` → `python -m pytest -q` → `python scripts/final_check.py http://127.0.0.1:8000` → `python -m satyapan.eval.report` → `python scripts/eval_holdout.py data/kit/holdout_community.jsonl`. Datasets and licences: `docs/disclosure/models.md`.

---

## 5. Rubric, line by line: what to say and where to point

### Stage 1 (30 → 10)
| Criterion | Say / show | Proof to point at |
|---|---|---|
| **1. Working prototype (25)** | "Give us any input." The judge's message, a QR, a PDF, a screenshot, a voice note, all live, input → detection → alert → action | the live site; `python scripts/final_check.py` (42 PASS) |
| **2. Measured accuracy (30)** | Numbers above, **with false positives and failures named**. "What we miss" list from section 8 | `/results` (every number read from a file; "not evaluated" where we did not measure), `docs/results/` |
| **3. Own engineering (15)** | The seven checks, the fine-tuned models, the dataset generators, the fusion step. Any of three people can walk through any part | `README.md`, `docs/models.md`, `training/`, `tools/`, `src/satyapan/` |
| **4. Alert and response (15)** | Clear alert, **Ask family**, signed **Evidence report**, **Wrong result? → human reviewer**, delete. Safeguards running: nothing raw kept (file read in memory and thrown away), 24 h expiry, masked data to the AI helper | `/console`, `/report`, the deletion receipt |
| **5. Delivery vs the plan (15)** | We cut Docker, FaceForensics-style video work and lip-sync on purpose, and added what mentors asked for: community, traction, Telegram, extension. We can say why for every line | `docs/DEVIATIONS.md` |

### Stage 2 (final)
| Criterion | Say / show |
|---|---|
| **1. Problem and user (20)** | Meena the tiffin seller, the refund scam, the ₹22,845 crore figure; second user: the shopkeeper who is shown a fake "payment successful" screen; third: the small business hit by the "our bank account has changed" invoice |
| **2. Deployability and scale (15)** | Section 7 below |
| **3. Communication and Q&A (10)** | Short answers. Say "we don't know" for: real phone screenshots, performance in languages beyond Hindi/English/Hinglish for the classifier, cost at national scale |
| **4. Live user journey (25)** | Sections 1 and 3: the attack reaches Meena, the alert, her action (Ask family), and a human review |
| **5. Adversarial robustness (20)** | Open `/attack`: *"This is how a scammer beats us."* Spacing and look-alike letters let 84% of flagged scams escape our rules, so we added a hook that undoes the tricks, and **it costs more false alarms** (up to 14 of 73 perturbed genuine messages). *"We have not tested a smart paraphrase. That is what we would do next: adversarial rewrites as training data, and a live UPI-handle feed."* |
| **6. Responsible AI (10)** | Show a genuine message flagged → Wrong result? → reference → reviewer → status; the alert says *why*; "no red flags" never means safe; privacy: in-memory, 24 h, masking |

---

## 6. Customer traction, awareness and education (the mentor's two asks)

- **Live traction:** open `/impact`. It counts only real visitors (our devices are excluded) and starts at zero. **Say only what it shows at that moment.** Before 11 AM, send the link and the Telegram bot to as many friends, family and shopkeepers as you can, and say the true number. A small honest number beats an invented big one.
- **Shop poster:** `/poster` makes a printable QR poster for a shop; scans are counted by referral.
- **Pilot sign-up:** `/pilot` is a real form (shopkeepers, NGOs, colleges, bank branches).
- **Awareness and education:** Scam Watch (people report what they saw, every report cleaned of numbers and names), twelve short lessons, **Scam Drill** (66 questions, streaks and badges, leaderboard), a family safe-word card, printable warning cards. *"People come back to learn, and every lesson is also a reason to check before they pay."*

---

## 7. Deployability, market, launch and "why us"

**Who is the customer.** People (free, always). The buyers are **UPI apps, wallets, banks, and law-enforcement helplines** who pay to cut fraud losses and complaint volume. **Platform agnostic by construction:** one API, many doors.

**How it gets into a real workflow (concrete):**
1. *A "Check before you pay" link or QR* inside a bank or UPI app's payment screen, SMS footer or branch poster (live today: `/poster`).
2. *The API* (`POST /api/v1/check`) called by a partner's app at the moment a payee is added or a collect request arrives.
3. *Helper mode* for bank branch staff and CSC/kirana volunteers: one person at a time, answer in their language, wipe.
4. *The signed evidence pack and complaint draft* that a cyber cell can verify (Ed25519), to speed up reporting to 1930 and cybercrime.gov.in.

**Who runs it, what it costs, what a pilot needs.** Our team runs it during a pilot. It is one small server (4 GB RAM) with open models; we measured about **5.8 checks per second on a laptop** that was also running the load generator. Cost per 1,000 checks is **server share plus a few paisa of AI-helper tokens**; we have not computed it for a real server and say so. A pilot needs: one partner contact, a few weeks of real traffic, a way for the partner to tell us when we were wrong, and sign-off on data handling. Plan: 5 shops and one bank branch first, measure complaints avoided.

**Launch.** Week 1: Telegram and shop posters in two neighbourhoods. Month 1: 50 shops and an NGO partner; Hindi plus one regional language chosen by where the pilots are. Month 3: a conversation with a UPI app on the API. WhatsApp needs paid business approval, which is why we launched on Telegram.

**Why us (the differentiator):**
1. **We start from understanding, not scoring.** Others return a risk score. We first tell the person, in their language, what the message says, then give a reason they can check themselves.
2. **Honest numbers.** Every number is read from a file; what we did not measure says "not evaluated"; we show the attack page and our false alarms.
3. **One brain, every channel,** with a human in the loop for mistakes.
4. **Built for the whole fraud, not one file type:** the payee and the words decide the verdict; image and voice detectors support it. Pixel detectors degrade on chat-compressed media, so we do not let them decide alone.
5. **Privacy as running code,** not a promise.

---

## 8. What we miss, and what we would change (say it before they ask)

| We miss | Why | What we would change |
|---|---|---|
| Scams that read like ordinary messages (a "payment done, screenshot attached" text, a bare "your bill is due") | no scary words; the wording is genuine-looking | train on adversarially rewritten scams; add a live UPI-handle verification feed from the payment network |
| About 6 in 10 edited screenshots | our tamper model is trained on generated screens and is weak on perfect edits | collect real, consented edited screenshots; add consistency checks (amount in words, dates, reference format) |
| Real phone screenshots | **we did not evaluate them**: we do not use anyone's payment data without permission | a consented collection with a partner |
| Phone-line voice | the detector degrades on 8 kHz audio | train on telephone-codec audio |
| A smart paraphrase of a scam | our attack panel uses fixed perturbations, not an LLM rewrite | an adversarial rewrite loop |
| Real accounts for reviewers | sign-in is a demo | real accounts with two-factor |

---

## 9. Questions to expect, with honest answers

1. **"Is this just a wrapper around an LLM?"** No. The verdict comes from our rules, our fine-tuned models and a deterministic fusion step. The LLM is an optional, boxed-in helper that can only add warnings and must quote the message. Attack mode uses no LLM at all.
2. **"What did you build during the finale?"** The payment-screen generator and tamper model, the scam corpus generator and classifier, rules, fusion, the whole web app, Telegram bot, extension, tests. (Section 4.)
3. **"How accurate is it?"** Give the table, then: *"The numbers on our own files are optimistic. Give us your kit and we will run it live; we expect it to score lower and we will show you where."*
4. **"False positives?"** 0 of 40 genuine messages on the held-out file; 7% of genuine synthetic screenshots; 4% of real voices. A flagged genuine user presses Wrong result?, gets a reference number, and a human decides.
5. **"How would a scammer beat you?"** Open `/attack`. Look-alike letters, spacing, split UPI IDs, a polite paraphrase. Then say what we would change.
6. **"What does the AI helper see? Where does data go?"** Masked text only, to Groq, only if a key is set, never stored; the check page says when it is on. Files are read in memory and discarded.
7. **"Why not just use Truecaller / bank SMS warnings?"** They flag numbers or fixed patterns. We explain the *content* in the person's language, check the payee and the link, work on pictures, QR and voice, and give the person an action. We would happily sit inside a bank's flow.
8. **"Why Telegram, not WhatsApp?"** WhatsApp's business channel needs paid approval; the engine is channel-independent, so adding it is wiring.
9. **"Languages?"** Verdict text in English and Hindi; any result can be explained and read aloud in 11 Indian languages through Sarvam (machine translation can err, and we say so). The classifier has only seen English, Hindi and Hinglish.
10. **"Who is liable if you say it is fine and it is not?"** We never say "safe". The best answer is "no red flags found, this is not a guarantee", and we list what we did not check.
11. **"Prompt injection?"** The model's output is forced to JSON; a match must quote the real message and name one of our rule IDs; reasons come from our templates; it cannot clear a message.
12. **"Cost at national scale?"** We do not know yet. One 4 GB server handled several checks per second; the AI helper cost per message is small but unmeasured on a paid plan.
13. **"Did you use real people's data?"** No. Generated screens, teammate-written messages, public datasets for voice and general SMS spam, all listed with licences.
14. **"Is the reviewer console secure?"** No, it is a demo sign-in. Production needs real accounts.
15. **"Can we run it ourselves?"** Yes, with Python and the model folder; five commands (section 4).

---

## 10. Morning checklist (report 8 to 9 AM, code freeze 11 AM)

- [ ] `git pull` on the demo laptop, `python -m pytest -q` is green, code pushed before 11 AM.
- [ ] Models in `var/models/`, `.env` has the Groq, Sarvam and Telegram keys and `INTERNAL_KEY`.
- [ ] Stop the server, **delete `var/satyapan.db`**, start it (`make serve`), wait 45 seconds (models warm up).
- [ ] `python scripts/preflight.py` says READY, `python scripts/final_check.py` shows 42 PASS (run it **before** the delete step).
- [ ] Open `/internal?key=...` on every team device so rehearsals are not counted as users.
- [ ] Public link: `cloudflared tunnel --url http://localhost:8000`; put it in `PUBLIC_URL`, restart the bot. **For the phone on the same Wi-Fi:** start with `--host 0.0.0.0` and open `http://<laptop IP>:8000`.
- [ ] Telegram: `make bot` running; message the bot once from a phone.
- [ ] Extension loaded (`chrome://extensions`, Developer mode, Load unpacked, the `extension/` folder) and pointed at the server.
- [ ] Printed: the Meena card, the demo QR codes, the poster.
- [ ] Charger, a phone hotspot, and the demo files copied to a USB stick.
- [ ] Tabs open in this order: `/check`, Telegram, `/shopkeeper`, `/results`, `/attack`, `/console`, `/impact`.
- [ ] The three source links for the statistic open in a tab.

---

## 11. Do not say

- "AI-made image detection" (we do not have it; only cloned voices).
- "It works on real phone screenshots" (not evaluated).
- "Zero false positives" (zero on one file of 40; say the file).
- Any traction number that `/impact` does not show.
- "Production-ready authentication" for the reviewer console.
- "Deployed to the cloud" (it runs on our laptop through a tunnel).
