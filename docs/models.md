# Workstream A: models and measurement

Owner: Ghana (branch `feat/models-eval`). Hardware: NVIDIA GeForce RTX 4060 Laptop GPU (8 GB), Windows 11, Python 3.13.
Every number this workstream shows comes from a file in `docs/results/` or a live run. Anything not measured says "not evaluated".

## Plan (written Saturday evening, before any training)

Order is by points at risk, with the GPU kept busy while code is written alongside it.

| # | Task | Why first | Output |
|---|---|---|---|
| 1 | **A1 data**: widen the screenshot generator so the model cannot memorise a style | The CPU run learned its validation styles (AUROC 0.997) but not unseen ones (0.664, 88% false alarms) | `tools/make_payment_screens.py`, `docs/results/splits.json` |
| 2 | **A1 train**: small encoder and ResNet-18 (ImageNet), run unattended on the GPU | Training takes hours; start it early | `var/models/tamper.pt` (not in git), `docs/results/tamper_test.json` |
| 3 | **A4 `/results`** while training runs: reads `docs/results/*.json`, live "Run the text kit" button | The 30-point accuracy row is this page | `api/ext/models_results.py`, templates under `web/templates/ext/models/` |
| 4 | **A2 voice notes**: ffmpeg in a locked-down subprocess, faster-whisper, cloned-voice detector, calibration | P0, the only check kind still on a sample page | `plugins/models_voice.py`, `docs/results/voice_*.json` |
| 5 | **A1 install and `/models/screenshot`**: the "edited amount is circled" page; real-screenshot evaluation | Needs the checkpoint and the real set | `api/ext/models_screenshot.py`, `docs/results/tamper_real.json` |
| 6 | **A4 `/attack`**: real perturbations of text, image and audio, tier drift per perturbation | The 20-point adversarial row | `api/ext/models_attack.py` |
| 7 | **A3 scam-message classifier** (P1): multilingual-e5-small, scam families held out | Ships only if it beats the rules on held-out messages without more false alarms | `plugins/models_text.py` or a written "kept off, because" |
| 8 | **A5 model cards** in this file | Every member must be able to explain each model | below |

### Fixing the tamper model's generalisation (A1)

The test styles failed because the generator has six fixed styles and three layouts: a style is a fixed palette plus a fixed layout, so the
model can learn "what genuine looks like for these six screens" instead of "what an edit looks like". Changes:

- **Many more styles, made procedurally**: random palettes (light and dark), several more layouts (card, list, receipt, banner, centred),
  random margins, extra non-edited elements (status bar, logos made of shapes, dividers, notes), more fonts. Split by **layout family**, so test layouts are never seen in training.
- **Harder edits**: same-font edits at about half the time, edits that copy the local background instead of a flat fill, small shifts only.
- **Genuine look-alikes**: genuine images that also contain re-rendered text, blur and sharpening, so "different text quality" alone is not an edit.
- **Chat-app copies**: resize, JPEG 40 to 95, sometimes twice, plus colour and noise jitter on all images (edited and genuine alike).
- Train `small` and `resnet18 --pretrained`. **Pick by the test split, never by validation**, and report both.

### Measurement protocol

- Splits are frozen before training and written to `docs/results/splits.json` with hashes: screenshot by layout family,
  voice by speaker and source dataset, text by scam family.
- One threshold per model, chosen on the dev/validation split at a stated false-alarm target, never re-tuned on test.
- Report TPR (scams or edits caught) and FPR (genuine wrongly flagged) at that threshold, AUROC, EER for voice,
  95% intervals (Wilson for rates, bootstrap where stated), per condition (clean, JPEG q40, shrunk to 60%; Opus 24k, AAC 64k, 8 kHz telephone).
- Every table has a baseline row: error-level analysis for screenshots, rules only for text, the second detector for voice.
- Honest numbers: the real-screenshot set (50 edited, 100 genuine, team-made, consented, kept out of git) and the held-out messages
  `data/kit/holdout_*.jsonl` written by B and C. Nothing in `data/kit/` is ever trained on.
- Failure cases are listed by name on `/results`.

### What we need from people

- **Ghana**: approve each download over 100 MB; install ffmpeg; collect the real screenshot set; record consented voice notes.
- **Tanish and Mohit**: `data/kit/holdout_community.jsonl` and `holdout_traction.jsonl` (40 scam and 40 genuine each, written without reading the rules).
- **Mohit (integrator)**: receives `tamper.pt` and the voice model files by chat or drive, never git.

## What changed from the plan, and why

- **Tamper model, first GPU run (Saturday 19:15): stopped after 2 epochs.** Validation AUROC 0.50 both epochs (chance). Two causes, both fixed:
  (1) the whole screenshot was shrunk to 704x384 before the model saw it, which washes out the pixel traces an edit leaves; now the
  model trains on 384x384 crops at full resolution and scores whole screenshots at full resolution (`--native`);
  (2) generator v2 made edits *too* perfect (exact fill colour, exact size and place), so there was nothing to learn. Generator v3
  adds the small traces real editors leave (eyedropper colour off by a few levels, retyped text a pixel or size off, a forwarded
  screenshot's JPEG blocks missing in the repainted patch) and keeps 15% "perfect" edits, reported separately as the hard case.
  The error-level-analysis baseline was also at chance on v2 (AUROC 0.49 on 400 validation images), which confirmed the data problem.
- **Second voice detector:** the brief named XLS-R-SLS. Its repository has no licence, its weights are only on Google Drive or Baidu,
  and it needs fairseq plus another 1.2 GB checkpoint, so we used `MelodyMachine/Deepfake-audio-detection-V2` (Apache-2.0) instead.
  Its authors do not document its training data, so it is only a second opinion: disagreement means we say nothing about the voice.
- **ffmpeg:** shipped through `imageio-ffmpeg` (a static ffmpeg build from PyPI), so no system install is needed on the server.
- **Hidden-word check (not in the plan):** the attack sweep showed look-alike letters let 32 of 37 flagged kit scams through the
  rules. We added a text hook that undoes look-alike letters, spaced-out letters and split UPI IDs and re-runs the same rules.

## Results

Every number below is copied from a file in `docs/results/`; `/results` shows the same files live. Hardware: NVIDIA GeForce RTX 4060
Laptop GPU (8 GB) for training and batch evaluation; the site runs the models on CPU. Rates are Wilson 95% intervals in the files.

### Measured

| Check | Data it never trained on | Caught | Wrongly flagged | Other | File |
|---|---|---|---|---|---|
| Tamper model, chosen (small U-Net) | 4,966 generated screens, layouts L6+L7 never seen | 975/2,511 edits (39%) | 124/2,455 genuine (5.1%) | AUROC 0.735; box IoU 0.32 | `tamper_test.json` |
| **Whole screenshot check as deployed** (OCR + rules + tamper model + fusion) | 300 screens from test layouts (150 edited, 150 genuine) | 62/150 edited flagged (41%) | **23/150 genuine (15%)**: 14 by the core payee rules, 9 by the edit sign | edit sign alone: 55/150 vs 9/150; CAN'T TELL 1/300 | `screenshot_system.json` |
| Tamper model, ResNet-18 (not chosen) | same | 954/2,511 (38%) | 130/2,455 (5.3%) | AUROC 0.697 | `tamper_test_resnet18.json` |
| Baseline: error-level analysis | same | | | AUROC 0.512 | inside both files |
| Voice detector as deployed (Spectra-AASIST3 alone) | 969 clips from test speakers x 4 conditions | 1,980/1,980 fakes | 78/1,884 real (4.1%) | EER 3.1% (CI 2.4-3.9%) | `voice_test.json` |
| Second voice detector (excluded) | same | 1/1,980 | 68/1,884 | EER 65.6%: worse than chance on our data | `voice_test.json` |
| Message rules (dev kit, optimistic) | `data/kit/messages.jsonl` | 37/38 scams | 0/33 genuine | HIGH RISK on 8/38 scams | `text_kit.json` |
| Scam-message model, full fine-tune | 79 team scams, each family held out | 23/79 (29%) | 2/62 genuine out of fold | head-only: 2/79 | `text_model_cv.json` |
| Scam-message model ship test | dev kit | 37 -> 38 of 38 | 0 -> 2 of 33 | **kept off** (more false alarms) | `text_model_decision.json` |
| Attack sweep, rules alone -> as deployed | dev kit scams the checks flag (37) | look-alike letters: 32 -> 0 slip through; spacing 10 -> 1; split UPI 4 -> 0; Hinglish 7 -> 7 | genuine with the same tricks flagged: 0 -> 4 of 33 | the defence was written after seeing these gaps: optimistic | `attack_text.json` |

### Voice by condition (Spectra-AASIST3, test speakers)

| Condition | Fakes caught | Real voices wrongly flagged |
|---|---|---|
| Clean | 495/495 | 5/471 (1.1%) |
| Opus 24 kbps (WhatsApp-like) | 495/495 | 6/471 (1.3%) |
| AAC 64 kbps | 495/495 | 8/471 (1.7%) |
| **8 kHz telephone** | 495/495 | **59/471 (12.5%)** |
| By source | In-The-Wild fakes 936/936, IndicSynth Hindi fakes 1,044/1,044 | FLEURS English real 67/588 (11%), FLEURS Hindi real 5/588, In-The-Wild real 6/708 |

### Not evaluated (yet)

- **Real, team-edited payment screenshots** (`tamper_real.json`): waiting for the 50 edited + 100 genuine set.
- **Held-out messages from teammates** (`text_holdout.json`): waiting for `data/kit/holdout_*.jsonl`. The classifier decision will be re-run on them.
- **Fresh voice clones** (a current TTS on a consenting teammate's voice): not evaluated. All fakes above come from public datasets.
- PDF edit traces, QR decoding and OCR accuracy on their own; the judges' kit.

### Failure cases we name

1. **Tamper model misses most edits** (61% at the 5% false-alarm point), worst on "perfect" edits (exact colour, size and place) and
   same-font edits. It is a weak sign only and never decides a verdict on its own.
2. **Phone-line voices**: real voices through an 8 kHz phone line are wrongly flagged 12.5% of the time; English read speech (FLEURS) 11%.
3. **The voice detector's perfect catch rate is suspicious**: the fakes come from public generators the detector may have been trained
   on. We do not know how it does on a voice clone made today.
4. **A cloned voice saying harmless words is not flagged** unless the voice sign is strong: one weak forensic sign never raises a flag.
5. **Hinglish respellings** of key words ("garunteed", "prophit") let 7 of 37 flagged scams through.
6. **Genuine payment screenshots to a personal UPI ID get flagged by the payee rules** (14 of 150 generated genuine screens:
   `PAYEE_PERSONAL_ACCOUNT` + `PAYEE_UNVERIFIED`). These rules were written for payment *requests*; on a *receipt* they mislead a
   shopkeeper. Reported to the integrator (`docs/requests/models.md`, item 4).
7. **OCR is required for screenshots**: without an OCR engine every screenshot is CAN'T TELL (see `docs/requests/models.md`, item 2b).

## Model cards

### 1. Payment-screenshot tamper model (trained by us)

- **Purpose:** find signs that an amount, name, UPI ID, time or reference on a "payment successful" screenshot was edited, and where.
  Adds `MEDIA_IMAGE_EDITED` (L2, WEAK, or STRONG when very confident). Forensics alone can never make a result HIGH RISK.
- **Model:** U-Net. Encoders: ResNet-18 from ImageNet weights, and a small encoder from scratch (`tamper_net.py`). Loss: BCE (positive
  weight 8) + Dice on the edit mask. Image score = the strongest 3x3-averaged edit probability anywhere. AdamW, one-cycle schedule,
  mixed precision, 10 epochs, batch 16, seed 7.
- **Input:** full-resolution screenshot (shrunk only if the long side is over 1600 px). Training uses 384x384 crops, 60% of crops
  on edited images contain the edit. Training-time augmentation: colour channel swap, brightness, crop, one more JPEG pass.
- **Data:** 20,000 generated screens (`tools/make_payment_screens.py` v3, seed 7). 8 layout families, random light and dark palettes,
  status bars, logos made of shapes, notes and buttons, 17 training fonts. Half are edited: one field erased (painted over or
  background copied) and retyped (same font 50%, other font 50%), sometimes softened; 15% of edits are "perfect". Genuine look-alikes:
  20% of genuine screens have one field slightly blurred. Chat-app copies: shrink to 50-100%, JPEG 40-95, sometimes twice; 60% were
  already a JPEG before editing.
- **Split:** by layout family. Train L0-L4, validation L5, test L6 and L7 (never seen in training). Five fonts appear only in
  validation and test images. Split and hash: `docs/results/tamper_splits.json`.
- **Threshold:** chosen on the validation layouts so that 5% of genuine screens are flagged; never re-tuned on test or real data.
- **Choosing between encoders:** highest AUROC on the test layouts (the brief's rule). This makes the chosen test number slightly
  optimistic; the real-screenshot set is the independent check.
- **Reproduce:** `python tools/make_payment_screens.py data/f1 --n 20000 --seed 7 --holdout-styles 3`, then
  `powershell -File training/tamper/run_both.ps1`, then `python training/tamper/finalize.py`, then
  `python training/tamper/evaluate_real.py --ckpt var/models/tamper.pt --edited data/real/edited --genuine data/real/genuine --data data/f1 --json docs/results/tamper_real.json`.
- **Licence:** our code and our generated data. ResNet-18 ImageNet weights from torchvision (BSD-3-Clause).

### 2. Voice notes: transcription and cloned-voice detection (pretrained, calibrated by us)

- **Pipeline:** ffmpeg (no shell, input only from a pipe, `-protocol_whitelist pipe`, metadata stripped, 30 s time limit, 15 MB and
  120 s limits) -> 16 kHz mono -> faster-whisper small (local; Hindi and English) -> the same payee and word checks as a message ->
  plus the voice sign from the detectors. `/models/voice` shows the transcript for the visitor to correct before checking; the voice
  result travels to the second step only as a signed token holding the band (fake, real, disagree, unknown), never audio or scores.
- **Detectors:** Spectra-AASIST3 (wav2vec2 XLS-R 300M + KAN-AASIST; Apache-2.0) as primary; Deepfake-audio-detection-V2
  (wav2vec2-base; Apache-2.0) as second opinion. Each scores the first ~8 s (two windows). Flag when the score is below the threshold.
  Both must say "fake" for the sign; if they disagree we say nothing about the voice. The sign is WEAK, or STRONG below the
  1%-false-alarm threshold; never "real voice".
- **Calibration data:** In-The-Wild (800 random clips, 400 real and 400 deepfake, Apache-2.0), FLEURS Hindi and English test (300 + 300
  real, CC-BY-4.0), IndicSynth Hindi (500 machine-made, CC-BY-NC-4.0), plus consented team recordings when present
  (`data/audio/team/real|fake/<speaker>_*.ext`). Every clip also as Opus 24 kbps, AAC 64 kbps and 8 kHz telephone copies.
- **Split:** by speaker (sha256 of seed and speaker id, mod 2): dev for thresholds, test for the numbers. FLEURS has no speaker ids,
  so its clips are grouped by sentence id (one sentence is read by 1-3 speakers: a known leak, small).
- **Reproduce:** `python training/voice/download_models.py`, `python training/voice/fetch_data.py`, `python training/voice/calibrate.py`.

### 3. Scam-message classifier (fine-tuned by us)

- **Purpose:** catch scam wording the rules miss (paraphrases, new families). Adds `ML_TEXT_SCAM_LIKE` (L4, WEAK only).
- **Base:** `intfloat/multilingual-e5-small` (MIT). Two variants: frozen encoder + trained linear head, and the whole encoder fine-tuned.
- **Data:** UCI SMS Spam Collection (5,574 English SMS, CC BY 4.0) and our team corpus `data/corpus/team_*.jsonl` (79 scams in 9 Indian
  payment-fraud families and 62 genuine messages, English, Hindi, Hinglish; weighted 5x). `data/kit/` is never used for training.
- **Protocol:** leave one scam family out (the model is scored on a family it never saw); the threshold flags 2% of out-of-fold genuine messages.
- **Shipping rule:** `training/text/decide.py` turns it on only if, on held-out messages, it flags more scams without flagging more
  genuine ones. Otherwise it stays off and this card says why.
- **Reproduce:** `python training/text/fetch.py`, `python training/text/train_classifier.py`, `python training/text/decide.py`.

### 4. Hidden-word check (rules on cleaned text; no learned weights)

- **Purpose:** undo look-alike Cyrillic and Greek letters inside Latin words, zero-width characters, letters spread out with dots or
  spaces (5+ letters count as a trick; "K.Y.C" is joined but not counted), and UPI IDs written as "name (at) bank" or split across lines.
  Then the same payee and word rules run again, and `ML_TEXT_OBFUSCATED` (WEAK) says the message hides words.
- **Not handled on purpose:** Hinglish respellings (undoing them would only memorise our own attack list).
- **Measured:** `docs/results/attack_text.json` (rules alone vs as deployed, on the same kit, so optimistic).
