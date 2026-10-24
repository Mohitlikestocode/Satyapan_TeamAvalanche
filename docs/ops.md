# Operations and traction (workstream C)

Branch `feat/traction`. Goal: real users on a public site, counted honestly, kept safe and online.

## Plan, in order

| # | Task | Needs an account or key? | Status |
|---|---|---|---|
| C3 | Metrics, internal-traffic switch, public `/impact`, staff `/ops` | no | in progress |
| C4 | Pilot sign-up `/pilot`, feedback on result pages | no | |
| C1 | Hardening middleware, `/healthz`, Docker and Caddy, backup, load test | server + domain at deploy time | |
| C2 | Telegram bot | bot token from @BotFather | |
| C5 | Shop poster `/poster` with referral codes, PWA | no | |
| C6 | Sarvam voice for the verdict | Sarvam API key | |
| C7 | C2PA "Verified original" demo | only if time | |

## What counts as a real number

- Only people and checks that are **not** marked internal. Team and test devices open `/internal?key=<INTERNAL_KEY>` once, which sets the cookie `sp_internal=1`. Internal traffic is stored but excluded from every public number.
- "People" means distinct random device ids (`sp_dev`), hashed with a salt before storage. One person using two browsers counts twice; we say so.
- Counting starts at the first real event. `/impact` prints that date.
- No IP addresses are stored. No message text or files are stored by metrics.

## What the human must create (nothing is done without asking)

- `INTERNAL_KEY`: any long random string in the server's environment.
- Telegram bot token (message @BotFather, `/newbot`).
- Sarvam API key (free credits).
- A server and optionally a domain for the public site (see the deployment section once written).

Measured numbers (load test, cost per 1,000 checks) are added to this file when they exist. Until then they say "not measured".
