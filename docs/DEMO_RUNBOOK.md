# Demo-day runbook

## The night before (Saturday)

1. `git fetch origin && git merge origin/main` on the demo laptop, then `python -m pytest -q` (about 2 minutes, all green).
2. Models in place: `var/models/` has `tamper.pt`, `faster-whisper-small/`, `spectra-aasist3/`, `voice_calibration.json`, `scam_text/`.
3. `.env` has `SARVAM_API_KEY`, `INTERNAL_KEY` (any long random string), and `TELEGRAM_BOT_TOKEN` + `PUBLIC_URL` if you use Telegram.
4. `python scripts/preflight.py` prints READY.

## Morning of the demo

```bash
python -m uvicorn satyapan.api.app:create_app --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*"
```

To start the counters (`/impact`, Scam Watch, "My checks" history) at zero, stop the server and delete `var/satyapan.db` first. **Do not delete `var/models/`.**

* Wait about 40 seconds: the models load in the background.
* On **every team device** open `http://<address>/internal?key=<INTERNAL_KEY>` once, so rehearsals are not counted as users.
* `python scripts/preflight.py http://<address>` should say READY.
* **Public link** (needs a tunnel or a server): `cloudflared tunnel --url http://localhost:8000`. Put the printed address in `PUBLIC_URL`, restart the Telegram bot, and print the poster from `/poster` with that address.
* Telegram: `python -m satyapan.bots.telegram_bot`.

## The 5-minute path (all inputs are in `demo/`)

1. **Home** → "Check now". Say who it is for: a person about to pay someone they are not sure about.
2. **Message**: paste "Digital arrest (Hindi)" → SUSPICIOUS, reason in Hindi, press **Listen**.
3. **Let the judge type their own message** (this is the row worth 25 points). Genuine ones should say "no red flags found" with "this is not a guarantee".
4. **QR**: upload `collect_trap__clean.png` → "Enter PIN to receive": explain why receiving money never needs a PIN.
5. **Voice note**: `voice/scam_hi.wav` → transcript, scam words, synthetic-voice note.
6. **Screenshot**: `screens/edited_000003.jpg` → the edit is circled. Then show `edited_000002.jpg` is **missed**: say "we catch about 4 in 10 edits, here is one we miss". Honesty scores.
7. **Act**: **Ask family** (WhatsApp share), **Report** (signed evidence pack), **Wrong result?** on a genuine message flagged → reference number → open `/console` to show the human reviewer decide.
8. **/results** and **/attack**: every number is read from a file, named failures, attacks measured.
9. **/impact**, **/poster**, **/community**, **/learn**: traction and education.

## If something breaks

| Symptom | Do |
|---|---|
| Page says "Could not start the check" | `python scripts/preflight.py http://<address>`; restart the server |
| Voice note slow the first time | wait; models warm up in the first minute after start |
| No spoken verdict | Sarvam daily cap or no internet: the browser's own voice is used |
| Screenshot check says CAN'T TELL | the OCR could not read the picture: say so, it is the designed safe answer |
| Telegram silent | it needs `TELEGRAM_BOT_TOKEN`; the website is the main channel |
| Internet down | the site, models and rules all run locally; only spoken verdicts and the public tunnel need internet |

## Answers to have ready
See `docs/JUDGE_QA.md`. The three to rehearse: what we miss (scams that read like ordinary messages; 6 in 10 edited screenshots; phone-line voices), what we did not measure (real phone screenshots), and why the reviewer sign-in is a demo (no real accounts yet).
