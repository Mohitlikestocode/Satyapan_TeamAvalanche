# Disclosure

- AI coding tools (Claude / Claude Code) are used to write and review code in this repository.
- Baseline skeleton derived from our Round 1 prototype; see `PRE_EVENT_BASELINE.md`.
- Models, datasets, APIs and licences used at the event are listed here as they are added. None are included in the baseline.
- Front-end pages were designed in an AI design tool, exported as static HTML, and converted into the pages under `web/site` with a one-off script (not committed). Behaviour in `web/static/*.js` is hand-written.
- Fonts: Noto Sans (SIL OFL 1.1), unmodified subsets in `web/static/fonts`. See `web/static/fonts/NOTICE.txt`.
- Libraries so far: FastAPI, Pydantic, Uvicorn, python-multipart (MIT/BSD). No models, datasets or external APIs are called yet.
- Read-aloud on `/listen` uses the browser's built-in speech voice as a local fallback; Sarvam is not wired yet.

