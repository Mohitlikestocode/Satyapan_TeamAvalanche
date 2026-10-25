"""Read KEY=value lines from ./.env (git-ignored) into the environment, without overriding real variables. Skipped under pytest (including while tests are being collected), so tests never see real keys."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def load_dotenv(path: str = ".env") -> None:
    f = Path(path)
    if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ or not f.is_file():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
