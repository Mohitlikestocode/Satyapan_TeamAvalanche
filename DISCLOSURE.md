# Disclosure

- AI coding tools (Claude / Claude Code) are used to write and review code in this repository.
- Baseline skeleton derived from our Round 1 prototype; see `PRE_EVENT_BASELINE.md`.
- Models, datasets, APIs and licences used at the event are listed here as they are added. None are included in the baseline.
- Front-end pages were designed in an AI design tool, exported as static HTML, and converted into the pages under `web/site` with a one-off script (not committed). Behaviour in `web/static/*.js` is hand-written.
- Fonts: Noto Sans (SIL OFL 1.1), unmodified subsets in `web/static/fonts`. See `web/static/fonts/NOTICE.txt`.
- Libraries so far: FastAPI, Pydantic, Uvicorn, python-multipart (MIT/BSD). No models, datasets or external APIs are called yet.
- Read-aloud on `/listen` uses the browser's built-in speech voice as a local fallback; Sarvam is not wired yet.
- Checks so far are deterministic rules we wrote (UPI field checks, link look-alikes, red-flag words). Libraries: zxing-cpp (Apache-2.0) for QR decoding, RapidFuzz (MIT) for name matching, Pillow (HPND), Jinja2 (BSD). No trained model is used yet and no media text is ever sent to an LLM.
- The SEBI handle list is read from `data/sebi_snapshot.json` if present; none is shipped, so no handle is confirmed as registered.
- Response flow (disputes, human review, known-fake registry, hash-chained audit log, signed evidence pack) is our own code. Signing uses the `cryptography` package (Ed25519, Apache-2.0/BSD). The console sign-in is a demo: no passwords are used or stored. The database and signing key live under `var/` and are git-ignored.
- OCR for screenshots uses Tesseract (English + Hindi) when installed, otherwise RapidOCR (Apache-2.0, pretrained ONNX text-detection and recognition models bundled in the pip package). PDF text and metadata use pypdf (BSD-3). Test PDFs are made with ReportLab. No model was trained for these.
- `tools/make_payment_screens.py` generates fully synthetic payment screens (made-up app names, people and references) as training data for our own tamper model; the model is trained at the finale only.
- Per-feature disclosures (models, datasets, APIs, licences) are kept in `docs/disclosure/models.md`, `community.md` and `traction.md`.
