# Disclosure: community

Everything the community, learning and gamification workstream (branch `feat/community`) uses. No machine-learning model is trained, downloaded or called by this workstream.

| Item | Source | Licence | Used for | Trained/changed by us? |
|---|---|---|---|---|
| Noto Sans (Latin) and Noto Sans Devanagari, as WOFF2 subsets | Already in the repo: `web/static/fonts` (served by Google Fonts, see `web/static/fonts/NOTICE.txt`) | SIL Open Font License 1.1 | Drawing Hindi and English text in warning cards, the certificate, the safe-word card and posters (read by Pillow, not copied) | No |
| Pillow | PyPI (already a core dependency) | HPND (Pillow licence) | Rendering PNG cards; Raqm text shaping for Devanagari | No |
| reportlab | PyPI, `requirements/community.txt` | BSD-3-Clause | Wrapping poster pictures into A4 PDFs | No |
| segno | PyPI, `requirements/community.txt` (also a dev dependency in core) | BSD-3-Clause | QR code on posters that points to the site address | No |
| Satyapan engine (`satyapan.service.analyse_text`) | This repository | Project licence | The verdict on every Scam Watch report; reason text comes only from `reasons/catalogue.yaml` | Not changed |
| Lessons, question bank, safety rules, safe-word list (`data/learn/*.json`) | Written for this project by Tanish with an AI assistant, from general public knowledge of how UPI, KYC, parcel, job-task, "digital arrest", lottery and voice-clone frauds work in India, and from the public helpline details (1930, cybercrime.gov.in) | Project content | Learning pages and Scam Drill. All scenarios are invented examples, not real people's cases. Hindi text needs a fluent reader's review before the demo | Authored here |
| Held-out messages (`data/kit/holdout_community.jsonl`) | Written for this project from real-world patterns, without reading the rules layer | Project content | Unseen test set for the models workstream | Authored here |
| Word filter lists (`community/profanity.py`) | Written by hand; small and incomplete by design | Project content | Handles and posts; moderation covers the rest | Authored here |

## Data this workstream stores

Only in the local SQLite file under `$SATYAPAN_HOME` (git-ignored). No third-party service is called.

- Scam Watch: sanitised excerpt (phone numbers, e-mails, long numbers, OTP/PIN values, PAN and greeting names masked; links reduced to the domain), the engine's tier, reason text, a keyed hash of the payee/domain/phone for linking duplicates, a masked display of it, an optional city or state (letters only), language, a keyed hash of the device cookie, time and status. Raw text, full phone numbers and the cookie value are never written.
- Learning: a profile per device (XP, streak, answers, badges, lessons read), an optional public handle, a hash of the recovery code, and challenge links as counts of who played whose challenge.
- Rate-limit events: a hash of the device, an event name and a time.
- The server secret for the keyed hashes is `community.key` in `$SATYAPAN_HOME` (created on first use, never committed).
