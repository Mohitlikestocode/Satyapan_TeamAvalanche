# Start the GPU job (tamper model, F1)

Brief for whoever has the GPU. Background and metrics: `docs/F1_TAMPER_SPEC.md`. Plan: `docs/PLAN.md`.

## 1. Set up (about 10 minutes)

```powershell
git clone https://github.com/Mohitlikestocode/Satyapan_TeamAvalanche.git
cd Satyapan_TeamAvalanche
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,train]"
python -c "import torch; print(torch.cuda.is_available())"
```

If the last line prints `False`, install the CUDA build of PyTorch from pytorch.org for your driver, then check again.
Then run `pytest -p no:warnings`. It should pass. (Two OCR tests skip unless you `pip install -e ".[ocr]"`.)

## 2. Make the data (about 10 to 20 minutes, a few GB, not committed)

```powershell
python tools\make_payment_screens.py data\f1 --n 12000 --seed 7 --holdout-styles 2
```

## 3. Train

Run from the training folder (this exact form was tested on CPU):

```powershell
cd training\tamper
$env:PYTHONPATH = "..\..\src"
python train.py --data ..\..\data\f1 --out ..\..\var\models\tamper.pt --epochs 12 --bs 16 --workers 4
```

- Default is the small encoder trained from scratch: no downloads. Optional: `--encoder resnet18 --pretrained` (downloads ImageNet weights once).
- It prints validation numbers each epoch and, at the end, writes `tamper_val_metrics.json`, `tamper_test_metrics.json` and `tamper_train_log.json` next to the checkpoint.
- If 12 epochs are too slow, watch the first epoch's time and scale. This was not timed on a GPU.

## 4. What to expect, and what to watch

A CPU test run (700 images, 10 epochs, small size) learned the *validation* styles well (AUROC 0.997, edited caught 95% at 4% false alarms, localisation IoU 0.68)
but did **not** carry over to the held-out *test* styles: AUROC 0.664, with 88% of genuine screenshots wrongly flagged at the validation threshold.
That is the number that matters, because judges' screenshots will not look like our generator.

So on the GPU run, judge success by the **test** split (held-out layout styles), not by validation:

- If test AUROC is still far below validation: add more styles and fonts to `tools/make_payment_screens.py`, try `--encoder resnet18 --pretrained`, and add random colour, font and layout augmentation.
- Report it either way. A model that fails on unseen styles is a finding for the Results page, not something to hide.
- The threshold in the checkpoint comes from validation styles. Do not re-tune it on the test styles.

## 5. Real screenshots: not collected (team decision)

We do not use anyone's payment data without permission, so there is no real-screenshot set. Report the tamper result as
"synthetic, held-out styles; not evaluated on real phone screenshots". The whole check as deployed is measured with `python training/tamper/evaluate_system.py`.

## 6. Use it in the app

Copy `var\models\tamper.pt` to `var\models\tamper.pt` on the machine that runs the site, restart, and screenshot checks add the edit check automatically
(`layers/l2_forensics/screenshot.py`). With no checkpoint present the check is simply skipped. Never commit the checkpoint, the data or the real screenshots.

## 7. Send back

`tamper_val_metrics.json`, `tamper_test_metrics.json`, `tamper_real.json`, `tamper_train_log.json`, the epoch lines printed in the terminal, and the checkpoint file (by chat or a drive, not git).
