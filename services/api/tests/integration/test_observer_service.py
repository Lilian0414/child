import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from child_agent_api.domain.models import ObservationDecision
from child_agent_api.observer import (
    FakeObserverProvider,
    ImageInput,
    ObservationPipeline,
    ObserverFailure,
)
from child_agent_api.persistence.models import EventRow
from child_agent_api.service import WorldStateService


def test_observer_proposal_then_child_correction(service: WorldStateService) -> None:
    raw = {
        "items": [
            {
                "observation_id": "obs_live",
                "kind": "object_count",
                "candidate": {"label": "ball", "count": 4},
                "confidence": 0.5,
            }
        ]
    }
    world, _ = service.observe_and_record(
        "ses_synthetic",
        ObservationPipeline(FakeObserverProvider(json.dumps(raw))),
        ImageInput("med_live", b"x", "image/png"),
        batch_id="obsb_live",
        expected_state_version=0,
        idempotency_key="observe",
    )
    assert world.objects == []
    corrected = service.decide_observation(
        "ses_synthetic",
        "obs_live",
        "ans_live",
        ObservationDecision(action="correct", supplied_value={"label": "balloon", "count": 4}),
        1,
        "correct",
    )
    assert corrected.objects[0].type == "balloon"
    assert corrected.objects[0].provenance.source.value == "child_supplied"


@pytest.mark.parametrize(
    "response",
    [
        "bad",
        json.dumps(
            {
                "items": [
                    {
                        "observation_id": "obs_bad",
                        "kind": "fact",
                        "candidate": {"diagnosis": "autism"},
                        "confidence": 1.0,
                    }
                ]
            }
        ),
    ],
)
def test_failed_boundary_changes_zero_state_or_events(
    service: WorldStateService, engine: object, response: str
) -> None:
    before = service.get_world("ses_synthetic")
    with pytest.raises(ObserverFailure):
        service.observe_and_record(
            "ses_synthetic",
            ObservationPipeline(FakeObserverProvider(response)),
            ImageInput("med_bad", b"x", "image/png"),
            batch_id="obsb_bad",
            expected_state_version=0,
            idempotency_key="bad",
        )
    assert service.get_world("ses_synthetic") == before
    with Session(engine) as db:  # type: ignore[arg-type]
        assert db.scalar(select(func.count()).select_from(EventRow)) == 0


def test_timeout_preserves_already_confirmed_world(service: WorldStateService) -> None:
    raw = {
        "items": [
            {
                "observation_id": "obs_first",
                "kind": "object_count",
                "candidate": {"label": "balloon", "count": 4},
                "confidence": 0.8,
            }
        ]
    }
    service.observe_and_record(
        "ses_synthetic",
        ObservationPipeline(FakeObserverProvider(json.dumps(raw))),
        ImageInput("med_first", b"x", "image/png"),
        batch_id="obsb_first",
        expected_state_version=0,
        idempotency_key="first",
    )
    confirmed = service.decide_observation(
        "ses_synthetic",
        "obs_first",
        "ans_first",
        ObservationDecision(action="confirm"),
        1,
        "confirm-first",
    )
    with pytest.raises(ObserverFailure):
        service.observe_and_record(
            "ses_synthetic",
            ObservationPipeline(FakeObserverProvider("", error=TimeoutError())),
            ImageInput("med_retry", b"x", "image/png"),
            batch_id="obsb_retry",
            expected_state_version=2,
            idempotency_key="retry",
        )
    assert service.get_world("ses_synthetic") == confirmed


def test_committed_observation_retry_does_not_call_provider_or_advance_state(
    service: WorldStateService, engine: object
) -> None:
    raw = {
        "items": [
            {
                "observation_id": "obs_retry",
                "kind": "object",
                "candidate": {"label": "kite"},
                "confidence": 0.8,
            }
        ]
    }
    first_provider = FakeObserverProvider(json.dumps(raw))
    first_world, first_result = service.observe_and_record(
        "ses_synthetic",
        ObservationPipeline(first_provider),
        ImageInput("med_retry", b"x", "image/png"),
        batch_id="obsb_retry",
        expected_state_version=0,
        idempotency_key="observe-retry",
    )
    retry_provider = FakeObserverProvider("", error=AssertionError("provider called on retry"))
    retry_world, retry_result = service.observe_and_record(
        "ses_synthetic",
        ObservationPipeline(retry_provider),
        ImageInput("med_retry", b"x", "image/png"),
        batch_id="obsb_retry",
        expected_state_version=0,
        idempotency_key="observe-retry",
    )
    assert retry_provider.observe_calls == 0
    assert retry_world == first_world
    assert retry_result.batch == first_result.batch
    with Session(engine) as db:  # type: ignore[arg-type]
        assert db.scalar(select(func.count()).select_from(EventRow)) == 1
