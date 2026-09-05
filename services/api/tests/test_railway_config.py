import tomllib
from pathlib import Path


def test_railway_runtime_contract() -> None:
    config = tomllib.loads(Path("railway.toml").read_text())

    assert config["build"] == {
        "builder": "RAILPACK",
        "buildCommand": "uv sync --project services/api --locked --no-dev",
    }

    deploy = config["deploy"]
    start = deploy["startCommand"]
    migration = "alembic -c services/api/alembic.ini upgrade head"
    server = "uvicorn child_agent_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"

    assert migration in start
    assert server in start
    assert start.index(migration) < start.index(server)
    assert "&& exec" in start
    assert deploy["healthcheckPath"] == "/health"
