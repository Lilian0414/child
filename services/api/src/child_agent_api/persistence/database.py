"""Database configuration."""

import os

from sqlalchemy import Engine, create_engine, event

DEFAULT_DATABASE_URL = "sqlite:///./child_agent.db"


def create_database_engine(url: str | None = None) -> Engine:
    engine = create_engine(url or os.getenv("CHILD_DATABASE_URL") or DEFAULT_DATABASE_URL)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(dbapi_connection: object, connection_record: object) -> None:
            del connection_record
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine
