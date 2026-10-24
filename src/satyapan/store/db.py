"""SQLite store. Holds verdicts, reviews, the known-fake registry and a hash-chained audit log.

Never holds uploaded files or raw message text: only the structured verdict and the payees/links that passed validation.
The database lives in $SATYAPAN_HOME (default ./var), which is git-ignored.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from ..contracts.models import Tier, Verdict

CASE_TTL_S = 24 * 3600          # a result disappears after a day unless the user shared it for review
SHARED_TTL_S = 7 * 24 * 3600

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases(
  id TEXT PRIMARY KEY, created INTEGER NOT NULL, kind TEXT NOT NULL, topic TEXT NOT NULL DEFAULT '',
  tier TEXT NOT NULL, verdicts TEXT NOT NULL, payees TEXT NOT NULL, links TEXT NOT NULL, phones TEXT NOT NULL,
  layers TEXT NOT NULL, share_token TEXT NOT NULL, outcome TEXT NOT NULL DEFAULT '', shared INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS reviews(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT UNIQUE NOT NULL, case_id TEXT, origin TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', shared INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL, first_reviewer TEXT, first_decision TEXT, second_reviewer TEXT, reviewer_note TEXT NOT NULL DEFAULT '',
  created INTEGER NOT NULL, decided INTEGER
);
CREATE TABLE IF NOT EXISTS registry(
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, value TEXT NOT NULL, review_id INTEGER, created INTEGER NOT NULL,
  UNIQUE(kind, value)
);
CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
  target TEXT NOT NULL, detail TEXT NOT NULL, prev TEXT NOT NULL, hash TEXT NOT NULL
);
"""

OPEN = ("needs_review", "awaiting_second", "escalated", "unsure")


def home() -> Path:
    return Path(os.environ.get("SATYAPAN_HOME") or Path(__file__).resolve().parents[3] / "var")


@contextmanager
def conn() -> Iterator[sqlite3.Connection]:
    path = home() / "satyapan.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path, timeout=10)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    try:
        yield c
        c.commit()
    finally:
        c.close()


@dataclass
class StoredCase:
    case_id: str
    kind: str
    tier: Tier
    verdicts: dict[str, Verdict]
    payees: list[dict[str, str]]
    links: list[str]
    phones: list[str]
    layers_run: list[str]
    created: int
    share_token: str
    topic: str = ""
    outcome: str = ""
    shared: bool = False
    review_ref: str | None = None
    extra: dict = field(default_factory=dict)


def _row_to_case(r: sqlite3.Row, review_ref: str | None = None) -> StoredCase:
    return StoredCase(
        case_id=r["id"], kind=r["kind"], tier=Tier(r["tier"]),
        verdicts={k: Verdict.model_validate(v) for k, v in json.loads(r["verdicts"]).items()},
        payees=json.loads(r["payees"]), links=json.loads(r["links"]), phones=json.loads(r["phones"]),
        layers_run=json.loads(r["layers"]), created=r["created"], share_token=r["share_token"], topic=r["topic"],
        outcome=r["outcome"], shared=bool(r["shared"]), review_ref=review_ref,
    )


# ---- cases --------------------------------------------------------------------------------------------------
def save_case(res, topic: str = "") -> StoredCase:
    token = secrets.token_urlsafe(9)
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO cases(id,created,kind,topic,tier,verdicts,payees,links,phones,layers,share_token) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (res.case_id, int(time.time()), res.kind, topic[:80], res.tier.value,
             json.dumps({k: v.model_dump(mode="json") for k, v in res.verdicts.items()}, ensure_ascii=False),
             json.dumps(res.payees), json.dumps(res.links), json.dumps(res.phones), json.dumps(res.layers_run), token),
        )
    return get_case(res.case_id)  # type: ignore[return-value]


def get_case(case_id: str) -> StoredCase | None:
    with conn() as c:
        r = c.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        if not r:
            return None
        rv = c.execute("SELECT ref FROM reviews WHERE case_id=? ORDER BY id DESC LIMIT 1", (case_id,)).fetchone()
        return _row_to_case(r, rv["ref"] if rv else None)


def get_case_by_token(token: str) -> StoredCase | None:
    with conn() as c:
        r = c.execute("SELECT * FROM cases WHERE share_token=?", (token,)).fetchone()
        return _row_to_case(r) if r else None


def delete_case(case_id: str) -> bool:
    """Delete a result and any review the user did not agree to share. Registry entries stay: they hold no user data."""
    with conn() as c:
        c.execute("DELETE FROM reviews WHERE case_id=? AND shared=0 AND status IN ('needs_review','unsure','escalated')", (case_id,))
        n = c.execute("DELETE FROM cases WHERE id=?", (case_id,)).rowcount
    if n:
        audit("user", "delete_case", case_id, "deleted by the user")
    return bool(n)


def purge(now: int | None = None) -> int:
    now = now or int(time.time())
    with conn() as c:
        n = c.execute(
            "DELETE FROM cases WHERE (shared=0 AND created<?) OR (shared=1 AND created<?)", (now - CASE_TTL_S, now - SHARED_TTL_S)
        ).rowcount
        try:
            c.execute("DELETE FROM community_events WHERE ts<?", (now - 2 * 86400,))
        except sqlite3.OperationalError:  # table is created lazily by the community plugin
            pass
    if n:
        audit("system", "purge", "cases", f"{n} expired")
    return n


def set_outcome(case_id: str, outcome: str) -> None:
    with conn() as c:
        c.execute("UPDATE cases SET outcome=? WHERE id=?", (outcome, case_id))


# ---- registry -----------------------------------------------------------------------------------------------
def norm(kind: str, value: str) -> str:
    return value.strip().lower()


def registry_add(kind: str, value: str, review_id: int | None) -> None:
    with conn() as c:
        c.execute("INSERT OR IGNORE INTO registry(kind,value,review_id,created) VALUES(?,?,?,?)", (kind, norm(kind, value), review_id, int(time.time())))


def registry_matches(payees: list[str], hosts: list[str]):
    """Return RegistryMatch objects for payees/domains a pair of reviewers confirmed as a scam."""
    from ..contracts.models import RegistryMatch
    out = []
    with conn() as c:
        for kind, vals in (("payee", payees), ("url", hosts)):
            for v in vals:
                r = c.execute("SELECT id FROM registry WHERE kind=? AND value=?", (kind, norm(kind, v))).fetchone()
                if r:
                    out.append(RegistryMatch(kind=kind, entry_id=r["id"], value=norm(kind, v)))
    return out


def registry_list() -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM registry ORDER BY id DESC")]


# ---- reviews ------------------------------------------------------------------------------------------------
def create_review(case_id: str | None, reason: str, note: str, shared: bool, origin: str = "user_dispute") -> str:
    ref = "R-" + secrets.token_hex(3).upper()
    with conn() as c:
        c.execute("INSERT INTO reviews(ref,case_id,origin,reason,note,shared,status,created) VALUES(?,?,?,?,?,?,?,?)",
                  (ref, case_id, origin, reason[:200], note[:2000], int(shared), "needs_review", int(time.time())))
        if shared and case_id:
            c.execute("UPDATE cases SET shared=1 WHERE id=?", (case_id,))
    audit("user", "dispute", ref, f"case {case_id or '-'}; shared={int(shared)}")
    return ref


def get_review(ref: str) -> dict | None:
    with conn() as c:
        r = c.execute("SELECT * FROM reviews WHERE ref=?", (ref,)).fetchone()
        return dict(r) if r else None


def list_reviews(group: str = "needs_review", q: str = "") -> list[dict]:
    with conn() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM reviews ORDER BY id DESC")]
        out = []
        for r in rows:
            r["case"] = None
            if r["case_id"]:
                cr = c.execute("SELECT * FROM cases WHERE id=?", (r["case_id"],)).fetchone()
                r["case"] = _row_to_case(cr) if cr else None
            out.append(r)
    def grp(r: dict) -> str:
        return {"needs_review": "needs_review", "unsure": "needs_review", "awaiting_second": "awaiting_second",
                "escalated": "escalated"}.get(r["status"], "closed")
    out = [r for r in out if group == "all" or grp(r) == group]
    if q:
        ql = q.lower()
        out = [r for r in out if ql in r["ref"].lower() or (r["case"] and (ql in r["case"].case_id.lower() or any(ql in p["upi"].lower() for p in r["case"].payees)))]
    return out


def counts() -> dict[str, int]:
    out = {"needs_review": 0, "awaiting_second": 0, "escalated": 0, "closed": 0}
    for r in list_reviews("all"):
        k = {"needs_review": "needs_review", "unsure": "needs_review", "awaiting_second": "awaiting_second", "escalated": "escalated"}.get(r["status"], "closed")
        out[k] += 1
    return out


def decide(ref: str, reviewer: str, decision: str, note: str = "") -> dict:
    """Apply a reviewer decision. Adding to the known-fake registry needs two different reviewers to confirm."""
    r = get_review(ref)
    if not r:
        raise KeyError(ref)
    if decision not in ("confirm_scam", "not_scam", "unsure", "escalate"):
        raise ValueError(decision)
    now = int(time.time())
    status = r["status"]
    with conn() as c:
        if decision == "confirm_scam":
            if r["first_decision"] == "confirm_scam" and r["status"] == "awaiting_second":
                if r["first_reviewer"] == reviewer:
                    raise PermissionError("a second, different reviewer must confirm")
                status = "confirmed"
                c.execute("UPDATE reviews SET status=?, second_reviewer=?, reviewer_note=?, decided=? WHERE ref=?", (status, reviewer, note[:1000], now, ref))
            else:
                status = "awaiting_second"
                c.execute("UPDATE reviews SET status=?, first_reviewer=?, first_decision=?, reviewer_note=? WHERE ref=?", (status, reviewer, decision, note[:1000], ref))
        else:
            status = {"not_scam": "not_scam", "unsure": "unsure", "escalate": "escalated"}[decision]
            c.execute("UPDATE reviews SET status=?, first_reviewer=COALESCE(first_reviewer,?), first_decision=COALESCE(first_decision,?), reviewer_note=?, decided=? WHERE ref=?",
                      (status, reviewer, decision, note[:1000], now if status == "not_scam" else None, ref))
    audit(reviewer, f"decision:{decision}", ref, note[:200])
    if status == "confirmed" and r["case_id"]:
        case = get_case(r["case_id"])
        if case:
            for p in case.payees:
                registry_add("payee", p["upi"], r["id"])
            for u in case.links:
                from urllib.parse import urlparse
                h = (urlparse(u).hostname or "").lower()
                if h:
                    registry_add("url", h, r["id"])
            set_outcome(case.case_id, "confirmed_scam")
        audit(reviewer, "registry_add", ref, "two reviewers confirmed")
    if status == "not_scam" and r["case_id"]:
        set_outcome(r["case_id"], "cleared_by_reviewer")
    return get_review(ref) or {}


# ---- audit (hash chain) -------------------------------------------------------------------------------------
def audit(actor: str, action: str, target: str, detail: str = "") -> None:
    with conn() as c:
        last = c.execute("SELECT hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
        prev = last["hash"] if last else "0" * 64
        ts = int(time.time())
        h = hashlib.sha256("|".join([prev, str(ts), actor, action, target, detail]).encode()).hexdigest()
        c.execute("INSERT INTO audit(ts,actor,action,target,detail,prev,hash) VALUES(?,?,?,?,?,?,?)", (ts, actor, action, target, detail, prev, h))


def audit_list(limit: int = 100) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,))]


def audit_verify() -> bool:
    with conn() as c:
        prev = "0" * 64
        for r in c.execute("SELECT * FROM audit ORDER BY id ASC"):
            h = hashlib.sha256("|".join([prev, str(r["ts"]), r["actor"], r["action"], r["target"], r["detail"]]).encode()).hexdigest()
            if r["prev"] != prev or r["hash"] != h:
                return False
            prev = h
    return True


def campaigns(min_cases: int = 1) -> list[dict]:
    """Group cases by payee: how many checks, which links and phones travel with it, review outcomes."""
    groups: dict[str, dict] = {}
    with conn() as c:
        for r in c.execute("SELECT * FROM cases ORDER BY created DESC LIMIT 1000"):
            case = _row_to_case(r)
            for p in case.payees:
                g = groups.setdefault(p["upi"].lower(), {"payee": p["upi"].lower(), "cases": [], "links": set(), "phones": set(), "first": case.created, "last": case.created})
                g["cases"].append(case.case_id)
                g["links"].update(case.links)
                g["phones"].update(case.phones)
                g["first"], g["last"] = min(g["first"], case.created), max(g["last"], case.created)
    reg = {r["value"] for r in registry_list() if r["kind"] == "payee"}
    out = []
    for g in groups.values():
        if len(g["cases"]) >= min_cases:
            out.append({**g, "links": sorted(g["links"]), "phones": sorted(g["phones"]), "count": len(g["cases"]), "in_registry": g["payee"] in reg})
    return sorted(out, key=lambda g: -g["count"])
