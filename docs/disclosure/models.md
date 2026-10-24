# Disclosure: models

List every model, dataset, API, library with its licence and how it is used. Update it when you add one.
Weights and data are never committed. Hashes let anyone check they have the same files.

## Models

| Item | Source | Licence | Used for | Trained/changed by us? |
|---|---|---|---|---|
| Screenshot tamper model (small U-Net or ResNet-18 U-Net) | Our code: `src/satyapan/layers/l2_forensics/tamper_net.py`, `training/tamper/` | ours | Finding edited areas in payment screenshots (`MEDIA_IMAGE_EDITED`, WEAK or STRONG, L2) | **Trained by us at the finale** on our own synthetic screens only. Checkpoint `var/models/tamper.pt`, never committed |
| ResNet-18 ImageNet weights (`IMAGENET1K_V1`) | torchvision | BSD-3-Clause (torchvision); ImageNet weights for research use | Starting point for the ResNet-18 tamper encoder (`--encoder resnet18 --pretrained`) | Fine-tuned by us (whole network) |
| faster-whisper small | Hugging Face `Systran/faster-whisper-small` (CTranslate2 conversion of OpenAI Whisper small) | MIT | Local speech-to-text for voice notes, Hindi and English. Audio never leaves our server | No. `model.bin` sha256 `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671` |
| Spectra-AASIST3 | Hugging Face `lab260/Spectra-AASIST3` (`model.safetensors`; network code vendored in `spectra_aasist3_net.py`) | Apache-2.0 | Primary cloned-voice detector (`MEDIA_VOICE_SYNTHETIC`, L2, WEAK or STRONG only) | Not retrained. **Threshold calibrated by us** on our dev split (`training/voice/calibrate.py`). Vendored code changed only to build the wav2vec2 front-end from its config. sha256 `327762caab3106ecee5f26b821ccdc6ab1fe34906a3e7042f416c87927df2088` |
| wav2vec2 XLS-R 300M config (`config.json` only, no weights) | Hugging Face `facebook/wav2vec2-xls-r-300m` | Apache-2.0 | Shape of Spectra-AASIST3's front-end | No |
| Deepfake-audio-detection-V2 | Hugging Face `MelodyMachine/Deepfake-audio-detection-V2` (wav2vec2-base classifier) | Apache-2.0 | Second-opinion voice detector: if it disagrees with the primary, we say nothing about the voice | Not retrained; threshold calibrated by us. **Its authors do not document its training data.** sha256 `997d9ce59e63151d5e444a6fa7c863986d0e56d515f67321bd705ac3b01bc38c` |
| XLS-R-SLS (`QiShanZhang/SLSforADD`) | GitHub | **none stated** | Not used | Considered as the second opinion; dropped because the repository has no licence, its weights are only on Google Drive or Baidu, and it needs fairseq plus another 1.2 GB checkpoint |

## Datasets

| Item | Source | Licence | Used for | Size and hash |
|---|---|---|---|---|
| Synthetic payment screens | `tools/make_payment_screens.py` (seed 7, 20,000 images, 8 layout families, held-out layouts L5 (val) and L6, L7 (test), held-out fonts) | ours | Training, validation and test of the tamper model | ~594 MB in `data/f1/`, not committed. Split and hash: `docs/results/tamper_splits.json` |
| Real payment screenshots | not collected | n/a | **Not used.** The team decided not to collect real payment screenshots: we do not use anyone's payment data without permission. Screenshot results are synthetic, held-out styles; not evaluated on real phone screenshots | none |
| In-The-Wild (Müller et al., 2022) | `https://owncloud.fraunhofer.de/index.php/s/JZgXh0JEAF0elxa/download` (official zip, 8.2 GB); we fetch a random sample of clips by HTTP range requests | Apache-2.0 | Calibration (dev speakers) and test (other speakers) of the voice detectors | Sample listed with sha256 per clip in `data/audio/manifest.jsonl` (not committed) |
| FLEURS Hindi (hi_in) and English (en_us), test split | Hugging Face `google/fleurs` | CC-BY-4.0 | Real voices for calibration and test | Archive hashes printed by `training/voice/fetch_data.py` |
| IndicSynth Hindi, shard 0 of 107 | Hugging Face `vdivyasharma/IndicSynth` | **CC-BY-NC-4.0** (non-commercial) | Machine-made Hindi voices for calibration and test. Evaluation only; a commercial pilot would need another source | Shard hash printed by `training/voice/fetch_data.py` |
| Our message kit | `data/kit/messages.jsonl` (team-written) | ours | Development checks of the rules (optimistic). **Never used to train any model** | in git |
| Held-out messages | `data/kit/holdout_*.jsonl`, written by teammates who did not read the rules | ours | Test only | in git |

## Libraries added by workstream A

| Library | Licence | Used for |
|---|---|---|
| PyTorch, torchvision (CUDA 12.8 build) | BSD-3-Clause | Tamper model training and inference; voice detectors |
| faster-whisper, CTranslate2 | MIT | Local speech-to-text |
| transformers, safetensors, huggingface_hub | Apache-2.0 | Loading the voice detectors and downloading models |
| pyarrow | Apache-2.0 | Reading the IndicSynth parquet shard |
| ffmpeg (system program, run as a locked-down subprocess) | LGPL/GPL | Decoding voice notes to 16 kHz mono; chat-app re-encoding for calibration and the attack panel |
