.PHONY: up down test seed lint typecheck clean build

up:
	docker-compose up -d

down:
	docker-compose down

test:
	.\.venv\Scripts\pytest tests/unit/

seed:
	.\.venv\Scripts\python scripts/seed_data.py

lint:
	.\.venv\Scripts\ruff check src/ tests/

typecheck:
	.\.venv\Scripts\pyright src/ tests/

clean:
	rm -rf .pytest_cache .coverage htmlcov coverage.xml src/resolveai.egg-info build dist

build:
	docker build -t resolveai-backend .
