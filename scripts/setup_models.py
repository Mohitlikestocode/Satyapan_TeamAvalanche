"""Put the models where the site looks for them, and say plainly what is still missing.

usage:
  python scripts/setup_models.py             # report only: which model files are present, and what each one switches on
  python scripts/setup_models.py --install   # copy our small trained files (models_release/) and download the public voice models

What this does NOT fetch: the fine-tuned scam-message encoder (about 470 MB, over GitHub's file limit). Rebuild it with
python training/text/fetch.py && python training/text/train_classifier.py --mode full (steps in README section 7).
Without it the site still runs and says which checks it could not do.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from satyapan.store import db  # noqa: E402

HOME = db.home() / "models"
RELEASE = ROOT / "models_release"

# (path under var/models, what it switches on, how it is obtained)
WANTED = [
    ("tamper.pt", "payment-screenshot tamper check (our own U-Net)", "models_release/ (in git)"),
    ("voice_calibration.json", "thresholds for the cloned-voice check", "models_release/ (in git)"),
    ("faster-whisper-small/model.bin", "voice notes: speech to text", "download (public, ~480 MB)"),
    ("spectra-aasist3/model.safetensors", "voice notes: cloned-voice detector", "download (public, ~1.3 GB)"),
    ("scam_text/encoder/model.safetensors", "scam-message classifier (fine-tuned e5)", "train it: README section 7"),
    ("scam_text/head.pt", "scam-message classifier head", "train it: README section 7"),
]


def report() -> int:
    missing = 0
    print(f"model folder: {HOME}\n")
    for rel, what, how in WANTED:
        ok = (HOME / rel).exists()
        missing += not ok
        print(f"  {'OK     ' if ok else 'MISSING'}  {rel:<40} {what}" + ("" if ok else f"   <- {how}"))
    print(f"\n{len(WANTED) - missing}/{len(WANTED)} present. Missing checks are skipped by the site and named on every result.")
    return missing


def install() -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    for f in sorted(RELEASE.glob("*")):
        if f.is_file():
            shutil.copy2(f, HOME / f.name)
            print("copied", f.name)
    py = sys.executable
    subprocess.run([py, str(ROOT / "training/voice/download_models.py"), "--only", "whisper"], check=False)
    subprocess.run([py, str(ROOT / "training/voice/download_models.py"), "--only", "spectra"], check=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--install", action="store_true", help="copy models_release/ and download the public voice models")
    a = ap.parse_args()
    if a.install:
        install()
        print()
    report()


if __name__ == "__main__":
    main()
