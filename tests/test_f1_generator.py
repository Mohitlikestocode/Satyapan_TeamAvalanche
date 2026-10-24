import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def test_generator_writes_images_masks_and_style_split(tmp_path):
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_payment_screens.py"), str(tmp_path), "--n", "30", "--seed", "3"], check=True, capture_output=True)
    rows = [json.loads(line) for line in (tmp_path / "meta.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 30
    train_styles = {r["style"] for r in rows if r["split"] == "train"}
    other_styles = {r["style"] for r in rows if r["split"] != "train"}
    assert not train_styles & other_styles                      # held-out styles never appear in training
    for r in rows:
        mask = Image.open(tmp_path / "masks" / f"{r['id']}.png")
        has_edit = mask.getextrema()[1] > 0
        assert has_edit == r["edited"]                           # a mask exists exactly when the image was edited
        assert (tmp_path / "images" / f"{r['id']}.jpg").exists()
