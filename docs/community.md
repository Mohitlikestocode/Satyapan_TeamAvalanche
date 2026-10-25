# Community, education and gamification (workstream B, branch `feat/community`)

Owner: Tanish. Everything here is real code on a real database. Nothing is a mock-up, and every number on a page is computed from the database.
Run it like the rest of the site: `python -m uvicorn satyapan.api.app:app --port 8000`, then open `/community`, `/learn`, `/me`, `/warn`.
Tests: `python -m pytest -p no:warnings tests/community` (about 20 s, mostly drawing pictures).

## What it is, and who it is for

Rekha, 52, retired teacher, tier-2 town. Hindi first. She learns best from a short story, a plain list and one next step. So: no jargon, 16 px text or larger, 48 px tap targets, every string in Hindi and English (`{{ tr("English", "हिन्दी") }}`), pages work at phone width and without JavaScript.

## Features and URLs

### B1: Scam Watch (`/community`)

| Page or API | What it does |
|---|---|
| `/community` | Feed of public reports, newest first. Filters: type, language, "most seen this week". Pagination. "Trending this week" box. Counts at the top. Empty states for no reports and for no match. |
| `/community/report` | The form: type, text (1,000 characters), optional city/state, language, consent box, hidden honeypot field. Shows a live preview of exactly what will be saved ("What other people will see") and how many items were hidden. |
| `/community/post/<id>` | The report, the engine's tier and its reasons (catalogue text, in the visitor's language), "I saw this too", WhatsApp share, copy link, "Check something similar", "Make a warning card", "Report this post", and "Delete my post" for the author's phone. |
| `/community/moderate` | Moderator tools, only for a signed-in reviewer (same sign-in as `/console`, otherwise redirect to `/console`). Approve, reject, remove, restore after abuse reports. Every action goes to `db.audit`. |
| `/api/v1/community/{posts, posts/<id>, posts/<id>/seen, trending, stats, preview}` | JSON for the same data. `preview` shows what would be saved and stores nothing. |

How a report flows: the raw text lives in memory for one request. `analyse_text` (the real engine) runs on it. The sanitiser builds the only text that is stored. A report is published at once only if the engine says SUSPICIOUS or worse and the sanitiser found nothing left over; anything else waits for a person.

**Duplicates.** Reports with the same UPI ID, link domain or phone number are linked to the first one (keyed hash match). The feed shows one card; "Seen by N people" counts distinct devices across the original, linked reports and "I saw this too" taps. One device counts once however many times it taps or re-reports.

**Abuse.** One privacy complaint hides a post at once; three different devices hide it for any other reason. A moderator then restores or removes it.

### B1b: discussion, "seen on", questions, and sharing a result (added after the first release)

| Feature | How it works |
|---|---|
| **Discussion under every report** | Each public report has a "Discussion" section. A comment is one of: *I saw this too* (with where: WhatsApp, SMS, Telegram, Instagram/Facebook, YouTube, phone call, e-mail, website/advert, elsewhere; no words needed), *My opinion*, or *A tip: what to do*. Up to 500 characters, run through the same sanitiser as reports (numbers, e-mails and names hidden). A clean comment is published at once; a doubtful one waits for a moderator and only its author sees it until then. |
| **Helpful, report, delete** | "Helpful" once per device (not on your own comment). A privacy complaint hides a comment at once; three other complaints hide it too; a moderator restores or removes it. Authors can erase their own comment. Deleting or removing a post erases its comments. |
| **Who is shown** | The public handle chosen on My progress, otherwise "Someone". Never a real name. |
| **"Seen on" platform** | An optional field on each report; shown on the card and post; a filter in the feed. |
| **Ask the community** | The report form has two intents: *warn others* or *ask: is this real?*. A question is published once it is clean, with the engine's verdict (and its "not a guarantee" wording), is labelled "Question", is never merged into a scam report, and is left out of Trending. The vote button reads "I got this too". |
| **Feed** | Filters: type, language, seen on, posts (reports or questions); sort: newest, most seen this week, most discussed; comment counts on cards; a "Recent discussion" box; a comments count at the top. |
| **Share to community** | A button next to the existing share buttons on the result page (`/case/<id>`, beside Listen and Ask family) and on the Ask-family page (beside Share on WhatsApp). It opens `/community/report?case=<id>`, starts the report from the payee, link and number the check found (the check never kept the message), and keeps the check's own verdict. The post is marked "Shared from a Satyapan check". The button is added by `web/static/js/community_share.js` because those two pages are core templates. |
| **Family Guardian badge** | Now given when Share or Copy is pressed on the Ask-family page, using the core `guardian` event (`/api/guardian/shared`), instead of when the page is opened. |
| **Community voice badge** | First published comment. |
| **Upgrade safety** | New columns are added to an existing database on first use (`store._migrate`), so a running site does not need to be reset. |

**Look.** The community pages use a feed layout: a hero with live counts, a "did something suspicious reach you today?" bar with Report, Ask and Check buttons, sort tabs, filter chips (plain links), cards with an avatar, the poster's public handle or "Someone", time ago, the verdict, a quick "I saw this too" and a comment link, a chat-style discussion, and side widgets (trending, recent discussion, how we keep it safe). Icons are inline SVG. The community area uses rounder corners and one gradient in its hero, a deliberate step away from the rest of the site's square look. No emoji, no third-party images or fonts.

New tables: `community_comments`, `community_comment_votes`, `community_comment_abuse`. New columns on `community_posts`: `platform`, `intent`, `case_ref`. New API: `GET /api/v1/community/posts/<id>/comments`; `platform` and `intent` filters and `sort=talk` on `/api/v1/community/posts`; `comments` in `/api/v1/community/stats`.

### B2: Learn, Scam Drill and gamification

| Page or API | What it does |
|---|---|
| `/learn` | Hub: today's challenge, Scam Drill, the 12 lessons with read ticks, safe-word card, safety rules, warning cards, posters, certificate, weekly top learners. |
| `/learn/<slug>` | One lesson: an example story (labelled as made up), how it works in 3 steps, red flags, what to do, what to check with Satyapan, the 1930 helpline box, "I have read this" (+5 XP once), links to a warning card and an A4 poster. |
| `/learn/drill`, `/drill/start`, `/drill/play`, `/drill/answer`, `/learn/drill/score` | Rounds of 5 questions from a bank of 66. The server grades. After each answer: right or wrong, the explanation, XP. The score page lists what to review. |
| `/drill/play?c=<code>`, `/drill/challenge` | Family challenge: a finished round becomes a code and a WhatsApp link; the relative gets the same 5 questions; both scores are shown to both people. |
| `/me`, `/me/handle`, `/me/recovery`, `/me/recover` | Progress: level, XP, streak, badges, lessons read, rounds, own reports, public name, recovery code (shown once). |
| `/learn/leaderboard` | Weekly leaderboard of public handles (XP since Monday 00:00 IST). |
| `/learn/certificate`, `/learn/certificate/<token>(.png)` | Scam-Aware certificate (PNG, English or Hindi) after 12 lessons and 3 rounds and a public name. A shareable page for it. |
| `/learn/safe-word`, `/learn/safe-word/card.png`, `/learn/safety` | Safe-word generator (random pair or your own word, who it is for) with a printable A4 card in English or Hindi; the 6-rule safety guide. Nothing typed here is stored. |
| `/api/v1/learn/{lessons, lessons/<slug>, rounds, rounds/<id>, rounds/<id>/answer, leaderboard, stats, me}` | JSON. `stats` has the real growth counts (learners, rounds, challenges sent, invites accepted, new learners via invite, certificates). |

Content (`data/learn/`): `lessons.json` (12 lessons), `questions.json` (66 questions: 28 scam-or-genuine of which 12 genuine, 16 phrase-tapping, 22 first-step), `safety.json`, `safe_words.json`. `community/content.py` validates all of it on load: both languages present, Hindi really in Devanagari, matching flags in both languages, lessons referenced exist. The lessons cover the stock-tips group, fake trading app, KYC link, refund PIN trap, parcel fee, fake customer care, invoice change, fake payment screenshot, job-task, digital arrest, lottery and voice-clone family emergency.

**Scoring cannot be peeked at.** A question reaches the browser only as `public_question` (text and options, no answer, no warning flags; test `test_public_question_never_carries_answers_or_flags`). The explanation is only returned after the answer is recorded. Answering twice changes nothing.

**Rules.** XP: 10 per right answer, +20 for 5 of 5, +10 for finishing the daily challenge, +5 per lesson read. Level = 1 + floor(sqrt(XP / 25)). Streak: a day counts when the visitor does something that teaches (answers, reads); the day is the visitor's own date (the browser sends its time zone in a cookie, India time otherwise); the next day adds 1, a gap restarts at 1, the same day twice changes nothing, a clock set backwards is ignored. Daily challenge: seeded by the IST date, so it is the same for everyone and fixed for the day. Badges (12): First round, 10 scams spotted (10 different scam questions), Perfect round, 3-day and 7-day streak, Lesson reader (3 lessons), All 12 lessons, Daily challenge, Family Guardian, Scam Watcher, Challenger, Scam-Aware.

### B3: cards and posters

`/warn` builds a warning card from a scam type or a public report, in Hindi or English, with "Share the picture" (the phone's share sheet, so it goes to WhatsApp as an image), a WhatsApp text link, and download. `/learn/posters` has A4 PDFs for each of the 12 scams, in each language, and one PDF with all 12; each page carries a QR code to the site, "Check before you pay" and the 1930 line. No photographs, no logos, no names. Pictures are drawn with Pillow using the Noto fonts already in the repo (Hindi is shaped correctly); PDFs wrap those pictures with reportlab.

### B4: held-out messages

`data/kit/holdout_community.jsonl`: 40 scam and 40 genuine messages, English, Hindi and Hinglish, 20+ scam families and 15+ genuine kinds (bank alerts, OTP notices, a genuine KYC reminder, utility bills, family messages, school fees, insurance, railway, doctor, marketing). Written without reading `layers/l4_rules/layer.py`.

An informal first run of the rules-only engine on this file (by the author): **7 of 40 scams flagged (SUSPICIOUS or worse), 0 of 40 genuine messages flagged.** The models workstream's proper evaluation confirmed it (rules only 7/40; with the text classifier 12/40; 0/40 false alarms both ways; see `docs/results/text_holdout.json` on the models branch). `holdout_community_missed.jsonl` is the rules-only miss list, so it stays at 33 scams. Misses are spread over every family and language: the rules know the stock-tips and KYC patterns of the Round 1 kit and little else. This is the case for the message classifier. It also shapes Scam Watch: most real reports from outside the kit will wait for a person today, and will publish automatically as the engine improves.

## Data model (all in the main SQLite file; tables only created by this area)

`community_posts` (sanitised excerpt, tier, reason text in both languages, `entity_key` keyed hash, masked `entity_display`, `dev` keyed hash, status `approved | pending | held | rejected | removed | deleted`, `parent_id` for duplicates, flags), `community_votes`, `community_abuse`, `community_events` (rate limits), `learn_profiles`, `learn_devices`, `learn_reads`, `learn_rounds`, `learn_answers`, `learn_badges`, `learn_xp` (ledger: weekly leaderboard), `learn_events`, `learn_challenges`, `learn_invites`.

## Safeguards that run (not only described)

- **Sanitiser** (`community/sanitise.py`): masks phone numbers, e-mails, 9+ digit runs and grouped card/Aadhaar-style numbers, OTP/PIN/CVV values, PAN, names after "Dear / Hi / प्रिय / my name is"; reduces links to their domain; keeps UPI IDs only if valid and masks phone-like ones. A final re-scan sends anything suspicious to a person. Test: raw numbers and e-mails are searched for in the database file itself and must not be there.
- **Keyed hashes.** Device cookies, recovery codes and the identifiers used to link duplicates are stored as HMAC(secret in `community.key`), so a stolen database cannot be used to take over a device or to look up a phone number by trying all of them.
- **Consent, honeypot, size limits, rate limits per device per day** (5 reports, 30 "saw this too", 10 abuse reports, 10 recovery tries, 30 rounds, 5 name changes, 20 challenges), escaped output (no `|safe`), parameterised SQL, links never clickable.
- **Human review.** Unclear reports and anything the sanitiser doubts wait in `/community/moderate`; every moderator action is in the hash-chained audit log, with the actor and without post text. Rejected and removed posts are wiped, not just hidden. Authors can delete their own post: the text is erased.
- **Handles**: 3-20 characters, letters (Hindi allowed), digits, underscore; profanity filtered; reserved names blocked; unique ignoring case.

## What a wrongly flagged genuine user goes through

A genuine message reported by mistake gets "NO RED FLAGS FOUND" or "CAN'T TELL", is not published, and is shown only to its author with "Waiting for a person to look at it". The author can delete it in one tap. If a genuine post is published and someone objects, "This is not a scam" is an abuse reason; three of them hide it until a moderator looks. Reports can say "shows signs of", never "is fake", and the page says they are not verified by a bank or the police.

## How an attacker would get around this, and what we miss

- **Poisoning Scam Watch**: post a rival shop's UPI ID as a scam. Mitigation: abuse reports, "not a scam" reason, moderation of anything the engine does not call suspicious, and the page states that reports are unverified. We miss: a determined group of different phones can still push a false report to the front page for a while. We would add reputation per device and a reviewer check before a payee's trending badge shows.
- **Leaking personal data in free text** (a name in the middle of a sentence, an address, a spelled-out number such as "nine eight seven..."). The sanitiser does not catch these. Moderation and delete exist, and the preview shows the user what is saved. We would add a name and address detector and a spelled-out-number rule.
- **XP farming**: answering twice gives nothing, rounds are capped per day, XP for lessons is once. Many phones could still be scripted. Not defended.
- **Clone or guess handles**: handles are unique and filtered; look-alike spellings (for example a capital I for a lowercase l) are not folded.
- **Recovery code guessing**: 60 bits, 10 tries per device per day; code holders can use the progress, so the page tells people to keep it private.
- **Comment spam and brigading**: a group of phones can post many comments. Limits (20 a day per device), the sanitiser, abuse reports and moderation are the defence; there is no per-device reputation yet.

## Not done, or done in a limited way (said plainly)

- Hindi text is written by the author with an AI assistant and needs a fluent reader's review.
- No accounts and no e-mail: a device without cookies cannot keep progress.
- The leaderboard and trending box recompute from tables on each request; fine for thousands of rows, not millions.
- Posters and cards need the public site address from the request (see requests).
- Question bank is 66 questions; after about 13 rounds a learner starts seeing repeats (oldest first).
- No notifications or reminders to come back; the streak is the only nudge.
- Moderator sign-in is the core demo sign-in, not real authentication.
- The one failing test in the repository at the start (`tests/test_f1_generator.py`, the tamper-model image generator) is not in this area and was failing before this work.
