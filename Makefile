# Cross-platform: assumes an activated virtualenv (or system python with deps).
PYTHON ?= python

.PHONY: up down build test test-unit test-integration lint typecheck seed eval clean

up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker build -t resolveai-backend .

test:
	$(PYTHON) -m pytest tests/

test-unit:
	$(PYTHON) -m pytest tests/unit tests/contract

test-integration:
	$(PYTHON) -m pytest tests/integration tests/e2e

lint:
	$(PYTHON) -m ruff check src/ tests/ scripts/

typecheck:
	$(PYTHON) -m pyright src/

seed:
	$(PYTHON) scripts/seed_data.py

eval:
	$(PYTHON) scripts/run_evaluation.py

clean:
	rm -rf .pytest_cache .coverage htmlcov coverage.xml src/resolveai.egg-info build dist
