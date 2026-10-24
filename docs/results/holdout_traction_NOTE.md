# holdout_traction.jsonl: how it was made

The 40 scam and 40 genuine messages were drafted by the integrator's AI assistant at the integrator's request, from commonly reported Indian scam types. They were **not independent of the rule author** (same assistant wrote the rules). Treat the baseline below as indicative, not as a clean blind test.

Baseline, measured before any rule was changed: 7 of 40 scams flagged, 0 of 40 genuine flagged (`holdout_traction_baseline.json`).
Any later number on this file is **tuned-on** and must be reported as such. Tanish's `holdout_community.jsonl` stays untouched by rule work and is the cleaner test.

## After adding the India rules (`layers/l4_rules/india.py`)

| File | Scams flagged | False alarms | Status |
|---|---|---|---|
| `holdout_traction.jsonl` | 32 / 40 (was 7) | 0 / 40 | **tuned-on**: the rules were written after this file existed |
| `holdout_community.jsonl` (Tanish) | 18 / 40 (was 7) | 0 / 40 | cleaner: rules were not fitted to it, but the author had seen a few of its lines |
| `messages.jsonl` (dev kit) | 38 / 38 | 0 / 33 | development set |

Rules still miss many scams that use no fixed wording (sextortion, fake loan apps, fake support, crypto pitches). The honest unseen figure is the Tanish file, about 45%.

## Whole system with the scam-message model installed (rules + model, as the live site runs)

| File | Scams flagged | False alarms | Status |
|---|---|---|---|
| `holdout_community.jsonl` (Tanish) | **25 / 40** (rules alone before India rules: 7; model alone with old rules: 12) | 0 / 40 | cleanest unseen figure; the author of the rules had seen part of the file |
| `holdout_traction.jsonl` | 36 / 40 | 0 / 40 | tuned-on, optimistic |
| `messages.jsonl` (dev kit) | 38 / 38 | 2 / 33 | development set; the model adds 2 false alarms here (Ghana reported this too) |

Reproduce: `SATYAPAN_HOME=var python scripts/eval_holdout.py data/kit/holdout_community.jsonl`. Raw files: `docs/results/system_*.json`.
