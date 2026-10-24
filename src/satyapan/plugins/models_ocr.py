"""Help the core OCR find Tesseract on Windows and use English + Hindi data from $SATYAPAN_HOME/models/tessdata.

The UB Mannheim installer puts tesseract.exe in Program Files without adding it to PATH, and installs English only.
This only adds the folder to this process's PATH and sets TESSDATA_PREFIX when they exist; it never installs anything.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from ..store import db

WINDOWS_DIRS = [Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tesseract-OCR",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR"]


def setup(registry) -> None:
    if shutil.which("tesseract") is None:
        for d in WINDOWS_DIRS:
            if (d / "tesseract.exe").exists():
                os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")
                break
    data = db.home() / "models" / "tessdata"
    if "TESSDATA_PREFIX" not in os.environ and (data / "eng.traineddata").exists():
        os.environ["TESSDATA_PREFIX"] = str(data)
