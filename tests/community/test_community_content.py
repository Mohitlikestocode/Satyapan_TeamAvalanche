"""The lessons and question bank: size, both languages, validation, and what a browser is allowed to see."""
from __future__ import annotations

import json
import re

import pytest

from satyapan.community import content

DEV = re.compile("[ऀ-ॿ]")


def test_twelve_lessons_and_sixty_questions_in_both_languages():
    assert len(content.lessons()) == 12 and len(content.questions()) >= 60
    for l in content.lessons():
        for k in ("title", "summary", "story", "check"):
            assert l[k]["en"] and DEV.search(l[k]["hi"]), (l["slug"], k)
        assert len(l["how"]["en"]) == 3 == len(l["how"]["hi"])
        assert len(l["flags"]["en"]) >= 4 and len(l["do"]["en"]) >= 3


def test_required_topics_are_covered():
    slugs = {l["slug"] for l in content.lessons()}
    assert slugs >= {"stock-tips-group", "fake-trading-app", "kyc-link", "refund-pin-trap", "parcel-customs-fee", "fake-customer-care", "invoice-bank-change",
                     "fake-payment-screenshot", "job-task-scam", "digital-arrest", "lottery-prize", "family-emergency-voice"}


def test_question_types_and_genuine_messages_are_present():
    qs = content.questions()
    types = {q["type"] for q in qs}
    assert types == {"scam_or_genuine", "tap_words", "first_step"}
    genuine = [q for q in qs if q["type"] == "scam_or_genuine" and q["answer"] == "genuine"]
    scam = [q for q in qs if q["type"] == "scam_or_genuine" and q["answer"] == "scam"]
    assert len(genuine) >= 10 and len(scam) >= 10
    assert all(q["why"]["en"] and DEV.search(q["why"]["hi"]) for q in qs)


def test_first_step_answers_are_not_always_the_same_position():
    assert len({q["answer"] for q in content.questions() if q["type"] == "first_step"}) == 4


def test_public_question_never_carries_answers_or_flags():
    for q in content.questions():
        for lang in ("en", "hi"):
            blob = json.dumps(content.public_question(q, lang), ensure_ascii=False)
            assert '"answer"' not in blob and '"why"' not in blob and "warning" not in blob
            if q["type"] == "tap_words":
                assert content.public_question(q, lang)["phrases"] == [s[0] for s in q["segments"][lang]]


def test_grading_each_type():
    sg = next(q for q in content.questions() if q["type"] == "scam_or_genuine" and q["answer"] == "scam")
    assert content.grade(sg, "scam")[0] and not content.grade(sg, "genuine")[0]
    fs = content.question("f01")
    assert content.grade(fs, fs["answer"])[0] and not content.grade(fs, "a" if fs["answer"] != "a" else "b")[0]
    tw = content.question("t01")
    flagged = [i for i, s in enumerate(tw["segments"]["en"]) if s[1]]
    assert content.grade(tw, [str(i) for i in flagged])[0]
    assert not content.grade(tw, flagged[:1])[0] and not content.grade(tw, [])[0]
    assert not content.grade(tw, list(range(len(tw["segments"]["en"]))))[0]       # tapping everything is wrong
    for bad in ("maybe", None, 5):
        with pytest.raises(ValueError):
            content.grade(sg, bad)
    with pytest.raises(ValueError):
        content.grade(tw, ["99"])
    with pytest.raises(ValueError):
        content.grade(tw, ["x"])


def test_genuine_message_shows_hindi_and_english_explanations():
    q = content.question("g04")
    assert content.reveal(q, "en", "genuine", True)["why"] != content.reveal(q, "hi", "genuine", True)["why"]


@pytest.fixture
def broken(tmp_path, monkeypatch):
    for f in ("lessons.json", "questions.json", "safety.json", "safe_words.json"):
        (tmp_path / f).write_text((content.DATA / f).read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(content, "DATA", tmp_path)
    for fn in (content.lessons, content.questions, content.safety_rules, content.safe_words):
        fn.cache_clear()
    yield tmp_path
    monkeypatch.undo()
    for fn in (content.lessons, content.questions, content.safety_rules, content.safe_words):
        fn.cache_clear()


def _edit(path, fn):
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_validation_rejects_english_pasted_as_hindi(broken):
    _edit(broken / "lessons.json", lambda d: d["lessons"][0]["title"].update(hi="Stock tips group"))
    with pytest.raises(content.ContentError, match="Devanagari"):
        content.lessons()


def test_validation_rejects_missing_language_and_bad_answers(broken):
    _edit(broken / "questions.json", lambda d: d["questions"][0].update(answer="maybe"))
    with pytest.raises(content.ContentError, match="answer"):
        content.questions()


def test_validation_rejects_mismatched_flags_between_languages(broken):
    def edit(d):
        q = next(q for q in d["questions"] if q["type"] == "tap_words")
        q["segments"]["hi"][0][1] = 1 - q["segments"]["hi"][0][1]
    _edit(broken / "questions.json", edit)
    with pytest.raises(content.ContentError, match="same phrases"):
        content.questions()


def test_validation_rejects_unknown_lesson_and_too_few(broken):
    _edit(broken / "questions.json", lambda d: d["questions"][0].update(lesson="nope"))
    with pytest.raises(content.ContentError, match="does not exist"):
        content.questions()
    _edit(broken / "lessons.json", lambda d: d.update(lessons=d["lessons"][:5]))
    content.lessons.cache_clear()
    with pytest.raises(content.ContentError, match="at least 12"):
        content.lessons()
