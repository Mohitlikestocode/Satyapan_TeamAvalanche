# Finale plan v2 (Sat 24 Oct to Sun 25 Oct, demo-ready by 10:00 IST Sunday)

Clock assumption: it is about 16:00 IST on Saturday now, so roughly 18 hours remain. Re-time the blocks if that is wrong.

## 1. What the rubric pays for (Round 2)

Stage 1 decides the top 10. Stage 2 decides the podium.

| Criterion | Pts | What earns a 5 | Where we earn it |
|---|---|---|---|
| Working prototype | 25 | Runs live on inputs the judge picks, from input to detection to alert or action | Message, link, QR, screenshot, PDF and voice checks all run live; every verdict leads to an action |
| Spot-check accuracy | **30** | Most kit samples right; error rates **including false positives on data never trained on**; failure cases named | Held-out evaluation page with real numbers, confidence intervals and a failure list |
| Own engineering | 15 | Substantial code written at the finale: **fine-tuning, fused signals, custom pipeline**; any member can explain it | Two fine-tuned models, a learned fusion stacker, and the check pipeline |
| Alert and response flow | 15 | Person sees a clear alert and can act; safeguards are *running* (no raw data kept, human review) | Real Guardian share, report packet, "Wrong result?" into a live reviewer queue, deletion that actually deletes |
| Delivery vs Round 1 | 15 | Built what we promised, or cut on purpose and can say why | `docs/DEVIATIONS.md`, kept current |
| Problem and user | 20 | A named user and a UPI-fraud scenario grounded in India | Rekha, the stock-tips chain, shopkeeper and invoice cases |
| Deployability | 15 | A concrete path into a bank, UPI app or police workflow: who runs it, cost, pilot needs | One-page pilot note, cost per check |
| Communication and Q&A | 10 | Clear, on time, "we don't know" is fine | Rehearsed answers, written failure list |
| Live user journey | **25** | Jury can vary the scenario; whole path from attack to alert to action to review | Judge-picked inputs, scripted fallbacks, full path on one screen flow |
| Adversarial robustness | **20** | We show how an attacker would evade us, what we miss now, what we would change | "Attack yourself" panel with measured score drift |
| Responsible AI | 10 | A genuine user flagged by mistake gets past it fast; the alert says why; privacy runs | Wrong-result path demonstrated live |

Spot-check (30) and live journey (25) are the two biggest. Custom models help both, but only if they are measured on data they never saw.

## 2. What "custom models" gets us, and what it risks

The rubric lists three equal ways to show own engineering: **fine-tuning, fused signals, custom pipeline**. Fine-tuning is one of three, worth up to the 15 points. It also lifts the 30-point accuracy score only if the model beats the pretrained baseline on held-out data. A fine-tune on a tiny, leaky dataset does the opposite: it looks great on our own test and fails on the judges' kit.

So the rule is: **fine-tune where nothing off-the-shelf exists, always compare to the baseline, ship whichever wins.**

Training happens only at the finale (after check-in) and is logged in git (scripts, seeds, metrics; never weights or data). This keeps us consistent with the form ("no models trained before the event").

## 3. The model portfolio

| # | Model | Why it is worth building | Base | Data | Held-out test | Owner (proposal) | GPU time |
|---|---|---|---|---|---|---|---|
| F1 | **Payment-screenshot tamper localiser** | Nothing off-the-shelf does this. Gives the "edited amount is circled" demo | ResNet-18 or EfficientNet-B0 encoder, small U-Net decoder | Our own generator: fake payment screens in 6+ styles with random amounts, names, references and fonts, plus edited copies and masks. Unlimited, no privacy issue | Styles never used in training; 50+ team-edited real screenshots; 100 genuine screenshots for false alarms; WhatsApp-recompressed copies | Ghana | 1 to 2 h on the RTX 4060 |
| F2 | **English / Hindi / Hinglish scam-message classifier** | Rules miss paraphrases; this catches them and is explainable next to the rules | multilingual-e5-small plus a classification head | Public SMS data for genuine and spam text, plus a team-written corpus split by scam family | Scam families held out; genuine bank, delivery and OTP notices as false-alarm set | Sai Mohit or Tanish | 20 min on CPU or GPU |
| F3 | **Learned fusion stacker** | The "fused signals" proof. Weights are non-negative on suspicion features, so it stays monotone and auditable | Logistic regression over layer outputs | Dev split outputs of every layer | Test split; thresholds stated as expected false-alarm rate | Tanish | seconds |
| F4 (stretch) | Voice-clone detector adaptation | Only if F1 to F3 are done by Sat 23:00. Else use the pretrained detector with on-site calibration | Spectra-AASIST3 or an XLS-R head | In-the-Wild sample, IndicSynth Hindi, FLEURS real, consented clones | Speakers and datasets not used in training | Ghana | 2 to 3 h |

Cut order if late: F4, then F2's full fine-tune (keep the frozen-encoder head), then nothing else. F1 and F3 stay.

## 4. Evaluation protocol (this is the 30-point row)

1. Freeze splits **before** training: by speaker, by screenshot style, by scam family. Write them to `docs/results/splits.json` with hashes.
2. Report per condition: clean, WhatsApp-compressed, cropped. Use TPR and FPR at one fixed threshold chosen on the dev split. Add bootstrap 95% intervals.
3. Always show a baseline row (rules only, pretrained only) next to the fine-tuned row.
4. Failure cases are listed, with a picture or text, on the Results page. Anything not measured says "not evaluated".
5. `docs/DATASET_PROVENANCE.md` records source, licence, date, size and hash for every dataset. Nothing is committed.

The judges' kit is unseen data. Expect a drop from our own numbers, and say so on stage.

## 5. Work packages and timeline

All clock times are IST.

**Block A: Sat 16:00 to 22:00. Data, baselines, harness**
- Finish checks for screenshot, PDF and QR input (in progress): OCR adapter, PDF edit traces, UTR and IFSC checks.
- Evaluation harness with confidence intervals and a failure list (started).
- Screenshot generator for F1; public text data and team scam corpus for F2.
- Wire the response flow for real: Guardian share, report packet, reviewer queue, deletion receipt.
- First measured baseline numbers (rules only, pretrained only).

**Block B: Sat 22:00 to Sun 04:00. Training and integration**
- F1 and F2 training runs start by 22:30 and run unattended; F4 only if on time.
- Meanwhile: Sarvam translation and voice with local fallback, C2PA demo, the "Attack yourself" panel.
- F3 stacker once layer outputs exist (about 01:00).
- Sleep in shifts: someone always owns the running jobs.

**Block C: Sun 04:00 to 10:00. Freeze and rehearse**
- 04:00 to 06:00: evaluate on held-out splits, fill the Results page, write the failure list.
- 06:00 to 08:00: feature freeze at 07:00; bug fixes only. Update `DEVIATIONS.md`.
- 08:00 to 10:00: rehearse the live journey three times with judge-style variations. Prepare fallback inputs for every step.

## 6. Demo path (Stage 2, 25 points)

Attack arrives (stock-tips QR plus message) → live check → plain result in Hindi and spoken → Ask family → "Already paid?" → report packet → "Wrong result?" lands in the reviewer queue → reviewer confirms → the same scam re-sent is a REGISTRY HIT. Then "Attack yourself": re-encode, crop, rewrite the text, and show what drifts.

## 7. Risks and honest limits

- **Fine-tuned models can overfit.** Mitigation: held-out styles and scam families, baseline rows, and the rule that the winner ships.
- **Synthetic data does not look like real phones.** Mitigation: a small real set from team phones (consented, with names and numbers covered) for testing only.
- **Hindi text is machine-drafted.** Needs a fluent reviewer before the demo.
- **OCR quality.** Tesseract (Hindi and English) must be installed on the demo machine; there is no Tesseract on this laptop yet.
- **Compute.** Only Ghana's RTX 4060 (8 GB) is a GPU; this laptop is CPU only. Keep models small; one training job at a time on the GPU.
- **Shared authorship.** The rule list and the message corpus come from the same people, so results on them are optimistic. The Results page says so.

## 8. Division of work

To be split when your teammates join. The code is already laid out so each person can own a folder: `layers/l2_forensics` and `eval` (detectors, training), `layers/l3_payee` and `integrations` (payee, SEBI, Sarvam, C2PA), `fusion`, `api` and `web` (UI, response flow, reviewer console).
