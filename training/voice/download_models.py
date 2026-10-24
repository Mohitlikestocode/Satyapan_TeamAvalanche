"""Download the pretrained voice models into $SATYAPAN_HOME/models (default var/models). Never committed.

usage: python training/voice/download_models.py [--only whisper|spectra|second]

- faster-whisper small (Systran/faster-whisper-small, MIT, ~484 MB): local speech to text, Hindi and English.
- Spectra-AASIST3 (lab260/Spectra-AASIST3, Apache-2.0, ~1.28 GB): cloned-voice detector, primary. Only model.safetensors is fetched;
  the wav2vec 2.0 front-end is built from the small facebook/wav2vec2-xls-r-300m config (its weights are inside the Spectra checkpoint).
- MelodyMachine/Deepfake-audio-detection-V2 (Apache-2.0, ~378 MB): second-opinion detector (training data undocumented by its authors).
Prints the SHA-256 of each big file for docs/disclosure/models.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from huggingface_hub import hf_hub_download, snapshot_download  # noqa: E402

from satyapan.store import db  # noqa: E402


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def whisper(dest: Path) -> dict:
    d = dest / "faster-whisper-small"
    snapshot_download("Systran/faster-whisper-small", local_dir=d, allow_patterns=["*.bin", "*.json", "*.txt"])
    return {"faster-whisper-small/model.bin": sha256(d / "model.bin")}


def spectra(dest: Path) -> dict:
    d = dest / "spectra-aasist3"
    d.mkdir(parents=True, exist_ok=True)
    p = hf_hub_download("lab260/Spectra-AASIST3", "model.safetensors", local_dir=d)
    cfg = hf_hub_download("facebook/wav2vec2-xls-r-300m", "config.json", local_dir=d / "_xlsr")
    shutil.copy(cfg, d / "ssl_config.json")
    shutil.rmtree(d / "_xlsr", ignore_errors=True)
    return {"spectra-aasist3/model.safetensors": sha256(Path(p))}


def second(dest: Path) -> dict:
    d = dest / "voice-second"
    snapshot_download("MelodyMachine/Deepfake-audio-detection-V2", local_dir=d, allow_patterns=["*.json", "model.safetensors"])
    return {"voice-second/model.safetensors": sha256(d / "model.safetensors")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["whisper", "spectra", "second"])
    a = ap.parse_args()
    dest = db.home() / "models"
    dest.mkdir(parents=True, exist_ok=True)
    hashes: dict = {}
    if a.only in (None, "whisper"):
        hashes |= whisper(dest)
    if a.only in (None, "spectra"):
        hashes |= spectra(dest)
    if a.only in (None, "second"):
        hashes |= second(dest)
    print(json.dumps(hashes, indent=1))


if __name__ == "__main__":
    main()
