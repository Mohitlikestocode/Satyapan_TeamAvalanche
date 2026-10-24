"""Plumbing test for the tamper model: generate data, train one tiny epoch, install the checkpoint, run the screenshot check.

This checks the pipeline works end to end. It says nothing about accuracy: that is measured by training/tamper/evaluate.py.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
ROOT = Path(__file__).resolve().parents[1]


def test_generate_train_install_and_run(tmp_path):
    data, out = tmp_path / "data", tmp_path / "model"
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_payment_screens.py"), str(data), "--n", "70", "--seed", "2"], check=True, capture_output=True)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    r = subprocess.run([sys.executable, str(ROOT / "training" / "tamper" / "train.py"), "--data", str(data), "--out", str(out / "tamper.pt"),
                        "--epochs", "1", "--size", "96", "56", "--bs", "4", "--workers", "0", "--max-train", "16"],
                       cwd=ROOT / "training" / "tamper", env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    assert (out / "tamper.pt").exists() and (out / "tamper_test_metrics.json").exists()

    from satyapan.layers.l2_forensics import screenshot
    from satyapan.service import analyse_image
    assert screenshot.run(b"x") is None                      # no checkpoint installed yet
    home = Path(os.environ["SATYAPAN_HOME"])
    (home / "models").mkdir(parents=True, exist_ok=True)
    shutil.copy(out / "tamper.pt", home / "models" / "tamper.pt")
    img = (data / "images" / "000000.jpg").read_bytes()
    res = screenshot.run(img)
    assert res is not None and "score" in res.internal
    assert screenshot.run(b"not an image") is None           # unreadable input never crashes
    case = analyse_image(img)
    assert "image" in case.layers_run
