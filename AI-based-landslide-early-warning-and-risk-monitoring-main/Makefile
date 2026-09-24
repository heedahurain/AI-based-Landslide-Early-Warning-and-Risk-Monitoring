# ShailSuraksha — developer entry points.
#
# `make up` must bring the entire local stack online from a clean checkout.
# On Windows without GNU make, use the mirror: ./make.ps1 <target>

COMPOSE := docker compose -f infra/docker-compose.yml
PY := python
VENV_PY := .venv/Scripts/python.exe

.DEFAULT_GOAL := help
.PHONY: help up up-workers up-ml down logs ps restart seed migrate revision train test test-api test-web \
        lint format typecheck contrast probe-sources build clean install-web install-py

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# --- Stack ------------------------------------------------------------------

up: ## Start the core stack (postgres, redis, mosquitto, minio, api, web)
	$(COMPOSE) up -d --build
	@echo ""
	@echo "  API      http://localhost:8000/docs"
	@echo "  Web      http://localhost:3000"
	@echo "  MinIO    http://localhost:9002"
	@echo ""

up-workers: ## Start the stack including the Celery worker and beat
	$(COMPOSE) --profile workers up -d --build

up-ml: ## Start the stack including MLflow
	$(COMPOSE) --profile ml up -d --build

down: ## Stop everything and remove containers
	$(COMPOSE) down

clean: ## Stop everything and delete volumes. Destroys local data.
	$(COMPOSE) down -v

logs: ## Follow logs for all services
	$(COMPOSE) logs -f

ps: ## Show service status
	$(COMPOSE) ps

restart: ## Restart the API and worker only
	$(COMPOSE) restart api worker

# --- Database ---------------------------------------------------------------

migrate: ## Apply Alembic migrations
	$(COMPOSE) exec api alembic upgrade head

revision: ## Create a migration. Usage: make revision m="add slope units"
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(m)"

seed: ## Load reference data. Phase 1 provides the admin hierarchy and terrain.
	$(COMPOSE) exec api python -m app.db.seed

# --- Machine learning -------------------------------------------------------

train: ## Train and register models. Phase 3 provides the pipeline.
	$(COMPOSE) --profile ml exec api python -m ml.train

# --- Quality ----------------------------------------------------------------

test: test-api test-web ## Run every test suite

test-api: ## Run the Python test suites
	$(VENV_PY) -m pytest -q

test-web: ## Run web unit tests and the contrast audit
	cd web && npm run test

lint: ## Lint Python and TypeScript
	$(VENV_PY) -m ruff check api ingest ml
	cd web && npm run lint

format: ## Format Python and TypeScript
	$(VENV_PY) -m ruff format api ingest ml
	cd web && npm run format

typecheck: ## Type-check Python and TypeScript
	PYTHONPATH=api:ml:ingest $(VENV_PY) -m mypy api ingest ml
	cd web && npm run typecheck

contrast: ## Audit design tokens against WCAG AA
	cd web && npm run contrast

# --- Data -------------------------------------------------------------------

probe-sources: ## Re-probe every upstream data source and print a status table
	$(PY) scripts/probe_sources.py

# --- Setup ------------------------------------------------------------------

install-py: ## Create the Python virtual environment and install dev dependencies
	$(PY) -m venv .venv
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -r requirements-dev.txt

install-web: ## Install web dependencies
	cd web && npm ci

build: ## Build all container images without starting them
	$(COMPOSE) build
