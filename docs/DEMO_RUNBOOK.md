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
2. **Let the judge type their own message** (this is the 25-point row). In any language, even Hinglish.
3. On the result, the first thing shown is **"First, what does this say?"**. Pick the judge's own language (Tamil, Telugu, Bengali, Marathi…) and press **Explain**: it shows what the message says, then our verdict, in that language. Press **Listen**. Say: "This is for people who are more comfortable in their own language: they understand it first, then decide whether to trust our verdict."
4. **Hindi message** from `demo/messages.txt` ("Digital arrest, Hindi") → SUSPICIOUS with reasons in Hindi.
5. **QR**: upload `qr/collect_trap__clean.png` → "Enter PIN to receive": receiving money never needs a PIN.
6. **Voice note**: `voice/scam_hi.wav` → transcript, scam words, synthetic-voice note.
7. **Screenshot**: `screens/edited_000003.jpg` → the edit is circled. Then show `edited_000002.jpg` is **missed**: say "we catch about 4 in 10 edits, here is one we miss". Honesty scores.
8. **Is this really them?** (menu: "Is this real?"): choose Amazon, paste a message with a look-alike link and a personal number → flagged as not an official Amazon address.
9. **Shopkeeper check**: save a UPI ID, upload `screens/genuine_000000.jpg` (it pays `sharma_kirana@ibl`): with a different shop ID it warns "money went to someone else"; with `sharma_kirana@ibl` it says "names your UPI ID, but check your own app".
10. **Telegram**: forward a scam message to **@Satyapanbot** on a phone; press "Explain in my language".
11. **Extension**: select text on any page, right-click → "Check with Satyapan".
12. **Act**: **Ask family** (WhatsApp share), **Report** (signed evidence pack), **Wrong result?** → reference number → `/console` shows the human reviewer decide, **Delete now** → real deletion receipt.
13. **/results** and **/attack**: every number is read from a file, named failures, attacks measured.
14. **/impact**, **/poster**, **/community**, **/learn**: traction and education.

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
