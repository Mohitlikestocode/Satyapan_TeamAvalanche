# Work split: three people, three branches, no shared files

Mentor feedback (Saturday) added two goals on top of `docs/PLAN.md`:

1. **Live traction.** Real users on a public site, counted honestly. This is what separates us from teams that only built a demo.
2. **Awareness and education.** A community place where people learn, share what scams they see, and are rewarded for it (gamification), so they come back.

Everything below is **fully functional software, not mock-ups**: real database, real validation, real counts, both languages.

## The three workstreams

| | Branch | Who | Theme | Needs GPU? |
|---|---|---|---|---|
| **A** | `feat/models-eval` | the person with the GPU | Detectors, our own trained models, voice notes, measured results, "Attack yourself" | yes |
| **B** | `feat/community` | one of the other two | Community, Scam Watch, learning, Scam Drill and gamification, share cards | no |
| **C** | `feat/traction` | the other one | Public deployment, Telegram bot, live metrics, pilot sign-ups, feedback, Sarvam voice, C2PA | no |

Suggested fit from earlier roles: C suits whoever owned Sarvam and C2PA; B suits whoever owned the chat UI and content. You decide.
The repo owner is the **integrator**: merges branches into `main`, owns every file not listed below ("core"), gives out accounts and keys.

## Why there will be no merge conflicts

1. Each workstream has its **own folders and file names** (table below). Nobody edits another's files.
2. Core files are frozen. The extension points (`src/satyapan/plugins/`, `src/satyapan/api/ext/`, `reasons/ext/`, per-area CSS/JS, per-area tables) mean a feature never needs a core edit.
3. Shared files that used to collide are split per area: `requirements/<area>.txt` instead of `pyproject.toml`, `docs/disclosure/<area>.md` instead of `DISCLOSURE.md`, `docs/<area>.md` instead of `README.md`.
4. Each area uses its own URL prefixes, table prefixes, CSS class prefixes, reason-code prefixes, and event listeners (below).

## File ownership

| Area | May create and edit (only these) |
|---|---|
| **A** | `training/**`, `tools/make_payment_screens.py`, `tools/make_qr_kit.py`, `src/satyapan/layers/l2_forensics/**`, `src/satyapan/layers/l4_semantic/**`, `src/satyapan/eval/**`, `src/satyapan/plugins/models_*.py`, `src/satyapan/api/ext/models_*.py`, `src/satyapan/reasons/ext/models.yaml`, `data/kit/**` (existing files), `docs/results/**`, `docs/models.md`, `docs/F1_TAMPER_SPEC.md`, `docs/GPU_START.md`, `docs/disclosure/models.md`, `docs/requests/models.md`, `requirements/models.txt`, `tests/models/**`, `web/templates/ext/models/**`, `web/static/css/models*.css`, `web/static/js/models*.js` |
| **B** | `src/satyapan/community/**`, `src/satyapan/plugins/community.py`, `src/satyapan/api/ext/community*.py`, `src/satyapan/reasons/ext/community.yaml`, `data/learn/**`, `docs/community.md`, `docs/disclosure/community.md`, `docs/requests/community.md`, `requirements/community.txt`, `tests/community/**`, `web/templates/ext/community/**`, `web/static/css/community*.css`, `web/static/js/community*.js`, `web/static/img/community/**` |
| **C** | `src/satyapan/ops/**`, `src/satyapan/bots/**`, `src/satyapan/integrations/**`, `src/satyapan/plugins/traction*.py`, `src/satyapan/api/ext/traction*.py`, `src/satyapan/reasons/ext/traction.yaml`, `deploy/**`, `scripts/**`, `.github/**`, `Makefile`, `.env.example`, `docs/ops.md`, `docs/DEVIATIONS.md`, `docs/disclosure/traction.md`, `docs/requests/traction.md`, `requirements/traction.txt`, `tests/traction/**`, `web/templates/ext/traction/**`, `web/static/css/traction*.css`, `web/static/js/traction*.js`, `web/static/manifest.webmanifest`, `web/static/sw.js` |
| **Anyone** (add-only, unique file names) | `data/kit/holdout_<area>.jsonl` (your own held-out test messages) |
| **Core (integrator only)** | everything else, including `service.py`, `api/app.py`, `api/routes_*.py`, `api/web.py`, `store/db.py`, `plugins/__init__.py`, `contracts/`, `fusion/`, `extract/`, `layers/l3_payee`, `layers/l4_rules`, `reasons/catalogue.yaml`, `reasons/render.py`, `evidence/`, `web/templates/base.html` and the other existing templates, `web/static/gov.css`, `site.js`, `pages.js`, `pages.json`, `pyproject.toml`, `README.md`, `DISCLOSURE.md`, `docs/PLAN.md`, `docs/BUILDER_GUIDE.md`, `docs/WORK_SPLIT.md`, `tests/conftest.py`, existing tests |

## Contracts between the areas

| Thing | A | B | C |
|---|---|---|---|
| URL prefixes | `/results`, `/attack`, `/api/v1/models/*` | `/community*`, `/learn*`, `/drill*`, `/me`, `/warn`, `/api/v1/community/*`, `/api/v1/learn/*` | `/impact`, `/ops`, `/pilot`, `/poster`, `/feedback`, `/healthz`, `/provenance`, `/api/v1/speak`, `/api/v1/metrics/*`, `/api/v1/pilot/*` |
| Tables | `eval_*` (only if needed) | `community_*`, `learn_*` | `metrics_*`, `pilot_*`, `feedback_*`, `ref_*` |
| CSS class prefix | `ml-` | `cm-` | `ops-` |
| Reason-code prefix | `ML_` (and existing `MEDIA_*`) | `CM_` (if any) | `OPS_` (if any) |
| Nav | Results, order 72 | Community, order 45 | For shops, order 75 |
| Cookies | reads `sp_dev`, `sp_lang` | reads `sp_dev`, `sp_lang` | reads `sp_dev`; sets `sp_internal`, `sp_ref` |

**Learn pages:** B owns `/learn`, `/learn/drill`, `/learn/drill/score`, `/learn/safe-word`, `/learn/safety` and `/warn`. Their ext routes override the design pages, so existing links keep working.
**Events:** C listens to `check`, `dispute`, `decision`, `delete`. B's and A's code only has to keep using the core routes; C counts the rest.
**Held-out test messages:** B and C each write 40 scam and 40 genuine messages in `data/kit/holdout_<area>.jsonl` (same format as `data/kit/messages.jsonl`) **without reading `src/satyapan/layers/l4_rules/layer.py`**. A uses them as the unseen test set. This is the honest accuracy number.
**The tamper checkpoint:** A produces `var/models/tamper.pt` and sends it to the integrator; it is never committed.

## Priorities and time boxes

P0 = must work at the demo. P1 = should. P2 = cut first. Times are rough hours for one person with Claude Code. It is about Saturday 18:00 IST; code freeze Sunday 07:00; rehearsal 08:00 to 10:00.

| | P0 | P1 | P2 |
|---|---|---|---|
| **A** | A1 tamper model trained and evaluated (3h). A2 voice notes: transcribe and detect cloned voice (4h). A4 `/results` page with real numbers and `/attack` panel (3h) | A3 scam-message classifier (2h). A5 model cards (1h) | CommunityForensics AI-image check |
| **B** | B1 Scam Watch feed with real posting, moderation, "seen this too" (4h). B2 lessons and Scam Drill with XP, streaks, badges, leaderboard (4h) | B3 share cards and family challenge (2h). B4 moderator tools (1h) | printable posters |
| **C** | C1 public deployment and hardening (3h). C2 Telegram bot (3h). C3 live metrics and `/impact` (3h). C4 pilot sign-up and feedback (2h) | C5 shop poster with referral codes and PWA (2h). C6 Sarvam voice (2h) | C7 C2PA demo |

## Merge schedule (integrator)

Merge each branch into `main` with `git merge --no-ff origin/<branch>` at about 23:00, 03:00 and 07:00 IST, then run the tests and redeploy. After each merge everyone runs `git fetch origin && git merge origin/main` on their branch. Push your branch before each slot even if unfinished.

## What the team must do outside the code (live traction)

- Create the accounts: a Telegram bot (via @BotFather), a Sarvam API key (free credits), a host for the public site (C1 explains the options and costs).
- Put the public link in front of **real people**: family and friends, shopkeepers near the venue, classmates, local groups. Ask them to forward real suspicious messages, not test ones.
- Mark team devices as internal by opening `/internal?key=<value from .env>` once, so test traffic is not counted. The `/impact` page shows only real numbers, with the date counting started.
- In the pitch, quote only what `/impact` shows at that moment.
