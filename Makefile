.PHONY: install dev test lint migrate seed clean build

install:
	uv sync

dev:
	docker-compose up -d

dev-local:
	uv run uvicorn app.api.routes:app --host 0.0.0.0 --port 8000 --reload

test:
	uv run pytest -v

lint:
	uv run ruff check app/
	uv run ruff format app/

migrate:
	uv run alembic upgrade head

seed:
	@echo "Seeding sources registry..."
	# This would run database seeding

build:
	docker-compose build

clean:
	docker-compose down -v
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete