# F1: payment-screenshot tamper model (hand-off brief)

Goal: given a payment-success screenshot, say whether a field was edited and **where** (so the page can circle it).
This is the "own engineering" model in `docs/PLAN.md`. Training must happen at the finale and be logged in git (script, seed, metrics; no weights, no data).

## Data
`python tools/make_payment_screens.py data/f1 --n 20000 --seed 7 --holdout-styles 2`

- Synthetic only: made-up app names, people, UPI IDs and references. No real brand or person.
- Output: `images/*.jpg`, `masks/*.png` (255 where the edit is), `meta.jsonl` (`style`, `split`, `edited`, `field`, `font`, `jpeg_q`).
- **Split is by style.** `train` styles are never in `val` or `test`, so test shows layouts the model has not seen.
- Edits: one of amount, reference, payee, time is erased and rewritten (different font about 70% of the time, same font with a small shift the rest), then shrunk and JPEG-compressed like a chat copy.

## Model (suggested, small enough for an RTX 4060 8 GB)
Encoder: ResNet-18 or EfficientNet-B0 from ImageNet weights. Decoder: small U-Net. Loss: BCE + Dice on the mask.
Image-level score = max of the predicted mask. Input 384x704, mixed precision, 8 to 15 epochs, about 1 to 2 hours on 20k images.

## Must report (Results page)
1. Image-level TPR and FPR at one threshold fixed on `val`, on `test` styles. Bootstrap 95% intervals.
2. Localisation: IoU of the predicted box with the true box on edited test images.
3. Per condition: clean, JPEG q40, shrunk to 60%.
4. **Real-world check: not done, on purpose.** The team decided not to collect real payment screenshots: we do not use anyone's payment data without permission. Report every screenshot number as "synthetic, held-out styles; not evaluated on real phone screenshots".
5. Baselines in the same table: a naive error-level-analysis heuristic, and (if time) the pretrained CommunityForensics image model.

## Known limits to state on stage
- Trained on generated screens. Real apps look different. The real-world set decides whether it ships.
- A careful editor using the same font and a clean paste may pass. Chat apps recompress and wash out traces.
- A clean result never means the payment is real. The shopkeeper must still check their own UPI app.

## Wiring
Return `LayerResult(layer=L2, signals=[Signal(code="MEDIA_IMAGE_EDITED", strength=WEAK_SUSPICIOUS or STRONG_SUSPICIOUS, evidence_ref="box:x0,y0,x1,y1")])`
from a new `layers/l2_forensics/screenshot.py` and pass it as `extra_layers` in `service.analyse_image`. Forensics alone caps at SUSPICIOUS (fusion already enforces this).
