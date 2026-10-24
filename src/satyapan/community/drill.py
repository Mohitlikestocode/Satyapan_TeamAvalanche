"""Scam Drill: rounds of five questions, scored on the server.

The browser is only ever given `content.public_question` (no answer, no warning flags). Each answer is graded here, recorded once,
and only then is the explanation revealed. XP, streak and badges are updated in the same transaction as the answer.
"""
from __future__ import annotations

import random
import secrets
import time

from . import content, progress, store

ROUND_SIZE = 5
MODES = ("random", "daily", "challenge")
LIMITS = {"challenge": 20}


class DrillError(Exception):
    def __init__(self, key: str, **extra):
        super().__init__(key)
        self.key = key
        self.extra = extra


# ---- choosing questions ---------------------------------------------------------------------------------
def pick_ids(rng: random.Random, seen_order: list[str] | None = None, n: int = ROUND_SIZE) -> list[str]:
    """One genuine message (most messages are fine), one phrase-tapping, one first-step, then fill with anything.
    Questions this learner has not met come first; after that, the ones answered longest ago."""
    rank = {qid: i for i, qid in enumerate(seen_order or [])}
    qs = sorted(content.questions(), key=lambda q: q["id"])
    taken: set[str] = set()

    def prefer(cands: list[dict]) -> dict:
        cands = [q for q in cands if q["id"] not in taken]
        unseen = [q for q in cands if q["id"] not in rank]
        got = rng.choice(unseen) if unseen else min(cands, key=lambda q: (rank[q["id"]], q["id"]))
        taken.add(got["id"])
        return got

    chosen = [prefer([q for q in qs if q["type"] == "scam_or_genuine" and q["answer"] == "genuine"]),
              prefer([q for q in qs if q["type"] == "tap_words"]), prefer([q for q in qs if q["type"] == "first_step"])]
    while len(chosen) < n:
        chosen.append(prefer(qs))
    rng.shuffle(chosen)
    return [q["id"] for q in chosen]


def daily_ids(day: str) -> list[str]:
    """The same five questions for everyone on a given date (IST). Depends only on the date and the question bank."""
    return pick_ids(random.Random(f"satyapan-daily-{day}"))


# ---- rounds -----------------------------------------------------------------------------------------------
def _seen(c, pid: int) -> list[str]:
    return [r["qid"] for r in c.execute("SELECT a.qid FROM learn_answers a JOIN learn_rounds r ON r.id=a.round_id WHERE r.profile_id=? ORDER BY a.ts", (pid,))]


def start(dev: str, mode: str, lang: str, code: str = "", now: int | None = None) -> str:
    """Create (or resume) a round and return its id. Raises DrillError: bad_mode, limit, bad_code, daily_done (extra: round)."""
    if mode not in MODES:
        raise DrillError("bad_mode")
    now = now or int(time.time())
    day = progress.ist_day(now)
    with store.conn() as c:
        pid = progress.ensure(c, dev, now)
        new_learner = c.execute("SELECT COUNT(*) FROM learn_answers a JOIN learn_rounds r ON r.id=a.round_id WHERE r.profile_id=?", (pid,)).fetchone()[0] == 0 \
            and c.execute("SELECT COUNT(*) FROM learn_reads WHERE profile_id=?", (pid,)).fetchone()[0] == 0
        challenge = None
        if mode == "daily":
            r = c.execute("SELECT id, finished FROM learn_rounds WHERE profile_id=? AND mode='daily' AND day=? ORDER BY created DESC LIMIT 1", (pid, day)).fetchone()
            if r and r["finished"]:
                raise DrillError("daily_done", round=r["id"])
            if r:
                return r["id"]
            qids = daily_ids(day)
        elif mode == "challenge":
            challenge = c.execute("SELECT * FROM learn_challenges WHERE code=?", (code.strip().upper(),)).fetchone()
            if not challenge:
                raise DrillError("bad_code")
            qids = challenge["qids"].split(",")
        else:
            qids = pick_ids(random.Random(secrets.randbits(64)), _seen(c, pid))
        if not store.take(c, dev, "round", progress.LIMITS["round"]):
            raise DrillError("limit")
        rid = secrets.token_urlsafe(9)
        c.execute("INSERT INTO learn_rounds(id, profile_id, created, mode, qids, day, challenge, lang) VALUES(?,?,?,?,?,?,?,?)",
                  (rid, pid, now, mode, ",".join(qids), day, challenge["code"] if challenge else None, "hi" if lang == "hi" else "en"))
        if challenge and challenge["creator_profile"] != pid:
            if c.execute("INSERT OR IGNORE INTO learn_invites(code, inviter_profile, invitee_profile, ts) VALUES(?,?,?,?)",
                         (challenge["code"], challenge["creator_profile"], pid, now)).rowcount and new_learner:
                c.execute("UPDATE learn_profiles SET invited_by=? WHERE id=? AND invited_by IS NULL", (challenge["creator_profile"], pid))
            progress.award(c, challenge["creator_profile"], now)
        return rid


def _round(c, rid: str, dev: str):
    r = c.execute("SELECT * FROM learn_rounds WHERE id=?", (rid,)).fetchone()
    if not r or r["profile_id"] != progress.find(c, dev):
        return None
    return r


def state(rid: str, dev: str, lang: str) -> dict | None:
    """Where the learner is in a round: the next unanswered question (public form only), or finished."""
    with store.conn() as c:
        r = _round(c, rid, dev)
        if not r:
            return None
        qids = r["qids"].split(",")
        done = {a["qid"] for a in c.execute("SELECT qid FROM learn_answers WHERE round_id=?", (rid,))}
        nxt = next((q for q in qids if q not in done), None)
        return {"id": rid, "mode": r["mode"], "total": len(qids), "answered": len(done), "finished": bool(r["finished"]),
                "question": content.public_question(content.question(nxt), lang) if nxt else None, "number": len(done) + 1}


def answer(rid: str, dev: str, qid: str, given, lang: str, tz_minutes: int = 330, now: int | None = None) -> dict:
    """Grade, record and reveal. Raises DrillError: no_round, not_in_round, invalid."""
    now = now or int(time.time())
    with store.conn() as c:
        r = _round(c, rid, dev)
        if not r:
            raise DrillError("no_round")
        if qid not in r["qids"].split(","):
            raise DrillError("not_in_round")
        q = content.question(qid)
        prior = c.execute("SELECT given, correct FROM learn_answers WHERE round_id=? AND qid=?", (rid, qid)).fetchone()
        if prior:                                                    # answering twice changes nothing and earns nothing
            return _after(c, r, q, lang, prior["given"], bool(prior["correct"]), 0, [])
        try:
            ok, stored = content.grade(q, given)
        except ValueError as e:
            raise DrillError("invalid") from e
        pid = r["profile_id"]
        c.execute("INSERT INTO learn_answers(round_id, qid, given, correct, ts) VALUES(?,?,?,?,?)", (rid, qid, stored, int(ok), now))
        gained = progress.XP_CORRECT if ok else 0
        progress.add_xp(c, pid, gained, "answer", now)
        c.execute("UPDATE learn_profiles SET answered=answered+1, correct=correct+? WHERE id=?", (int(ok), pid))
        progress.touch_day(c, pid, progress.local_day(now, tz_minutes))
        total = len(r["qids"].split(","))
        answered = c.execute("SELECT COUNT(*) FROM learn_answers WHERE round_id=?", (rid,)).fetchone()[0]
        if answered == total:
            score = c.execute("SELECT COALESCE(SUM(correct),0) FROM learn_answers WHERE round_id=?", (rid,)).fetchone()[0]
            bonus = 0
            if score == total:
                bonus += progress.XP_PERFECT
                progress.add_xp(c, pid, progress.XP_PERFECT, "perfect", now)
            if r["mode"] == "daily":
                bonus += progress.XP_DAILY
                progress.add_xp(c, pid, progress.XP_DAILY, "daily", now)
            gained += bonus
            c.execute("UPDATE learn_rounds SET finished=1, score=?, xp=? WHERE id=?", (score, score * progress.XP_CORRECT + bonus, rid))
        new = progress.award(c, pid, now)
        r = c.execute("SELECT * FROM learn_rounds WHERE id=?", (rid,)).fetchone()
        return _after(c, r, q, lang, stored, ok, gained, new)


def _after(c, r, q: dict, lang: str, given: str, ok: bool, gained: int, new_badges: list[str]) -> dict:
    n = c.execute("SELECT COUNT(*) FROM learn_answers WHERE round_id=?", (r["id"],)).fetchone()[0]
    return {"reveal": content.reveal(q, lang, given, ok), "xp": gained, "badges": new_badges, "finished": bool(r["finished"]),
            "answered": n, "total": len(r["qids"].split(","))}


def answered_view(rid: str, dev: str, qid: str, lang: str) -> dict | None:
    """A question that has already been answered, with its explanation. Unanswered questions are never revealed."""
    with store.conn() as c:
        r = _round(c, rid, dev)
        a = c.execute("SELECT given, correct FROM learn_answers WHERE round_id=? AND qid=?", (rid, qid)).fetchone() if r else None
        if not a:
            return None
        q = content.question(qid)
        return {"question": content.public_question(q, lang), "reveal": content.reveal(q, lang, a["given"], bool(a["correct"])), "finished": bool(r["finished"]),
                "answered": c.execute("SELECT COUNT(*) FROM learn_answers WHERE round_id=?", (rid,)).fetchone()[0], "total": len(r["qids"].split(","))}


def score(rid: str, dev: str, lang: str) -> dict | None:
    """The result of a finished round: score, XP, what to review, and the comparison for challenge rounds."""
    with store.conn() as c:
        r = _round(c, rid, dev)
        if not r or not r["finished"]:
            return None
        rows = {a["qid"]: a for a in c.execute("SELECT * FROM learn_answers WHERE round_id=?", (rid,))}
        items, review = [], []
        for qid in r["qids"].split(","):
            q, a = content.question(qid), rows[qid]
            rv = content.reveal(q, lang, a["given"], bool(a["correct"]))
            items.append({"question": content.public_question(q, lang), "reveal": rv})
            if not a["correct"] and q.get("lesson") and q["lesson"] not in [x["slug"] for x in review]:
                review.append({"slug": q["lesson"], "title": content.lesson(q["lesson"])["title"][lang]})
        out = {"id": rid, "mode": r["mode"], "score": r["score"], "total": len(rows), "xp": r["xp"], "items": items, "review": review, "challenge": None,
               "day": r["day"], "code": None}
        mine = c.execute("SELECT code FROM learn_challenges WHERE creator_round=?", (rid,)).fetchone()
        out["code"] = mine["code"] if mine else None
        code = r["challenge"] or (mine["code"] if mine else None)
        if code:
            out["challenge"] = _compare(c, code, rid)
        return out


def _compare(c, code: str, my_round: str) -> dict | None:
    ch = c.execute("SELECT * FROM learn_challenges WHERE code=?", (code,)).fetchone()
    if not ch:
        return None
    owner = c.execute("SELECT score FROM learn_rounds WHERE id=?", (ch["creator_round"],)).fetchone()
    handle = c.execute("SELECT handle FROM learn_profiles WHERE id=?", (ch["creator_profile"],)).fetchone()["handle"]
    players = [{"handle": x["handle"], "score": x["score"], "me": x["id"] == my_round} for x in c.execute(
        "SELECT r.id, r.score, p.handle FROM learn_rounds r JOIN learn_profiles p ON p.id=r.profile_id WHERE r.challenge=? AND r.finished=1 ORDER BY r.created", (code,))]
    return {"code": code, "creator_score": owner["score"] if owner else None, "creator_handle": handle, "is_creator": ch["creator_round"] == my_round,
            "players": players}


def make_challenge(rid: str, dev: str, now: int | None = None) -> str:
    """Turn a finished round into a challenge code for a relative. Same questions, same order. Raises DrillError: no_round, limit."""
    now = now or int(time.time())
    with store.conn() as c:
        r = _round(c, rid, dev)
        if not r or not r["finished"] or r["mode"] == "challenge":
            raise DrillError("no_round")
        have = c.execute("SELECT code FROM learn_challenges WHERE creator_round=?", (rid,)).fetchone()
        if have:
            return have["code"]
        if not store.take(c, dev, "challenge", LIMITS["challenge"]):
            raise DrillError("limit")
        code = "".join(secrets.choice(progress.CODE_ALPHABET) for _ in range(8))
        c.execute("INSERT INTO learn_challenges(code, creator_profile, creator_round, qids, created) VALUES(?,?,?,?,?)", (code, r["profile_id"], rid, r["qids"], now))
        progress.event(c, r["profile_id"], "family_open", now)       # sending a family challenge counts as asking family to play
        progress.award(c, r["profile_id"], now)
        return code


def challenge_intro(code: str) -> dict | None:
    with store.conn() as c:
        ch = c.execute("SELECT * FROM learn_challenges WHERE code=?", (code.strip().upper(),)).fetchone()
        if not ch:
            return None
        who = c.execute("SELECT handle FROM learn_profiles WHERE id=?", (ch["creator_profile"],)).fetchone()["handle"]
        played = c.execute("SELECT COUNT(*) FROM learn_rounds WHERE challenge=? AND finished=1", (ch["code"],)).fetchone()[0]
        return {"code": ch["code"], "from": who, "played": played}


def daily_status(dev: str | None, day: str | None = None) -> dict:
    day = day or progress.ist_day()
    out = {"day": day, "finished": False, "round": None}
    with store.conn() as c:
        pid = progress.find(c, dev)
        r = c.execute("SELECT id, finished, score FROM learn_rounds WHERE profile_id=? AND mode='daily' AND day=? ORDER BY created DESC LIMIT 1", (pid, day)).fetchone() if pid else None
        if r:
            out.update(finished=bool(r["finished"]), round=r["id"], score=r["score"])
    return out


def certificate(dev: str) -> dict | None:
    """A learner is eligible after reading all lessons and finishing 3 rounds, and must have chosen a public handle."""
    s = progress.summary(dev)
    if not s or not s["certificate_ready"] or not s["handle"]:
        return None
    return {"handle": s["handle"], "level": s["level"], "profile": s["id"]}


def _cert_token(handle: str, pid: int) -> str:
    return f"{handle}-{store.hkey('cert', str(pid))[:12]}"


def issue_certificate(dev: str, now: int | None = None) -> dict | None:
    """The learner's certificate details, once they qualify. The first call records the issue date and gives the Scam-Aware badge."""
    info = certificate(dev)
    if not info:
        return None
    now = now or int(time.time())
    with store.conn() as c:
        pid = info["profile"]
        got = c.execute("SELECT ts FROM learn_events WHERE profile_id=? AND kind='certificate' ORDER BY id LIMIT 1", (pid,)).fetchone()
        if not got:
            progress.event(c, pid, "certificate", now)
            progress.award(c, pid, now)
        return {**info, "token": _cert_token(info["handle"], pid), "issued": got["ts"] if got else now}


def public_certificate(token: str) -> dict | None:
    """Look up a shared certificate by its link token (handle plus a keyed code nobody can guess). Only while the holder still qualifies."""
    handle, _, code = token.rpartition("-")
    if not handle or not code:
        return None
    with store.conn() as c:
        p = c.execute("SELECT id, handle, xp FROM learn_profiles WHERE handle_lc=?", (handle.casefold(),)).fetchone()
        if not p or _cert_token(p["handle"], p["id"]) != f"{p['handle']}-{code}":
            return None
        ev = c.execute("SELECT ts FROM learn_events WHERE profile_id=? AND kind='certificate' ORDER BY id LIMIT 1", (p["id"],)).fetchone()
        if not ev:
            return None
        return {"handle": p["handle"], "level": progress.level_for(p["xp"]), "issued": ev["ts"], "token": token}
