PY ?= python
PORT ?= 8000
COMPOSE = docker compose -f deploy/docker-compose.yml --env-file .env
export PYTHONPATH := $(CURDIR)/src

.PHONY: setup run test lint docker up down logs bot deploy-check backup loadtest
setup:
	$(PY) -m pip install -e ".[dev,ocr]" -r requirements/traction.txt
run:
	$(PY) -m uvicorn satyapan.api.app:app --host 127.0.0.1 --port $(PORT) --reload
test:
	$(PY) -m pytest -p no:warnings
lint:
	$(PY) -m ruff check src tests scripts --select E9,F

# --- deployment (needs Docker and a filled-in .env) ---
docker:
	docker build -f deploy/Dockerfile -t satyapan --build-arg BUILD_TIME=$$(date -u +%Y-%m-%dT%H:%MZ) .
up:
	$(COMPOSE) up -d --build
down:
	$(COMPOSE) down
logs:
	$(COMPOSE) logs -f --tail=100
bot:
	$(COMPOSE) --profile bot up -d
deploy-check:
	$(PY) scripts/deploy_check.py $(URL)
backup:
	$(PY) scripts/backup.py $(or $(DEST),backups) --keep 7
loadtest:
	$(PY) scripts/loadtest.py $(or $(URL),http://127.0.0.1:$(PORT)) --out docs/results/loadtest.json
