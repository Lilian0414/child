from pathlib import Path
from typing import Literal

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from child_agent_api.domain.errors import VersionConflictError
from child_agent_api.domain.models import (
    CandidateDecision,
    JsonValue,
    ObservationBatch,
    ObservationItem,
    ObservationKind,
    RevisionState,
)
from child_agent_api.persistence.database import create_database_engine
from child_agent_api.persistence.models import EventRow
from child_agent_api.service import WorldStateService


def batch(identifier: str, *values: tuple[str, str, int]) -> ObservationBatch:
    return ObservationBatch(
        schema_version="observation.v1",
        batch_id=f"obsb_{identifier}",
        media_id=f"med_{identifier}",
        items=[
            ObservationItem(
                observation_id=observation_id,
                kind=ObservationKind.OBJECT_COUNT,
                candidate={"label": label, "count": count},
                confidence=0.9,
            )
            for observation_id, label, count in values
        ],
    )


def decision(
    state: RevisionState,
    observation_id: str,
    action: Literal["confirm", "reject", "correct", "skip"],
    value: dict[str, JsonValue] | None = None,
) -> CandidateDecision:
    candidate = next(item for item in state.candidates if item.observation_id == observation_id)
    return CandidateDecision(
        candidate_id=candidate.candidate_id, action=action, supplied_value=value
    )


def test_two_revision_correction_addition_retry_stale_and_reload(
    service: WorldStateService, engine: Engine, tmp_path: Path
) -> None:
    r1 = service.submit_revision(
        "ses_synthetic",
        "rev_r1",
        batch("r1", ("obs_people", "person", 4), ("obs_balls", "ball", 4)),
        0,
        "revision-r1",
    )
    assert r1.world.version == 0
    assert {candidate.change.value for candidate in r1.candidates} == {"added"}
    r1_done = service.resolve_revision(
        "ses_synthetic",
        "rev_r1",
        [
            decision(r1, "obs_people", "confirm"),
            decision(r1, "obs_balls", "correct", {"label": "balloon", "count": 4}),
        ],
        "ans_r1",
        0,
        "resolve-r1",
    )
    assert r1_done.world.version == 1
    assert {(item.type, item.count) for item in r1_done.world.objects} == {
        ("person", 4),
        ("balloon", 4),
    }

    r2_batch = batch(
        "r2",
        ("obs_people_r2", "person", 4),
        ("obs_balloons_r2", "balloon", 4),
        ("obs_dog", "dog", 1),
    )
    r2 = service.submit_revision("ses_synthetic", "rev_r2", r2_batch, 1, "revision-r2")
    assert [prompt.candidate_id for prompt in r2.prompts] == [
        decision(r2, "obs_dog", "confirm").candidate_id
    ]
    assert sum(candidate.change.value == "unchanged" for candidate in r2.candidates) == 2

    r2_done = service.resolve_revision(
        "ses_synthetic",
        "rev_r2",
        [decision(r2, "obs_dog", "confirm")],
        "ans_r2",
        1,
        "resolve-r2",
    )
    duplicate = service.resolve_revision(
        "ses_synthetic",
        "rev_r2",
        [decision(r2, "obs_dog", "confirm")],
        "ans_r2",
        1,
        "resolve-r2",
    )
    assert duplicate.world == r2_done.world
    assert r2_done.world.version == 2
    assert {(item.type, item.count) for item in r2_done.world.objects} == {
        ("person", 4),
        ("balloon", 4),
        ("dog", 1),
    }
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(EventRow)) == 2
    with pytest.raises(VersionConflictError):
        service.submit_revision(
            "ses_synthetic",
            "rev_stale",
            batch("stale", ("obs_cat", "cat", 1)),
            1,
            "revision-stale",
        )

    engine.dispose()
    reloaded_engine = create_database_engine(f"sqlite:///{tmp_path / 'test.db'}")
    reloaded = WorldStateService(reloaded_engine)
    assert reloaded.get_world("ses_synthetic") == r2_done.world
    assert reloaded.get_revision("ses_synthetic", "rev_r2").revision.number == 2
    reloaded_engine.dispose()


def test_changed_and_removed_require_authority(service: WorldStateService) -> None:
    r1 = service.submit_revision(
        "ses_synthetic",
        "rev_seed",
        batch("seed", ("obs_kite", "kite", 1), ("obs_hat", "hat", 1)),
        0,
        "revision-seed",
    )
    service.resolve_revision(
        "ses_synthetic",
        "rev_seed",
        [decision(r1, "obs_kite", "confirm"), decision(r1, "obs_hat", "confirm")],
        "ans_seed",
        0,
        "resolve-seed",
    )
    changed = service.submit_revision(
        "ses_synthetic",
        "rev_change",
        batch("change", ("obs_boat", "boat", 1)),
        1,
        "revision-change",
    )
    assert {item.change.value for item in changed.candidates} == {"changed", "removed"}
    decisions = [
        CandidateDecision(candidate_id=item.candidate_id, action="confirm")
        for item in changed.candidates
    ]
    resolved = service.resolve_revision(
        "ses_synthetic", "rev_change", decisions, "ans_change", 1, "resolve-change"
    )
    assert [item.type for item in resolved.world.objects] == ["boat"]
    assert len(resolved.world.retired_ids) == 1
