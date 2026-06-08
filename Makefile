# Property Analysis AI Agent — Development Makefile
#
# Use `make <target>` to run common development tasks.
# Run `make help` to see available targets.

.PHONY: help install-server lint lint-fix format typecheck test test-v test-all test-coverage clean dev dev-server dev-client docker-up docker-down docker-logs docker-rebuild docker-test

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Python / Server ---

install-server: ## Install server dependencies with uv
	cd server && uv sync

lint: ## Run ruff linter
	cd server && uv run ruff check .

lint-fix: ## Run ruff linter Fix
	cd server && uv run ruff check . --fix

format: ## Run ruff formatter
	cd server && uv run ruff format .

typecheck: ## Run mypy type checker
	cd server && uv run mypy --config-file pyproject.toml .

test: ## Run all tests (fast, excluding slow integration tests)
	cd server && uv run python -m pytest tests/ -v

test-all: ## Run all tests including integration
	cd server && uv run python -m pytest tests/ -v --run-integration

test-v: ## Run tests with verbose output and live logs
	cd server && uv run python -m pytest tests/ -v --log-cli-level=INFO

test-coverage: ## Run tests with coverage report
	cd server && uv run python -m pytest tests/ -v --cov=server --cov-report=term-missing

dev: ## Start both the frontend (Vite) and backend (FastAPI) development servers
	@echo "Starting backend (FastAPI) on http://0.0.0.0:8000 ..."
	uv run python -m server.main &
	@sleep 2
	@if [ -f client/package.json ]; then \
		echo "Starting frontend (Vite) on http://localhost:5173 ..."; \
		cd client && pnpm dev & \
	else \
		echo "Skipping frontend — client/package.json not found"; \
	fi
	@wait

dev-server: ## Start the FastAPI development server only
	cd server && uv run python -m server.main

dev-client: ## Start the Vite frontend development server only
	@if [ -f client/package.json ]; then \
		cd client && pnpm dev; \
	else \
		echo "Skipping frontend — client/package.json not found"; \
	fi

# --- Docker ---

docker-up: ## Start all Docker services (app, ollama, redis)
	docker compose up -d

docker-down: ## Stop all Docker services
	docker compose down

docker-logs: ## Tail logs from all Docker services
	docker compose logs -f

docker-rebuild: ## Rebuild and restart the app container
	docker compose up -d --force-recreate --build app

docker-test: ## Run tests inside the Docker app container
	docker compose exec app python -m pytest tests/ -v

# --- Cleanup ---

clean: ## Remove Python cache files and runtime data
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf server/.pytest_cache
	rm -rf server/*.egg-info
	rm -rf .eggs
	rm -rf dist
	rm -rf build
	rm -f server/data/analyses.json