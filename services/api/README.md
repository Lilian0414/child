# Child Agent API

FastAPI service for the Child-Grounded Story Agent. It exposes the original
health endpoint and contains the provider-neutral session/world-state core.
Persistence defaults to `sqlite:///./child_agent.db` and can be configured with
`CHILD_DATABASE_URL`. Run migrations from the repository root:

```bash
alembic -c services/api/alembic.ini upgrade head
```
