# Core change requests from workstream A (models)

## 1. `.gitignore`: the bare `models/` rule hides workstream A's own folders

Line 16 of `.gitignore` is `models/`. It matches every folder named `models`, including `tests/models/` and
`web/templates/ext/models/`, which `docs/WORK_SPLIT.md` gives to workstream A. Weights live in `var/models/`, which `var/` already ignores.

Request: change line 16 from `models/` to `/models/` (root only), or delete it.
Workaround meanwhile: those files were added with `git add -f`; once tracked, git keeps tracking them.

## 1b. `.gitignore`: add `data/corpus/uci_sms/`

The scam-message classifier downloads the public UCI SMS Spam Collection into `data/corpus/uci_sms/`. It must never be committed.
Request: add `data/corpus/uci_sms/` to `.gitignore`. Meanwhile it is excluded locally on the GPU machine (`.git/info/exclude`).
The team-written corpus `data/corpus/team_*.jsonl` is ours and is committed on purpose (reproducibility).

## 2. `tests/test_api.py::test_voice_still_points_to_a_labelled_sample` (informational)

The voice handler (`plugins/models_voice.py`) now gives a real result when the server has ffmpeg and the Whisper model in
`var/models/faster-whisper-small/`. Without them it returns `None`, and the core route falls back to the labelled sample, so this
test still passes in CI. On the demo server (voice stack installed) a voice upload returns `mode: "engine"`.
No change needed now; if the test ever runs with the voice stack installed, it should accept `mode == "engine"` too.

## 2b. Demo server MUST have OCR, or every screenshot is CAN'T TELL (important)

Without an OCR engine `analyse_image` reads no text, the quality gate says "We could not read this file", and the edit sign is
never shown. `rapidocr-onnxruntime` (the `.[ocr]` extra) has **no Python 3.13 build**. Either:
- run the server on Python 3.11 or 3.12 and `pip install -e ".[ocr]"`, or
- install Tesseract (`winget install --id UB-Mannheim.TesseractOCR -e` on Windows, `apt install tesseract-ocr tesseract-ocr-hin` on
  Linux) and `pip install pytesseract`. On Windows, `plugins/models_ocr.py` finds Program Files\Tesseract-OCR by itself and uses the
  English + Hindi data in `var/models/tessdata/` (we send that folder with the models).
Measured on the GPU laptop with Tesseract: see `docs/results/screenshot_system.json`.
Suggested core change (optional): `extract/ocr.py` could also try the newer `rapidocr` package, which supports Python 3.13.

## 3. Core `/check` page: link voice notes to the transcript-first page (optional)

`/models/voice` shows the transcript for the visitor to correct before checking, as the `/check/voice` design promises.
If you want the core check form to use it, point its voice option to `/models/voice`. The plain API path works without this.
