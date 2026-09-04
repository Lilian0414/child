.PHONY: setup dev-api dev-web benchmark-observer lint typecheck test check

setup:
	uv sync --project services/api --all-groups --locked

dev-api:
	uv run --project services/api uvicorn child_agent_api.main:app --reload --port 8000

dev-web:
	@echo "apps/web is plain HTML/CSS/JS — no dev server needed."
	@echo "Run 'make dev-api' and open http://localhost:8000 (FastAPI serves apps/web),"
	@echo "or open apps/web/index.html directly in a browser."

benchmark-observer:
	uv run --project services/api python -m child_agent_api.benchmark

lint:
	uv run --project services/api ruff check services/api

typecheck:
	uv run --project services/api mypy services/api/src services/api/tests

test:
	uv run --project services/api pytest services/api/tests

check: lint typecheck test
