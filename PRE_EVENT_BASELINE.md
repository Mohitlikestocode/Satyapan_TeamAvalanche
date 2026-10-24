# Pre-event baseline

Skeleton only. No working detection, no models, no backend logic, no data, no keys.

Source: https://github.com/Tanish-Shitanshu/satyapan at commit `4ee064db9ff22aa277f658193aced43f5ed6b83e` (Round 1 prototype).

## Copied unchanged from the prototype
- `.gitignore`, `.env.example`
- `src/satyapan/contracts/models.py` (typed schemas, verdict tiers; no logic)
- `src/satyapan/reasons/catalogue.yaml` (reason-code EN/HI template catalogue)
- `web/static/base.css` (shared styles; font-face lines removed)

## Adapted from the prototype
- `pyproject.toml` (package metadata and core dependency list; ML extras and some deps removed)
- `Makefile` (reduced to setup/run/test/lint)

## Written new for this baseline
- `README.md`, `DISCLOSURE.md`, this file
- `src/satyapan/api/app.py` (health check and static mounts only)
- Docstring-only stub packages: `layers/*`, `fusion`, `intake`, `extract`, `evidence`
- `web/sim/index.html` (placeholder page)
- `tests/test_baseline.py` (checks tiers and catalogue load)

## Not copied
Pipeline, layers, fusion, intake, extraction, evidence, console, store, eval code; model weights; datasets; screenshots; docs; browser extension; `.env`, keys, `var/`, `assets/`.
