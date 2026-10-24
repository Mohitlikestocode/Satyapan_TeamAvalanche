# Deviations from the Round 1 plan

Judges score "delivery against the Round 1 plan": built what we promised, or cut scope deliberately and can say why. This file is the honest record. The integrator keeps it current; add a row whenever something changes.

| Round 1 plan | What we did | Why | Status |
|---|---|---|---|
| Train and test on FaceForensics++, Celeb-DF, Deepfake-Eval-2024 | Dropped. Use ungated data instead: In-The-Wild and IndicSynth (audio), FLEURS (real speech), CommunityForensics-Small (images), our own synthetic payment screens, and consented team recordings | Those sets need access approvals or licences we could not get in time | cut, deliberately |
| Lip-sync check | Not built | Weights not available under a usable licence; low value for the payment-fraud flow | cut, deliberately |
| Focus on deepfake audio and video | Product widened to the money step: payee, QR, link, invoice and bank-code checks, payment screenshots and PDFs, plus voice notes | The money layer decides the verdict. Pixel and voice detectors degrade on chat-compressed media, so they support the verdict but never decide it alone | changed, deliberately |
| Sarvam vernacular verdicts | Built: Hindi and English reasons from reviewed templates; spoken verdict via Sarvam with a browser-voice fallback | Added to serve low-literacy users | added |
| C2PA provenance | Demo only if time allows (lowest priority) | Chat apps strip credentials, so a missing credential is neutral | at risk |
| Reviewer console, known-fake registry, evidence pack | Built and running: human review, four-eyes rule for the registry, hash-chained audit log, Ed25519-signed evidence pack | Alert and response flow row | delivered |
| (not in Round 1) Community, learning and gamification | Added: Scam Watch, lessons, Scam Drill, leaderboard | Mentor feedback: awareness and education | added |
| (not in Round 1) Live traction | Added: public deployment, Telegram bot, honest metrics page, pilot sign-ups | Mentor feedback: real users | added |
| Trained models | Fine-tuned at the finale only: screenshot tamper model, scam-message classifier. Everything else is pretrained and calibrated. No model was trained before the event | Rules of the event and our form | delivered: both models trained and measured (see `docs/results/`); the scam-message model is shipped only because it flagged more held-out scams with no extra false alarms, and it is switched off for screenshots, PDFs, QR and links because it was never trained on that text |

## Known gaps we will say out loud

- Accuracy numbers are measured only where `docs/results/` has a file. Anything else is "not evaluated".
- No official public list of `@valid` UPI handles exists, so we never confirm a payee as registered; we say "format looks right, check SEBI Check".
- Hindi text is machine-drafted until a fluent reviewer signs it off.
- WhatsApp needs paid business approval, so the live chat channel is Telegram.
- Real payment screenshots were not collected (no permission to use people's payment data). Screenshot numbers are on synthetic screens from unseen layouts and `/results` says "not evaluated" for real ones.
- Docker and Caddy files are in the repo but were never built or tested; the team runs plain `uvicorn`.
- Telegram bot is tested against fake Telegram updates; it has not been run with a real token.
- No public address yet: a server or tunnel is needed.
