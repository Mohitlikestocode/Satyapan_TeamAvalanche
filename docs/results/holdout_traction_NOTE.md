# holdout_traction.jsonl: how it was made

The 40 scam and 40 genuine messages were drafted by the integrator's AI assistant at the integrator's request, from commonly reported Indian scam types. They were **not independent of the rule author** (same assistant wrote the rules). Treat the baseline below as indicative, not as a clean blind test.

Baseline, measured before any rule was changed: 7 of 40 scams flagged, 0 of 40 genuine flagged (`holdout_traction_baseline.json`).
Any later number on this file is **tuned-on** and must be reported as such. Tanish's `holdout_community.jsonl` stays untouched by rule work and is the cleaner test.
