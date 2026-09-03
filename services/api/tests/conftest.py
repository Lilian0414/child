from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine

from child_agent_api.persistence.database import create_database_engine
from child_agent_api.persistence.models import Base
from child_agent_api.service import WorldStateService


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    value = create_database_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(value)
    yield value
    value.dispose()


@pytest.fixture
def service(engine: Engine) -> WorldStateService:
    result = WorldStateService(engine)
    result.create_session(
        "ses_synthetic",
        __import__(
            "child_agent_api.domain.models", fromlist=["AccessibilityProfile"]
        ).AccessibilityProfile(),
    )
    return result
