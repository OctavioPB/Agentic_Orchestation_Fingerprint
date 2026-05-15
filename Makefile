.PHONY: up down logs test lint build

# Start all services (rebuild images if changed)
up:
	docker compose up -d --build

# Stop all services and remove volumes (clean slate)
down:
	docker compose down -v

# Tail logs for all services (Ctrl+C to exit)
logs:
	docker compose logs -f

# Run unit tests locally (requires: pip install pytest pydantic)
test:
	pytest tests/unit/ -v --tb=short

# Lint Python and TypeScript sources
lint:
	ruff check services/ tests/
	ruff format --check services/ tests/

# Build Docker images without starting services (CI check)
build:
	docker compose build
