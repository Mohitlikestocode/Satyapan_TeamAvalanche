# Prompt for person C: live traction, deployment and operations

Paste everything below the line into Claude Code, opened in an empty folder on your machine.

---

You are Claude Code, working with one teammate on **Satyapan**, a website that lets ordinary people in India check a suspicious payment message, link, QR code, PDF, screenshot or voice note before they pay. It gives a plain English or Hindi verdict with reasons. It is advisory only. We are in a hackathon final (RAKSHAM, IIT Delhi). The code freeze is Sunday 07:00 IST and the live demo is judged on Sunday. A mentor who will judge us said that **real live users** are what separates us from teams that only built a demo, and that **deployability** matters. **Build fully working features. Do not build mock-ups, fake numbers or placeholder pages.**

You are **workstream C: traction, distribution and operations**. Two other people work in parallel on other branches: A (models, GPU) and B (community, education, gamification). You must not touch their files.

## 1. Set up (do this first)

```bash
git clone https://github.com/Mohitlikestocode/Satyapan_TeamAvalanche.git
cd Satyapan_TeamAvalanche
git fetch origin
git checkout feat/traction
git config user.name  "<the human's own name>"
git config user.email "<the human's own email>"
git config core.hooksPath .githooks
python -m venv .venv    # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pip install -r requirements/traction.txt
python -m pytest -p no:warnings                      # must pass before you change anything
python -m uvicorn satyapan.api.app:app --port 8000 --reload
```

Ask the human for their name and email before configuring git. Commit only under their identity. **Never** add `Co-Authored-By`, "Generated with Claude", or any AI credit to a commit message (the hook rejects it).

## 2. Read first, in this order

1. `docs/BUILDER_GUIDE.md`: how to add pages, hooks, events, tables and tests without touching shared files. Binding.
2. `docs/WORK_SPLIT.md`: who owns which files. Binding.
3. `docs/PLAN.md`: the rubric (note "Deployability and scale" and "Live user journey").
4. `src/satyapan/plugins/__init__.py` (the registry: events, middleware, global scripts), `src/satyapan/api/app.py`, `routes_check.py`, `routes_review.py`, `store/db.py`, `service.py`, `web/templates/base.html`.

Then write a short plan into `docs/ops.md` (what you will build, in what order, what the human must do) and commit it. Then start.

## 3. Files you may create or edit (only these)

`src/satyapan/ops/**`, `src/satyapan/bots/**`, `src/satyapan/integrations/**`, `src/satyapan/plugins/traction*.py`, `src/satyapan/api/ext/traction*.py`, `src/satyapan/reasons/ext/traction.yaml`, `deploy/**`, `scripts/**`, `.github/**`, `Makefile`, `.env.example`, `docs/ops.md`, `docs/disclosure/traction.md`, `docs/requests/traction.md`, `requirements/traction.txt`, `tests/traction/**` (name files `test_traction_*.py`), `web/templates/ext/traction/**`, `web/static/css/traction*.css`, `web/static/js/traction*.js`, `web/static/manifest.webmanifest`, `web/static/sw.js`, and the add-only file `data/kit/holdout_traction.jsonl`.
**Everything else is frozen** (`service.py`, `api/app.py`, `api/routes_*.py`, `api/web.py`, `store/db.py`, `base.html`, `gov.css`, `site.js`, `pyproject.toml`, `README.md`, `DISCLOSURE.md`, all other templates). If you need a core change, write the exact request in `docs/requests/traction.md` and tell the human; work around it meanwhile. (Example of working around: you cannot edit `base.html`, so you add scripts with `registry.add_global_js(...)`.)

URLs you own: `/impact`, `/ops`, `/pilot`, `/poster`, `/feedback`, `/healthz`, `/internal`, `/provenance`, `/api/v1/speak`, `/api/v1/metrics/*`, `/api/v1/pilot/*`, `/api/v1/feedback*`. Tables: `metrics_*`, `pilot_*`, `feedback_*`, `ref_*`. CSS prefix `ops-`. Nav: "For shops" order 75 (key `pilot`) via `registry.add_nav`.

## 4. Rules that apply to everything you build

- Honesty is the product. **Every traction number is real and computed from the database.** No seeding, no inflation, no "sample" users on `/impact`. Empty shows 0 and the date counting started. Team and test traffic is excluded (the `sp_internal` cookie, set by `/internal?key=<INTERNAL_KEY>`; events carry `internal`).
- Privacy: no IP addresses stored (use them in memory for rate limiting only, hashed, never written), no message text, no files, no phone numbers or emails except what a shop owner types into the pilot form on purpose (and say so on the form). The only cookies are `sp_dev`, `sp_lang` (core), `sp_internal`, `sp_ref` (yours): random values, no personal data.
- Security: size and rate limits, strict headers (CSP that still allows our own scripts and styles, HSTS in production, no framing, no sniffing), no stack traces to users, no open CORS, parameterised SQL, escaped output, secrets only from environment variables, never in git.
- Never commit `.env`, keys, tokens, databases or backups. `.env.example` lists names and safe placeholder values only.
- **Ask the human before** creating any account, spending money, deploying, or sending anything to a third party. Do not paste or log tokens or API keys. Tell the human exactly which accounts and keys they must create themselves.
- Both languages for every visible string (`i18n="server"` and `{{ tr("English", "हिन्दी") }}`).
- Record every service, library, API and licence in `docs/disclosure/traction.md`.

## 5. Tasks, in priority order

### C1 (P0, about 3 h): deploy publicly and harden
- `deploy/Dockerfile` (Python 3.12 slim; install the app; apt packages `tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin ffmpeg`; run as a non-root user; `uvicorn` with 2 workers), `deploy/docker-compose.yml` (app + Caddy for automatic HTTPS, a volume for `var/`, restart always, env file), `deploy/Caddyfile`, `Makefile` targets (`make run`, `make test`, `make docker`, `make deploy-check`), `scripts/backup.sh` (copies the SQLite file to a dated archive, keeps 7) and `/healthz` (checks the database and reports the version and build time).
- Recommended hosting, tell the human and let them choose: a small VPS (about $5 a month) with Docker and Caddy, using a free hostname like `<server-ip>.sslip.io` if there is no domain, for reliable always-on HTTPS. Free tiers that sleep are bad for a live demo. A temporary public link from a laptop using a tunnel is a fallback for testing only. Write the exact commands in `docs/ops.md` and walk the human through it step by step, asking before each outward action.
- Hardening as a Starlette middleware registered with `registry.add_middleware`: per-device and per-IP rate limits (in memory, for example 20 checks per minute and 200 requests per minute), request-size caps, security headers, a short timeout for slow clients, and a friendly 429 page in both languages. Make limits configurable by environment variables and **tested**.
- Load test: `scripts/loadtest.py` (plain `httpx` + asyncio, or locust) that sends realistic checks (message, QR image, PDF) at increasing concurrency and writes `docs/results/loadtest.json` with p50, p95, error rate and requests per second, plus the machine used. Compute "cost per 1,000 checks" from the measured numbers and the server price. This feeds the Deployability score.
- Acceptance: the site runs from `docker compose up` on a clean machine, over HTTPS, survives a restart with its data, rejects abuse politely, and `docs/ops.md` has the full runbook and the measured numbers.

### C2 (P0, about 3 h): a real Telegram bot
Telegram gives us a real channel where people already forward messages (WhatsApp needs paid business approval, so we say so honestly).
- `src/satyapan/bots/telegram_bot.py`, run as `python -m satyapan.bots.telegram_bot`. Token from `TELEGRAM_BOT_TOKEN`. Use `httpx` long polling (`getUpdates`) so no extra dependency is needed, or `python-telegram-bot` if you prefer; add it to `requirements/traction.txt`.
- It calls the **same engine in process**: `satyapan.service.analyse_text`, `analyse_pdf`, `analyse_image`, and for voice notes the handler in `REGISTRY.handlers["voice"]` if it exists (person A is building it) else it replies that voice checks are not ready yet. Save results with `db.save_case(...)` so the website link `PUBLIC_URL/case/<id>` works. Process photos, PDFs and voice files in memory and discard them.
- Behaviour: `/start` (short privacy note: "we do not keep your file", language buttons EN/हिन्दी), plain forwarded text, a photo or a QR image, a PDF, a voice note. The reply: the verdict headline, the top three reasons, the action line, the footer line, and buttons: "Wrong result?" (asks whether the case may be shared with reviewers, then `db.create_review(...)`), "Ask family" (a ready-to-forward message), "Delete my result" (`db.delete_case`), and "Open on the website". Language is remembered per chat as a salted hash of the chat id, never the id itself.
- Per-user rate limit, a maximum file size, ignores group chatter unless the bot is addressed, and never replies "safe". Records each check in metrics with `channel="telegram"` by calling your metrics function directly (the bot is a separate process, so web events do not reach it). Enable SQLite WAL mode in your own init (`PRAGMA journal_mode=WAL`) since two processes write.
- Tests: feed fake Telegram updates into the handler functions (no network) and check replies, languages, rate limits, deletion, dispute creation.
- Acceptance: with a real token the human can forward a scam message to the bot and get the same verdict as the website within seconds.

### C3 (P0, about 3 h): live metrics and the public Impact page
- `src/satyapan/ops/metrics.py` with tables `metrics_events` and `metrics_pageviews` (created lazily by your module). A plugin listens to `check`, `dispute`, `decision`, `delete`. A script added with `registry.add_global_js("/static/js/traction_pv.js")` sends one beacon per page load to `POST /api/v1/metrics/pv` (path, language cookie, `?ref=` code, device id from the cookie; no IP).
- `/internal?key=...` sets the `sp_internal` cookie (key from env `INTERNAL_KEY`) and `/internal?off=1` clears it. Internal traffic is stored but excluded from every public number.
- `/impact` (public, bilingual, honest): since-date; people who checked (unique devices); checks done; by type (message, link, QR, PDF, screenshot, voice) and by channel (web, Telegram); verdict mix; people who came back within 7 days; median and 95th-percentile time to a verdict; "wrong result?" reports and how they were resolved (cleared, confirmed, pending) and the median time to a decision; community numbers if table `community_posts` exists (join read-only, tolerate absence). Small charts drawn with plain SVG/CSS, no external scripts. Says "team and test traffic excluded".
- `/ops` (guarded by `from satyapan.api.routes_review import who`): the same numbers by day, per referral code, per channel, recent pilot sign-ups, feedback, and a CSV export of daily aggregates. No personal data.
- Acceptance: running real checks through the website and the bot moves the numbers; internal traffic does not; tests prove it, including the empty state and both languages.

### C4 (P0, about 2 h): pilot sign-ups and feedback
- `/pilot` ("For shops"): a real form for shopkeepers, NGOs, colleges, bank branches and police cyber cells to ask for a pilot: organisation, type, city, what they want to use it for, expected checks per week, contact (phone or email, optional, with a clear line that it is kept only to reach them), consent checkbox. Validated, rate limited, stored, and listed on `/ops` with a CSV export. A thank-you page that says what happens next.
- Feedback: a small script loaded globally appears only on `/case/<id>` pages: "Was this helpful?" thumbs or 1 to 5, optional comment (up to 300 chars, no contact details), stored in `feedback_*` with the tier shown and the device id, one answer per case per device. Results summarised on `/impact` (helpfulness share, number of answers) and `/ops`.
- Acceptance: a real submission appears on `/ops`; duplicates and abuse are limited; tests included.

### C5 (P1, about 2 h): distribution kit
- `/poster`: a real generator. A shopkeeper enters shop name and city; the server returns a printable A4 PDF (reportlab, QR via `segno`) with a large QR to `PUBLIC_URL/?ref=<code>`, the line "Check before you pay / पैसे भेजने से पहले जाँचें" in both languages, three simple steps, and the Telegram bot QR. The `ref` code is created and stored in `ref_codes` so we can report checks per partner. A script (global JS) stores `?ref=` in cookie `sp_ref` for 30 days; metrics attribute devices to a code on first touch.
- PWA: `web/static/manifest.webmanifest` and `web/static/sw.js` (cache the shell and an offline page that shows the 1930 helpline and the Telegram link), registered by a global script, so people can add the site to their phone's home screen. Open Graph and Twitter meta tags cannot be added to `base.html` (frozen); if needed, request it in `docs/requests/traction.md`.

### C6 (P1, about 2 h): Sarvam voice for the verdict
- `POST /api/v1/speak` with `{case_id, lang}` returns audio of the **verdict text** (headline, reasons, action, built from the stored catalogue text in the visitor's language) using Sarvam's text-to-speech (read the current docs at docs.sarvam.ai for the endpoint, model and voices; key from `SARVAM_API_KEY`). Only our template text is sent, never the user's file or message. Cache audio on disk by a hash of text, language and voice. If there is no key or Sarvam fails, return 503 and the browser falls back to its own speech. Keep the amounts spoken in words in Hindi (for example "पच्चीस हज़ार रुपये").
- A global script `web/static/js/traction_speak.js` upgrades the existing "Listen" buttons (`[data-speak]` on the result page) to use this endpoint first and the browser voice second. Do not edit `pages.js`; attach a capture-phase handler.
- Tests with a fake Sarvam server (no network, no key). Disclosure entry: what is sent, and that audio is cached.

### C7 (P2, cut first, about 3 h): C2PA "Verified original" demo
`c2pa-python` with a test certificate: a script that signs a genuine sample image as "official", a page `/provenance` where a visitor uploads an image and sees "Verified original" or "Credentials missing or broken" (edit one pixel, it breaks), and an image hook in `plugins/traction_c2pa.py` that adds the existing reason code `PROV_VALID_CREDENTIALS` (layer L1, a supporting sign only). Missing credentials are neutral because chat apps strip them. Clearly label the certificate as a test certificate.

### Also (about 30 min): holdout messages for the models person
Write 40 scam and 40 genuine messages (EN, HI, Hinglish, varied) into `data/kit/holdout_traction.jsonl`, same format as `data/kit/messages.jsonl` (`text`, `label`, `lang`, `family`). **Do not read `src/satyapan/layers/l4_rules/layer.py` first.** Use real patterns you or your family have actually seen.

## 6. Git rhythm

Commit small. `git push origin feat/traction` at least every 30 minutes and before 23:00, 03:00 and 07:00 IST (merge slots). Run `python -m pytest -p no:warnings` and `python -m ruff check src tests scripts --select E9,F` before each push.

## 7. Definition of done

A public HTTPS address serves the site from Docker with a runbook; the Telegram bot answers real forwards; `/impact` shows real, honestly counted numbers with team traffic excluded; pilot sign-ups and feedback work and show on `/ops`; abuse protection and measured load numbers exist; every page is bilingual and phone-friendly; tests pass; `docs/ops.md` lists what the human must create (accounts, keys), what is running, the measured cost per 1,000 checks, and what is not done; `docs/disclosure/traction.md` is complete.

First action now: ask the human for their name and email, run the setup, read the documents, and commit your plan in `docs/ops.md`.
