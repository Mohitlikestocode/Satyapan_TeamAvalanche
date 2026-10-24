"""Calibrate the cloned-voice detectors on a dev split and report on a test split, split by speaker.

usage: python training/voice/calibrate.py [--target-fpr 0.05] [--strong-fpr 0.01] [--seed 7]

Data: data/audio/manifest.jsonl (training/voice/fetch_data.py) plus consented team recordings, if present, in
data/audio/team/real/<speaker>_*.<ext> and data/audio/team/fake/<speaker>_*.<ext> (clones of teammates' own voices only).
Every clip is also re-encoded like a chat app (Opus 24k, AAC 64k, 8 kHz telephone) and scored again.

Thresholds: a clip is flagged when its score is below the threshold (higher score = more like a real voice). The threshold is the
one that flags --target-fpr of the REAL voices in the dev split (all conditions pooled); "strong" flags --strong-fpr. They are
fixed before the test split is scored and never changed after.
Writes: var/models/voice_calibration.json (used by the site), docs/results/voice_test.json, docs/results/voice_splits.json.
Scores are cached in data/audio/scores.jsonl so a re-run only scores new clips.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from satyapan.eval.metrics import rate  # noqa: E402
from satyapan.layers.l2_forensics import audio  # noqa: E402
from satyapan.store import db  # noqa: E402

DATA = ROOT / "data" / "audio"
CONDITIONS = ["clean", "opus24k", "aac64k", "tel8k"]
AUDIO_EXT = {".wav", ".ogg", ".opus", ".m4a", ".mp3", ".aac", ".amr", ".flac", ".webm"}


def team_rows() -> list[dict]:
    rows = []
    for label in ("real", "fake"):
        d = DATA / "team" / label
        if not d.exists():
            continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() in AUDIO_EXT:
                rows.append({"file": p.relative_to(DATA).as_posix(), "source": "team_consented", "label": label,
                             "speaker": "team:" + p.stem.split("_")[0].lower(), "lang": "hi/en"})
    return rows


def assign_splits(rows: list[dict], seed: int) -> None:
    """Speaker-disjoint dev/test split, balanced per source: within each source, speakers are ordered by a seeded hash and
    alternate dev, test, dev, ... (a plain hash put both IndicSynth speakers in dev, leaving no Hindi fakes to test)."""
    by_source: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        by_source[r["source"] + ":" + r["label"]].add(r["speaker"])
    split: dict[str, str] = {}
    for spk in by_source.values():
        for i, s in enumerate(sorted(spk, key=lambda s: hashlib.sha256(f"{seed}:{s}".encode()).hexdigest())):
            split.setdefault(s, "dev" if i % 2 == 0 else "test")
    for r in rows:
        r["split"] = split[r["speaker"]]


MAX_SECOND_EER = 0.30  # a second opinion worse than this on the dev split would only veto good detections


def eer(real: np.ndarray, fake: np.ndarray) -> float:
    """Equal error rate with 'flag when score < t': the point where real-flagged rate equals fake-missed rate."""
    if not len(real) or not len(fake):
        return float("nan")
    ts = np.unique(np.concatenate([real, fake]))
    fpr = np.array([(real < t).mean() for t in ts])
    fnr = np.array([(fake >= t).mean() for t in ts])
    i = int(np.argmin(np.abs(fpr - fnr)))
    return float((fpr[i] + fnr[i]) / 2)


def auroc(real: np.ndarray, fake: np.ndarray) -> float:
    """Probability a random fake scores below a random real clip."""
    if not len(real) or not len(fake):
        return float("nan")
    return float((fake[:, None] < real[None, :]).mean() + 0.5 * (fake[:, None] == real[None, :]).mean())


def boot_eer(real: np.ndarray, fake: np.ndarray, n: int = 300, seed: int = 0) -> list[float]:
    if len(real) < 5 or len(fake) < 5:
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    vals = [eer(rng.choice(real, len(real)), rng.choice(fake, len(fake))) for _ in range(n)]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


SCORE_SECONDS = 12  # both detectors only look at the first ~8 s (spectra_aasist3.MAX_WINDOWS, voice_second.MAX_WINDOWS)


def _prepare(r: dict, todo: list[str]) -> list[tuple[str, np.ndarray | None]]:
    """Decode a clip and make its chat-app copies (CPU, ffmpeg). Runs in worker threads."""
    wav = audio.decode((DATA / r["file"]).read_bytes(), max_seconds=SCORE_SECONDS)
    out = []
    for c in todo:
        w = wav
        if wav is not None and c != "clean":
            enc = audio.encode(wav, c)
            w = audio.decode(enc, max_seconds=SCORE_SECONDS) if enc else None
        out.append((c, w))
    return out


def score_all(rows: list[dict], cache_path: Path) -> dict[tuple[str, str], dict]:
    from concurrent.futures import ThreadPoolExecutor
    cache: dict[tuple[str, str], dict] = {}
    if cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            cache[(r["file"], r["cond"])] = r
    jobs = [(r, [c for c in CONDITIONS if (r["file"], c) not in cache]) for r in rows]
    jobs = [j for j in jobs if j[1]]
    t0, done = time.time(), 0
    with cache_path.open("a", encoding="utf-8") as out, ThreadPoolExecutor(6) as ex:
        for (r, _), prepared in zip(jobs, ex.map(lambda j: _prepare(*j), jobs)):
            for c, w in prepared:   # detectors run here, one clip at a time on the GPU
                rec = {"file": r["file"], "cond": c, "primary": None, "second": None}
                if w is not None:
                    vs = audio.score(w, all_detectors=True)
                    rec["primary"], rec["second"] = vs.primary, vs.second
                cache[(r["file"], c)] = rec
                out.write(json.dumps(rec) + "\n")
            done += 1
            if done % 50 == 0:
                out.flush()
                print(f"  scored {done}/{len(jobs)} clips ({time.time() - t0:.0f}s)", flush=True)
    return cache


def threshold(real_scores: np.ndarray, target: float) -> float:
    """Flag when score < t; choose t so that `target` of real voices are flagged."""
    return float(np.quantile(real_scores, target))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-fpr", type=float, default=0.05)
    ap.add_argument("--strong-fpr", type=float, default=0.01)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    if audio.ffmpeg_path() is None:
        sys.exit("ffmpeg not found: install it (winget install Gyan.FFmpeg) and retry")
    if not audio.detectors_available()["primary"]:
        sys.exit("Spectra-AASIST3 not installed: run training/voice/download_models.py")
    manifest = [json.loads(x) for x in (DATA / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = manifest + team_rows()
    assign_splits(rows, a.seed)
    print(f"{len(rows)} clips; dev {sum(r['split'] == 'dev' for r in rows)}, test {sum(r['split'] == 'test' for r in rows)}")
    scores = score_all(rows, DATA / "scores.jsonl")
    dets = ["primary"] + (["second"] if any(s.get("second") is not None for s in scores.values()) else [])

    def arr(split: str, label: str, det: str, cond: str | None = None, source: str | None = None) -> np.ndarray:
        v = [scores[(r["file"], c)][det] for r in rows for c in ([cond] if cond else CONDITIONS)
             if r["split"] == split and r["label"] == label and (source is None or r["source"] == source)
             and scores.get((r["file"], c), {}).get(det) is not None]
        return np.asarray(v, dtype=float)

    cal = {"made": datetime.now(timezone.utc).isoformat(timespec="seconds"), "seed": a.seed, "target_fpr": a.target_fpr, "strong_fpr": a.strong_fpr,
           "rule": "flag when score < threshold; higher score = more like a real voice; thresholds from the dev split, all conditions pooled"}
    for det in dets:
        dev_real = arr("dev", "real", det)
        cal[det] = {"threshold": threshold(dev_real, a.target_fpr), "strong_threshold": threshold(dev_real, a.strong_fpr), "n_dev_real": int(len(dev_real)),
                    "dev_eer": eer(dev_real, arr("dev", "fake", det))}
    excluded = {}
    if "second" in cal and not cal["second"]["dev_eer"] <= MAX_SECOND_EER:
        excluded["second"] = (f"dev-split EER {100 * cal['second']['dev_eer']:.0f}% (limit {100 * MAX_SECOND_EER:.0f}%): it would veto good "
                              "detections, so the site uses the primary detector alone")
    cal["excluded"] = excluded

    def flag(det: str, s: float) -> bool:
        return s < cal[det]["threshold"]

    def combined(file: str, cond: str) -> str | None:
        """'fake', 'real' or 'disagree', exactly like the site (audio.judge)."""
        s = scores.get((file, cond))
        if not s or s["primary"] is None:
            return None
        fp = flag("primary", s["primary"])
        if "second" in dets and "second" not in excluded and s.get("second") is not None and fp != flag("second", s["second"]):
            return "disagree"
        return "fake" if fp else "real"

    res_rows, conditions, failures = [], [], []
    for det in dets:
        name = {"primary": "Spectra-AASIST3 (primary, calibrated)", "second": "Deepfake-audio-detection-V2 (second opinion, calibrated)"}[det]
        tr, tf = arr("test", "real", det), arr("test", "fake", det)
        res_rows.append({"name": name, "baseline": det == "second", "tpr": rate(int((tf < cal[det]["threshold"]).sum()), len(tf)),
                         "fpr": rate(int((tr < cal[det]["threshold"]).sum()), len(tr)), "auroc": auroc(tr, tf), "eer": eer(tr, tf),
                         "eer_ci": boot_eer(tr, tf)})
        for cond in CONDITIONS:
            cr, cf = arr("test", "real", det, cond), arr("test", "fake", det, cond)
            conditions.append({"name": cond, "row": name.split(" (")[0], "tpr": rate(int((cf < cal[det]["threshold"]).sum()), len(cf)),
                               "fpr": rate(int((cr < cal[det]["threshold"]).sum()), len(cr)), "eer": eer(cr, cf)})
        for src in sorted({r["source"] for r in rows}):
            cr, cf = arr("test", "real", det, source=src), arr("test", "fake", det, source=src)
            conditions.append({"name": f"source:{src}", "row": name.split(" (")[0], "tpr": rate(int((cf < cal[det]["threshold"]).sum()), len(cf)) if len(cf) else None,
                               "fpr": rate(int((cr < cal[det]["threshold"]).sum()), len(cr)) if len(cr) else None})
    # the rule the site uses: both must say fake; disagreement says nothing
    test = [r for r in rows if r["split"] == "test"]
    by: dict[str, list[str | None]] = defaultdict(list)
    for r in test:
        for c in CONDITIONS:
            by[r["label"]].append(combined(r["file"], c))
    fake_flag = sum(v == "fake" for v in by["fake"])
    real_flag = sum(v == "fake" for v in by["real"])
    n_fake = sum(v is not None for v in by["fake"])
    n_real = sum(v is not None for v in by["real"])
    disagree = sum(v == "disagree" for v in by["fake"] + by["real"])
    deployed_name = ("As deployed: both detectors must agree (disagreement = says nothing)" if "second" in dets and "second" not in excluded
                     else "As deployed: primary detector alone (second opinion excluded: " + excluded.get("second", "not installed") + ")")
    res_rows.insert(0, {"name": deployed_name, "baseline": False, "tpr": rate(fake_flag, n_fake), "fpr": rate(real_flag, n_real),
                        "disagree_rate": disagree / max(1, n_fake + n_real)})
    for r in test:
        v = combined(r["file"], "clean")
        if r["label"] == "fake" and v != "fake":
            failures.append({"kind": "missed", "text": f"{r['file']} ({r['source']}, clean audio): detector said {v}"})
        elif r["label"] == "real" and v == "fake":
            failures.append({"kind": "false_alarm", "text": f"{r['file']} ({r['source']}, clean audio)"})
    try:
        import torch
        hw = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    except Exception:
        hw = "cpu"
    out = {"schema": 1, "dataset": "In-The-Wild sample, FLEURS hi/en test, IndicSynth Hindi shard 0" + (", consented team recordings" if team_rows() else ""),
           "split": f"test split by speaker ({len(test)} clips x {len(CONDITIONS)} conditions); thresholds fixed on the dev split",
           "held_out": True, "hardware": hw, "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "reproduce": "python training/voice/fetch_data.py && python training/voice/calibrate.py", "rows": res_rows,
           "conditions": conditions, "failures": failures[:60], "calibration": {k: v for k, v in cal.items() if k in dets},
           "excluded": excluded}
    (db.home() / "models").mkdir(parents=True, exist_ok=True)
    site_cal = {k: v for k, v in cal.items() if k not in excluded}  # the site only uses detectors that passed
    (db.home() / "models" / "voice_calibration.json").write_text(json.dumps(site_cal, indent=1), encoding="utf-8")
    res_dir = ROOT / "docs" / "results"
    res_dir.mkdir(parents=True, exist_ok=True)
    (res_dir / "voice_test.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    spk = defaultdict(set)
    for r in rows:
        spk[r["split"]].add(r["speaker"])
    (res_dir / "voice_splits.json").write_text(json.dumps({
        "rule": "speaker-disjoint; within each source and label, speakers ordered by sha256(seed:speaker) alternate dev, test", "seed": a.seed,
        "counts": {s: {"speakers": len(v), "clips": sum(r["split"] == s for r in rows)} for s, v in spk.items()},
        "manifest_sha256": hashlib.sha256((DATA / "manifest.jsonl").read_bytes()).hexdigest()}, indent=1), encoding="utf-8")
    for r in res_rows:
        print(f"{r['name']}: fakes flagged {r['tpr']['k']}/{r['tpr']['n']}, real flagged {r['fpr']['k']}/{r['fpr']['n']}"
              + (f", EER {100 * r['eer']:.1f}%" if r.get("eer") is not None else ""))


if __name__ == "__main__":
    random.seed(0)
    main()
