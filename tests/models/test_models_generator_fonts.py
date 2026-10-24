"""The screenshot generator works on machines where Pillow finds no system font by name (macOS), using the repo's Noto fonts."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_generator():
    spec = importlib.util.spec_from_file_location("make_payment_screens_fonts_test", ROOT / "tools" / "make_payment_screens.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_falls_back_to_the_repo_fonts_when_no_system_font_is_found(tmp_path, monkeypatch):
    gen = load_generator()
    monkeypatch.setattr(gen, "FONT_CANDIDATES", ["no-such-font.ttf"])      # what a Mac looks like to Pillow
    monkeypatch.setattr(gen, "HELD_FONT_CANDIDATES", [])
    monkeypatch.setattr(gen, "EDIT_ONLY_FONTS", [])
    monkeypatch.setattr(gen, "SYSTEM_FONT_PATHS", [])
    found = gen.fonts()
    assert found and all(Path(f).parent == gen.REPO_FONTS for f in found)
    assert all(gen.covers(f) for f in found)
    monkeypatch.setattr(sys, "argv", ["make_payment_screens.py", str(tmp_path), "--n", "12", "--seed", "3"])
    gen.main()
    rows = [json.loads(line) for line in (tmp_path / "meta.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 12 and any(r["edited"] for r in rows)
