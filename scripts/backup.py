"""Make a consistent copy of the SQLite database, keep the newest N.

usage: python scripts/backup.py DEST_DIR [--keep 7] [--home /path/to/var]
Uses SQLite's online backup, so it is safe while the site is running. Run it from cron, for example hourly:
  0 * * * *  docker compose -f deploy/docker-compose.yml exec -T app python scripts/backup.py /data/backups --keep 24
The signing key is NOT copied here: back it up separately and keep it private ($SATYAPAN_HOME/keys).
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import time
from pathlib import Path


def backup(home: Path, dest: Path, keep: int) -> Path:
    src = home / "satyapan.db"
    if not src.exists():
        raise SystemExit(f"no database at {src}")
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / f"satyapan-{time.strftime('%Y%m%d-%H%M%S')}.db"
    a = sqlite3.connect(src)
    b = sqlite3.connect(out)
    with b:
        a.backup(b)
    a.close()
    b.close()
    old = sorted(dest.glob("satyapan-*.db"))[:-keep] if keep > 0 else []
    for p in old:
        p.unlink()
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dest", type=Path)
    ap.add_argument("--keep", type=int, default=7)
    ap.add_argument("--home", type=Path, default=Path(os.environ.get("SATYAPAN_HOME", "var")))
    a = ap.parse_args()
    print("wrote", backup(a.home, a.dest, a.keep))


if __name__ == "__main__":
    main()
