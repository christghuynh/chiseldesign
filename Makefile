.PHONY: dev test types eval

# Run backend (reload) + Vite dev server with proxy. Real target: INF-9.
# Until then, in two terminals:
#   cd backend && uv run uvicorn app.main:app --reload --port 8000
#   cd frontend && npm run dev            (or `npm run dev:fixtures` to run without the backend)
dev:
	@echo "TODO (INF-9): start backend with reload and the Vite dev server"

# Backend (pytest) and frontend (vitest, type-check) tests. Must pass on main.
test:
	cd backend && uv run pytest
	cd frontend && npm test
	cd frontend && npx tsc --noEmit

# Regenerate shared/schema (JSON Schema) from the Pydantic models, then the TS types from it.
# Run after ANY change to backend/app/models/.
types:
	cd backend && uv run python scripts/generate_schema.py
	cd frontend && npm run types

# Run the parse eval set and report accuracy per param. Real target: AI-8.
eval:
	@echo "TODO (AI-8): run evals/run_parse_eval.py"
