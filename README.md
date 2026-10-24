# Satyapan (सत्यापन): verify before you pay

**Team Avalanche** · RAKSHAM AI Cybersecurity Hackathon (IIT Delhi x Amazon) · Track 3: Deepfake Detection for Financial Communications
Tanish Shitanshu (lead) · Sai Mohit Kotta · Ghana Polisetty

Forward a suspicious video, voice note, screenshot, link or QR. In about a minute Satyapan returns a plain verdict in your
language that combines deepfake checks with a check of who is asking for the money, plus a ready-to-file report for 1930 /
cybercrime.gov.in. Advisory only: it never blocks or moves money.

Verdict tiers: HIGH RISK, SUSPICIOUS, CAN'T TELL, NO RED FLAGS FOUND (never "safe"), REGISTRY HIT.

## Status
This repository starts from a skeleton only (see `PRE_EVENT_BASELINE.md`). All working functionality is built at the finale.

## Layout
- `src/satyapan/contracts` typed schemas and verdict tiers
- `src/satyapan/reasons` reason-code catalogue (EN/HI templates)
- `src/satyapan/api` FastAPI app (health check only)
- `src/satyapan/{layers,fusion,intake,extract,evidence}` empty stub packages
- `web/` placeholder frontend

## Run
```
make setup
make run     # http://127.0.0.1:8000/sim/
make test
```
