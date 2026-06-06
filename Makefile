.PHONY: up down logs ps api worker ingest test lint build ask

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

api:
	uv run uvicorn apps.api.main:app --reload --port 8000

worker:
	cd apps/worker && uv run python worker.py

ingest:
	cd apps/worker && uv run python ingest.py

ask:
	cd apps/api && uv run python ask.py "$(q)"

test:
	uv run pytest

lint:
	uv run ruff check .

build:
	@echo "No build configured yet"
