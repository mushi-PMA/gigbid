# GigBid developer commands. Python commands use the project virtual environment when it exists.
PY ?= $(if $(wildcard .venv/Scripts/python.exe),.venv/Scripts/python.exe,$(if $(wildcard .venv/bin/python),.venv/bin/python,python))
COMPOSE = docker compose -f infra/docker-compose.yml --env-file .env

.PHONY: dev test eval smoke-eval seed demo lint indexes graphs up down

dev:            ## run the whole stack locally (web on :8080, API on :8000, Phoenix on :6006)
	$(COMPOSE) up --build

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

test:           ## unit, contract and integration tests (offline, no API key needed)
	$(PY) -m pytest -q
	cd apps/web && npx playwright test

seed:           ## rebuild data (personas, GigSim seed, dev and holdout sets) and the evidence indexes
	$(PY) -m data.build.build_all
	$(PY) -m rag.ingest.build_indexes

indexes:
	$(PY) -m rag.ingest.build_indexes

eval:           ## full evaluation: retrieval, decisions, proposals, GigSim outcomes; writes evals/results/*.json
	$(PY) -m evals.runners.run_all

smoke-eval:     ## 30-job smoke evaluation with failure thresholds (used by CI)
	$(PY) -m evals.runners.smoke_eval

demo:           ## one job from inbox to approval against GigSim, printed step by step
	$(PY) -m evals.runners.demo_single_agent

graphs:         ## render both graphs from code into docs/images
	$(PY) -m scripts.render_graphs

lint:
	$(PY) -m ruff check .
	cd apps/web && npm run build
