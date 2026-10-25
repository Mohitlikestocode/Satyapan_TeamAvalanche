# Operations and traction (workstream C)

Branch `feat/traction`. Goal: real users on a public site, counted honestly, kept safe and online.

## Status

| # | Task | Needs an account or key? | Status |
|---|---|---|---|
| C3 | Metrics, internal-traffic switch, public `/impact`, staff `/ops` | no | **done**, tested |
| C4 | Pilot sign-up `/pilot`, feedback on result pages and `/feedback` | no | **done**, tested |
| C1 | Hardening middleware, `/healthz`, backup, deploy check, load test | a server and a domain or `sslip.io` name | runs from plain `uvicorn` (the team decided not to use Docker; the Docker and Caddy files were never built or tested); not yet on a public address |
| C2 | Telegram bot | bot token from @BotFather | **done and tested with fake updates**; not yet run with a real token |
| C5 | Shop poster `/poster` with referral codes, installable PWA, offline helpline page | no | **done**, tested |
| C6 | Sarvam voice for the verdict (`POST /api/v1/speak`) | Sarvam API key | **done and tested**; also tried once with a real key (Hindi and English, fixed template sentences only) |
| C7 | C2PA "Verified original" demo | only if time | not started (cut first) |

## What counts as a real number

- Only people and checks that are **not** marked internal. Team and test devices open `/internal?key=<INTERNAL_KEY>` once, which sets the cookie `sp_internal=1`. Internal traffic is stored but excluded from every public number. `/internal?off=1` undoes it.
- "People" means distinct random device ids (`sp_dev`) or Telegram chats, salted and hashed before storage. One person using two browsers counts twice; the page says so.
- Counting starts at the first real event; `/impact` prints that date. Empty means 0.
- Not stored: IP addresses, message text, files. Page-view paths have ids and tokens masked (`/case/*`). Do-Not-Track browsers are not counted as visitors.
- The same numbers are available as JSON at `/api/v1/metrics/summary`, and staff can download daily counts at `/ops/daily.csv`.

## Measured performance (first run: developer laptop, not the production server)

Run on 24 Oct 2026 with `scripts/loadtest.py` against `uvicorn --workers 2` on an Intel Core Ultra 5 125H laptop (15 GB RAM) **that also ran the load generator**, rate limiting off. Mix: 60% messages, 15% links, 15% QR images, 10% PDFs. Raw file: `docs/results/loadtest.json`.

| Visitors at once | Checks per second | Median time | Slowest 1 in 20 | Errors |
|---|---|---|---|---|
| 1 | 2.2 | 82 ms | 1.18 s | 0 |
| 4 | 3.5 | 748 ms | 2.25 s | 0 |
| 8 | 5.8 | 1,057 ms | 2.72 s | 0 |

What the single-request timings say (one request at a time, warm): a message check takes about 20 ms, a link 26 ms, a PDF 21 ms, and a **QR image about 0.8 to 0.95 s**. Almost all of the image time is the OCR model reading the picture (detector, direction classifier and recogniser, about 0.2 to 0.3 s each on CPU); decoding the QR itself takes 1 ms. So capacity is set by how many image checks arrive, not by text checks. Text-only traffic would be far faster.

Not yet measured: a real remote server, the Tesseract path, and behaviour with rate limiting on. Cost per 1,000 checks is not computed until the server price is known: run `python scripts/loadtest.py <url> --price-per-month <price> --out docs/results/loadtest.json` on the real deployment; the script prints its assumptions.

## Protection that is on

`src/satyapan/ops/hardening.py`, one middleware, tested in `tests/traction/test_traction_hardening.py`:

- Security headers on every response: content-security-policy (own scripts, styles and images only, no framing, no plugins), no sniffing, strict referrer policy, camera/microphone/location denied, HSTS over HTTPS.
- Size limits: uploads capped (default 25 MB) and other posts capped at 256 KB, refused before the body is read.
- Rate limits per visitor (device cookie, else hashed address, in memory only): checks 20 a minute and everything else 300 a minute by default, Hindi and English messages, `Retry-After` header. **Off unless `RATE_LIMIT=1`**, so local runs and tests are never throttled; set `RATE_LIMIT=1` on a public server. The proxy address is trusted only with `TRUST_PROXY=1`.
- Errors never show a stack trace; the visitor sees a plain sentence in their language.

## Deployment runbook (no Docker)

The team runs plain Python. For the demo, run it on the laptop that has the models and give it a public address with a free tunnel.

1. `pip install -e .` and put the models in `var/models/` (see the README).
2. `.env` (git-ignored): `SARVAM_API_KEY`, `GROQ_API_KEY` (optional AI rule check), `TELEGRAM_BOT_TOKEN`, `INTERNAL_KEY`, `PUBLIC_URL`.
3. `make serve` (or `python -m uvicorn satyapan.api.app:create_app --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*"`). Models load in the background; wait about 40 seconds.
4. Public address: `cloudflared tunnel --url http://localhost:8000` (free, no account) prints an `https://...trycloudflare.com` link. Put it in `PUBLIC_URL`.
5. `python scripts/preflight.py http://127.0.0.1:8000` must say READY; `python scripts/deploy_check.py <public link>` must print only PASS lines.
6. Open `<link>/internal?key=<INTERNAL_KEY>` once in every team browser so rehearsals are not counted as users.
7. Telegram bot: `make bot` in a second terminal.
8. Backups: `python scripts/backup.py backups --keep 7`. The signing key in `var/keys` is not in the backup; copy it somewhere private once.

A tunnel dies with the laptop, so keep it plugged in and awake. A paid server was never used or tested.

## What a bank, UPI app or cyber cell pilot would need

Written as a plan, not an agreement: nobody has agreed to anything.

- **Who runs it:** during a pilot, our team. A partner would later run the same container, or call it as a service.
- **How it plugs in:** (1) a "Check before you pay" link or QR in the partner's app, SMS or branch poster (live now: `/poster`); (2) the partner's call-centre or branch staff use Helper mode for a customer; (3) cyber-cell staff use the reviewer console, the signed evidence pack and the known-fake registry. A JSON check API already exists (`POST /api/v1/check`) and returns a verdict without keeping the file.
- **What it costs:** server cost divided by measured checks; see the load-test section. Excludes people and the partner's own work.
- **What the partner provides:** a point of contact, a few weeks of real traffic, a way to tell us when a verdict was wrong, and legal sign-off on data handling.
- **Data:** no raw messages or files kept; results deleted after 24 hours unless a user shares them for review; no addresses stored.

## What the human must create (nothing is done without asking)

- A server and optionally a domain (step above).
- `INTERNAL_KEY`: any long random string in `.env`.
- Telegram bot token (message @BotFather, `/newbot`).
- Sarvam API key (free credits).
