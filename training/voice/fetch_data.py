"""Fetch the public voice data used to calibrate and test the cloned-voice detectors. Nothing here is committed.

usage: python training/voice/fetch_data.py [--itw-per-label 600] [--seed 7] [--only itw|fleurs|indicsynth]

- In-The-Wild (Müller et al. 2022, Apache-2.0): real and deepfake speech of public figures from the web. The official zip is 8.2 GB;
  we read only its directory and a random sample of clips with HTTP range requests (no full download). Speakers are recorded,
  so the split is by speaker.
- FLEURS (google/fleurs, CC-BY-4.0): read speech, Hindi (hi_in) and English (en_us), test split only. Real voices.
- IndicSynth (vdivyasharma/IndicSynth, CC-BY-NC-4.0): machine-made Hindi speech, one parquet shard of 107.
Output: data/audio/<source>/... plus data/audio/manifest.jsonl (file, source, label real|fake, speaker, lang, sha256).
Provenance (URL, licence, date, size, hash) is printed for docs/disclosure/models.md.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import random
import struct
import tarfile
import time
import urllib.request
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "audio"
ITW_URL = "https://owncloud.fraunhofer.de/index.php/s/JZgXh0JEAF0elxa/download"
FLEURS = "https://huggingface.co/datasets/google/fleurs/resolve/main/data/{lang}/{part}"
INDICSYNTH = "https://huggingface.co/datasets/vdivyasharma/IndicSynth/resolve/main/Hindi/train-00000-of-00107.parquet"


class HTTPRangeFile(io.RawIOBase):
    """A read-only, seekable file over HTTP range requests, so zipfile can read single members of a remote zip."""

    def __init__(self, url: str):
        self.url, self.pos = url, 0
        req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            self.size = int(r.headers["Content-Range"].split("/")[1])
        self.fetched = 0

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, off: int, whence: int = 0) -> int:
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def read(self, n: int = -1) -> bytes:
        if self.pos >= self.size:
            return b""
        end = self.size - 1 if n is None or n < 0 else min(self.size - 1, self.pos + n - 1)
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        self.pos += len(data)
        self.fetched += len(data)
        return data

    def readinto(self, b) -> int:
        data = self.read(len(b))
        b[: len(data)] = data
        return len(data)


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _range(url: str, start: int, end: int, tries: int = 5) -> bytes:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read()
        except (OSError, TimeoutError):
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def _member(url: str, info: zipfile.ZipInfo) -> bytes:
    """One zip member with a single range request: local header + data (+ slack for the local extra field)."""
    blob = _range(url, info.header_offset, info.header_offset + 30 + len(info.filename.encode()) + 1024 + info.compress_size)
    name_len, extra_len = struct.unpack("<HH", blob[26:30])
    start = 30 + name_len + extra_len
    raw = blob[start:start + info.compress_size]
    if info.compress_type == zipfile.ZIP_STORED:
        return raw
    if info.compress_type == zipfile.ZIP_DEFLATED:
        return zlib.decompress(raw, -15)
    raise ValueError(f"unsupported compression {info.compress_type}")


def fetch_itw(per_label: int, rnd: random.Random) -> list[dict]:
    f = HTTPRangeFile(ITW_URL)
    z = zipfile.ZipFile(io.BufferedReader(f, buffer_size=1 << 18))
    meta_name = next(n for n in z.namelist() if n.endswith("meta.csv"))
    meta = list(csv.DictReader(io.StringIO(z.read(meta_name).decode("utf-8"))))
    prefix = meta_name[: -len("meta.csv")]
    infos = {i.filename: i for i in z.infolist()}
    by_label: dict[str, list[dict]] = {"bona-fide": [], "spoof": []}
    for r in meta:
        by_label.setdefault(r["label"], []).append(r)
    dest = OUT / "itw"
    dest.mkdir(parents=True, exist_ok=True)
    picks = [(label, r) for label, items in by_label.items() for r in rnd.sample(items, min(per_label, len(items)))]

    def one(item) -> dict | None:
        label, r = item
        p = dest / r["file"]
        if not p.exists():
            try:
                p.write_bytes(_member(ITW_URL, infos[prefix + r["file"]]))
            except Exception as e:  # a clip we cannot fetch is skipped and reported, never invented
                print(f"  skipped {r['file']}: {e}", flush=True)
                return None
        return {"file": f"itw/{r['file']}", "source": "in_the_wild", "label": "real" if label == "bona-fide" else "fake",
                "speaker": "itw:" + r["speaker"], "lang": "en", "sha256": sha256(p.read_bytes())}

    rows = []
    with ThreadPoolExecutor(8) as ex:
        for i, row in enumerate(ex.map(one, picks), 1):
            if row:
                rows.append(row)
            if i % 100 == 0:
                print(f"  In-The-Wild {i}/{len(picks)}", flush=True)
    print(f"In-The-Wild: {len(meta)} clips listed, {len(rows)} fetched of {len(picks)} picked, zip {f.size / 1e9:.1f} GB "
          f"({ITW_URL}, Apache-2.0, {datetime.now(timezone.utc):%Y-%m-%d})")
    return rows


def fetch_fleurs(lang: str, n: int, rnd: random.Random) -> list[dict]:
    tsv = urllib.request.urlopen(FLEURS.format(lang=lang, part="test.tsv"), timeout=120).read().decode("utf-8")
    meta = {}
    for line in tsv.splitlines():
        cols = line.split("\t")
        if len(cols) >= 7:
            meta[cols[1]] = {"sentence": cols[0], "gender": cols[6]}
    tar_bytes = urllib.request.urlopen(FLEURS.format(lang=lang, part="audio/test.tar.gz"), timeout=600).read()
    dest = OUT / "fleurs" / lang
    dest.mkdir(parents=True, exist_ok=True)
    rows = []
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as t:
        members = [m for m in t.getmembers() if m.isfile() and m.name.endswith(".wav")]
        for m in rnd.sample(members, min(n, len(members))):
            name = Path(m.name).name
            data = t.extractfile(m).read()
            (dest / name).write_bytes(data)
            info = meta.get(name, {})
            # FLEURS has no speaker ids; sentence id is the closest grouping (one sentence is read by 1-3 speakers)
            rows.append({"file": f"fleurs/{lang}/{name}", "source": f"fleurs_{lang}", "label": "real",
                         "speaker": f"fleurs:{lang}:{info.get('sentence', name)}", "lang": lang[:2], "sha256": sha256(data)})
    print(f"FLEURS {lang}: {len(rows)} clips from test split, archive {len(tar_bytes) / 1e6:.0f} MB sha256 {sha256(tar_bytes)[:16]}… "
          f"(google/fleurs, CC-BY-4.0)")
    return rows


def fetch_indicsynth(n: int, rnd: random.Random) -> list[dict]:
    import pyarrow.parquet as pq
    blob = urllib.request.urlopen(INDICSYNTH, timeout=1200).read()
    table = pq.read_table(io.BytesIO(blob))
    cols = table.column_names
    audio_col = next(c for c in cols if "audio" in c.lower())
    spk_col = next((c for c in cols if "speaker" in c.lower() or "voice" in c.lower()), None)
    idx = rnd.sample(range(table.num_rows), min(n, table.num_rows))
    dest = OUT / "indicsynth"
    dest.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in idx:
        a = table.column(audio_col)[i].as_py()
        data = a["bytes"] if isinstance(a, dict) else a
        name = f"is_{i:06d}.wav"
        (dest / name).write_bytes(data)
        spk = str(table.column(spk_col)[i].as_py()) if spk_col else f"row{i}"
        rows.append({"file": f"indicsynth/{name}", "source": "indicsynth_hi", "label": "fake", "speaker": f"indicsynth:{spk}",
                     "lang": "hi", "sha256": sha256(data)})
    print(f"IndicSynth Hindi: {len(rows)} of {table.num_rows} rows from shard 0 ({len(blob) / 1e6:.0f} MB, sha256 {sha256(blob)[:16]}…, "
          f"CC-BY-NC-4.0); columns {cols}")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--itw-per-label", type=int, default=400)
    ap.add_argument("--fleurs-n", type=int, default=300)
    ap.add_argument("--indicsynth-n", type=int, default=500)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--only", choices=["itw", "fleurs", "indicsynth"])
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = OUT / "manifest.jsonl"
    rows = [json.loads(x) for x in manifest.read_text(encoding="utf-8").splitlines()] if manifest.exists() else []
    have = {r["source"] for r in rows}

    def save() -> None:  # after every source, so one failing source does not lose the others
        manifest.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    jobs = []
    if a.only in (None, "fleurs"):
        jobs += [(f"fleurs_{lang}", lambda lang=lang: fetch_fleurs(lang, a.fleurs_n, random.Random(f"{a.seed}:{lang}"))) for lang in ("hi_in", "en_us")]
    if a.only in (None, "indicsynth"):
        jobs.append(("indicsynth_hi", lambda: fetch_indicsynth(a.indicsynth_n, random.Random(f"{a.seed}:is"))))
    if a.only in (None, "itw"):
        jobs.append(("in_the_wild", lambda: fetch_itw(a.itw_per_label, random.Random(f"{a.seed}:itw"))))
    for source, job in jobs:
        if source in have:
            continue
        try:
            rows.extend(job())
            save()
        except Exception as e:
            print(f"{source}: FAILED ({e}); re-run this script to retry it", flush=True)
    print(f"manifest: {len(rows)} clips -> {manifest}")


if __name__ == "__main__":
    main()
