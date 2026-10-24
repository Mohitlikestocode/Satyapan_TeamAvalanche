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
