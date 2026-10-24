"""Fetch what the scam-message classifier needs. Nothing here is committed.

usage: python training/text/fetch.py
- intfloat/multilingual-e5-small (MIT, ~471 MB) -> $SATYAPAN_HOME/models/e5-small/
- UCI SMS Spam Collection (CC BY 4.0, ~200 KB) -> data/corpus/uci_sms/SMSSpamCollection
Prints sha256 hashes for docs/disclosure/models.md.
"""
from __future__ import annotations

import hashlib
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from huggingface_hub import snapshot_download  # noqa: E402

from satyapan.store import db  # noqa: E402

UCI = "https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip"


def main() -> None:
    d = db.home() / "models" / "e5-small"
    snapshot_download("intfloat/multilingual-e5-small", local_dir=d,
                      allow_patterns=["model.safetensors", "*.json", "sentencepiece.bpe.model", "tokenizer*"])
    print("e5-small model.safetensors sha256", hashlib.sha256((d / "model.safetensors").read_bytes()).hexdigest())
    out = ROOT / "data" / "corpus" / "uci_sms"
    out.mkdir(parents=True, exist_ok=True)
    blob = urllib.request.urlopen(UCI, timeout=120).read()
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        (out / "SMSSpamCollection").write_bytes(z.read("SMSSpamCollection"))
    print("UCI SMS Spam zip sha256", hashlib.sha256(blob).hexdigest(), f"({len(blob) / 1e3:.0f} KB, {UCI}, CC BY 4.0)")


if __name__ == "__main__":
    main()
