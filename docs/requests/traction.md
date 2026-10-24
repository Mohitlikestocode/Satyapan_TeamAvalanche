# Requests from workstream C to the integrator (core changes)

1. **Image checks spend almost all their time in OCR (measured).** A QR image check takes about 0.8 to 0.95 s, of which decoding the QR is 1 ms and OCR is 0.2 to 0.3 s per stage. `service.analyse_image` runs OCR on every image, including pure QR codes. Consider skipping OCR when a QR payload was decoded and the image has little other text, or running OCR with a smaller input size. This sets capacity (see docs/ops.md).
2. **Open Graph and Twitter meta tags** for link previews cannot be added without editing `base.html`. Suggested: add `<meta property="og:title" content="Satyapan: check before you pay">`, `og:description`, `og:image` (a static image), `og:url`.
3. **`Dockerfile` assumes `pyproject.toml` dependencies are enough** for text, QR, PDF and OCR. If new core dependencies are added, no change is needed there; model dependencies come from `requirements/models.txt` through `--build-arg WITH_MODELS=1`.
