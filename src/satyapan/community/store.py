"""Tables for the community area, the server secret and per-device rate limits.

A device is the random `sp_dev` cookie. It is never stored as given: only HMAC(server secret, cookie) is, so a copy of the database
cannot be used to act as someone else. The same HMAC turns UPI IDs, domains and phone numbers into cluster keys that cannot be
reversed by trying every phone number.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager

from ..store import db

SCHEMA = """
CREATE TABLE IF NOT EXISTS community_posts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, created INTEGER NOT NULL, kind TEXT NOT NULL, lang TEXT NOT NULL,
  excerpt TEXT NOT NULL, tier TEXT NOT NULL, codes TEXT NOT NULL DEFAULT '[]',
  reasons_en TEXT NOT NULL DEFAULT '[]', reasons_hi TEXT NOT NULL DEFAULT '[]',
  entity_kind TEXT, entity_key TEXT, entity_display TEXT, phone_masked TEXT, place TEXT NOT NULL DEFAULT '',
  dev TEXT NOT NULL, status TEXT NOT NULL, parent_id INTEGER, flags TEXT NOT NULL DEFAULT '[]',
  moderated_by TEXT, moderated_at INTEGER
);
CREATE INDEX IF NOT EXISTS community_posts_status ON community_posts(status, parent_id, created);
CREATE INDEX IF NOT EXISTS community_posts_entity ON community_posts(entity_key);
CREATE TABLE IF NOT EXISTS community_votes(
  post_id INTEGER NOT NULL, dev TEXT NOT NULL, ts INTEGER NOT NULL, PRIMARY KEY(post_id, dev)
);
CREATE TABLE IF NOT EXISTS community_abuse(
  id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER NOT NULL, dev TEXT NOT NULL, reason TEXT NOT NULL, ts INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'open', UNIQUE(post_id, dev)
);
CREATE TABLE IF NOT EXISTS community_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, dev TEXT NOT NULL, kind TEXT NOT NULL, ts INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS community_events_lookup ON community_events(dev, kind, ts);
CREATE TABLE IF NOT EXISTS learn_profiles(
  id INTEGER PRIMARY KEY AUTOINCREMENT, created INTEGER NOT NULL, handle TEXT, handle_lc TEXT UNIQUE, recovery_hash TEXT,
  xp INTEGER NOT NULL DEFAULT 0, streak INTEGER NOT NULL DEFAULT 0, best_streak INTEGER NOT NULL DEFAULT 0, last_day TEXT,
  correct INTEGER NOT NULL DEFAULT 0, answered INTEGER NOT NULL DEFAULT 0, invited_by INTEGER, cert_name TEXT
);
CREATE INDEX IF NOT EXISTS learn_profiles_recovery ON learn_profiles(recovery_hash);
CREATE TABLE IF NOT EXISTS learn_devices(dev TEXT PRIMARY KEY, profile_id INTEGER NOT NULL, ts INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS learn_reads(profile_id INTEGER NOT NULL, slug TEXT NOT NULL, ts INTEGER NOT NULL, PRIMARY KEY(profile_id, slug));
CREATE TABLE IF NOT EXISTS learn_rounds(
  id TEXT PRIMARY KEY, profile_id INTEGER NOT NULL, created INTEGER NOT NULL, mode TEXT NOT NULL, qids TEXT NOT NULL,
  day TEXT NOT NULL, finished INTEGER NOT NULL DEFAULT 0, score INTEGER NOT NULL DEFAULT 0, xp INTEGER NOT NULL DEFAULT 0,
  challenge TEXT, lang TEXT NOT NULL DEFAULT 'en'
);
CREATE INDEX IF NOT EXISTS learn_rounds_profile ON learn_rounds(profile_id, created);
CREATE TABLE IF NOT EXISTS learn_answers(
  round_id TEXT NOT NULL, qid TEXT NOT NULL, given TEXT NOT NULL, correct INTEGER NOT NULL, ts INTEGER NOT NULL, PRIMARY KEY(round_id, qid)
);
CREATE TABLE IF NOT EXISTS learn_badges(profile_id INTEGER NOT NULL, badge TEXT NOT NULL, ts INTEGER NOT NULL, PRIMARY KEY(profile_id, badge));
CREATE TABLE IF NOT EXISTS learn_challenges(
  code TEXT PRIMARY KEY, creator_profile INTEGER NOT NULL, qids TEXT NOT NULL, created INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS learn_invites(
  code TEXT NOT NULL, inviter_profile INTEGER NOT NULL, invitee_profile INTEGER NOT NULL, ts INTEGER NOT NULL, PRIMARY KEY(code, invitee_profile)
);
CREATE TABLE IF NOT EXISTS learn_events(id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER NOT NULL, kind TEXT NOT NULL, ts INTEGER NOT NULL);
"""

DEVICE_RE = re.compile(r"^[A-Za-z0-9_\-]{8,64}$")
DAY = 24 * 3600


@contextmanager
def conn() -> Iterator[sqlite3.Connection]:
    """The core connection with this area's tables guaranteed to exist (IF NOT EXISTS, so it is cheap and safe in every test home)."""
    with db.conn() as c:
        c.executescript(SCHEMA)
        yield c


def _secret() -> bytes:
    path = db.home() / "community.key"
    try:
        return path.read_bytes()
    except OSError:
        path.parent.mkdir(parents=True, exist_ok=True)
        key = secrets.token_bytes(32)
        try:
            with open(path, "xb") as f:
                f.write(key)
        except FileExistsError:
            return path.read_bytes()
        return key


def hkey(kind: str, value: str) -> str:
    """Keyed hash of an identifier: stable for clustering, useless to someone who only has the database."""
    return hmac.new(_secret(), f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()[:32]


def valid_device(raw: str | None) -> str | None:
    return raw if raw and DEVICE_RE.match(raw) else None


def dev_hash(raw: str) -> str:
    return hkey("dev", raw)


def take(c: sqlite3.Connection, dev: str, kind: str, limit: int, window: int = DAY) -> bool:
    """Count one write by this device in the last `window` seconds. False (and nothing recorded) when the limit is reached."""
    now = int(time.time())
    n = c.execute("SELECT COUNT(*) FROM community_events WHERE dev=? AND kind=? AND ts>?", (dev, kind, now - window)).fetchone()[0]
    if n >= limit:
        return False
    c.execute("INSERT INTO community_events(dev,kind,ts) VALUES(?,?,?)", (dev, kind, now))
    return True


def left(c: sqlite3.Connection, dev: str, kind: str, limit: int, window: int = DAY) -> int:
    n = c.execute("SELECT COUNT(*) FROM community_events WHERE dev=? AND kind=? AND ts>?", (dev, kind, int(time.time()) - window)).fetchone()[0]
    return max(0, limit - n)
