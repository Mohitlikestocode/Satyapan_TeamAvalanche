"""XP, levels, streaks, badges, handles, recovery codes and the leaderboard."""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from satyapan.community import content, progress, store

DAY = 86400


def dev(n: str) -> str:
    return store.dev_hash(f"device-number-{n}")


# ---- streaks ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("streak,last,day,expect", [
    (0, None, "2026-10-24", (1, "2026-10-24")),            # first ever
    (3, "2026-10-24", "2026-10-24", (3, "2026-10-24")),    # same day twice: unchanged
    (3, "2026-10-24", "2026-10-25", (4, "2026-10-25")),    # next day
    (3, "2026-10-24", "2026-10-26", (1, "2026-10-26")),    # a missed day starts again
    (5, "2026-10-24", "2026-10-23", (5, "2026-10-24")),    # clock moved back: ignored
    (2, "2026-12-31", "2027-01-01", (3, "2027-01-01")),    # across the year
    (2, "2028-02-28", "2028-02-29", (3, "2028-02-29")),    # leap day
])
def test_next_streak(streak, last, day, expect):
    assert progress.next_streak(streak, last, day) == expect


def test_midnight_is_the_visitors_own_midnight():
    t = datetime(2026, 10, 24, 18, 30, tzinfo=timezone.utc).timestamp()       # = 2026-10-25 00:00 in India
    assert progress.local_day(t - 1, 330) == "2026-10-24"
    assert progress.local_day(t, 330) == "2026-10-25"
    assert progress.local_day(t, 0) == "2026-10-24"
    assert progress.local_day(t, 99999) == progress.local_day(t, 840)       # silly offsets are clamped


def test_streak_grows_across_days_through_lessons_and_resets_after_a_gap():
    d = dev("a")
    for day in ("2026-10-20", "2026-10-21", "2026-10-22"):
        progress.mark_read(d, content.lessons()[0]["slug"], day)
    s = progress.summary(d)
    assert s["best_streak"] == 3 and s["last_day"] == "2026-10-22"
    progress.mark_read(d, content.lessons()[1]["slug"], "2026-10-22")             # same day twice
    assert progress.summary(d)["best_streak"] == 3
    progress.mark_read(d, content.lessons()[2]["slug"], "2026-10-25")             # missed two days
    with store.conn() as c:
        assert c.execute("SELECT streak, best_streak FROM learn_profiles").fetchone()[:] == (1, 3)


def test_shown_streak_is_zero_when_a_day_was_missed():
    d = dev("b")
    old = progress.local_day(time.time() - 3 * DAY, 330)
    progress.mark_read(d, content.lessons()[0]["slug"], old)
    assert progress.summary(d)["streak"] == 0


# ---- levels and xp ----------------------------------------------------------------------------------------
def test_levels():
    assert progress.level_for(0)["level"] == 1 and progress.level_for(24)["level"] == 1
    assert progress.level_for(25)["level"] == 2 and progress.level_for(100)["level"] == 3
    lv = progress.level_for(60)
    assert lv["into"] == 35 and lv["span"] == 75 and lv["next_at"] == 100
    assert progress.level_for(10**6)["name_en"] == "Community guardian"


def test_reading_a_lesson_gives_xp_once():
    d, slug = dev("c"), content.lessons()[0]["slug"]
    assert progress.mark_read(d, slug, "2026-10-24")["xp"] == progress.XP_LESSON
    assert progress.mark_read(d, slug, "2026-10-24")["xp"] == 0
    assert progress.summary(d)["level"]["xp"] == progress.XP_LESSON
    with pytest.raises(KeyError):
        progress.mark_read(d, "no-such-lesson", "2026-10-24")


def test_xp_total_equals_the_ledger():
    d = dev("d")
    for l in content.lessons()[:4]:
        progress.mark_read(d, l["slug"], "2026-10-24")
    with store.conn() as c:
        assert c.execute("SELECT xp FROM learn_profiles").fetchone()[0] == c.execute("SELECT SUM(amount) FROM learn_xp").fetchone()[0] == 20


# ---- badges ----------------------------------------------------------------------------------------------
def test_lesson_badges_and_no_early_badges():
    d = dev("e")
    ls = content.lessons()
    progress.mark_read(d, ls[0]["slug"], "2026-10-24")
    assert [b["id"] for b in progress.summary(d)["badges"] if b["got"]] == []
    progress.mark_read(d, ls[1]["slug"], "2026-10-24")
    got = progress.mark_read(d, ls[2]["slug"], "2026-10-24")["badges"]
    assert got == ["lesson_reader"]
    for l in ls[3:]:
        last = progress.mark_read(d, l["slug"], "2026-10-24")["badges"]
    assert last == ["all_lessons"]


def test_streak_badges():
    d = dev("f")
    ls = content.lessons()
    for i, day in enumerate(["2026-10-20", "2026-10-21", "2026-10-22"]):
        out = progress.mark_read(d, ls[i]["slug"], day)["badges"]
    assert "streak_3" in out
    for i, day in enumerate(["2026-10-23", "2026-10-24", "2026-10-25", "2026-10-26"]):
        out = progress.mark_read(d, ls[3 + i]["slug"], day)["badges"]
    assert "streak_7" in out


def test_event_badges_family_guardian_and_scam_watcher():
    d = dev("g")
    assert progress.note_event(d, "family_open") == ["family_guardian"]
    assert progress.note_event(d, "family_open") == []                      # never twice
    progress.post_approved(d)
    assert {b["id"] for b in progress.summary(d)["badges"] if b["got"]} == {"family_guardian", "scam_watcher"}


def test_every_badge_has_both_languages():
    assert len(progress.BADGES) >= 10
    for b in progress.BADGES:
        assert all(b[1:5]) and any("ऀ" <= ch <= "ॿ" for ch in b[2] + b[4])


# ---- handles ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("handle,err", [("ab", "length"), ("x" * 21, "length"), ("has space", "chars"), ("a@b.com", "chars"), ("9876543210", "digits"),
                                        ("Rekha_52", None), ("रेखा_शर्मा", None), ("fuck_you", "profanity"), ("Ch0d", "profanity"), ("admin", "reserved"),
                                        ("Satyapan_Team", "reserved"), ("class_pass", None), ("Tanish_Shitanshu", None)])
def test_handle_rules(handle, err):
    assert progress.validate_handle(handle) == err


def test_handles_are_unique_ignoring_case_and_can_be_changed():
    a, b = dev("h1"), dev("h2")
    assert progress.set_handle(a, "Rekha_52") is None
    assert progress.set_handle(b, "rekha_52") == "taken"
    assert progress.set_handle(a, "REKHA_52") is None                         # your own name in other letters is fine
    assert progress.set_handle(b, "Meena_7") is None


def test_handle_changes_are_limited():
    a = dev("h3")
    results = [progress.set_handle(a, f"name_{i}") for i in range(7)]
    assert results[:5] == [None] * 5 and results[5] == "limit"


# ---- recovery --------------------------------------------------------------------------------------------
def test_recovery_code_moves_progress_to_another_device():
    a, b = dev("r1"), dev("r2")
    progress.set_handle(a, "Rekha_52")
    progress.mark_read(a, content.lessons()[0]["slug"], "2026-10-24")
    code = progress.new_recovery_code(a)
    assert code.startswith("SP-") and len(code) == 17
    assert progress.summary(b) is None
    assert progress.recover(b, code.lower().replace("-", " ")) == "ok"          # tolerant of how it is typed
    s = progress.summary(b)
    assert s["handle"] == "Rekha_52" and len(s["reads"]) == 1
    with store.conn() as c:
        assert code not in str([tuple(r) for r in c.execute("SELECT * FROM learn_profiles")])      # only a hash is stored


def test_new_recovery_code_cancels_the_old_one_and_wrong_codes_fail():
    a, b = dev("r3"), dev("r4")
    old = progress.new_recovery_code(a)
    new = progress.new_recovery_code(a)
    assert progress.recover(b, old) == "bad"
    assert progress.recover(b, "SP-AAAA-BBBB-CCCC") == "bad"
    assert progress.recover(b, "") == "bad"
    assert progress.recover(b, new) == "ok"


def test_recovery_guessing_is_rate_limited():
    b = dev("r5")
    assert [progress.recover(b, f"SP-AAAA-BBBB-CC{i:02d}") for i in range(12)].count("limit") == 2


# ---- leaderboard -----------------------------------------------------------------------------------------
def test_leaderboard_orders_by_week_xp_then_total_then_name_and_hides_unnamed():
    devs = {n: dev(f"lb{n}") for n in "abcde"}
    for n, h in (("a", "Alpha"), ("b", "Bravo"), ("c", "Charlie"), ("d", "Delta")):
        progress.set_handle(devs[n], h)
    with store.conn() as c:
        ids = {n: progress.ensure(c, devs[n]) for n in "abcde"}
        now = int(time.time())
        for n, amt in (("a", 30), ("b", 50), ("c", 50), ("d", 10), ("e", 99)):
            progress.add_xp(c, ids[n], amt, "t", now)
        progress.add_xp(c, ids["b"], 5, "t", progress.week_start() - 10)            # last week's XP does not count for the week
        progress.add_xp(c, ids["c"], 5, "t", progress.week_start() - 10)
        progress.add_xp(c, ids["a"], 40, "t", progress.week_start() - 10)
    top = progress.leaderboard(devs["a"])["top"]
    assert [r["handle"] for r in top] == ["Bravo", "Charlie", "Alpha", "Delta"]       # b and c tie on week and total: name decides
    assert [r["week"] for r in top] == [50, 50, 30, 10]
    assert [r["me"] for r in top] == [False, False, True, False]
    assert len(top) == 4                                                               # device "e" earned most but has no public name: not listed


def test_leaderboard_shows_me_when_outside_the_top():
    me = dev("lbme")
    progress.set_handle(me, "Slowcoach")
    with store.conn() as c:
        mine = progress.ensure(c, me)
        progress.add_xp(c, mine, 1, "t")
        for i in range(5):
            pid = progress.ensure(c, dev(f"lbx{i}"))
            c.execute("UPDATE learn_profiles SET handle=?, handle_lc=? WHERE id=?", (f"Fast_{i}", f"fast_{i}", pid))
            progress.add_xp(c, pid, 20 + i, "t")
    b = progress.leaderboard(me, limit=3)
    assert len(b["top"]) == 3 and b["me"]["handle"] == "Slowcoach" and b["me"]["rank"] == 6


def test_empty_leaderboard_and_stats():
    assert progress.leaderboard(None)["top"] == []
    assert progress.stats()["learners"] == 0 and progress.stats()["certificates"] == 0
