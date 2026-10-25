# Demo kit

Ready-to-use inputs for rehearsing and for the live demo. **Everything here is made up**: messages are typical scam patterns, QR payees are invented, payment screens are generated, and the voice notes are synthetic speech made from fixed sentences. No real person or account appears.

The "result" column is what the final code returned on 25 Oct 2026 (laptop, CPU, no topic chosen). It is a record of behaviour, not a promise: a judge's own input may behave differently, and several rows below show a miss on purpose.

## Messages (`messages.txt`: paste into "Paste a message")

| Input | Result | Why |
|---|---|---|
| Digital arrest (English) | SUSPICIOUS | claims to be police, threatens arrest, asks for a transfer |
| Digital arrest (Hindi) | SUSPICIOUS | same, in Devanagari |
| KYC block with a link | SUSPICIOUS | account-blocked threat + look-alike bank link |
| Lottery with a fee to claim | **HIGH RISK** | advance fee + prize claim + UPI id (two independent strong signs) |
| OLX army buyer (Hinglish) | SUSPICIOUS | "army", advance by QR, enter your PIN to receive |
| Guaranteed returns (Hinglish) | SUSPICIOUS | guaranteed returns + group invite |
| Genuine bank alert | NO RED FLAGS | |
| Genuine OTP message ("do not share") | NO RED FLAGS | negation understood |
| Genuine delivery (Hinglish) | NO RED FLAGS | |

## Links
`http://sbi-yono-kyc.in/update` → SUSPICIOUS (imitates a bank site). `https://www.sbi.co.in` → NO RED FLAGS.

## QR codes (`qr/`: "Scan or upload a QR code")
| File | Result | Why |
|---|---|---|
| `plain_link__clean.png` | SUSPICIOUS | the QR opens a look-alike bank link |
| `collect_trap__clean.png` | SUSPICIOUS | the payment note says "Enter PIN to receive": a collect trap |
| `stock_tips_personal__clean.png` | SUSPICIOUS | personal account asked for "VIP profits" |
| `broker_valid__clean.png` | NO RED FLAGS | well-formed payee; we say "format looks right, check SEBI Check", never "safe" |

## Payment screenshots (`screens/`: synthetic, held-out layouts)
| File | Truth | Result |
|---|---|---|
| `edited_000003.jpg` | edited | SUSPICIOUS (edit sign) |
| `edited_000002.jpg`, `edited_000004.jpg` | edited | **missed** (NO RED FLAGS): the tamper model catches about 4 in 10 edits |
| `genuine_000000.jpg`, `genuine_000006.jpg` | genuine | NO RED FLAGS |
| `genuine_000001.jpg` | genuine | **false alarm** (SUSPICIOUS) |

Say this out loud: on 150 + 150 held-out synthetic screens the check flags 61 edited (41%) and 11 genuine (7%). It is a supporting signal, never the only one.

## Voice notes (`voice/`: "Voice note")
| File | Result | Why |
|---|---|---|
| `scam_hi.wav` | SUSPICIOUS | transcript asks for the OTP and threatens to close the account; the detector also notes a synthetic voice |
| `normal_en.wav` | NO RED FLAGS | nothing scammy said; the synthetic-voice note is still shown |

First voice note after the server starts takes about 6 s, later ones 6 to 10 s (CPU). Both clips are synthetic speech from Sarvam, so the "synthetic voice" note is correct for them.

`_outcomes.json` has the raw results and timings.

## PDFs (`pdf/`: "PDF") and QR cards (`qr_cards/`: "Scan or upload a QR code")
Invented documents. With the AI rule check on (a Groq key in `.env`): the six `scam_*.pdf` files and three `scam_card_*.png` cards come back SUSPICIOUS, the four `genuine_*.pdf` files and two `genuine_card_*.png` cards come back NO RED FLAGS. Without the key the rules still catch most of them (9 of 10 scam PDFs, 2 of 4 scam QR cards in our measurement).
