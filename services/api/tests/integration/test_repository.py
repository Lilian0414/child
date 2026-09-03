from datetime import UTC

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from child_agent_api.domain.models import (
    ObservationBatch,
    ObservationDecision,
    ObservationItem,
    ObservationKind,
)
from child_agent_api.persistence.models import (
    EventRow,
    IdempotencyRow,
    SessionRow,
    WorldSnapshotRow,
)
from child_agent_api.service import WorldStateService


def test_event_snapshot_and_idempotency_are_atomic(
    engine: object, service: WorldStateService
) -> None:
    item = ObservationItem(
        observation_id="obs_atomic",
        kind=ObservationKind.OBJECT,
        candidate={"type": "kite"},
        confidence=0.8,
    )
    batch = ObservationBatch(
        schema_version="observation.v1", batch_id="obsb_atomic", media_id="med_fake", items=[item]
    )
    failing = WorldStateService(
        service.engine,
        before_commit=lambda: (_ for _ in ()).throw(RuntimeError("synthetic failure")),
    )
    with pytest.raises(RuntimeError):
        failing.record_observations("ses_synthetic", batch, 0, "key_atomic")
    with Session(engine) as db:  # type: ignore[arg-type]
        assert db.scalar(select(func.count()).select_from(EventRow)) == 0
        assert db.scalar(select(func.count()).select_from(IdempotencyRow)) == 0
        session_row = db.get(SessionRow, "ses_synthetic")
        snapshot_row = db.get(WorldSnapshotRow, "ses_synthetic")
        assert session_row is not None and snapshot_row is not None
        assert session_row.state_version == 0
        assert snapshot_row.version == 0


def test_sqlite_timestamps_round_trip_as_utc(
    engine: object, service: WorldStateService
) -> None:
    service.record_observations(
        "ses_synthetic",
        ObservationBatch(
            schema_version="observation.v1",
            batch_id="obsb_time",
            media_id="med_fake",
            items=[
                ObservationItem(
                    observation_id="obs_time",
                    kind=ObservationKind.OBJECT,
                    candidate={"type": "kite"},
                    confidence=0.8,
                )
            ],
        ),
        0,
        "key_time",
    )
    with Session(engine) as db:  # type: ignore[arg-type]
        session_row = db.get(SessionRow, "ses_synthetic")
        event_row = db.scalar(select(EventRow))
        assert session_row is not None and event_row is not None
        assert session_row.created_at.tzinfo is UTC
        assert session_row.expires_at.tzinfo is UTC
        assert event_row.created_at.tzinfo is UTC


def test_correction_keeps_history_and_marks_transitive_derived_facts_stale(
    service: WorldStateService, engine: object
) -> None:
    with Session(engine) as db, db.begin():  # type: ignore[arg-type]
        snapshot = db.get(WorldSnapshotRow, "ses_synthetic")
        assert snapshot is not None
        snapshot.state = {
            "schema_version": "world.v1",
            "session_id": "ses_synthetic",
            "version": 0,
            "characters": [
                {
                    "character_id": "char_a",
                    "name": "A",
                    "attributes": {},
                    "provenance": {"source": "child_supplied", "source_ref": "ans_seed"},
                }
            ],
            "objects": [],
            "relationships": [],
            "facts": [
                {
                    "fact_id": "fact_base",
                    "subject_ref": "char_a",
                    "predicate": "mood",
                    "value": "sad",
                    "provenance": {"source": "child_confirmed", "source_ref": "ans_old"},
                    "depends_on": [],
                },
                {
                    "fact_id": "fact_d1",
                    "subject_ref": "char_a",
                    "predicate": "quiet",
                    "value": True,
                    "provenance": {"source": "story_derived", "source_ref": "choice_seed"},
                    "depends_on": ["fact_base"],
                },
                {
                    "fact_id": "fact_d2",
                    "subject_ref": "char_a",
                    "predicate": "apart",
                    "value": True,
                    "provenance": {"source": "story_derived", "source_ref": "choice_seed"},
                    "depends_on": ["fact_d1"],
                },
            ],
            "stale_fact_ids": [],
        }
    item = ObservationItem(
        observation_id="obs_base",
        kind=ObservationKind.FACT,
        candidate={
            "fact_id": "fact_base",
            "subject_ref": "char_a",
            "predicate": "mood",
            "value": "sad",
        },
        confidence=0.6,
    )
    service.record_observations(
        "ses_synthetic",
        ObservationBatch(
            schema_version="observation.v1", batch_id="obsb_fact", media_id="med_fake", items=[item]
        ),
        0,
        "key_obs",
    )
    world = service.decide_observation(
        "ses_synthetic",
        "obs_base",
        "ans_fix",
        ObservationDecision(
            action="correct",
            supplied_value={
                "fact_id": "fact_base",
                "subject_ref": "char_a",
                "predicate": "mood",
                "value": "happy",
            },
        ),
        1,
        "key_fix",
    )
    assert world.version == 2
    assert set(world.stale_fact_ids) == {"fact_d1", "fact_d2"}
    assert (
        next(f for f in world.facts if f.fact_id == "fact_base").provenance.source.value
        == "child_supplied"
    )
    with Session(engine) as db:  # type: ignore[arg-type]
        assert [e.event_type for e in db.scalars(select(EventRow).order_by(EventRow.sequence))] == [
            "OBSERVATIONS_PROPOSED",
            "OBSERVATION_CORRECTED",
        ]
