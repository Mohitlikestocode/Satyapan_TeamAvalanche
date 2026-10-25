"""Scam Watch: reports from visitors, shown in a feed with the engine's verdict.

Flow of a report: the raw text lives in memory for the length of one request. The real engine analyses it; the sanitiser builds the
only text that is ever stored; the row keeps the sanitised excerpt, tier, reason text (from the catalogue, both languages), a keyed
hash of the payee/domain/phone for linking duplicates, a masked display of it, and the HMAC of the device. Raw text, full phone
numbers and the device cookie are never written.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

from ..contracts.models import Tier
from ..reasons.render import catalogue
from ..service import analyse_text
from ..store import db
from . import store
from .sanitise import MAX_INPUT, Sanitised, sanitise, sanitise_place

KINDS = ("message", "link", "upi", "call", "qr")
LANGS = ("en", "hi", "mix", "other")
ABUSE_REASONS = ("spam", "personal_info", "not_a_scam", "abusive", "other")
PLATFORMS = ("whatsapp", "sms", "telegram", "social", "youtube", "call", "email", "web", "other")
INTENTS = ("warn", "ask")
COMMENT_KINDS = ("saw", "opinion", "tip")
LIMITS = {"post": 5, "vote": 30, "abuse": 10, "comment": 20, "helpful": 60}
MAX_COMMENT = 500
PAGE_SIZE = 10
WEEK = 7 * 24 * 3600
PUBLISH_TIERS = {Tier.SUSPICIOUS.value, Tier.HIGH_RISK.value, Tier.REGISTRY_HIT.value}
HOLD_AFTER_REPORTS = 3
VISIBLE = ("approved",)


class SubmitError(Exception):
    """A problem the visitor can fix. `key` selects the bilingual message in the template."""

    def __init__(self, key: str):
        super().__init__(key)
        self.key = key


@dataclass
class Submitted:
    post_id: int
    status: str                 # approved | pending
    linked_to: int | None       # the post this report was added to, when the same payee/link/number was reported before
    already_counted: bool = False


def detect_lang(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "en"
    share = sum(1 for c in letters if "ऀ" <= c <= "ॿ") / len(letters)
    return "hi" if share > 0.5 else "mix" if share > 0.05 else "en"


def tier_label(tier: str, lang: str) -> str:
    return catalogue()["tiers"][tier]["headline"]["hi" if lang == "hi" else "en"]


TIER_CLASS = {"HIGH_RISK": "r", "REGISTRY_HIT": "r", "SUSPICIOUS": "a", "CANT_TELL": "n", "NO_RED_FLAGS": "g"}


def _prepare_for_engine(raw: str, kind: str) -> str:
    t = raw.strip()
    if kind == "link" and "://" not in t:
        t = "http://" + t
    return t


def _hide_ids(texts: list[str], sanitised: Sanitised, found_vpas: list[str]) -> list[str]:
    """Reason text may quote the payee: swap each real UPI ID for its masked display form."""
    pairs = {e.value: e.display for e in sanitised.entities if e.kind == "upi"}
    out = []
    for t in texts:
        for vpa in set(found_vpas) | set(pairs):
            disp = pairs.get(vpa.lower()) or pairs.get(vpa)
            if disp:
                t = re.sub(re.escape(vpa), disp, t, flags=re.I)
        out.append(t)
    return out


def _cluster_devs(c, since: int = 0) -> dict[int, set[str]]:
    """For every visible post that is not itself a duplicate: the distinct devices that reported or confirmed it since `since`."""
    roots: dict[int, set[str]] = {}
    for r in c.execute("SELECT id, dev, created, parent_id, status FROM community_posts WHERE status IN ('approved','held')"):
        if r["parent_id"] is None:
            roots.setdefault(r["id"], set())
            if r["created"] >= since:
                roots[r["id"]].add(r["dev"])
    for r in c.execute("SELECT id, dev, created, parent_id FROM community_posts WHERE parent_id IS NOT NULL AND status='approved'"):
        if r["parent_id"] in roots and r["created"] >= since:
            roots[r["parent_id"]].add(r["dev"])
    for r in c.execute("SELECT post_id, dev, ts FROM community_votes"):
        if r["post_id"] in roots and r["ts"] >= since:
            roots[r["post_id"]].add(r["dev"])
    return roots


def _view(r, lang: str, total: dict[int, set[str]] | None = None, weekly: dict[int, set[str]] | None = None,
          talk: dict[int, int] | None = None) -> dict:
    reasons = json.loads(r["reasons_hi" if lang == "hi" else "reasons_en"])
    return {
        "id": r["id"], "created": r["created"], "kind": r["kind"], "lang": r["lang"], "excerpt": r["excerpt"], "tier": r["tier"],
        "tier_class": TIER_CLASS.get(r["tier"], "n"), "tier_label": tier_label(r["tier"], lang), "reasons": reasons,
        "entity_kind": r["entity_kind"], "entity": r["entity_display"], "place": r["place"], "status": r["status"],
        "parent_id": r["parent_id"], "sightings": len(total.get(r["id"], ())) if total is not None else None,
        "weekly": len(weekly.get(r["id"], ())) if weekly is not None else None,
        "platform": r["platform"], "intent": r["intent"], "from_check": bool(r["case_ref"]),
        "comments": (talk or {}).get(r["id"], 0), "author": None, "can_vote": False, "mine": False, "_dev": r["dev"],
    }


# ---- reporting ---------------------------------------------------------------------------------------------
def submit(raw: str, kind: str, lang: str, place: str, dev: str, consent: bool, platform: str = "", intent: str = "warn",
           case_id: str = "") -> Submitted:
    """Validate, analyse, sanitise and store one report. `dev` is the already-hashed device. Raises SubmitError for fixable problems.

    intent "warn" is a report of a scam; "ask" is a question to the community ("is this real?"). A question is published once it is clean,
    whatever the engine says, and shows the engine's verdict with its usual "not a guarantee" wording.
    case_id: a result the visitor shared from the Check page. Its verdict (tier and reasons) is used as it was made; the text still goes
    through the sanitiser, and the case's own text was never kept, so the visitor's words are what is shown."""
    if intent not in INTENTS:
        intent = "warn"
    platform = platform if platform in PLATFORMS else ""
    if kind not in KINDS:
        raise SubmitError("bad_kind")
    if not consent:
        raise SubmitError("consent")
    raw = (raw or "").strip()
    if len(raw) > MAX_INPUT:
        raise SubmitError("too_long")
    s = sanitise(raw)
    if len(s.excerpt) < 8 and kind not in ("upi", "link"):
        raise SubmitError("too_short")
    if kind == "link" and not s.first("domain"):
        raise SubmitError("need_link")
    if kind == "upi" and not s.first("upi"):
        raise SubmitError("need_upi")
    if not s.excerpt:
        raise SubmitError("too_short")
    lang = lang if lang in LANGS else detect_lang(raw)

    shared = db.get_case(case_id) if case_id else None
    if shared:                                              # a result shared from the Check page: use the verdict it already has
        tier, verdicts = shared.tier, shared.verdicts
        found_vpas = [p["upi"] for p in shared.payees]
    else:
        res = analyse_text(_prepare_for_engine(raw, kind), kind="link" if kind == "link" else "message")
        tier, verdicts = res.tier, res.verdicts
        found_vpas = [p["upi"] for p in res.payees]
    reasons_en = _hide_ids(verdicts["en"].reasons_text, s, found_vpas)
    reasons_hi = _hide_ids(verdicts["hi"].reasons_text, s, found_vpas)
    codes = verdicts["en"].reason_codes

    publish = s.clean and (intent == "ask" or tier.value in PUBLISH_TIERS)
    status = "approved" if publish else "pending"
    flags = list(s.flags) + (["from_check"] if shared else [])
    if intent == "warn" and tier.value not in PUBLISH_TIERS:
        flags.append("engine_" + tier.value.lower())
    ent = s.primary()
    key = store.hkey(ent.kind, ent.value) if ent else None
    phone = s.first("phone")

    with store.conn() as c:
        if store.left(c, dev, "post", LIMITS["post"]) == 0:
            raise SubmitError("rate_limit")
        root = None
        if key and intent == "warn":
            root = c.execute("SELECT id, dev FROM community_posts WHERE entity_key=? AND parent_id IS NULL AND intent='warn' "
                             "AND status IN ('approved','held') ORDER BY id LIMIT 1", (key,)).fetchone()
        if root and dev in _cluster_devs(c).get(root["id"], set()):
            return Submitted(root["id"], "approved", root["id"], already_counted=True)
        store.take(c, dev, "post", LIMITS["post"])
        cur = c.execute(
            "INSERT INTO community_posts(created,kind,lang,excerpt,tier,codes,reasons_en,reasons_hi,entity_kind,entity_key,entity_display,"
            "phone_masked,place,dev,status,parent_id,flags,platform,intent,case_ref) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (int(time.time()), kind, lang, s.excerpt, tier.value, json.dumps(codes), json.dumps(reasons_en, ensure_ascii=False),
             json.dumps(reasons_hi, ensure_ascii=False), ent.kind if ent else None, key, ent.display if ent else None,
             phone.display if phone else None, sanitise_place(place), dev, status, root["id"] if root else None, json.dumps(flags),
             platform, intent, 1 if shared else 0))
        new_id = cur.lastrowid
    if status == "approved":
        from . import progress
        progress.post_approved(dev)
    return Submitted(new_id, status, root["id"] if root else None)


# ---- reading -----------------------------------------------------------------------------------------------
def comment_counts(c) -> dict[int, int]:
    return {r["post_id"]: r["n"] for r in c.execute("SELECT post_id, COUNT(*) n FROM community_comments WHERE status='approved' GROUP BY post_id")}


def feed(lang: str, kind: str = "", post_lang: str = "", sort: str = "new", page: int = 1, size: int = PAGE_SIZE, platform: str = "",
         intent: str = "", dev: str | None = None) -> dict:
    where, args = ["status='approved'", "parent_id IS NULL"], []
    if platform in PLATFORMS:
        where.append("platform=?"), args.append(platform)
    if intent in INTENTS:
        where.append("intent=?"), args.append(intent)
    if kind in KINDS:
        where.append("kind=?"), args.append(kind)
    if post_lang in LANGS:
        where.append("lang=?"), args.append(post_lang)
    with store.conn() as c:
        rows = c.execute(f"SELECT * FROM community_posts WHERE {' AND '.join(where)} ORDER BY id DESC", args).fetchall()
        total = _cluster_devs(c)
        weekly = _cluster_devs(c, int(time.time()) - WEEK)
        talk = comment_counts(c)
    views = [_view(r, lang, total, weekly, talk) for r in rows]
    if sort == "week":
        views = [v for v in views if v["weekly"]]
        views.sort(key=lambda v: (-v["weekly"], -v["id"]))
    elif sort == "talk":
        views = [v for v in views if v["comments"]]
        views.sort(key=lambda v: (-v["comments"], -v["id"]))
    n = len(views)
    pages = max(1, -(-n // size))
    page = min(max(1, page), pages)
    shown = views[(page - 1) * size: page * size]
    with store.conn() as c:
        names = _names(c, {v["_dev"] for v in shown})
    for v in shown:
        d = v.pop("_dev")
        v["author"], v["mine"] = names.get(d), bool(dev) and d == dev
        v["can_vote"] = bool(dev) and dev not in total.get(v["id"], set())
    for v in views:
        v.pop("_dev", None)
    return {"posts": shown, "total": n, "page": page, "pages": pages}


def trending(lang: str, limit: int = 5) -> list[dict]:
    """Payees, links and numbers reported by the most different devices in the last 7 days."""
    cut = int(time.time()) - WEEK
    with store.conn() as c:
        weekly = _cluster_devs(c, cut)
        rows = {r["id"]: r for r in c.execute("SELECT * FROM community_posts WHERE status='approved' AND parent_id IS NULL AND entity_key IS NOT NULL AND intent='warn'")}
    ranked = sorted(((len(devs), pid) for pid, devs in weekly.items() if devs and pid in rows), key=lambda x: (-x[0], -x[1]))
    return [{"id": pid, "entity": rows[pid]["entity_display"], "entity_kind": rows[pid]["entity_kind"], "count": n,
             "tier_class": TIER_CLASS.get(rows[pid]["tier"], "n")} for n, pid in ranked[:limit]]


def stats() -> dict:
    with store.conn() as c:
        total = _cluster_devs(c)
        week = _cluster_devs(c, int(time.time()) - WEEK)
        pending = c.execute("SELECT COUNT(*) FROM community_posts WHERE status='pending'").fetchone()[0]
        held = c.execute("SELECT COUNT(*) FROM community_posts WHERE status='held'").fetchone()[0]
        abuse = c.execute("SELECT COUNT(*) FROM community_abuse WHERE status='open'").fetchone()[0]
        comments = c.execute("SELECT COUNT(*) FROM community_comments WHERE status='approved'").fetchone()[0]
        c_pending = c.execute("SELECT COUNT(*) FROM community_comments WHERE status IN ('pending','held')").fetchone()[0]
        c_abuse = c.execute("SELECT COUNT(*) FROM community_comment_abuse WHERE status='open'").fetchone()[0]
    return {"posts": sum(1 for pid in total), "sightings": sum(len(d) for d in total.values()),
            "sightings_week": sum(len(d) for d in week.values()), "pending": pending, "held": held, "abuse_open": abuse + c_abuse,
            "comments": comments, "comments_waiting": c_pending}


def get(post_id: int, lang: str, dev: str | None = None, staff: bool = False) -> dict | None:
    """One post with its sightings, other versions of the same scam and what this device may do. None when it must not be shown."""
    with store.conn() as c:
        r = c.execute("SELECT * FROM community_posts WHERE id=?", (post_id,)).fetchone()
        if not r or r["status"] in ("deleted", "rejected", "removed"):
            return None
        mine = bool(dev) and r["dev"] == dev
        if r["status"] != "approved" and not (mine or staff):
            return None
        root_id = r["parent_id"] or r["id"]
        total = _cluster_devs(c)
        v = _view(r, lang, total, None, comment_counts(c))
        v.pop("_dev", None)
        v["author"] = _names(c, {r["dev"]}).get(r["dev"])
        v["mine"], v["root_id"] = mine, root_id
        v["comments"] = comment_counts(c).get(root_id, 0)
        v["sightings"] = len(total.get(root_id, ()))
        v["voted"] = bool(dev) and c.execute("SELECT 1 FROM community_votes WHERE post_id=? AND dev=?", (root_id, dev)).fetchone() is not None
        v["can_vote"] = bool(dev) and r["status"] == "approved" and dev not in total.get(root_id, set())
        v["others"] = [{"excerpt": o["excerpt"], "lang": o["lang"], "created": o["created"]} for o in c.execute(
            "SELECT excerpt, lang, created FROM community_posts WHERE parent_id=? AND status='approved' ORDER BY id DESC LIMIT 3", (root_id,))]
        v["reported"] = bool(dev) and c.execute("SELECT 1 FROM community_abuse WHERE post_id=? AND dev=?", (post_id, dev)).fetchone() is not None
        v["flags"] = json.loads(r["flags"])
        return v


# ---- reactions ---------------------------------------------------------------------------------------------
def vote(post_id: int, dev: str) -> str:
    """"I saw this too". One per device per scam. Returns ok | already | own | limit | missing."""
    with store.conn() as c:
        r = c.execute("SELECT id, parent_id, status FROM community_posts WHERE id=?", (post_id,)).fetchone()
        if not r or r["status"] != "approved":
            return "missing"
        root = r["parent_id"] or r["id"]
        if dev in _cluster_devs(c).get(root, set()):
            has_vote = c.execute("SELECT 1 FROM community_votes WHERE post_id=? AND dev=?", (root, dev)).fetchone()
            return "already" if has_vote else "own"
        if not store.take(c, dev, "vote", LIMITS["vote"]):
            return "limit"
        c.execute("INSERT INTO community_votes(post_id,dev,ts) VALUES(?,?,?)", (root, dev, int(time.time())))
        return "ok"


def report_abuse(post_id: int, dev: str, reason: str) -> str:
    """Ask for a post to be looked at. Privacy reports hide the post at once; others hide it after three different devices report it."""
    reason = reason if reason in ABUSE_REASONS else "other"
    with store.conn() as c:
        r = c.execute("SELECT id, status FROM community_posts WHERE id=?", (post_id,)).fetchone()
        if not r or r["status"] in ("deleted", "rejected", "removed"):
            return "missing"
        if c.execute("SELECT 1 FROM community_abuse WHERE post_id=? AND dev=?", (post_id, dev)).fetchone():
            return "already"
        if not store.take(c, dev, "abuse", LIMITS["abuse"]):
            return "limit"
        c.execute("INSERT INTO community_abuse(post_id,dev,reason,ts) VALUES(?,?,?,?)", (post_id, dev, reason, int(time.time())))
        open_n = c.execute("SELECT COUNT(*) FROM community_abuse WHERE post_id=? AND status='open'", (post_id,)).fetchone()[0]
        if r["status"] == "approved" and (reason == "personal_info" or open_n >= HOLD_AFTER_REPORTS):
            c.execute("UPDATE community_posts SET status='held' WHERE id=?", (post_id,))
            _promote(c, post_id)
            held = True
        else:
            held = False
    if held:
        db.audit("system", "community_hold", f"post:{post_id}", f"hidden after abuse reports ({reason})")
    return "ok"


# ---- removal and moderation --------------------------------------------------------------------------------
def _promote(c, post_id: int) -> None:
    """When a post that other reports were linked to disappears, the oldest of them becomes the new main post."""
    kids = [r["id"] for r in c.execute("SELECT id FROM community_posts WHERE parent_id=? AND status='approved' ORDER BY id", (post_id,))]
    if not kids:
        return
    new = kids[0]
    c.execute("UPDATE community_posts SET parent_id=NULL WHERE id=?", (new,))
    c.execute("UPDATE community_posts SET parent_id=? WHERE parent_id=? AND id!=?", (new, post_id, new))
    c.execute("UPDATE community_votes SET post_id=? WHERE post_id=?", (new, post_id))


def _wipe_comments(c, post_id: int) -> None:
    ids = [r["id"] for r in c.execute("SELECT id FROM community_comments WHERE post_id=?", (post_id,))]
    for cid in ids:
        c.execute("DELETE FROM community_comment_votes WHERE comment_id=?", (cid,))
        c.execute("DELETE FROM community_comment_abuse WHERE comment_id=?", (cid,))
    c.execute("DELETE FROM community_comments WHERE post_id=?", (post_id,))


def _wipe(c, post_id: int, status: str, actor: str | None = None) -> None:
    _wipe_comments(c, post_id)
    c.execute("UPDATE community_posts SET status=?, excerpt='', reasons_en='[]', reasons_hi='[]', entity_display=NULL, entity_key=NULL, "
              "phone_masked=NULL, place='', moderated_by=?, moderated_at=? WHERE id=?", (status, actor, int(time.time()), post_id))


def delete_own(post_id: int, dev: str) -> bool:
    """The author's device can delete a post: the text is wiped, not just hidden."""
    with store.conn() as c:
        r = c.execute("SELECT id, dev, status, parent_id FROM community_posts WHERE id=?", (post_id,)).fetchone()
        if not r or r["dev"] != dev or r["status"] in ("deleted", "rejected", "removed"):
            return False
        if r["parent_id"] is None:
            _promote(c, post_id)
            c.execute("DELETE FROM community_votes WHERE post_id=?", (post_id,))
        _wipe(c, post_id, "deleted")
        c.execute("DELETE FROM community_abuse WHERE post_id=?", (post_id,))
        return True


def moderation_queue() -> dict:
    with store.conn() as c:
        pending = [dict(r) for r in c.execute("SELECT * FROM community_posts WHERE status='pending' ORDER BY id")]
        held = [dict(r) for r in c.execute("SELECT * FROM community_posts WHERE status='held' ORDER BY id")]
        abuse = {}
        for r in c.execute("SELECT post_id, reason, COUNT(*) n FROM community_abuse WHERE status='open' GROUP BY post_id, reason"):
            abuse.setdefault(r["post_id"], []).append((r["reason"], r["n"]))
        approved = [dict(r) for r in c.execute("SELECT * FROM community_posts WHERE status='approved' AND parent_id IS NULL ORDER BY id DESC LIMIT 20")]
    with store.conn() as c:
        cabuse: dict[int, list] = {}
        for r in c.execute("SELECT comment_id, reason, COUNT(*) n FROM community_comment_abuse WHERE status='open' GROUP BY comment_id, reason"):
            cabuse.setdefault(r["comment_id"], []).append((r["reason"], r["n"]))
        comments = [dict(r) for r in c.execute("SELECT * FROM community_comments WHERE status IN ('pending','held') ORDER BY id")]
    for cm in comments:
        cm["flags"] = json.loads(cm["flags"])
        cm["abuse"] = cabuse.get(cm["id"], [])
    for lst in (pending, held, approved):
        for p in lst:
            p["flags"] = json.loads(p["flags"])
            p["tier_class"] = TIER_CLASS.get(p["tier"], "n")
            p["abuse"] = abuse.get(p["id"], [])
    return {"pending": pending, "held": held, "approved": approved, "comments": comments}


def moderate(post_id: int, action: str, actor: str) -> bool:
    """approve | reject | remove | dismiss. Every action is written to the audit log with the actor; the log never holds post text."""
    with store.conn() as c:
        r = c.execute("SELECT id, status, tier, entity_key, parent_id, dev FROM community_posts WHERE id=?", (post_id,)).fetchone()
        if not r:
            return False
        st = r["status"]
        if action in ("approve", "dismiss") and st in ("pending", "held"):
            root = None
            if r["entity_key"] and r["parent_id"] is None:
                root = c.execute("SELECT id FROM community_posts WHERE entity_key=? AND parent_id IS NULL AND status='approved' AND id!=? "
                                 "ORDER BY id LIMIT 1", (r["entity_key"], post_id)).fetchone()
            c.execute("UPDATE community_posts SET status='approved', parent_id=?, moderated_by=?, moderated_at=? WHERE id=?",
                      (root["id"] if root else r["parent_id"], actor, int(time.time()), post_id))
            c.execute("UPDATE community_abuse SET status='dismissed' WHERE post_id=? AND status='open'", (post_id,))
        elif action in ("reject", "remove") and st in ("pending", "held", "approved"):
            if st == "approved" and r["parent_id"] is None:
                _promote(c, post_id)
            c.execute("DELETE FROM community_votes WHERE post_id=?", (post_id,))
            _wipe(c, post_id, "rejected" if action == "reject" else "removed", actor)
            c.execute("UPDATE community_abuse SET status='actioned' WHERE post_id=? AND status='open'", (post_id,))
        else:
            return False
    db.audit(actor, f"community_{action}", f"post:{post_id}", f"was {st}, tier {r['tier']}")
    if action == "approve" and st == "pending":
        from . import progress
        progress.post_approved(r["dev"])
    return True


def audit_trail(limit: int = 30) -> list[dict]:
    return [a for a in db.audit_list(300) if a["action"].startswith("community_")][:limit]


# ---- discussion --------------------------------------------------------------------------------------------
def _root_of(c, post_id: int):
    r = c.execute("SELECT id, parent_id, status, dev FROM community_posts WHERE id=?", (post_id,)).fetchone()
    return r


def add_comment(post_id: int, dev: str, body: str, kind: str, platform: str = "") -> dict:
    """Add a comment to a public post. Returns {id, status}: published at once when the sanitiser finds nothing left over, otherwise it waits
    for a person. kind: saw ("I saw this on <platform>"), opinion, tip ("what to do"). A bare "I saw this on WhatsApp" needs no words."""
    kind = kind if kind in COMMENT_KINDS else "opinion"
    platform = platform if (kind == "saw" and platform in PLATFORMS) else ""
    raw = (body or "").strip()
    if len(raw) > MAX_COMMENT:
        raise SubmitError("comment_long")
    s = sanitise(raw)
    if len(s.excerpt) < 3 and not (kind == "saw" and platform):
        raise SubmitError("comment_short")
    with store.conn() as c:
        r = _root_of(c, post_id)
        if not r or r["status"] != "approved":
            raise SubmitError("post_closed")
        root = r["parent_id"] or r["id"]
        if not store.take(c, dev, "comment", LIMITS["comment"]):
            raise SubmitError("comment_limit")
        status = "approved" if s.clean else "pending"
        cur = c.execute("INSERT INTO community_comments(post_id,dev,created,kind,platform,body,status,flags) VALUES(?,?,?,?,?,?,?,?)",
                        (root, dev, int(time.time()), kind, platform, s.excerpt, status, json.dumps(s.flags)))
        cid = cur.lastrowid
    if status == "approved":
        from . import progress
        progress.note_event(dev, "comment_posted")
    return {"id": cid, "status": status, "post": root}


def _names(c, devs: set[str]) -> dict[str, str]:
    """Public handles for devices that chose one. Everyone else is shown as anonymous, never by a real name."""
    out: dict[str, str] = {}
    for d in devs:
        r = c.execute("SELECT p.handle FROM learn_devices x JOIN learn_profiles p ON p.id=x.profile_id WHERE x.dev=? AND p.handle IS NOT NULL", (d,)).fetchone()
        if r:
            out[d] = r["handle"]
    return out


def comments(post_id: int, dev: str | None = None, staff: bool = False) -> list[dict]:
    """The discussion under a post, oldest first. People see published comments; authors also see their own waiting ones."""
    with store.conn() as c:
        r = _root_of(c, post_id)
        root = (r["parent_id"] or r["id"]) if r else post_id
        rows = c.execute("SELECT * FROM community_comments WHERE post_id=? AND status IN ('approved','pending','held') ORDER BY id", (root,)).fetchall()
        rows = [x for x in rows if x["status"] == "approved" or (dev and x["dev"] == dev) or staff]
        names = _names(c, {x["dev"] for x in rows})
        helpful = {x["comment_id"]: x["n"] for x in c.execute("SELECT comment_id, COUNT(*) n FROM community_comment_votes GROUP BY comment_id")}
        mine_votes = {x["comment_id"] for x in c.execute("SELECT comment_id FROM community_comment_votes WHERE dev=?", (dev,))} if dev else set()
        reported = {x["comment_id"] for x in c.execute("SELECT comment_id FROM community_comment_abuse WHERE dev=?", (dev,))} if dev else set()
    return [{"id": x["id"], "created": x["created"], "kind": x["kind"], "platform": x["platform"], "body": x["body"], "status": x["status"],
             "name": names.get(x["dev"]), "mine": bool(dev) and x["dev"] == dev, "helpful": helpful.get(x["id"], 0), "voted": x["id"] in mine_votes,
             "reported": x["id"] in reported} for x in rows]


def recent_comments(limit: int = 5) -> list[dict]:
    with store.conn() as c:
        rows = c.execute("SELECT m.id, m.post_id, m.kind, m.platform, m.body, m.created, p.excerpt FROM community_comments m "
                         "JOIN community_posts p ON p.id=m.post_id WHERE m.status='approved' AND p.status='approved' ORDER BY m.id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(x) for x in rows]


def mark_helpful(comment_id: int, dev: str) -> str:
    """"Helpful" on a comment. One per device; not on your own. Returns ok | already | own | limit | missing."""
    with store.conn() as c:
        r = c.execute("SELECT dev, status FROM community_comments WHERE id=?", (comment_id,)).fetchone()
        if not r or r["status"] != "approved":
            return "missing"
        if r["dev"] == dev:
            return "own"
        if c.execute("SELECT 1 FROM community_comment_votes WHERE comment_id=? AND dev=?", (comment_id, dev)).fetchone():
            return "already"
        if not store.take(c, dev, "helpful", LIMITS["helpful"]):
            return "limit"
        c.execute("INSERT INTO community_comment_votes(comment_id,dev,ts) VALUES(?,?,?)", (comment_id, dev, int(time.time())))
        return "ok"


def report_comment(comment_id: int, dev: str, reason: str) -> str:
    """Same rules as for posts: a privacy complaint hides the comment at once, three different devices hide it for other reasons."""
    reason = reason if reason in ABUSE_REASONS else "other"
    with store.conn() as c:
        r = c.execute("SELECT id, status FROM community_comments WHERE id=?", (comment_id,)).fetchone()
        if not r or r["status"] in ("deleted", "removed", "rejected"):
            return "missing"
        if c.execute("SELECT 1 FROM community_comment_abuse WHERE comment_id=? AND dev=?", (comment_id, dev)).fetchone():
            return "already"
        if not store.take(c, dev, "abuse", LIMITS["abuse"]):
            return "limit"
        c.execute("INSERT INTO community_comment_abuse(comment_id,dev,reason,ts) VALUES(?,?,?,?)", (comment_id, dev, reason, int(time.time())))
        open_n = c.execute("SELECT COUNT(*) FROM community_comment_abuse WHERE comment_id=? AND status='open'", (comment_id,)).fetchone()[0]
        held = r["status"] == "approved" and (reason == "personal_info" or open_n >= HOLD_AFTER_REPORTS)
        if held:
            c.execute("UPDATE community_comments SET status='held' WHERE id=?", (comment_id,))
    if held:
        db.audit("system", "community_comment_hold", f"comment:{comment_id}", f"hidden after abuse reports ({reason})")
    return "ok"


def delete_comment_own(comment_id: int, dev: str) -> int | None:
    """The author's device erases a comment. Returns the post id it was on, or None."""
    with store.conn() as c:
        r = c.execute("SELECT post_id, dev, status FROM community_comments WHERE id=?", (comment_id,)).fetchone()
        if not r or r["dev"] != dev or r["status"] in ("deleted", "removed", "rejected"):
            return None
        c.execute("UPDATE community_comments SET status='deleted', body='' WHERE id=?", (comment_id,))
        c.execute("DELETE FROM community_comment_votes WHERE comment_id=?", (comment_id,))
        c.execute("DELETE FROM community_comment_abuse WHERE comment_id=?", (comment_id,))
        return r["post_id"]


def moderate_comment(comment_id: int, action: str, actor: str) -> bool:
    """approve | reject | remove | dismiss, written to the audit log with the actor (never the comment text)."""
    with store.conn() as c:
        r = c.execute("SELECT status, dev FROM community_comments WHERE id=?", (comment_id,)).fetchone()
        if not r:
            return False
        st = r["status"]
        if action in ("approve", "dismiss") and st in ("pending", "held"):
            c.execute("UPDATE community_comments SET status='approved' WHERE id=?", (comment_id,))
            c.execute("UPDATE community_comment_abuse SET status='dismissed' WHERE comment_id=? AND status='open'", (comment_id,))
        elif action in ("reject", "remove") and st in ("pending", "held", "approved"):
            c.execute("UPDATE community_comments SET status=?, body='' WHERE id=?", ("rejected" if action == "reject" else "removed", comment_id))
            c.execute("DELETE FROM community_comment_votes WHERE comment_id=?", (comment_id,))
            c.execute("UPDATE community_comment_abuse SET status='actioned' WHERE comment_id=? AND status='open'", (comment_id,))
        else:
            return False
    db.audit(actor, f"community_comment_{action}", f"comment:{comment_id}", f"was {st}")
    if action == "approve" and st == "pending":
        from . import progress
        progress.note_event(r["dev"], "comment_posted")
    return True
