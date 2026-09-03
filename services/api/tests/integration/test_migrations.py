from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_empty_database_upgrades_to_head(tmp_path: Path) -> None:
    database = tmp_path / "migration.db"
    config = Config("services/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    command.upgrade(config, "head")
    assert set(inspect(create_engine(f"sqlite:///{database}")).get_table_names()) == {
        "alembic_version",
        "events",
        "idempotency_records",
        "observation_batches",
        "observations",
        "sessions",
        "world_snapshots",
    }
