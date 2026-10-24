"""The held-out message file written for the models workstream: format and balance only (it is never used to tune anything here)."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "data" / "kit" / "holdout_community.jsonl"
KIT = Path(__file__).resolve().parents[2] / "data" / "kit" / "messages.jsonl"


def rows(p: Path) -> list[dict]:
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_forty_scam_and_forty_genuine_in_three_languages():
    r = rows(PATH)
    assert Counter(x["label"] for x in r) == {"scam": 40, "benign": 40}
    for label in ("scam", "benign"):
        langs = Counter(x["lang"] for x in r if x["label"] == label)
        assert set(langs) == {"en", "hi", "hinglish"} and min(langs.values()) >= 10
    assert all(set(x) == {"text", "label", "lang", "family"} and x["text"].strip() for x in r)


def test_varied_families_and_no_duplicates_or_overlap_with_the_existing_kit():
    r = rows(PATH)
    assert len({x["family"] for x in r if x["label"] == "scam"}) >= 15
    assert len({x["family"] for x in r if x["label"] == "benign"}) >= 10
    texts = [x["text"] for x in r]
    assert len(set(texts)) == 80
    assert not set(texts) & {x["text"] for x in rows(KIT)}


def test_hindi_rows_are_in_devanagari_and_english_rows_are_not():
    for x in rows(PATH):
        has = any("ऀ" <= ch <= "ॿ" for ch in x["text"])
        assert has == (x["lang"] == "hi"), x["text"][:40]


def test_missed_file_holds_only_scams_from_the_holdout_and_matches_what_the_rules_alone_miss():
    from satyapan.service import analyse_text as run

    def analyse_text(text):                    # rules only: a model plugin installed on another machine must not change this file's meaning
        return run(text, use_plugins=False)

    missed = rows(PATH.with_name("holdout_community_missed.jsonl"))
    originals = {x["text"]: x for x in rows(PATH)}
    assert len(missed) == 33 and all(m["label"] == "scam" and originals[m["text"]] == m for m in missed)
    flagged = {"SUSPICIOUS", "HIGH_RISK", "REGISTRY_HIT"}
    assert all(analyse_text(m["text"]).tier.value not in flagged for m in missed)
    caught = [x for x in originals.values() if x["label"] == "scam" and x["text"] not in {m["text"] for m in missed}]
    assert len(caught) == 7 and all(analyse_text(x["text"]).tier.value in flagged for x in caught)
