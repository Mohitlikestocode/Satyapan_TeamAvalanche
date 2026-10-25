# Small trained files we ship

| File | What it is |
|---|---|
| `tamper.pt` | our own U-Net payment-screenshot tamper model (3.7 MB), trained by `training/tamper/train.py` on synthetic screenshots |
| `voice_calibration.json` | thresholds for the cloned-voice check, made by `training/voice/calibrate.py` |

`python scripts/setup_models.py --install` copies them into `var/models/`. The big files (voice models, fine-tuned scam-message encoder) are not in git: see README section 7.
