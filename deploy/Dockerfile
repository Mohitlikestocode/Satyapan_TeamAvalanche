# Satyapan web app. Build from the repo root:  docker build -f deploy/Dockerfile -t satyapan .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 SATYAPAN_HOME=/data

# Tesseract (English + Hindi) for reading screenshots, ffmpeg for voice notes. libgomp is needed by the OCR runtime.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin ffmpeg libgomp1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# dependencies first so rebuilds are fast when only code changes
COPY pyproject.toml README.md ./
COPY requirements ./requirements
RUN mkdir -p src/satyapan && touch src/satyapan/__init__.py \
 && pip install -e ".[ocr]" -r requirements/traction.txt -r requirements/community.txt

# Model dependencies (torch and friends) are large. Build with --build-arg WITH_MODELS=1 once checkpoints are ready.
ARG WITH_MODELS=0
RUN if [ "$WITH_MODELS" = "1" ]; then pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements/models.txt; fi

COPY src ./src
COPY web ./web
COPY data ./data
COPY docs ./docs

# run as an ordinary user; the database, signing key and models live in the /data volume
RUN useradd --create-home --uid 10001 app && mkdir -p /data && chown -R app /data /app
USER app
VOLUME ["/data"]
EXPOSE 8000

ARG APP_VERSION=dev
ARG BUILD_TIME=
ENV APP_VERSION=$APP_VERSION BUILD_TIME=$BUILD_TIME RATE_LIMIT=1 TRUST_PROXY=1 PUBLIC_HTTPS=1

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "satyapan.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*", "--timeout-keep-alive", "15", "--no-server-header"]
