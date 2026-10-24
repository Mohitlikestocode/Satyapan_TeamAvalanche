"""Profiles, XP, levels, daily streaks, badges, handles, recovery codes and the weekly leaderboard.

A profile is created the first time a device does something that earns progress (marks a lesson read, answers a question, asks family).
It is tied to the hashed device, never to an e-mail or phone number. A recovery code (shown once, stored only as a hash) attaches
another device to the same profile.
"""
from __future__ import annotations

import re
import secrets
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from math import isqrt

from . import content, store
from .profanity import contains_profanity, is_reserved

XP_CORRECT = 10
XP_PERFECT = 20
XP_DAILY = 10
XP_LESSON = 5
IST = timezone(timedelta(hours=5, minutes=30))
HANDLE_RE = re.compile(r"^[A-Za-z0-9_ऀ-ॣ०-९ॱ-ॿ]{3,20}$")
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LIMITS = {"recover": 10, "handle": 5, "round": 30}

LEVELS = [("Beginner", "शुरुआती"), ("Learner", "सीखने वाला"), ("Careful reader", "सावधान पाठक"), ("Scam spotter", "स्कैम पहचानने वाला"),
          ("Scam fighter", "स्कैम से लड़ने वाला"), ("Community guardian", "समुदाय रक्षक")]

# id, English name, Hindi name, English how, Hindi how, test over the stats dict
BADGES = [
    ("first_round", "First round", "पहला राउंड", "Finish one Scam Drill round.", "स्कैम ड्रिल का एक राउंड पूरा करें।", lambda s: s["rounds"] >= 1),
    ("spotted_10", "10 scams spotted", "10 स्कैम पहचाने", "Answer 10 different scam questions correctly.", "10 अलग स्कैम-सवाल सही करें।", lambda s: s["spotted"] >= 10),
    ("perfect", "Perfect round", "पूरे अंक", "Get all 5 right in one round.", "एक राउंड में सारे 5 सही करें।", lambda s: s["perfect"] >= 1),
    ("streak_3", "3-day streak", "3 दिन लगातार", "Learn on 3 days in a row.", "लगातार 3 दिन सीखें।", lambda s: s["best_streak"] >= 3),
    ("streak_7", "7-day streak", "7 दिन लगातार", "Learn on 7 days in a row.", "लगातार 7 दिन सीखें।", lambda s: s["best_streak"] >= 7),
    ("lesson_reader", "Lesson reader", "पाठ पढ़ने वाला", "Mark 3 lessons as read.", "3 पाठ पढ़ा हुआ चिह्नित करें।", lambda s: s["lessons"] >= 3),
    ("all_lessons", "All 12 lessons", "सारे 12 पाठ", "Mark all 12 lessons as read.", "सारे 12 पाठ पढ़ा हुआ चिह्नित करें।", lambda s: s["lessons"] >= 12),
    ("daily", "Daily challenge", "आज की चुनौती", "Finish a daily challenge.", "एक दैनिक चुनौती पूरी करें।", lambda s: s["daily"] >= 1),
    ("family_guardian", "Family Guardian", "परिवार रक्षक", "Open Ask family for a check, so someone you trust can look at it with you.",
     "किसी जाँच के लिए \"परिवार से पूछें\" खोलें, ताकि कोई भरोसेमंद आपके साथ उसे देखे।", lambda s: s["family_open"] >= 1),
    ("scam_watcher", "Scam Watcher", "स्कैम वॉचर", "Have a Scam Watch report published.", "स्कैम वॉच पर आपकी एक रिपोर्ट प्रकाशित हो।", lambda s: s["posts_approved"] >= 1),
    ("challenger", "Challenger", "चुनौती देने वाला", "Someone plays a challenge you sent.", "आपकी भेजी चुनौती कोई और खेले।", lambda s: s["invite_accepted"] >= 1),
    ("scam_aware", "Scam-Aware", "स्कैम-सजग", "Earn the learning certificate.", "सीखने का प्रमाणपत्र पाएँ।", lambda s: s["certified"] >= 1),
]
BADGE_IDS = [b[0] for b in BADGES]


# ---- pure rules (tested directly) -------------------------------------------------------------------------
def level_for(xp: int) -> dict:
    lvl = 1 + isqrt(max(0, xp) // 25)
    lo, hi = 25 * (lvl - 1) ** 2, 25 * lvl ** 2
    en, hi_name = LEVELS[min(lvl, len(LEVELS)) - 1]
    return {"level": lvl, "name_en": en, "name_hi": hi_name, "xp": xp, "into": xp - lo, "span": hi - lo, "next_at": hi}


def local_day(ts: float, tz_minutes: int = 330) -> str:
    """The visitor's calendar date. tz_minutes is minutes east of UTC (India = 330); clamped to real-world offsets."""
    tz_minutes = max(-720, min(840, int(tz_minutes)))
    return datetime.fromtimestamp(ts, timezone(timedelta(minutes=tz_minutes))).strftime("%Y-%m-%d")


def ist_day(ts: float | None = None) -> str:
    return local_day(time.time() if ts is None else ts, 330)


def next_streak(streak: int, last_day: str | None, day: str) -> tuple[int, str | None]:
    """Same day: unchanged. The next day: +1. A gap: starts again at 1. A day before the last one (clock moved back): ignored."""
    if last_day is None:
        return 1, day
    d, last = date.fromisoformat(day), date.fromisoformat(last_day)
    if d == last:
        return streak, last_day
    if d == last + timedelta(days=1):
        return streak + 1, day
    if d < last:
        return streak, last_day
    return 1, day


def week_start(ts: float | None = None) -> int:
    """Monday 00:00 IST of the week containing ts."""
    t = datetime.fromtimestamp(time.time() if ts is None else ts, IST)
    return int((t - timedelta(days=t.weekday())).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())


def validate_handle(raw: str) -> str | None:
    h = (raw or "").strip()
    if not 3 <= len(h) <= 20:
        return "length"
    if not HANDLE_RE.match(h):
        return "chars"
    if re.search(r"\d{7,}", h):
        return "digits"
    if contains_profanity(h):
        return "profanity"
    if is_reserved(h):
        return "reserved"
    return None


def new_code() -> str:
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(12))
    return "SP-" + "-".join(raw[i:i + 4] for i in range(0, 12, 4))


def _norm_code(code: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (code or "").upper())


# ---- profiles ---------------------------------------------------------------------------------------------
def find(c: sqlite3.Connection, dev: str | None) -> int | None:
    if not dev:
        return None
    r = c.execute("SELECT profile_id FROM learn_devices WHERE dev=?", (dev,)).fetchone()
    return r["profile_id"] if r else None


def ensure(c: sqlite3.Connection, dev: str, now: int | None = None) -> int:
    pid = find(c, dev)
    if pid:
        return pid
    now = now or int(time.time())
    pid = c.execute("INSERT INTO learn_profiles(created) VALUES(?)", (now,)).lastrowid
    c.execute("INSERT INTO learn_devices(dev, profile_id, ts) VALUES(?,?,?)", (dev, pid, now))
    return pid


def add_xp(c: sqlite3.Connection, pid: int, amount: int, why: str, now: int | None = None) -> None:
    if amount:
        c.execute("INSERT INTO learn_xp(profile_id, ts, amount, why) VALUES(?,?,?,?)", (pid, now or int(time.time()), amount, why))
        c.execute("UPDATE learn_profiles SET xp=xp+? WHERE id=?", (amount, pid))


def touch_day(c: sqlite3.Connection, pid: int, day: str) -> None:
    r = c.execute("SELECT streak, best_streak, last_day FROM learn_profiles WHERE id=?", (pid,)).fetchone()
    streak, last = next_streak(r["streak"], r["last_day"], day)
    c.execute("UPDATE learn_profiles SET streak=?, best_streak=MAX(best_streak, ?), last_day=? WHERE id=?", (streak, streak, last, pid))


def event(c: sqlite3.Connection, pid: int, kind: str, now: int | None = None) -> None:
    c.execute("INSERT INTO learn_events(profile_id, kind, ts) VALUES(?,?,?)", (pid, kind, now or int(time.time())))


def _stats(c: sqlite3.Connection, pid: int) -> dict:
    p = c.execute("SELECT best_streak FROM learn_profiles WHERE id=?", (pid,)).fetchone()
    done = c.execute("SELECT mode, score FROM learn_rounds WHERE profile_id=? AND finished=1", (pid,)).fetchall()
    right = {r["qid"] for r in c.execute("SELECT a.qid FROM learn_answers a JOIN learn_rounds r ON r.id=a.round_id "
                                          "WHERE r.profile_id=? AND a.correct=1", (pid,))}
    count = lambda kind: c.execute("SELECT COUNT(*) FROM learn_events WHERE profile_id=? AND kind=?", (pid, kind)).fetchone()[0]  # noqa: E731
    return {
        "rounds": len(done), "perfect": sum(1 for r in done if r["score"] >= 5), "daily": sum(1 for r in done if r["mode"] == "daily"),
        "spotted": sum(1 for q in right if (qq := content.question(q)) and content.is_scam_type(qq)), "best_streak": p["best_streak"],
        "lessons": c.execute("SELECT COUNT(*) FROM learn_reads WHERE profile_id=?", (pid,)).fetchone()[0],
        "family_open": count("family_open"), "posts_approved": count("post_approved"), "certified": count("certificate"),
        "invite_accepted": c.execute("SELECT COUNT(*) FROM learn_invites WHERE inviter_profile=?", (pid,)).fetchone()[0],
    }


def award(c: sqlite3.Connection, pid: int, now: int | None = None) -> list[str]:
    """Give every badge whose rule is now met. Returns the badges that are new."""
    have = {r["badge"] for r in c.execute("SELECT badge FROM learn_badges WHERE profile_id=?", (pid,))}
    s = _stats(c, pid)
    new = [b[0] for b in BADGES if b[0] not in have and b[5](s)]
    for b in new:
        c.execute("INSERT OR IGNORE INTO learn_badges(profile_id, badge, ts) VALUES(?,?,?)", (pid, b, now or int(time.time())))
    return new


def mark_read(dev: str, slug: str, day: str, now: int | None = None) -> dict:
    if content.lesson(slug) is None:
        raise KeyError(slug)
    with store.conn() as c:
        pid = ensure(c, dev, now)
        first = c.execute("INSERT OR IGNORE INTO learn_reads(profile_id, slug, ts) VALUES(?,?,?)", (pid, slug, now or int(time.time()))).rowcount == 1
        if first:
            add_xp(c, pid, XP_LESSON, "lesson", now)
        touch_day(c, pid, day)
        return {"first": first, "xp": XP_LESSON if first else 0, "badges": award(c, pid, now)}


def note_event(dev: str, kind: str, day: str | None = None) -> list[str]:
    """Record something that happened elsewhere (family_open, post_approved) and give any badge it unlocks."""
    with store.conn() as c:
        pid = ensure(c, dev)
        event(c, pid, kind)
        return award(c, pid)


def family_open(dev: str) -> list[str]:
    """The visitor opened Ask family for one of their own results. Limited per day so it cannot be farmed."""
    with store.conn() as c:
        if not store.take(c, dev, "family", 10):
            return []
        pid = ensure(c, dev)
        event(c, pid, "family_open")
        return award(c, pid)


def post_approved(dev: str) -> None:
    """Called when a community post of this (hashed) device is published, at once or after moderation."""
    note_event(dev, "post_approved")


# ---- handle and recovery ---------------------------------------------------------------------------------
def set_handle(dev: str, raw: str) -> str | None:
    """Returns None on success, else one of: length chars digits profanity reserved taken limit."""
    err = validate_handle(raw)
    if err:
        return err
    h = raw.strip()
    with store.conn() as c:
        pid = ensure(c, dev)
        if not store.take(c, dev, "handle", LIMITS["handle"]):
            return "limit"
        try:
            c.execute("UPDATE learn_profiles SET handle=?, handle_lc=? WHERE id=?", (h, h.casefold(), pid))
        except sqlite3.IntegrityError:
            return "taken"
    return None


def new_recovery_code(dev: str) -> str:
    """A fresh code. Shown once by the caller; only its hash is kept, and any earlier code stops working."""
    code = new_code()
    with store.conn() as c:
        pid = ensure(c, dev)
        c.execute("UPDATE learn_profiles SET recovery_hash=? WHERE id=?", (store.hkey("recovery", _norm_code(code)), pid))
    return code


def recover(dev: str, code: str) -> str:
    """Attach this device to the profile the code belongs to. Returns ok | bad | limit."""
    with store.conn() as c:
        if not store.take(c, dev, "recover", LIMITS["recover"]):
            return "limit"
        norm = _norm_code(code)
        r = c.execute("SELECT id FROM learn_profiles WHERE recovery_hash=?", (store.hkey("recovery", norm),)).fetchone() if len(norm) >= 14 else None
        if not r:
            return "bad"
        c.execute("INSERT OR REPLACE INTO learn_devices(dev, profile_id, ts) VALUES(?,?,?)", (dev, r["id"], int(time.time())))
        return "ok"


# ---- reading ----------------------------------------------------------------------------------------------
def summary(dev: str | None) -> dict | None:
    """Everything /me shows. None when this device has no progress yet."""
    with store.conn() as c:
        pid = find(c, dev)
        if not pid:
            return None
        p = c.execute("SELECT * FROM learn_profiles WHERE id=?", (pid,)).fetchone()
        have = {r["badge"]: r["ts"] for r in c.execute("SELECT badge, ts FROM learn_badges WHERE profile_id=?", (pid,))}
        reads = {r["slug"] for r in c.execute("SELECT slug FROM learn_reads WHERE profile_id=?", (pid,))}
        rounds = c.execute("SELECT COUNT(*) FROM learn_rounds WHERE profile_id=? AND finished=1", (pid,)).fetchone()[0]
        today = ist_day()
        streak = p["streak"]
        if p["last_day"] and (date.fromisoformat(today) - date.fromisoformat(p["last_day"])).days > 1:
            streak = 0                                    # a missed day ends the streak as soon as it is shown
        wk = c.execute("SELECT COALESCE(SUM(amount),0) FROM learn_xp WHERE profile_id=? AND ts>=?", (pid, week_start())).fetchone()[0]
        posts = [dict(r) for r in c.execute("SELECT id, created, tier, status FROM community_posts WHERE dev=? AND status IN ('approved','pending','held') "
                                            "ORDER BY id DESC LIMIT 10", (dev,))]
        invited = c.execute("SELECT COUNT(*) FROM learn_invites WHERE inviter_profile=?", (pid,)).fetchone()[0]
        return {"id": pid, "handle": p["handle"], "level": level_for(p["xp"]), "streak": streak, "best_streak": p["best_streak"], "last_day": p["last_day"],
                "reads": reads, "rounds": rounds, "answered": p["answered"], "correct": p["correct"], "week_xp": wk, "posts": posts, "invited": invited,
                "has_code": bool(p["recovery_hash"]), "badges": [{"id": b[0], "en": b[1], "hi": b[2], "how_en": b[3], "how_hi": b[4], "got": b[0] in have,
                                                                  "ts": have.get(b[0])} for b in BADGES],
                "certificate_ready": len(reads) >= len(content.lessons()) and rounds >= 3}


def leaderboard(me_dev: str | None = None, limit: int = 20) -> dict:
    """This week's public handles by XP earned since Monday (IST). Ties: total XP, then handle."""
    ws = week_start()
    with store.conn() as c:
        rows = c.execute("SELECT p.id, p.handle, p.xp, COALESCE(SUM(x.amount),0) AS week FROM learn_profiles p JOIN learn_xp x ON x.profile_id=p.id AND x.ts>=? "
                         "WHERE p.handle IS NOT NULL GROUP BY p.id HAVING week>0 ORDER BY week DESC, p.xp DESC, p.handle_lc ASC", (ws,)).fetchall()
        me = find(c, me_dev)
    ranked = [{"rank": i + 1, "handle": r["handle"], "week": r["week"], "xp": r["xp"], "me": r["id"] == me, "level": level_for(r["xp"])["level"]} for i, r in enumerate(rows)]
    return {"top": ranked[:limit], "me": next((r for r in ranked if r["me"] and r["rank"] > limit), None), "since": ws, "total": len(ranked)}


def stats() -> dict:
    """Counts for reporting real growth. Everything comes from the database."""
    with store.conn() as c:
        one = lambda q: c.execute(q).fetchone()[0]  # noqa: E731
        return {"learners": one("SELECT COUNT(*) FROM learn_profiles"), "rounds_finished": one("SELECT COUNT(*) FROM learn_rounds WHERE finished=1"),
                "answers": one("SELECT COUNT(*) FROM learn_answers"), "lessons_read": one("SELECT COUNT(*) FROM learn_reads"),
                "challenges_sent": one("SELECT COUNT(*) FROM learn_challenges"), "invites_accepted": one("SELECT COUNT(*) FROM learn_invites"),
                "new_learners_via_invite": one("SELECT COUNT(*) FROM learn_profiles WHERE invited_by IS NOT NULL"),
                "certificates": one("SELECT COUNT(*) FROM learn_events WHERE kind='certificate'"), "handles": one("SELECT COUNT(*) FROM learn_profiles WHERE handle IS NOT NULL")}
