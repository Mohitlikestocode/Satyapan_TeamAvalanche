# Community, education and gamification (workstream B, branch `feat/community`)

Owner: Tanish. Everything here is real code on a real database. Nothing is a mock-up; every number on a page comes from the
database.

## Plan, in order

| # | What | Pages and APIs | Tables |
|---|---|---|---|
| B1 | **Scam Watch**: report a scam, see what others saw, "I saw this too", moderation | `/community`, `/community/report`, `/community/post/<id>`, `/community/moderate`, `/api/v1/community/*` | `community_posts`, `community_votes`, `community_abuse`, `community_events` |
| B2 | **Learn, Scam Drill, gamification**: 12 lessons, 60+ questions, server-side scoring, XP, streak, badges, daily challenge, leaderboard, recovery code, certificate, family challenge | `/learn`, `/learn/<slug>`, `/learn/drill`, `/drill/play`, `/learn/drill/score`, `/me`, `/learn/safe-word`, `/learn/safety`, `/warn`, `/api/v1/learn/*` | `learn_profiles`, `learn_devices`, `learn_reads`, `learn_rounds`, `learn_answers`, `learn_badges`, `learn_invites` |
| B3 | Share cards and A4 posters (Pillow, reportlab) | `/community/post/<id>/card.png`, `/learn/<slug>/card.png`, `/learn/posters/<lang>.pdf` | none |
| B4 | 40 scam + 40 genuine held-out messages written without reading the rules layer | `data/kit/holdout_community.jsonl` | none |

## Design decisions (and why)

- **Identity** is the random `sp_dev` cookie plus an optional public handle. The server never stores the cookie itself: it stores
  `HMAC(server key, cookie)`, so a leaked database cannot be used to impersonate anyone.
- **Sanitiser first, then store** (`community/sanitise.py`). Raw text lives in memory for one request: the engine is run on it, then a
  sanitised excerpt is built (phones, emails, long digit runs, OTP/PIN values, PAN, salutation names masked; links reduced to the
  domain; UPI IDs kept only if they pass the validator, phone-like ones are masked). A post-condition check re-scans the output;
  anything that still looks like personal data goes to the moderation queue instead of being published.
- **Duplicate clustering** uses an HMAC of the normalised UPI ID / domain / phone, so the same scam reported twice becomes one
  post with a growing "seen by" count, without storing the identifier in a reversible form.
- **Verdicts come from the engine** (`satyapan.service.analyse_text`) and the reason catalogue; this workstream never writes verdict text.
- **Scoring is server-side.** The browser gets a question and options; the answer key is only sent after the answer is submitted.
- **Streaks** are counted per device/profile by the visitor's local date (sent by the browser as an offset in minutes, bounded to a
  valid range), so midnight is the visitor's midnight.
- **Recovery code**: shown once, stored only as a hash; entering it on another phone attaches that phone to the same progress.
- **Rate limits** per device in `community_events` (rolling 24 h window): 5 posts, 30 votes, 10 abuse reports, 10 recovery tries.

## Order of work

1. Sanitiser, store, posts, feed, form, post page, votes, abuse, delete, moderation, tests.
2. Content (lessons, questions) with a validator, then profile/handle/XP/streak/badges, then drill, daily challenge, leaderboard,
   recovery, family challenge, `/me`, then safe-word card, safety guide, certificate.
3. Share cards, warning-card builder at `/warn`, posters.
4. Holdout messages, disclosure, this document's "not done" list.

## What is not done

Filled in at the end of the work (see "Status" below).
