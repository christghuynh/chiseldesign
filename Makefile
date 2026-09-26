.PHONY: dev test types eval

# Run backend (reload) + Vite dev server with proxy. Real target: INF-9.
dev:
	@echo "TODO (INF-9): start backend with reload and the Vite dev server"

# Run backend pytest suite (and frontend checks). Must pass on main. Real target: INF-9.
test:
	@echo "TODO (INF-9): run pytest and frontend checks"

# Regenerate shared/schema JSON Schema from Pydantic and the TS types. Real target: F-2.
types:
	@echo "TODO (F-2): generate JSON Schema from Pydantic models and TS types"

# Run the parse eval set and report accuracy per param. Real target: AI-8.
eval:
	@echo "TODO (AI-8): run evals/run_parse_eval.py"
