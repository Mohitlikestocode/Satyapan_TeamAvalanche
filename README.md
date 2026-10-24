# Satyapan (सत्यापन): verify before you pay

**Team Avalanche** · RAKSHAM AI Cybersecurity Hackathon (IIT Delhi x Amazon) · Track 3: Deepfake Detection for Financial Communications
Tanish Shitanshu (lead) · Sai Mohit Kotta · Ghana Polisetty

Forward a suspicious video, voice note, screenshot, link or QR. In about a minute Satyapan returns a plain verdict in your
language that combines deepfake checks with a check of who is asking for the money, plus a ready-to-file report for 1930 /
cybercrime.gov.in. Advisory only: it never blocks or moves money.

Verdict tiers: HIGH RISK, SUSPICIOUS, CAN'T TELL, NO RED FLAGS FOUND (never "safe"), REGISTRY HIT.

## Status
The repository started from a skeleton only (see `PRE_EVENT_BASELINE.md`). Everything after the `pre-event` tag is finale work.

Built so far: the full web front end (41 pages: home, check flow, results, listen, next steps, guardian review, evidence
report and complaint draft, warn others, wrong-result path, Amazon/shopkeeper/helper checks, learn pages, system states,
reviewer console, how it works) and a demo API. **No detection runs yet**: the check endpoint accepts a submission,
discards it and points to a labelled sample result. Detectors, payee checks and the verdict engine are still to build.

## Layout
- `src/satyapan/contracts` typed schemas and verdict tiers
- `src/satyapan/reasons` reason-code catalogue (EN/HI templates)
- `src/satyapan/api` FastAPI app: serves the site, demo `/api/v1/check`, `/api/v1/wrong-result`, health
- `src/satyapan/{layers,fusion,intake,extract,evidence}` empty stub packages
- `web/site` the pages (plain HTML, one folder per route), `web/static` shared CSS, JS and fonts

## Run
```
make setup
make run     # http://127.0.0.1:8000/
make test
```
