from pathlib import Path
from typing import Literal

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from child_agent_api.domain.errors import InvalidReferenceError, VersionConflictError
from child_agent_api.domain.models import (
    CandidateDecision,
    JsonValue,
    ObservationBatch,
    ObservationItem,
    ObservationKind,
    RevisionState,
)
from child_agent_api.observer import ObserverPayload
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


def test_only_safely_canonicalizable_observer_shapes_are_grounding_prompts(
    service: WorldStateService,
) -> None:
    payload = ObserverPayload.model_validate(
        {
            "items": [
                {
                    "observation_id": "obs_a_obj",
                    "kind": "object",
                    "candidate": {"label": "dog"},
                    "confidence": 0.9,
                },
                {
                    "observation_id": "obs_b_count",
                    "kind": "object_count",
                    "candidate": {"label": "ball", "count": 2},
                    "confidence": 0.9,
                },
                {
                    "observation_id": "obs_c_character",
                    "kind": "character",
                    "candidate": {"visible_description": "a drawn figure"},
                    "confidence": 0.9,
                },
                {
                    "observation_id": "obs_d_fact",
                    "kind": "fact",
                    "candidate": {"visible_expression": "curved mouth"},
                    "confidence": 0.9,
                },
                {
                    "observation_id": "obs_e_relationship",
                    "kind": "relationship",
                    "candidate": {"visible": "side by side", "relationship": "unknown"},
                    "confidence": 0.9,
                },
            ]
        }
    )
    batch_from_boundary = ObservationBatch(
        schema_version="observation.v1",
        batch_id="obsb_all_shapes",
        media_id="med_all_shapes",
        items=payload.to_domain_items(),
    )
    state = service.submit_revision(
        "ses_synthetic", "rev_all_shapes", batch_from_boundary, 0, "revision-all-shapes"
    )
    prompts = {prompt.kind: prompt for prompt in state.prompts}
    assert set(prompts) == {
        ObservationKind.OBJECT,
        ObservationKind.OBJECT_COUNT,
        ObservationKind.CHARACTER,
    }
    assert all(
        prompt.allowed_actions == ["confirm", "correct", "reject", "skip"]
        for prompt in prompts.values()
    )

    for kind in (ObservationKind.FACT, ObservationKind.RELATIONSHIP):
        unsafe = next(candidate for candidate in state.candidates if candidate.kind == kind)
        with pytest.raises(InvalidReferenceError, match="does not target a grounding prompt"):
            service.resolve_revision(
                "ses_synthetic",
                "rev_all_shapes",
                [
                    CandidateDecision(
                        candidate_id=unsafe.candidate_id,
                        action="correct",
                        supplied_value={"visible_description": "不能成為 canonical state"},
                    )
                ],
                f"ans_invalid_{kind.value}",
                0,
                f"resolve-invalid-{kind.value}",
            )
    assert service.get_world("ses_synthetic").version == 0

    decisions = []
    for candidate in state.candidates:
        if candidate.kind in {ObservationKind.OBJECT, ObservationKind.OBJECT_COUNT}:
            decisions.append(
                CandidateDecision(candidate_id=candidate.candidate_id, action="confirm")
            )
        elif candidate.kind == ObservationKind.CHARACTER:
            decisions.append(
                CandidateDecision(
                    candidate_id=candidate.candidate_id,
                    action="correct",
                    supplied_value={"visible_description": "小畫家"},
                )
            )
    resolved = service.resolve_revision(
        "ses_synthetic", "rev_all_shapes", decisions, "ans_all_shapes", 0, "resolve-all-shapes"
    )
    assert resolved.revision.status == "resolved"
    assert len(resolved.world.objects) == 2
    assert len(resolved.world.characters) == 1
    assert resolved.world.characters[0].name == "小畫家"
    assert resolved.world.characters[0].provenance.source.value == "child_supplied"
    assert resolved.world.facts == []
    assert resolved.world.relationships == []


def test_confirmed_character_is_canonical_and_not_reasked(service: WorldStateService) -> None:
    first = ObserverPayload.model_validate(
        {
            "items": [
                {
                    "observation_id": "obs_figure",
                    "kind": "character",
                    "candidate": {
                        "visible_description": "戴帽子的人",
                        "visible_gesture": "揮手",
                    },
                    "confidence": 0.9,
                }
            ]
        }
    )
    proposed = service.submit_revision(
        "ses_synthetic",
        "rev_character_1",
        ObservationBatch(
            schema_version="observation.v1",
            batch_id="obsb_character_1",
            media_id="med_character_1",
            items=first.to_domain_items(),
        ),
        0,
        "revision-character-1",
    )
    assert proposed.prompts[0].allowed_actions == ["confirm", "correct", "reject", "skip"]
    resolved = service.resolve_revision(
        "ses_synthetic",
        "rev_character_1",
        [CandidateDecision(candidate_id=proposed.prompts[0].candidate_id, action="confirm")],
        "ans_character_1",
        0,
        "resolve-character-1",
    )
    character = resolved.world.characters[0]
    assert character.name == "戴帽子的人"
    assert character.attributes == {"visible_gesture": "揮手"}
    assert character.provenance.source.value == "child_confirmed"

    next_observation = ObserverPayload.model_validate(
        {
            "items": [
                {
                    "observation_id": "obs_figure_again",
                    "kind": "character",
                    "candidate": {
                        "visible_description": "戴帽子的人",
                        "visible_gesture": "揮手",
                    },
                    "confidence": 0.9,
                }
            ]
        }
    )
    second = service.submit_revision(
        "ses_synthetic",
        "rev_character_2",
        ObservationBatch(
            schema_version="observation.v1",
            batch_id="obsb_character_2",
            media_id="med_character_2",
            items=next_observation.to_domain_items(),
        ),
        1,
        "revision-character-2",
    )
    assert second.candidates[0].change.value == "unchanged"
    assert second.prompts == []


def test_stale_revision_is_superseded_and_does_not_block_fresh_submission(
    service: WorldStateService,
) -> None:
    stale = service.submit_revision(
        "ses_synthetic", "rev_old", batch("old", ("obs_old", "kite", 1)), 0, "revision-old"
    )
    service.record_observations(
        "ses_synthetic", batch("unrelated", ("obs_other", "cloud", 1)), 0, "other-mutation"
    )
    result = service.resolve_revision(
        "ses_synthetic",
        "rev_old",
        [decision(stale, "obs_old", "confirm")],
        "ans_old",
        1,
        "resolve-old",
    )
    assert result.revision.status == "superseded"
    assert result.world.version == 1
    assert result.world.objects == []
    fresh = service.submit_revision(
        "ses_synthetic", "rev_fresh", batch("fresh", ("obs_fresh", "kite", 1)), 1, "revision-fresh"
    )
    assert fresh.revision.status == "awaiting_grounding"
