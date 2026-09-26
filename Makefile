.PHONY: help install dev test test-backend test-frontend types eval deploy up-local down-local

COMPOSE_LOCAL = docker compose -f deploy/docker-compose.local.yml

help:
	@echo "make install        install backend (uv) and frontend (npm) dependencies"
	@echo "make dev            backend on :8000 with reload + Vite on :5173 (proxies /api); Ctrl-C stops both"
	@echo "make test           everything below; must pass on main"
	@echo "make test-backend   pytest"
	@echo "make test-frontend  vitest + TypeScript type-check"
	@echo "make types          regenerate shared/schema and frontend/src/types from the Pydantic models"
	@echo "make eval           run the sketch-parsing eval set (AI-8)"
	@echo "make up-local       production stack in Docker on http://localhost:8080 (no TLS)"
	@echo "make down-local     stop it"
	@echo "make deploy         deploy to the VM (needs DEPLOY_HOST and DOMAIN; see deploy/deploy.sh)"

install:
	cd backend && uv sync
	cd frontend && npm ci

# Backend (reload) + Vite dev server with proxy. Ctrl-C (or either process exiting on a signal)
# stops both. `npm run dev:fixtures` in frontend/ runs the UI without a backend.
dev:
	@trap 'kill 0' INT TERM; \
	(cd backend && uv run uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

# Backend (pytest) and frontend (vitest, type-check) tests. Must pass on main.
test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest

test-frontend:
	cd frontend && npm test
	cd frontend && npx tsc --noEmit

# Regenerate shared/schema (JSON Schema) from the Pydantic models, then the TS types from it.
# Run after ANY change to backend/app/models/.
types:
	cd backend && uv run python scripts/generate_schema.py
	cd frontend && npm run types

# Run the parse eval set and report accuracy per param. The runner itself is AI-8.
eval:
	@test -f evals/run_parse_eval.py || { echo "evals/run_parse_eval.py does not exist yet (AI-8)"; exit 1; }
	cd backend && uv run python ../evals/run_parse_eval.py

deploy:
	deploy/deploy.sh

up-local:
	$(COMPOSE_LOCAL) up -d --build
	@echo "http://localhost:$${LOCAL_PORT:-8080}"

down-local:
	$(COMPOSE_LOCAL) down
