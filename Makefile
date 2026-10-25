PY ?= python
PORT ?= 8000
export PYTHONPATH := $(CURDIR)/src

.PHONY: setup run test lint serve bot deploy-check backup loadtest
setup:
	$(PY) -m pip install -e ".[dev,ocr]" -r requirements/traction.txt
run:
	$(PY) -m uvicorn satyapan.api.app:app --host 127.0.0.1 --port $(PORT) --reload
test:
	$(PY) -m pytest -p no:warnings
lint:
	$(PY) -m ruff check src tests scripts --select E9,F

# --- running it (no Docker): reads .env, loads the models in the background ---
serve:
	$(PY) -m uvicorn satyapan.api.app:create_app --factory --host 0.0.0.0 --port $(PORT) --proxy-headers --forwarded-allow-ips="*"
bot:
	$(PY) -m satyapan.bots.telegram_bot
deploy-check:
	$(PY) scripts/deploy_check.py $(URL)
backup:
	$(PY) scripts/backup.py $(or $(DEST),backups) --keep 7
loadtest:
	$(PY) scripts/loadtest.py $(or $(URL),http://127.0.0.1:$(PORT)) --out docs/results/loadtest.json
