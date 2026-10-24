# Prompt for person B: community, education and gamification

Paste everything below the line into Claude Code, opened in an empty folder on your machine.

---

You are Claude Code, working with a three-person hackathon team on **Satyapan**, a website that lets ordinary people in India check a suspicious payment message, link, QR code, PDF, screenshot or voice note before they pay. It gives a plain English or Hindi verdict with reasons. It is advisory only. We are in a hackathon final (RAKSHAM, IIT Delhi). The code freeze is Sunday 07:00 IST and the live demo is judged on Sunday. A mentor who will judge us said two things matter: **awareness and education**, and **real live users**. **Build fully working features. Do not build mock-ups, fake numbers or placeholder pages.**

The team: **Ghana** (workstream A: models, has the only GPU), **Tanish** (workstream B: community and learning), **Mohit** (workstream C: traction and operations, and the integrator who merges all branches). 

The human you are working with is **Tanish**. You are **workstream B: community, education and gamification**. Two other people work in parallel on other branches: A (models, GPU) and C (public deployment, Telegram bot, metrics). You must not touch their files.

The target user is Rekha, 52, a retired teacher in a tier-2 town. She trusts familiar faces and gets confused by English text and numbers. Hindi comes first for her. Everything you build must be simple, calm, and work on a phone.

## 0. How we are judged (the official Round 2 rubric: build for this)

The jury scores each row from 1 to 5; the weight is the number of points the row is worth.

**Stage 1: shortlist, 30 teams to 10**

| Row | Weight | What a 5 looks like |
|---|---|---|
| 1. Working prototype | 25 | Runs end to end, live, **on inputs the judge picks**: input, then detection, then alert or action. (3 = parts mocked or shown on slides; 1 = slides or a video.) |
| 2. Spot-check results and measured accuracy | **30** | Gets most of the judges' kit samples right; **shows error rates including false positives on data the model never trained on; names its failure cases.** (3 = small or unclear test set; 1 = fails the kit or claims accuracy with no measurement.) |
| 3. Own engineering contribution | 15 | Substantial code written during the finale beyond off-the-shelf models: **fine-tuning, fused signals, a custom pipeline**; any member can walk a judge through it. (1 = a thin wrapper around one API or model.) |
| 4. Alert and response flow, as built | 15 | The step after detection works: a person sees a clear alert and can act on it, and **safeguards are running, not just described** (nothing raw kept, human review). |
| 5. Delivery against the Round 1 plan | 15 | Built what the 48-hour plan promised, or cut scope deliberately and can say why. |

**Stage 2: final presentations, 10 teams to 3**

| Row | Weight | What a 5 looks like |
|---|---|---|
| 1. Problem and user understanding | 20 | Names a specific user and threat scenario grounded in how UPI, banking or wallet fraud actually happens in India; the pitch shows how victims get hurt today. |
| 2. Deployability and scale | 15 | A concrete path into a bank, UPI app, wallet or law-enforcement workflow; says who runs it, what it costs, and what a pilot would need. |
| 3. Communication and Q&A | 10 | Clear, on time, direct answers, including "we don't know". |
| 4. Live user journey | **25** | Works live on a realistic scenario **the jury can vary**; shows the whole path from the attack reaching the user, to the alert, the user's action, and any review or report. |
| 5. Adversarial robustness | **20** | In Q&A the team shows **how an attacker would evade us, what we miss now, and what we would change.** |
| 6. Responsible AI and handling mistakes | 10 | Shows what a genuine user flagged by mistake goes through and how fast they get past it; the alert says why it fired; privacy safeguards are running. |

Our mentor, who will also judge, added two things we agreed to: **live traction** (real users on a public site, counted honestly) and **awareness and education** (a community place that teaches and rewards people so they come back). Honesty beats polish: judges reward measured numbers, named failures and "we don't know" over claims.

### Where your work earns points
- **Problem and user understanding (20)**: the lessons and Scam Watch posts are grounded in how fraud really reaches Indian users (stock-tips group, KYC link, refund PIN trap, fake payment screenshot, invoice change, digital arrest). Write for Rekha.
- **Live user journey (25)**: a visitor reports a scam, sees the engine's verdict, shares a warning, learns, plays, and returns tomorrow. It must work live with whatever a judge types.
- **Responsible AI (10)**: sanitising, consent, moderation, abuse reporting, delete-my-post, no PII stored.
- **Own engineering (15)**: the sanitiser, duplicate clustering, server-side scoring, streak and badge engine are real code you can walk through.
- **Alert and response (15)**: community alerts and share cards are an action people can take after a verdict.
- **Awareness and education** is the mentor's second ask: this is your whole workstream.

## 1. Set up (do this first)

The branch already exists on the remote: do **not** create a new one, just check it out.

```bash
git clone https://github.com/Mohitlikestocode/Satyapan_TeamAvalanche.git
cd Satyapan_TeamAvalanche
git fetch origin
git checkout feat/community
git config user.name  "<the human's own name>"
git config user.email "<the human's own email>"
git config core.hooksPath .githooks
python -m venv .venv    # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pip install -r requirements/community.txt
python -m pytest -p no:warnings                      # must pass before you change anything
python -m uvicorn satyapan.api.app:app --port 8000 --reload
```

Ask the human for their name and email before configuring git. Commit only under their identity. **Never** add `Co-Authored-By`, "Generated with Claude", or any AI credit to a commit message (the hook rejects it).

## 2. Read first, in this order

1. `docs/BUILDER_GUIDE.md`: how to add pages, hooks, tables and tests without touching shared files. Binding.
2. `docs/WORK_SPLIT.md`: who owns which files. Binding.
3. `docs/PLAN.md`: the rubric and what scores.
4. `web/static/gov.css` (the shared look), `web/templates/base.html`, `web/templates/case.html` and `home.html` (examples of finished pages), `src/satyapan/api/routes_pages.py` and `routes_review.py` (examples of routes), `src/satyapan/store/db.py`, `src/satyapan/service.py`.
5. The existing design pages you will replace, so you keep their intent: `web/templates/pages/learn*.html`, `warn.html`.

Then write a short plan into `docs/community.md` (what you will build, the data model, the order) and commit it. Then start.

## 3. Files you may create or edit (only these)

`src/satyapan/community/**`, `src/satyapan/plugins/community.py`, `src/satyapan/api/ext/community*.py`, `src/satyapan/reasons/ext/community.yaml`, `data/learn/**`, `docs/community.md`, `docs/disclosure/community.md`, `docs/requests/community.md`, `requirements/community.txt`, `tests/community/**` (name files `test_community_*.py`), `web/templates/ext/community/**`, `web/static/css/community*.css`, `web/static/js/community*.js`, `web/static/img/community/**`, and the add-only file `data/kit/holdout_community.jsonl`.
**Everything else is frozen** (`service.py`, `api/app.py`, `api/routes_*.py`, `api/web.py`, `store/db.py`, `base.html`, `gov.css`, `site.js`, `pyproject.toml`, `README.md`, `DISCLOSURE.md`, and all other templates). If you need a core change, write the exact request in `docs/requests/community.md` and tell the human; work around it meanwhile.

How you plug in: a router in `src/satyapan/api/ext/community.py` (mounted automatically, before the core pages, so your routes override the design pages) and a plugin in `src/satyapan/plugins/community.py` (`setup(registry)` adds the nav item "Community" with order 45, footer links, related links). Pages use `wide(...)` or `screen(...)` with `i18n="server"` and `{{ tr("English", "हिन्दी") }}` for every visible string.

URLs you own: `/community*`, `/learn`, `/learn/*`, `/drill*`, `/me`, `/warn`, `/api/v1/community/*`, `/api/v1/learn/*`. Tables: `community_*`, `learn_*`. CSS classes: prefix `cm-`.
**You replace** the design pages `/learn`, `/learn/drill`, `/learn/drill/score`, `/learn/safe-word`, `/learn/safety`, `/warn` with real ones at the same URLs (existing links across the site point to them).

## 4. Rules that apply to everything you build

- Honest wording: "shows signs of", never "is fake"; never "safe". The verdict on a post comes from the real engine and its catalogue templates, never written by you or a model.
- Privacy: no accounts with email or phone. Identity is the random device cookie (`sp_dev`, set automatically) plus an optional public handle. **Sanitise anything users submit before it is stored or shown**: mask phone numbers, emails, long digit runs (Aadhaar/account/card numbers), and keep only validated entities (UPI IDs and link domains that scammers use). Never show a victim's name. Ask for consent that the post will be public.
- Safety: rate-limit writes per device (for example 5 posts per day, 30 votes per day), size-limit input, escape all output (Jinja autoescape stays on; never `|safe` on user content), parameterised SQL only, a honeypot field on forms, and a moderation path (below).
- Content is for awareness. Never include instructions that help someone commit fraud.
- Every number you show (counts, streaks, leaderboard, "seen by") comes from the real database. Demo seed data is allowed only if clearly labelled "sample" and removable by one command; prefer none.
- Both languages for every string. Hindi is not optional and not machine-pasted placeholder text: write it properly, plain and short, for a non-technical reader.
- Record any library or content source and licence in `docs/disclosure/community.md`.

## 5. Tasks, in priority order

### B1 (P0, about 4 h): Scam Watch, a real community feed
Anyone can report a scam they saw, see what others saw, and say "I saw this too".
- `/community`: feed of approved posts, newest first, with filters (type: message, link, UPI ID, phone call, QR; language; "most seen this week"), pagination, and a "Trending this week" box (top payees/domains by sightings, computed from the database).
- `/community/report`: form. Type, the text or the UPI ID/link/phone (up to 1,000 characters), optional city/state, language, consent checkbox. On submit the server runs the **real engine** (`satyapan.service.analyse_text`) on it, stores: the sanitised excerpt, the tier and reason codes, the extracted payee/link (validated), the masked phone, language, device id, time. Never store the raw text. Posts whose tier is SUSPICIOUS or worse and that pass the sanitiser are published at once; others wait in a moderation queue.
- `/community/post/<id>`: the post, the engine's reasons (from the catalogue, in the visitor's language), "I saw this too" (one per device per post; shows a count), "Report this post" (abuse), "Check something similar" link to `/check`, share buttons (WhatsApp link with the post URL), and "delete my post" for the author's device.
- Duplicate handling: if the same UPI ID or domain was already reported, the new post is linked to it and increases its sighting count instead of cluttering the feed.
- Moderator tools at `/community/moderate` guarded with `from satyapan.api.routes_review import who` (redirect to `/console` when None): approve, reject, remove, see abuse reports, with each action logged through `db.audit(actor, action, target, detail)`.
- Acceptance: real posts through the real form appear in the feed; the counts change; abuse and rate limits work; tests cover posting, sanitising (phone numbers and emails never appear), duplicates, voting once per device, moderation, rate limits, both languages, and an empty feed.

### B2 (P0, about 4 h): Learn, Scam Drill and gamification
Replace the static learn pages with a real learning system that makes people come back.
- Content in `data/learn/` (JSON or Markdown you validate on load): **12 short lessons**, each in English and Hindi, grounded in how fraud happens in India: stock-tips group with a cloned "expert", fake trading app and "pay tax to withdraw", KYC link, refund "enter PIN" trap, parcel/customs fee, fake customer care and screen-sharing app, invoice with changed bank details, fake payment screenshot at a shop, job-task scam, digital-arrest call, lottery, a "family emergency" voice-clone call. Each lesson: how it works (3 steps), red flags, what to do, what to check with Satyapan, and the helpline (1930, cybercrime.gov.in). Plain words, short sentences.
- Question bank: **at least 60 questions**, English and Hindi, types: "which words are the warning signs" (tap the suspicious phrases in a short message), "scam or genuine", "what should you do first". Each has an explanation shown after answering. Include genuine-looking messages so people learn that most messages are fine.
- Scam Drill at `/learn/drill` and `/drill/play`: 5 questions per round. **Scoring happens on the server**: the correct answers are not sent to the browser before it answers. After each answer show whether it was right and the explanation. Final page `/learn/drill/score` shows the score and what to review.
- Gamification, real and stored: XP per correct answer, levels, daily streak (counted by device and local date), badges (for example "First round", "10 scams spotted", "7-day streak", "Lesson reader", "Family Guardian" when they use the Ask-family share, "Scam Watcher" after their first approved community post), a **daily challenge** (the same 5 questions for everyone that day, chosen by date), and a weekly **leaderboard** of public handles. Handle rules: 3 to 20 characters, profanity-filtered, unique. A **recovery code** shown once lets the person move their progress to another phone (no email, no password).
- `/me`: progress page: level, XP, streak, badges, lessons read, rounds played, their posts, and "save my recovery code".
- **Scam-Aware certificate**: after finishing the 12 lessons and 3 rounds, generate a shareable PNG (Pillow) with their handle, level and date in English or Hindi, and a WhatsApp share link. No fake credentials, no government logos; it says "Satyapan Scam-Aware, a learning certificate, not an official qualification".
- **Family challenge**: `/drill/play?c=<code>` lets someone challenge a relative with the same 5 questions; show both scores. Record who invited whom (counts only) so we can report real growth.
- `/learn/safe-word` (family safe-word card): a working generator (word, who it is for, printable A4 card in English or Hindi) and `/learn/safety` (the safety guide, 6 rules). `/warn`: build a warning-card image from a chosen scam type or community post, in Hindi or English, ready to share on WhatsApp.
- Acceptance: a visitor can read a lesson, play a round, see a streak and a badge, appear on the leaderboard, get a certificate, and use a recovery code on another browser. The server never leaks answers. Tests cover scoring, streak edge cases (missed day, same day twice, midnight), badge rules, daily-challenge determinism, leaderboard ordering and handle rules, recovery, and both languages.

### B3 (P1, about 2 h): share cards and posters
Server-generated images (Pillow) for: a community post (warning card), a lesson ("Scam of the week"), and printable A4 posters (reportlab is installed) of the 12 scams in Hindi and English for shops and housing societies. Each carries the site address and a "Check before you pay" line. No real person's photo, no copied logos.

### B4 (P1, about 1 h): holdout messages for the models person
Write 40 scam and 40 genuine messages (EN, HI, Hinglish, varied scam families and varied genuine kinds) into `data/kit/holdout_community.jsonl`, same format as `data/kit/messages.jsonl` (`text`, `label`, `lang`, `family`). **Do not read `src/satyapan/layers/l4_rules/layer.py` first**: these must be written without knowing our rules, so they are an honest test. Use real-world patterns you or your family have actually seen.

## 6. Git rhythm

Commit small. `git push origin feat/community` at least every 30 minutes and before 23:00, 03:00 and 07:00 IST (merge slots). Run `python -m pytest -p no:warnings` and `python -m ruff check src tests --select E9,F` before each push.

## 7. Definition of done

On a fresh clone and an empty database: a real person can report a scam, see it in the feed with a verdict, vote, share it; a real person can learn, play, earn badges, appear on the leaderboard and get a certificate; moderation works; every page is bilingual, phone-friendly and accessible; tests pass; `docs/community.md` explains each feature, the data model, and what is not done; `docs/disclosure/community.md` is complete.

First action now: ask the human for their name and email, run the setup, read the documents, and commit your plan in `docs/community.md`.
