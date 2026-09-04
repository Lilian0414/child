.PHONY: setup dev-api dev-web benchmark-observer lint typecheck test build check

setup:
	uv sync --project services/api --all-groups --locked
	npm ci --prefix apps/web

dev-api:
	uv run --project services/api uvicorn child_agent_api.main:app --reload --port 8000

dev-web:
	npm run dev --prefix apps/web

benchmark-observer:
	uv run --project services/api python -m child_agent_api.benchmark

lint:
	uv run --project services/api ruff check services/api
	npm run lint --prefix apps/web

typecheck:
	uv run --project services/api mypy services/api/src services/api/tests
	npm run typecheck --prefix apps/web

test:
	uv run --project services/api pytest services/api/tests
	npm run test --prefix apps/web

build:
	npm run build --prefix apps/web

check: lint typecheck test build
