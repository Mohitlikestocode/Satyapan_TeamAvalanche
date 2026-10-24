"""Lessons, the question bank, the safety guide and safe words: loaded from data/learn/ and validated.

A bad content file fails loudly with a message that says which item and which field, so a typo cannot ship as a blank page.
`public_question` is the only shape a question is ever sent to the browser in: it never carries the answer or the warning flags.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[3] / "data" / "learn"
LANGS = ("en", "hi")
QTYPES = ("scam_or_genuine", "tap_words", "first_step")
MIN_LESSONS = 12
MIN_QUESTIONS = 60
_DEVANAGARI = re.compile("[ऀ-ॿ]")


class ContentError(ValueError):
    pass


def _pair(obj, where: str, hindi_script: bool = True) -> dict:
    if not isinstance(obj, dict) or any(not isinstance(obj.get(k), str) or not obj[k].strip() for k in LANGS):
        raise ContentError(f"{where}: needs non-empty 'en' and 'hi' text")
    if hindi_script and not _DEVANAGARI.search(obj["hi"]):
        raise ContentError(f"{where}: the Hindi text has no Devanagari letters (is it a pasted English copy?)")
    return obj


def _list_pair(obj, where: str, low: int, high: int) -> dict:
    if not isinstance(obj, dict):
        raise ContentError(f"{where}: needs 'en' and 'hi' lists")
    for k in LANGS:
        items = obj.get(k)
        if not isinstance(items, list) or not (low <= len(items) <= high) or any(not isinstance(i, str) or not i.strip() for i in items):
            raise ContentError(f"{where}.{k}: needs {low} to {high} non-empty strings")
        if not any(_DEVANAGARI.search(i) for i in items) and k == "hi":
            raise ContentError(f"{where}.hi: no Devanagari letters")
    if len(obj["en"]) != len(obj["hi"]):
        raise ContentError(f"{where}: English and Hindi lists differ in length")
    return obj


def _read(name: str) -> dict:
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ContentError(f"data/learn/{name}: {e}") from e


@lru_cache(maxsize=1)
def lessons() -> tuple[dict, ...]:
    items = _read("lessons.json").get("lessons")
    if not isinstance(items, list) or len(items) < MIN_LESSONS:
        raise ContentError(f"lessons.json: needs at least {MIN_LESSONS} lessons")
    seen: set[str] = set()
    for l in items:
        slug = l.get("slug", "")
        w = f"lesson {slug or '?'}"
        if not re.fullmatch(r"[a-z0-9\-]{3,40}", slug) or slug in seen:
            raise ContentError(f"{w}: slug missing, badly formed or repeated")
        seen.add(slug)
        for k in ("title", "summary", "story", "check"):
            _pair(l.get(k), f"{w}.{k}")
        _list_pair(l.get("how"), f"{w}.how", 3, 3)
        _list_pair(l.get("flags"), f"{w}.flags", 4, 6)
        _list_pair(l.get("do"), f"{w}.do", 3, 5)
        if l.get("check_kind") not in ("message", "link", "qr", "screenshot", "pdf", "voice"):
            raise ContentError(f"{w}.check_kind: unknown kind")
    return tuple(sorted(items, key=lambda x: x["order"]))


def lesson(slug: str) -> dict | None:
    return next((l for l in lessons() if l["slug"] == slug), None)


@lru_cache(maxsize=1)
def questions() -> tuple[dict, ...]:
    items = _read("questions.json").get("questions")
    if not isinstance(items, list) or len(items) < MIN_QUESTIONS:
        raise ContentError(f"questions.json: needs at least {MIN_QUESTIONS} questions")
    slugs = {l["slug"] for l in lessons()}
    seen: set[str] = set()
    for q in items:
        qid = q.get("id", "")
        w = f"question {qid or '?'}"
        if not re.fullmatch(r"[a-z]\d{2,3}", qid) or qid in seen:
            raise ContentError(f"{w}: id missing, badly formed or repeated")
        seen.add(qid)
        if q.get("type") not in QTYPES:
            raise ContentError(f"{w}: unknown type")
        if q.get("lesson") is not None and q["lesson"] not in slugs:
            raise ContentError(f"{w}: lesson '{q['lesson']}' does not exist")
        _pair(q.get("why"), f"{w}.why")
        if q["type"] == "scam_or_genuine":
            _pair(q.get("text"), f"{w}.text")
            if q.get("answer") not in ("scam", "genuine"):
                raise ContentError(f"{w}.answer: must be 'scam' or 'genuine'")
        elif q["type"] == "first_step":
            _pair(q.get("text"), f"{w}.text")
            opts = q.get("options")
            if not isinstance(opts, list) or [o.get("id") for o in opts] != ["a", "b", "c", "d"]:
                raise ContentError(f"{w}.options: needs four options with ids a, b, c, d")
            for o in opts:
                _pair(o, f"{w}.option {o.get('id')}", hindi_script=False)
            if q.get("answer") not in "abcd" or not q.get("answer"):
                raise ContentError(f"{w}.answer: must be one of a, b, c, d")
        else:
            segs = q.get("segments") or {}
            if any(not isinstance(segs.get(k), list) for k in LANGS) or len(segs["en"]) != len(segs["hi"]) or not 3 <= len(segs["en"]) <= 10:
                raise ContentError(f"{w}.segments: needs 3 to 10 phrases in both languages")
            if [s[1] for s in segs["en"]] != [s[1] for s in segs["hi"]]:
                raise ContentError(f"{w}.segments: English and Hindi must flag the same phrases")
            flags = [s[1] for s in segs["en"]]
            if not (any(flags) and not all(flags)) or set(flags) - {0, 1}:
                raise ContentError(f"{w}.segments: at least one phrase must be a warning sign and at least one must not be")
            if any(not isinstance(s[0], str) or not s[0].strip() for k in LANGS for s in segs[k]):
                raise ContentError(f"{w}.segments: empty phrase")
    return tuple(items)


def question(qid: str) -> dict | None:
    return next((q for q in questions() if q["id"] == qid), None)


@lru_cache(maxsize=1)
def safety_rules() -> tuple[dict, ...]:
    rules = _read("safety.json").get("rules")
    if not isinstance(rules, list) or len(rules) != 6:
        raise ContentError("safety.json: needs exactly 6 rules")
    for r in rules:
        _pair(r.get("title"), f"rule {r.get('id')}.title")
        _pair(r.get("body"), f"rule {r.get('id')}.body")
    return tuple(rules)


@lru_cache(maxsize=1)
def safe_words() -> tuple[dict, ...]:
    words = _read("safe_words.json").get("words")
    if not isinstance(words, list) or len(words) < 40:
        raise ContentError("safe_words.json: needs at least 40 words")
    for w in words:
        _pair(w, f"safe word {w.get('en')}")
    return tuple(words)


# ---- what the browser may see, and grading --------------------------------------------------------------
def is_scam_type(q: dict) -> bool:
    """Counts toward "scams spotted": phrase-tapping always, and scam-or-genuine questions whose answer is scam."""
    return q["type"] == "tap_words" or (q["type"] == "scam_or_genuine" and q["answer"] == "scam")


def public_question(q: dict, lang: str) -> dict:
    lang = "hi" if lang == "hi" else "en"
    base = {"id": q["id"], "type": q["type"]}
    if q["type"] == "tap_words":
        return {**base, "phrases": [s[0] for s in q["segments"][lang]]}
    if q["type"] == "first_step":
        return {**base, "text": q["text"][lang], "options": [{"id": o["id"], "label": o[lang]} for o in q["options"]]}
    return {**base, "text": q["text"][lang]}


def grade(q: dict, given) -> tuple[bool, str]:
    """(correct, normalised answer to store). Raises ValueError for an answer that is not a valid choice for this question."""
    if q["type"] == "scam_or_genuine":
        if given not in ("scam", "genuine"):
            raise ValueError("choose scam or genuine")
        return given == q["answer"], given
    if q["type"] == "first_step":
        if given not in ("a", "b", "c", "d"):
            raise ValueError("choose one option")
        return given == q["answer"], given
    n = len(q["segments"]["en"])
    try:
        picked = sorted({int(i) for i in given})
    except (TypeError, ValueError) as e:
        raise ValueError("bad phrase numbers") from e
    if any(not 0 <= i < n for i in picked):
        raise ValueError("phrase number out of range")
    flagged = [i for i, s in enumerate(q["segments"]["en"]) if s[1]]
    return picked == flagged, ",".join(map(str, picked))


def reveal(q: dict, lang: str, given: str, correct: bool) -> dict:
    """What is shown after an answer has been recorded: the verdict, the right answer and the explanation."""
    lang = "hi" if lang == "hi" else "en"
    out = {"correct": correct, "why": q["why"][lang], "given": given, "lesson": q.get("lesson")}
    if q["type"] == "scam_or_genuine":
        out["answer"] = q["answer"]
    elif q["type"] == "first_step":
        out["answer"] = q["answer"]
        out["answer_label"] = next(o[lang] for o in q["options"] if o["id"] == q["answer"])
    else:
        picked = {int(x) for x in given.split(",") if x != ""}
        out["marks"] = [{"text": s[0], "warning": bool(s[1]), "picked": i in picked} for i, s in enumerate(q["segments"][lang])]
    return out
