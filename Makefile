PY ?= python
PORT ?= 8000
export PYTHONPATH := $(CURDIR)/src

.PHONY: setup run test lint
setup:
	$(PY) -m pip install -e ".[dev]"
run:
	uvicorn satyapan.api.app:app --host 127.0.0.1 --port $(PORT)
test:
	pytest
lint:
	ruff check src tests
