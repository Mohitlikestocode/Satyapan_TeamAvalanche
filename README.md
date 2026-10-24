# Satyapan (सत्यापन): verify before you pay

**Team Avalanche** · RAKSHAM AI Cybersecurity Hackathon (IIT Delhi x Amazon) · Track 3: Deepfake Detection for Financial Communications
Tanish Shitanshu (lead) · Sai Mohit Kotta · Ghana Polisetty

Forward a suspicious video, voice note, screenshot, link or QR. In about a minute Satyapan returns a plain verdict in your
language that combines deepfake checks with a check of who is asking for the money, plus a ready-to-file report for 1930 /
cybercrime.gov.in. Advisory only: it never blocks or moves money.

Verdict tiers: HIGH RISK, SUSPICIOUS, CAN'T TELL, NO RED FLAGS FOUND (never "safe"), REGISTRY HIT.

## Status
The repository started from a skeleton only (see `PRE_EVENT_BASELINE.md`). Everything after the `pre-event` tag is finale work.

Built so far: the full web front end (42 pages, public-service style with a landing page and a My checks dashboard)
and a first working check engine for **messages, links and QR codes**: UPI field checks, red-flag words in English, Hindi
and Hinglish, look-alike bank links, and a fusion step that picks the tier (HIGH RISK needs two independent strong signals;
nothing is ever called "safe"). Reasons come only from the pre-written templates. Screenshot, PDF and voice checks are not
built yet: they open a clearly labelled sample result. No SEBI list is shipped, so no payee is confirmed as registered.

## Layout
- `src/satyapan/contracts` typed schemas and verdict tiers
- `src/satyapan/reasons` reason-code catalogue (EN/HI templates)
- `src/satyapan/api` FastAPI app: serves the site, demo `/api/v1/check`, `/api/v1/wrong-result`, health
- `src/satyapan/{layers/l3_payee,layers/l4_rules,fusion,extract,reasons}` the check engine; `service.py` runs a check
- `src/satyapan/{intake,evidence,layers/l1_provenance,layers/l2_forensics}` stub packages
- `web/templates` Jinja page templates (shared shell in `base.html`), `web/pages.json` route list, `web/static` CSS, JS and fonts

## Run
```
make setup
make run     # http://127.0.0.1:8000/
make test
```

## Contributing
Three people work in parallel on three branches without touching each other's files: see `docs/WORK_SPLIT.md` and `docs/BUILDER_GUIDE.md`.

## Measure it
```
python tools/make_qr_kit.py kit/qr          # real, scannable QR images with phone-style damage (synthetic payees)
python -m satyapan.eval.run data/kit/messages.jsonl   # rates with 95% intervals and every failure
```
The message kit is a *dev* kit written by the same people who wrote the rules, so its numbers are optimistic. The held-out
test must be written by someone who has not seen the rules. See `docs/PLAN.md`.
