# Disclosure: traction and operations

| Item | Source | Licence | Used for | Trained/changed by us? |
|---|---|---|---|---|
| FastAPI, Starlette, Uvicorn, Jinja2, httpx | PyPI | MIT / BSD-3 | web server, templates, HTTP client | no |
| Caddy 2 | caddyserver.com (Docker image `caddy:2`) | Apache-2.0 | automatic HTTPS reverse proxy | no |
| segno | PyPI | BSD-3 | QR codes on shop posters | no |
| ReportLab | PyPI | BSD-3 | test PDFs in load tests and tests | no |
| pytesseract + Tesseract OCR (eng, hin) | Debian packages | Apache-2.0 | reading screenshots on the server | no |
| RapidOCR (onnxruntime) | PyPI | Apache-2.0 | reading screenshots when Tesseract is absent | no |
| Telegram Bot API | telegram.org | service terms | the Telegram bot (we send only our own verdict text; files are handled in memory) | no |
| Sarvam text-to-speech (bulbul) | api.sarvam.ai | Sarvam API terms | speaking the verdict aloud. **Only our template text is sent** (headline, reasons, action), never a user's file, message or transcript. Audio is cached on our server by a hash of the text | no |
| Noto Sans font | Google Fonts | SIL OFL 1.1 | page text (already in the repo) | no |

Data we collect on the public site (all first-party, no third-party analytics): a random device cookie (`sp_dev`), a language cookie (`sp_lang`), a referral cookie (`sp_ref`, 30 days, only when a poster or link carries `?ref=`), an optional team marker (`sp_internal`). Stored in our own database as salted hashes with timestamps and counts. No IP address, message text or file is stored by the metrics. Pilot forms store only what the person types, with their consent.
