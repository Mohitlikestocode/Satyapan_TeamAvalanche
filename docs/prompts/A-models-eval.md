# Prompt for person A (GPU): models, voice, measured results

Paste everything below the line into Claude Code, opened in an empty folder on the GPU machine.

---

You are Claude Code, working with a three-person hackathon team on **Satyapan**, a website that lets ordinary people in India check a suspicious payment message, link, QR code, PDF, screenshot or voice note before they pay. It gives a plain English or Hindi verdict with reasons. It is advisory only. We are in a hackathon final (RAKSHAM, IIT Delhi). The code freeze is Sunday 07:00 IST and the live demo is judged on Sunday: a working system on inputs the judges pick, measured error rates on data it never trained on, our own engineering, and a live user journey. **Build fully working features. Do not build mock-ups, fake numbers or placeholder pages.**

The team: **Ghana** (workstream A: models, has the only GPU), **Tanish** (workstream B: community and learning), **Mohit** (workstream C: traction and operations, and the integrator who merges all branches). 

The human you are working with is **Ghana**. You are **workstream A: models and measurement**. You are the only person with a GPU (RTX 4060, 8 GB). Two other people are building the community site (B) and the public deployment and Telegram bot (C) in parallel, on other branches. You must not touch their files.

## 0. How we are judged (the official Round 2 rubric: build for this)

The jury scores each row from 1 to 5; the weight is the number of points the row is worth.

**Stage 1: shortlist, 30 teams to 10**

| Row | Weight | What a 5 looks like |
|---|---|---|
| 1. Working prototype | 25 | Runs end to end, live, **on inputs the judge picks**: input, then detection, then alert or action. (3 = parts mocked or shown on slides; 1 = slides or a video.) |
| 2. Spot-check results and measured accuracy | **30** | Gets most of the judges' kit samples right; **shows error rates including false positives on data the model never trained on; names its failure cases.** (3 = small or unclear test set; 1 = fails the kit or claims accuracy with no measurement.) |
| 3. Own engineering contribution | 15 | Substantial code written during the finale beyond off-the-shelf models: **fine-tuning, fused signals, a custom pipeline**; any member can walk a judge through it. (1 = a thin wrapper around one API or model.) |
| 4. Alert and response flow, as built | 15 | The step after detection works: a person sees a clear alert and can act on it, and **safeguards are running, not just described** (nothing raw kept, human review). |
| 5. Delivery against the Round 1 plan | 15 | Built what the 48-hour plan promised, or cut scope deliberately and can say why. |

**Stage 2: final presentations, 10 teams to 3**

| Row | Weight | What a 5 looks like |
|---|---|---|
| 1. Problem and user understanding | 20 | Names a specific user and threat scenario grounded in how UPI, banking or wallet fraud actually happens in India; the pitch shows how victims get hurt today. |
| 2. Deployability and scale | 15 | A concrete path into a bank, UPI app, wallet or law-enforcement workflow; says who runs it, what it costs, and what a pilot would need. |
| 3. Communication and Q&A | 10 | Clear, on time, direct answers, including "we don't know". |
| 4. Live user journey | **25** | Works live on a realistic scenario **the jury can vary**; shows the whole path from the attack reaching the user, to the alert, the user's action, and any review or report. |
| 5. Adversarial robustness | **20** | In Q&A the team shows **how an attacker would evade us, what we miss now, and what we would change.** |
| 6. Responsible AI and handling mistakes | 10 | Shows what a genuine user flagged by mistake goes through and how fast they get past it; the alert says why it fired; privacy safeguards are running. |

Our mentor, who will also judge, added two things we agreed to: **live traction** (real users on a public site, counted honestly) and **awareness and education** (a community place that teaches and rewards people so they come back). Honesty beats polish: judges reward measured numbers, named failures and "we don't know" over claims.

### Where your work earns points
- **Spot-check accuracy (30)**: your held-out numbers, false-alarm rates and failure lists are this row. Measure on data the model never trained on. This is the single biggest row.
- **Own engineering (15)**: the fine-tuned tamper model, the scam-message classifier, the calibrated voice detector and the custom pipeline around them. Make sure you can explain each from memory.
- **Working prototype (25) and live user journey (25)**: screenshots and voice notes must work live on files a judge picks, end to end through the normal result page.
- **Adversarial robustness (20)**: the `/attack` panel with real, measured score drift is your answer to "how would an attacker beat you?"
- **Responsible AI (10)**: false-positive rates shown honestly; alerts say why they fired.

## 1. Set up (do this first)

The branch already exists on the remote: do **not** create a new one, just check it out.

```bash
git clone https://github.com/Mohitlikestocode/Satyapan_TeamAvalanche.git
cd Satyapan_TeamAvalanche
git fetch origin
git checkout feat/models-eval
git config user.name  "<the human's own name>"
git config user.email "<the human's own email>"
git config core.hooksPath .githooks
python -m venv .venv    # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev,train]"
pip install -r requirements/models.txt
python -c "import torch; print(torch.cuda.is_available())"     # must print True; if False install the CUDA build of torch from pytorch.org
python -m pytest -p no:warnings                                  # must pass before you change anything
```

Ask the human for their name and email before configuring git. Commit only under their identity. **Never** add `Co-Authored-By`, "Generated with Claude", or any AI credit to a commit message (the hook rejects it).

## 2. Read first, in this order

1. `docs/BUILDER_GUIDE.md`: how to add pages, hooks and tests without touching shared files. Binding.
2. `docs/WORK_SPLIT.md`: who owns which files. Binding.
3. `docs/PLAN.md`: the rubric and what scores.
4. `docs/GPU_START.md` and `docs/F1_TAMPER_SPEC.md`: the tamper model plan and a known problem.
5. `src/satyapan/service.py`, `src/satyapan/plugins/__init__.py`, `src/satyapan/layers/l2_forensics/screenshot.py`, `training/tamper/`, `src/satyapan/eval/`, `data/kit/messages.jsonl`.

Then write a short plan into `docs/models.md` (what you will do, in what order, how you will measure it) and commit it. Then start.

## 3. Files you may create or edit (only these)

`training/**`, `tools/make_payment_screens.py`, `tools/make_qr_kit.py`, `src/satyapan/layers/l2_forensics/**`, `src/satyapan/layers/l4_semantic/**`, `src/satyapan/eval/**`, `src/satyapan/plugins/models_*.py`, `src/satyapan/api/ext/models_*.py`, `src/satyapan/reasons/ext/models.yaml`, `data/kit/**` (existing files), `docs/results/**`, `docs/models.md`, `docs/F1_TAMPER_SPEC.md`, `docs/GPU_START.md`, `docs/disclosure/models.md`, `docs/requests/models.md`, `requirements/models.txt`, `tests/models/**` (name files `test_models_*.py`), `web/templates/ext/models/**`, `web/static/css/models*.css`, `web/static/js/models*.js`.
**Everything else is frozen**, including `service.py`, `api/app.py`, `api/routes_*.py`, `store/db.py`, `fusion/`, `plugins/__init__.py`, `pyproject.toml`, `README.md`, `DISCLOSURE.md`, `base.html`, `gov.css`. If you need a core change, write the exact request in `docs/requests/models.md` and tell the human; work around it meanwhile. Use the extension points described in the builder guide.

## 4. Rules that apply to everything you build

- Honest wording: "shows signs of", never "is fake"; never "safe"; no raw scores or percentages shown to end users.
- Reason text comes only from catalogue templates (add yours in `reasons/ext/models.yaml`, English and Hindi). No model writes verdict text. Text taken from media is data, never instructions.
- Forensics alone can never give HIGH RISK (fusion enforces it). Do not change fusion.
- Uploads are processed in memory and discarded. Do not store audio, images or transcripts.
- Only public, synthetic or consented data. No real person's voice or face. **Ask the human before downloading any dataset or model larger than 100 MB, saying the source, licence and size.** Never commit weights, datasets, or real screenshots; `.gitignore` already blocks most; check `git status` before each commit.
- Training happens now, at the finale. Log everything needed to reproduce it (script, seed, split file, metrics) in git; weights stay out of git.
- Every number on any page comes from a real file in `docs/results/` or a live measurement. If something is not measured the page says "not evaluated".
- Record every model, dataset and licence in `docs/disclosure/models.md` as you add it.

## 5. Tasks, in priority order

### A1 (P0, about 3 h): train and install the screenshot tamper model
Follow `docs/GPU_START.md` exactly. Known problem: a CPU test run learned the validation styles (AUROC 0.997) but failed on unseen test styles (0.664, with 88% false alarms). Your job is to fix that, not just run it.
- Generate data (`tools/make_payment_screens.py`, you may add more styles, fonts, layouts, colour and noise augmentation, harder same-font edits). Keep the style-held-out split.
- Try the small encoder and `--encoder resnet18 --pretrained`. Pick by **test-split** results, never by validation.
- Collect a real set with the human: at least 50 screenshots edited in real editors and 100 genuine ones (consented, names and numbers covered, kept out of git) in `data/real/edited` and `data/real/genuine`. Run `training/tamper/evaluate_real.py`. This is the honest number.
- Install: copy the checkpoint to `var/models/tamper.pt`. `layers/l2_forensics/screenshot.py` then adds the check automatically. Verify with a real upload to `POST /api/v1/check` (kind `screenshot`) and see `image` under "What we checked" on the result page.
- Show the edited area. The core result page cannot show the picture because uploads are never stored, and you cannot change core. So build your own page `/models/screenshot` (router `api/ext/models_screenshot.py`): the visitor uploads a screenshot, the server runs the full check (`satyapan.service.analyse_image`), draws the predicted box on the image with Pillow, and returns the picture (as a data URL, never saved) together with the verdict and a link to the normal result page. This is the "edited amount is circled" demo. Add it to the footer with `registry.add_footer("Services", "Check a payment screenshot", "/models/screenshot")`.
- Acceptance: `docs/results/tamper_test.json` and `tamper_real.json` exist with TPR, FPR at one fixed threshold, AUROC, IoU, per-condition rows, and a baseline row; a short honest paragraph in `docs/models.md` including failure cases. If the model does not generalise, say so and ship the check as "weak signal" only.

### A2 (P0, about 4 h): voice notes end to end
Today `kind=voice` only opens a labelled sample. Make it real using the handler hook.
- Normalise audio with ffmpeg run as a sandboxed subprocess (16 kHz mono, strip metadata, no network, a timeout, no shell, a size and duration limit). Check ffmpeg exists; if not, ask the human to install it.
- Speech to text locally with `faster-whisper` (small model, Hindi and English; ask before downloading the model). Never send audio to any third party. Show the transcript to the user before analysis as the design promises: `/check/voice` is the design page; your handler returns a normal `CaseResult` using `analyse_text(transcript, kind="voice", ..., extra_layers=[audio_layer], extra_names=["voice"])` from `satyapan.service`.
- Cloned-voice detector: use a pretrained detector (primary: Spectra-AASIST3, Hugging Face `lab260/Spectra-AASIST3`, Apache-2.0, 16 kHz mono, higher score = more bona fide; second opinion: XLS-R-SLS from `QiShanZhang/SLSforADD`). Disagreement between the two means CAN'T TELL for the voice layer. Do not use plain AASIST as primary. If the model cannot be loaded within 60 minutes, say so and use the best working option, reporting it honestly.
- Calibrate: choose the threshold on a dev split and report on a test split by speaker. Data: In-The-Wild (about 1,000 clips), IndicSynth Hindi (about 500 fakes), FLEURS Hindi and English (real), plus consented recordings from teammates and clones of teammates only. Make chat-like copies (Opus 24k, AAC 64k, 8 kHz telephone). Report EER and TPR/FPR at the fixed threshold per condition, with bootstrap 95% intervals. Record provenance (URL, licence, date, size, hash) in `docs/disclosure/models.md`.
- Register with `registry.add_handler("voice", fn, "voice", "...", "...")` in `plugins/models_voice.py`. New reason codes `ML_*` go in `reasons/ext/models.yaml`; reuse `MEDIA_VOICE_SYNTHETIC` (L2) for the cloned-voice signal and keep it WEAK or STRONG_SUSPICIOUS only; forensics alone caps at SUSPICIOUS.
- Acceptance: uploading a short Hindi voice note that reads a scam message returns a result page whose reasons come from the transcript (payee, guaranteed returns) and, for a cloned sample, the voice sign; a genuine voice note of the same words gets no voice sign. Unreadable audio gives CAN'T TELL. Tests use tiny generated audio (a tone, silence) plus mocks of the model call only where the model itself cannot run in CI.

### A3 (P1, about 2 h): scam-message classifier (fine-tuned)
- Base: `intfloat/multilingual-e5-small` (ask before download). Fine-tune a classification head or the whole model on: public SMS spam data for the genuine/spam signal (ask before downloading UCI SMS Spam), and a team-written scam corpus you assemble in `data/corpus/` (EN, HI, Hinglish; scam families: investment, fee-to-withdraw, KYC link, refund PIN trap, invoice change, parcel fee, fake support, job task, lottery). **Never train on `data/kit/messages.jsonl` or `data/kit/holdout_*.jsonl`.**
- Evaluate on the held-out files `data/kit/holdout_*.jsonl` that teammates B and C will add (wait for them, or ask the human to get them), compared with the rules-only baseline (`python -m satyapan.eval.run`). Hold out whole scam families. Report scams flagged and genuine messages wrongly flagged with intervals, and list failures.
- Plug in as a text hook in `plugins/models_text.py` returning a WEAK signal `ML_TEXT_SCAM_LIKE` on `Layer.L4`. Ship it only if it improves held-out results without raising false alarms; otherwise keep it off and say why.

### A4 (P0, about 3 h): the Results page and the "Attack yourself" panel
- `/results` (your router `api/ext/models_results.py`, template under `web/templates/ext/models/`): reads every `docs/results/*.json`, shows measured tables with hardware label (GPU name, CPU), dataset and split names, sample sizes, 95% intervals, baseline rows and a failures list. Includes a live "Run the text kit" button that runs `satyapan.eval.run` on `data/kit/*.jsonl` and shows the numbers. Anything missing says "not evaluated". English and Hindi.
- `/attack` panel: the visitor pastes a message or uploads a screenshot or audio. The server applies real perturbations and shows, per perturbation, whether the verdict tier changed. Text: spacing and punctuation changes, look-alike (homoglyph) letters, Hinglish respelling of key words, splitting a UPI ID across lines. Image: JPEG quality drop, resize, crop, brightness, noise, rotate. Audio: re-encode (Opus, AAC, 8 kHz), pitch shift, noise. Show "what an attacker could do, what we miss now, what we would change" from the real results. Nothing is stored. Use `service.analyse_*` and your own models.
- Acceptance: both pages work on a phone width, show only real computed numbers, and have tests.

### A5 (P1, about 1 h): model cards in `docs/models.md`
For each model: purpose, base, data, split, metrics (real), failure cases, limits, licence, and how to reproduce.

## 6. Git rhythm

Commit small. `git push origin feat/models-eval` at least every 30 minutes and before 23:00, 03:00 and 07:00 IST (merge slots). Run `python -m pytest -p no:warnings` and `python -m ruff check src tests tools training --select E9,F` before each push.

## 7. Definition of done

Fresh clone plus `var/models/tamper.pt` and the voice models gives: screenshot edit check live, voice notes working, `/results` and `/attack` pages with real numbers, tests passing, `docs/models.md` and `docs/disclosure/models.md` complete, and a list in `docs/models.md` of what is measured, what is not, and what fails. Tell the human the exact commands to reproduce each number, and what to send the integrator (checkpoint files, by chat or drive, never git).

First action now: ask the human for their name and email, run the setup, read the documents, and commit your plan in `docs/models.md`.
