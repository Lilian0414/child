from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from child_agent_api.domain.models import (
    AccessibilityProfile,
    ObservationBatch,
    Session,
    SessionStatus,
    WorldState,
)


def test_contracts_are_strict_and_versioned() -> None:
    with pytest.raises(ValidationError):
        ObservationBatch.model_validate(
            {
                "schema_version": "observation.v2",
                "batch_id": "obsb_x",
                "media_id": "med_x",
                "items": [],
                "provider_payload": {},
            }
        )
    with pytest.raises(ValidationError):
        AccessibilityProfile(choice_count="2")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        WorldState(session_id="ses_x", version=0, stale_fact_ids=["fact_missing"])


def test_session_requires_aware_ordered_expiry() -> None:
    now = datetime.now(UTC)
    session = Session(
        session_id="ses_x",
        status=SessionStatus.GROUNDING,
        state_version=0,
        profile=AccessibilityProfile(),
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    assert session.created_at.tzinfo is UTC
    with pytest.raises(ValidationError):
        session.model_copy(update={"expires_at": now - timedelta(seconds=1)}).model_validate(
            session.model_copy(update={"expires_at": now - timedelta(seconds=1)}).model_dump()
        )
