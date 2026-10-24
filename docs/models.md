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

## Results

Not evaluated yet. This section is filled from `docs/results/` as each measurement lands.

## Model cards

To be written per model (purpose, base, data, split, metrics, failures, limits, licence, how to reproduce).
