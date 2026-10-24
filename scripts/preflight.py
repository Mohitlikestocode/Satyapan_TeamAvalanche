"""Check that everything the demo needs is in place, and say plainly what is missing.

    python scripts/preflight.py                  # checks this machine
    python scripts/preflight.py http://host:8000 # also checks a running server

Exit code 0 when every REQUIRED item passes. Optional items only print a note.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)

rows: list[tuple[str, bool, str, bool]] = []   # name, ok, detail, required


def check(name: str, ok: bool, detail: str = "", required: bool = True) -> None:
    rows.append((name, bool(ok), detail, required))


def main() -> int:
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    home = Path(os.environ.get("SATYAPAN_HOME", ROOT / "var"))
    models = home / "models"
    check("Python 3.11 to 3.12", (3, 11) <= sys.version_info[:2] <= (3, 12), sys.version.split()[0] + " (3.13 breaks RapidOCR: install Tesseract)", required=False)
    for name, rel, need in (
        ("Screenshot tamper model", "tamper.pt", True),
        ("Speech to text (faster-whisper)", "faster-whisper-small/model.bin", True),
        ("Cloned-voice detector", "spectra-aasist3/model.safetensors", True),
        ("Voice thresholds", "voice_calibration.json", True),
        ("Scam-message model", "scam_text/config.json", False),
    ):
        check(name, (models / rel).exists(), str(models / rel), required=need)

    cfg = models / "scam_text" / "config.json"
    if cfg.exists():
        enabled = json.loads(cfg.read_text(encoding="utf-8")).get("enabled")
        check("Scam-message model is switched on", enabled, "config.json enabled=true", required=False)

    try:
        from satyapan.extract import ocr
        check("OCR engine", ocr.engine_name() is not None, str(ocr.engine_name()))
    except Exception as e:  # pragma: no cover
        check("OCR engine", False, str(e)[:80])
    try:
        from satyapan.layers.l2_forensics import audio
        check("ffmpeg for voice notes", audio.ffmpeg_path() is not None, str(audio.ffmpeg_path()))
    except Exception as e:  # pragma: no cover
        check("ffmpeg for voice notes", False, str(e)[:80])
    try:
        from satyapan.integrations import sarvam
        check("Sarvam key (spoken verdicts)", sarvam.configured(), "SARVAM_API_KEY in .env", required=False)
    except Exception as e:  # pragma: no cover
        check("Sarvam key", False, str(e)[:80], required=False)
    check("Telegram bot token", bool(os.environ.get("TELEGRAM_BOT_TOKEN")), "TELEGRAM_BOT_TOKEN in .env", required=False)
    check("Team traffic key (so /impact excludes you)", bool(os.environ.get("INTERNAL_KEY")), "INTERNAL_KEY in .env", required=False)

    try:
        from satyapan.plugins import load_plugins
        from satyapan.service import analyse_text
        load_plugins()
        r = analyse_text("This is CBI. A parcel in your name has drugs and you face arrest. Do not disconnect this video call. Transfer Rs 90,000 to the RBI verification account.", kind="message")
        check("Engine answers a scam message", r.tier.value in ("SUSPICIOUS", "HIGH_RISK", "REGISTRY_HIT"), r.tier.value)
    except Exception as e:  # pragma: no cover
        check("Engine answers a scam message", False, str(e)[:80])

    if len(sys.argv) > 1:
        import httpx
        base = sys.argv[1].rstrip("/")
        try:
            h = httpx.get(base + "/healthz", timeout=10).json()
            check("Server /healthz", h.get("status") == "ok", f"plugins: {', '.join(h.get('plugins', []))}")
            r = httpx.post(base + "/api/v1/check", data={"kind": "message", "text": "Pay a processing fee of Rs 500 to claim your lottery prize"}, timeout=60).json()
            check("Server answers a check", r.get("mode") == "engine", f"{r.get('tier')}")
        except Exception as e:
            check("Server reachable", False, str(e)[:80])

    width = max(len(n) for n, *_ in rows)
    bad = 0
    for name, ok, detail, required in rows:
        mark = "OK  " if ok else ("MISS" if required else "note")
        bad += (not ok) and required
        print(f"[{mark}] {name.ljust(width)}  {detail}")
    print("\nREADY" if not bad else f"\nNOT READY: {bad} required item(s) missing")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
