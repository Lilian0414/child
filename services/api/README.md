# Child Agent API

FastAPI service for the Child-Grounded Story Agent. It exposes the original
health endpoint and contains the provider-neutral session/world-state core.
Persistence defaults to `sqlite:///./child_agent.db` and can be configured with
`CHILD_DATABASE_URL`. Run migrations from the repository root:

```bash
alembic -c services/api/alembic.ini upgrade head
```

## Drawing observer benchmark

Run the 12-case repository-owned synthetic benchmark without credentials or network access:

```bash
make benchmark-observer
```

It writes machine-readable JSON and a Markdown summary under `build/`. The optional
OpenAI-compatible adapter is isolated in `providers/openai_compatible.py` and reads
`CHILD_OBSERVER_API_KEY`, `CHILD_OBSERVER_MODEL`, and `CHILD_OBSERVER_BASE_URL`.
Live evaluation is deliberately opt-in and is never part of `make check`:

```bash
uv run --project services/api python -m child_agent_api.benchmark --provider live
```

The live command sends the same 12 valid, repository-owned synthetic SVG fixtures through
the configured adapter. Without all three variables it exits explicitly as `not run`; it
never substitutes fake-provider results for live evidence. CI runs only the offline fake
provider benchmark.
