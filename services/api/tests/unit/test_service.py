import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from child_agent_api.domain.errors import InvalidReferenceError, VersionConflictError
from child_agent_api.domain.models import (
    ObservationBatch,
    ObservationDecision,
    ObservationItem,
    ObservationKind,
)
from child_agent_api.persistence.models import EventRow, ObservationRow
from child_agent_api.service import WorldStateService


def batch() -> ObservationBatch:
    return ObservationBatch(
        schema_version="observation.v1",
        batch_id="obsb_shapes",
        media_id="med_synthetic",
        items=[
            ObservationItem(
                observation_id="obs_shapes",
                kind=ObservationKind.OBJECT_COUNT,
                candidate={"label": "ball", "count": 4},
                confidence=0.67,
            )
        ],
    )


def test_proposal_is_not_a_confirmed_fact_and_confirmation_is_explicit(
    service: WorldStateService,
) -> None:
    proposed = service.record_observations("ses_synthetic", batch(), 0, "key_propose")
    assert proposed.version == 1
    assert service.confirmed_facts("ses_synthetic") == []
    confirmed = service.decide_observation(
        "ses_synthetic",
        "obs_shapes",
        "ans_confirm",
        ObservationDecision(action="confirm"),
        1,
        "key_confirm",
    )
    assert confirmed.version == 2
    assert confirmed.objects[0].provenance.source.value == "child_confirmed"
    assert confirmed.objects[0].provenance.source_ref == "ans_confirm"


def test_stale_version_and_duplicate_are_no_ops(service: WorldStateService, engine: object) -> None:
    first = service.record_observations("ses_synthetic", batch(), 0, "same_key")
    duplicate = service.record_observations("ses_synthetic", batch(), 999, "same_key")
    assert duplicate == first
    with pytest.raises(VersionConflictError) as error:
        service.decide_observation(
            "ses_synthetic",
            "obs_shapes",
            "ans_x",
            ObservationDecision(action="reject"),
            0,
            "new_key",
        )
    assert error.value.current == 1
    with Session(engine) as db:  # type: ignore[arg-type]
        assert db.scalar(select(func.count()).select_from(EventRow)) == 1
        row = db.get(ObservationRow, "obs_shapes")
        assert row is not None
        assert row.status == "proposed"


def test_invalid_candidate_rolls_back_decision(service: WorldStateService, engine: object) -> None:
    invalid = ObservationBatch(
        schema_version="observation.v1",
        batch_id="obsb_bad",
        media_id="med_synthetic",
        items=[
            ObservationItem(
                observation_id="obs_bad",
                kind=ObservationKind.FACT,
                candidate={"predicate": "mood", "value": True},
                confidence=0.4,
            )
        ],
    )
    service.record_observations("ses_synthetic", invalid, 0, "key_p")
    with pytest.raises(InvalidReferenceError):
        service.decide_observation(
            "ses_synthetic",
            "obs_bad",
            "ans_bad",
            ObservationDecision(action="confirm"),
            1,
            "key_bad",
        )
    with Session(engine) as db:  # type: ignore[arg-type]
        row = db.get(ObservationRow, "obs_bad")
        assert row is not None
        assert row.status == "proposed"
        assert db.scalar(select(func.count()).select_from(EventRow)) == 1
