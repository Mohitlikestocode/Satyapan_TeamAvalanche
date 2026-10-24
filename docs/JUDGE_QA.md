# Questions a judge may ask, and our honest answers

Every number is from a file in `docs/results/`. "Optimistic" means we looked at that data while building.

## What do you miss right now?
* **Scams with no fixed wording.** On Tanish's 80 unseen messages the whole system flags **25 of 40 scams (62%)** with **0 of 40 genuine messages** flagged. About 3 in 8 unseen scams still get through: sextortion, fake loan apps, crypto pitches, and scam text with no money ask.
* **Edited payment screenshots.** On synthetic screens from layouts the model never saw, the tamper model catches about **39%** of edits (975 / 2,511) and wrongly flags about **5%** of genuine ones. The whole screenshot check flags 61 / 150 edited and 11 / 150 genuine (the 150 + 150 are synthetic screens from unseen layouts).
* **Cloned voices over a phone line.** The detector flags every synthetic fake in the test split (1,980 / 1,980) but wrongly flags 78 / 1,884 real voices (4.1%), and it degrades on 8 kHz telephone audio.
* **Real phone screenshots.** Not evaluated. We did not collect anyone's real payment screens without permission, so `/results` says "not evaluated".

## How would an attacker evade you?
Spacing out letters, look-alike characters, splitting a UPI ID over lines, Hinglish respelling, JPEG and shrinking for images, a phone-line codec for audio. `/attack` measures each. With rules alone, look-alike letters let 84% of flagged scams through; after our undo-the-trick hook, 0 of 50 escape, but false alarms on perturbed genuine messages rise (up to 14 / 73). The hook was written after seeing the gap, so treat the as-deployed escape number as optimistic.
**What we would change:** a classifier trained on adversarially rewritten scams, a real UPI-handle verification feed from the payment network, and a payee check against live registries.

## What if a genuine person is flagged?
Every alert shows the reason it fired, in plain English or Hindi. The person presses **Wrong result?**, gets a reference number and a status page, and a human reviewer decides. Verdicts are advisory: we never block or move money. A first-time genuine flag costs them about a minute.

## Why should we trust the numbers?
Splits were fixed before training; thresholds were chosen on dev data at a stated false-alarm target and never re-tuned on the test set; every table has a baseline and a 95% interval; the held-out message file was written by a teammate who had not read the rules; and our own message file, written by the same assistant that wrote the rules, is labelled optimistic.

## What is your own engineering?
Fine-tuned: the screenshot tamper U-Net (own synthetic data generator, layout-held-out splits) and the scam-message classifier (full fine-tune of multilingual-e5-small, held-out scam families). Fused signals: deterministic fusion where HIGH RISK needs two independent strong layers. Custom pipeline: bilingual rule lexicon, UPI, IFSC and QR checks, look-alike-letter undoing, sandboxed voice path, plugin registry. Pretrained and calibrated, not trained by us: speech to text and the voice detector.

## What does a bank, UPI app or police unit need to pilot this?
One server (Python, about 4 GB RAM for the models), a domain, a Telegram bot token, and a person for the review queue. We measured about 5.8 checks per second for 8 users on a laptop. Cost per 1,000 checks is **not computed** until the server price is known (`scripts/loadtest.py --price-per-month`). A shop pilot needs a printed poster and the `/pilot` form.

## What don't you know?
How well the screenshot check works on real phone screenshots; how Hindi reads to a fluent speaker (machine-drafted until reviewed); real-world traffic (we report only what the server counted, team traffic excluded); whether the scam-message classifier generalises beyond an 80-message held-out set (the intervals are wide: 62% has a 95% interval of about 47% to 76%).

## Is the reviewer sign-in secure?
No. It is a demo sign-in, not real authentication. A production deployment needs real accounts with two-factor sign-in.
