# Railway staging deployment

The first staging release uses one Railway service for both the FastAPI API and the
static files in `apps/web`. FastAPI serves the web application from the same origin, so
this deployment does not need a separate frontend service or CORS configuration.

## Service configuration

Create a Railway service from this repository. The repository-owned `railway.toml` uses
Railpack, installs the locked production dependencies, and starts the service on
`0.0.0.0` using Railway's `PORT`. The start command runs `alembic upgrade head` before
Uvicorn on every runtime start. This ordering is intentional: a Railway volume is only
available at runtime, so a pre-deploy migration cannot migrate the SQLite database on
that volume.

Configure the service health check to use the repository setting, `GET /health`.

## Persistent SQLite state

For the first staging environment:

1. Add a Railway volume to the service and mount it at `/data`.
2. Set `CHILD_DATABASE_URL=sqlite:////data/child_agent.db`.
3. Run exactly one service replica. SQLite on one volume is the staging persistence
   choice for this phase; do not attach the same database file to multiple replicas.

The database contains canonical session, world, story, and provenance state. Uploaded
drawing and generated audio media remain transient.

## Variables

Required for first staging:

```dotenv
CHILD_DATABASE_URL=sqlite:////data/child_agent.db
GMI_API_KEY=
```

MiniMax on GMI Cloud (`GMI_API_KEY`) is the confirmed live VLM + story provider; there is
no offline/demo fallback mode. The following variables are optional:

- `ELEVENLABS_API_KEY` for ElevenLabs TTS;
- `CHILD_OBSERVER_API_KEY`, `CHILD_OBSERVER_MODEL`, and
  `CHILD_OBSERVER_BASE_URL` for the generic observer adapter;
- `CHILD_API_CORS_ORIGINS` only if a future deployment introduces a separate origin.

Keep all secrets in Railway Variables, never in repository files. Railway supplies
`PORT`; do not set it manually.

## Release verification

Before deploying a commit, run:

```bash
make check
python -c 'import tomllib; tomllib.load(open("railway.toml", "rb"))'
```

For a local production-style smoke test, use a temporary database and port while
running the exact commands represented by `railway.toml`:

```bash
export CHILD_DATABASE_URL="sqlite:////tmp/child-agent-staging.db"
export GMI_API_KEY="<your GMI Cloud key>"
export PORT=8000
uv run --project services/api --no-sync alembic -c services/api/alembic.ini upgrade head \
  && uv run --project services/api --no-sync uvicorn child_agent_api.main:app \
    --host 0.0.0.0 --port "${PORT:-8000}"
curl --fail "http://127.0.0.1:${PORT}/health"
```

## Follow-up hardening

Provider selection is now fixed to MiniMax in code (no public switch endpoint), so there
is no live-provider mode switch to restrict before treating the staging URL as a
hardened public deployment.
