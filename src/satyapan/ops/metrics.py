"""Honest usage metrics: what real people did, with team and test traffic excluded.

Stored in the main SQLite file under tables prefixed metrics_, feedback_, pilot_ and ref_. No IP addresses, no message text, no files.
A visitor is a random first-party device id (cookie `sp_dev`), hashed with a salt before it is stored. One person using two browsers
counts twice, and the public page says so.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from ..store import db

IST = timezone(timedelta(hours=5, minutes=30))

SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, event TEXT NOT NULL, kind TEXT, channel TEXT, tier TEXT, mode TEXT,
  elapsed_ms INTEGER, device TEXT, internal INTEGER NOT NULL DEFAULT 0, ref TEXT, extra TEXT
);
CREATE INDEX IF NOT EXISTS metrics_events_ts ON metrics_events(ts);
CREATE TABLE IF NOT EXISTS metrics_pageviews(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, path TEXT NOT NULL, device TEXT, lang TEXT, ref TEXT,
  internal INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS metrics_pageviews_ts ON metrics_pageviews(ts);
CREATE TABLE IF NOT EXISTS metrics_devices(
  device TEXT PRIMARY KEY, first_ts INTEGER NOT NULL, ref TEXT, internal INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS feedback_answers(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, case_id TEXT NOT NULL, device TEXT NOT NULL, rating INTEGER NOT NULL,
  comment TEXT NOT NULL DEFAULT '', tier TEXT, internal INTEGER NOT NULL DEFAULT 0, UNIQUE(case_id, device)
);
CREATE TABLE IF NOT EXISTS pilot_requests(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, org TEXT NOT NULL, org_type TEXT NOT NULL, city TEXT NOT NULL,
  purpose TEXT NOT NULL DEFAULT '', weekly_checks INTEGER, contact TEXT NOT NULL DEFAULT '', consent INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'new', device TEXT, internal INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS ref_codes(
  code TEXT PRIMARY KEY, name TEXT NOT NULL, city TEXT NOT NULL DEFAULT '', created INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ops_chat_lang(
  chat TEXT PRIMARY KEY, lang TEXT NOT NULL, ts INTEGER NOT NULL
);
"""
_READY: set[str] = set()


@contextmanager
def conn() -> Iterator[sqlite3.Connection]:
    """Main database connection with this module's tables created and WAL mode on (the bot runs as a second process)."""
    with db.conn() as c:
        key = str(db.home())
        if key not in _READY:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(SCHEMA)
            _READY.add(key)
        yield c


def _salt() -> str:
    env = os.environ.get("METRICS_SALT")
    if env:
        return env
    p = db.home() / "keys" / "metrics_salt"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(secrets.token_hex(16))
    return p.read_text().strip()


def hash_id(raw: str | None) -> str | None:
    """Salted hash of a device or chat id. The raw id is never stored."""
    if not raw:
        return None
    return hashlib.sha256((_salt() + ":" + raw).encode()).hexdigest()[:20]


def _now() -> int:
    return int(time.time())


# ---- recording --------------------------------------------------------------------------------------------------
def touch_device(c: sqlite3.Connection, device: str | None, ref: str | None, internal: bool) -> None:
    if device:
        c.execute("INSERT OR IGNORE INTO metrics_devices(device, first_ts, ref, internal) VALUES(?,?,?,?)", (device, _now(), (ref or None), int(internal)))


def record_check(*, kind: str, channel: str = "web", tier: str | None = None, mode: str = "engine", elapsed_ms: int = 0,
                 device_raw: str | None = None, internal: bool = False, ref: str | None = None, hashed: bool = False) -> None:
    device = device_raw if hashed else hash_id(device_raw)
    with conn() as c:
        touch_device(c, device, ref, internal)
        c.execute("INSERT INTO metrics_events(ts,event,kind,channel,tier,mode,elapsed_ms,device,internal,ref) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (_now(), "check", kind, channel, tier, mode, int(elapsed_ms), device, int(internal), ref))


def record_simple(event: str, extra: dict | None = None, device_raw: str | None = None, internal: bool = False) -> None:
    with conn() as c:
        c.execute("INSERT INTO metrics_events(ts,event,device,internal,extra) VALUES(?,?,?,?,?)",
                  (_now(), event, hash_id(device_raw), int(internal), json.dumps(extra or {})))


def clean_path(path: str) -> str:
    """Keep the shape of the URL, drop ids and tokens so the table cannot identify a case."""
    path = (path or "/").split("?")[0].split("#")[0][:120] or "/"
    parts = []
    for seg in path.split("/"):
        parts.append("*" if (len(seg) >= 8 and any(ch.isdigit() for ch in seg) and seg.replace("-", "").replace("_", "").isalnum()) else seg)
    return "/".join(parts) or "/"


def record_pageview(path: str, lang: str, device_raw: str | None, internal: bool, ref: str | None) -> None:
    device = hash_id(device_raw)
    with conn() as c:
        touch_device(c, device, ref, internal)
        c.execute("INSERT INTO metrics_pageviews(ts,path,device,lang,ref,internal) VALUES(?,?,?,?,?,?)",
                  (_now(), clean_path(path), device, lang if lang in ("en", "hi") else "en", ref or None, int(internal)))


# ---- listeners for core events (registered in plugins/traction.py) ----------------------------------------------
def on_check(p: dict) -> None:
    record_check(kind=p.get("kind", "?"), channel=p.get("channel", "web"), tier=p.get("tier"), mode=p.get("mode", "engine"),
                 elapsed_ms=p.get("elapsed_ms", 0), device_raw=p.get("device"), internal=bool(p.get("internal")), ref=p.get("ref"))


def on_dispute(p: dict) -> None:
    record_simple("dispute", {"ref": p.get("ref"), "case_id": bool(p.get("case_id"))}, internal=bool(p.get("internal")))


def on_decision(p: dict) -> None:
    record_simple("decision", {"ref": p.get("ref"), "status": p.get("status")})


def on_delete(p: dict) -> None:
    record_simple("delete", {})


# ---- reading ----------------------------------------------------------------------------------------------------
def _pct(sorted_vals: list[int], q: float) -> int | None:
    if not sorted_vals:
        return None
    return sorted_vals[min(len(sorted_vals) - 1, int(round(q * (len(sorted_vals) - 1))))]


def day_of(ts: int) -> str:
    return datetime.fromtimestamp(ts, IST).strftime("%Y-%m-%d")


def summary() -> dict:
    """Every public number. Internal (team and test) traffic is excluded from all of them."""
    with conn() as c:
        checks = [dict(r) for r in c.execute(
            "SELECT ts,kind,channel,tier,elapsed_ms,device FROM metrics_events WHERE event='check' AND internal=0 AND mode='engine'")]
        views = c.execute("SELECT COUNT(*) n, COUNT(DISTINCT device) d, MIN(ts) first FROM metrics_pageviews WHERE internal=0").fetchone()
        disputes = [json.loads(r["extra"] or "{}") for r in c.execute("SELECT extra FROM metrics_events WHERE event='dispute' AND internal=0")]
        refs = [d["ref"] for d in disputes if d.get("ref")]
        reviews = []
        if refs:
            q = ",".join("?" * len(refs))
            reviews = [dict(r) for r in c.execute(f"SELECT status, created, decided FROM reviews WHERE ref IN ({q})", refs)]
        fb = c.execute("SELECT COUNT(*) n, SUM(rating>=4) good FROM feedback_answers WHERE internal=0").fetchone()
        pilots = c.execute("SELECT COUNT(*) FROM pilot_requests WHERE internal=0").fetchone()[0]
        try:
            posts = c.execute("SELECT COUNT(*) FROM community_posts").fetchone()[0]
        except sqlite3.OperationalError:
            posts = None
    first_candidates = [x for x in ([min((r["ts"] for r in checks), default=None)] + [views["first"]]) if x]
    days_by_device: dict[str, set[str]] = {}
    for r in checks:
        if r["device"]:
            days_by_device.setdefault(r["device"], set()).add(day_of(r["ts"]))
    lat = sorted(r["elapsed_ms"] for r in checks if r["elapsed_ms"] is not None)
    cleared = sum(1 for r in reviews if r["status"] == "not_scam")
    confirmed = sum(1 for r in reviews if r["status"] == "confirmed")
    decided = sorted(r["decided"] - r["created"] for r in reviews if r["decided"] and r["created"])
    return {
        "since": datetime.fromtimestamp(min(first_candidates), IST).strftime("%d %b %Y, %H:%M IST") if first_candidates else None,
        "checks": len(checks),
        "people": len(days_by_device),
        "visitors": views["d"] or 0,
        "pageviews": views["n"] or 0,
        "came_back": sum(1 for d in days_by_device.values() if len(d) >= 2),
        "by_kind": dict(Counter(r["kind"] for r in checks)),
        "by_channel": dict(Counter(r["channel"] for r in checks)),
        "by_tier": dict(Counter(r["tier"] for r in checks if r["tier"])),
        "p50_ms": _pct(lat, 0.5),
        "p95_ms": _pct(lat, 0.95),
        "disputes": len(disputes),
        "cleared": cleared,
        "confirmed": confirmed,
        "pending": max(0, len(reviews) - cleared - confirmed),
        "median_decision_s": _pct(decided, 0.5),
        "feedback_n": fb["n"] or 0,
        "feedback_good": fb["good"] or 0,
        "pilots": pilots,
        "community_posts": posts,
    }


def daily(days: int = 14) -> list[dict]:
    """Checks and people per day for the last `days` days (IST), oldest first, zero-filled."""
    today = datetime.now(IST).date()
    keys = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]
    start = int(datetime.combine(today - timedelta(days=days - 1), datetime.min.time(), IST).timestamp())
    with conn() as c:
        rows = [dict(r) for r in c.execute("SELECT ts, device FROM metrics_events WHERE event='check' AND internal=0 AND mode='engine' AND ts>=?", (start,))]
    checks, people = Counter(), {k: set() for k in keys}
    for r in rows:
        k = day_of(r["ts"])
        checks[k] += 1
        if r["device"] and k in people:
            people[k].add(r["device"])
    return [{"day": k, "checks": checks[k], "people": len(people[k])} for k in keys]


def by_ref() -> list[dict]:
    """Devices and checks attributed to each referral code (first touch), with the shop's name."""
    with conn() as c:
        names = {r["code"]: (r["name"], r["city"]) for r in c.execute("SELECT code,name,city FROM ref_codes")}
        devs = Counter(r["ref"] for r in c.execute("SELECT ref FROM metrics_devices WHERE internal=0 AND ref IS NOT NULL AND ref!=''"))
        checks = Counter(r["ref"] for r in c.execute(
            "SELECT d.ref ref FROM metrics_events e JOIN metrics_devices d ON d.device=e.device WHERE e.event='check' AND e.internal=0 AND e.mode='engine' AND d.ref IS NOT NULL AND d.ref!=''"))
    codes = set(devs) | set(names)
    return sorted(({"code": k, "name": names.get(k, ("(unknown code)", ""))[0], "city": names.get(k, ("", ""))[1], "people": devs[k], "checks": checks[k]} for k in codes),
                  key=lambda r: (-r["checks"], r["code"]))
