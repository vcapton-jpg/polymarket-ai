.PHONY: install dev dev-local test lint migrate build clean seed

install:
	# `--extra dev` brings in pytest-asyncio + ruff + pytest-cov so `make test`
	# and `make lint` work out of the box. Without it, `pytest` collects
	# asyncio tests as plain functions and 30+ fail with "async not supported".
	uv sync --extra dev
	uv run python -m spacy download en_core_web_lg

dev:
	docker compose up -d

dev-local:
	uv run uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload

test:
	uv run pytest -v

lint:
	uv run ruff check app/
	uv run ruff format app/

migrate:
	uv run alembic upgrade head

migrate-new:
	uv run alembic revision --autogenerate -m "$(msg)"

seed:
	uv run python -m app.scripts.seed_sources

build:
	docker compose build

clean:
	docker compose down -v
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

logs:
	docker compose logs -f app worker beat

tunnel:
	@echo "Starting Cloudflare tunnel → accessible from anywhere (4G, etc.)"
	cloudflared tunnel --url http://localhost:3000

mobile:
	@echo "Starting mobile dev server → accessible on local WiFi"
	cd frontend && npm run dev -- --host
