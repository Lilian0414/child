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
        "drawing_revisions",
        "events",
        "idempotency_records",
        "observation_batches",
        "observations",
        "reconciliation_candidates",
        "sessions",
        "story_proposals",
        "story_snapshots",
        "world_snapshots",
    }


def test_upgrade_uses_configured_application_database(tmp_path: Path, monkeypatch) -> None:
    configured_database = tmp_path / "configured.db"
    ini_database = tmp_path / "ini-default.db"
    monkeypatch.setenv("CHILD_DATABASE_URL", f"sqlite:///{configured_database}")
    config = Config("services/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{ini_database}")

    command.upgrade(config, "head")

    assert (
        "sessions" in inspect(create_engine(f"sqlite:///{configured_database}")).get_table_names()
    )
    assert not ini_database.exists()
