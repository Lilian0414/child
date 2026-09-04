from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as DbSession

from child_agent_api.domain.models import ObservationBatch
from child_agent_api.observer import ObserverPayload
from child_agent_api.persistence.models import EventRow
from child_agent_api.revisions import RevisionResolution, RevisionSubmission
from child_agent_api.service import WorldStateService


def payload(*items: dict[str, object]) -> ObserverPayload:
    return ObserverPayload.model_validate({"items": list(items)})


def object_count(observation_id: str, label: str, count: int) -> dict[str, object]:
    return {
        "observation_id": observation_id,
        "kind": "object_count",
        "candidate": {"label": label, "count": count},
        "confidence": 0.8,
    }


def submit(
    service: WorldStateService,
    observations: ObserverPayload,
    version: int,
    key: str,
    media: str,
):
    return service.submit_revision(
        "ses_synthetic",
        RevisionSubmission(
            expected_state_version=version,
            idempotency_key=key,
            media_id=media,
            observations=observations,
        ),
    )


def test_r1_correction_r2_selective_addition_retry_and_reload(
    service: WorldStateService, engine: Engine
) -> None:
    first = submit(
        service,
        payload(object_count("obs_balls", "ball", 4)),
        0,
        "submit-r1",
        "med_r1",
    )
    assert first.revision_number == 1
    assert [item.change for item in first.candidates] == ["added"]

    r1_request = RevisionResolution.model_validate(
        {
            "expected_state_version": 0,
            "idempotency_key": "resolve-r1",
            "decisions": [
                {
                    "candidate_id": first.prompts[0].candidate_id,
                    "action": "correct",
                    "supplied_value": {"kind": "object", "label": "balloon", "count": 4},
                }
            ],
        }
    )
    first_result = service.resolve_revision("ses_synthetic", first.revision_id, r1_request)
    assert first_result.world.version == 1
    assert [(item.type, item.count) for item in first_result.world.objects] == [("balloon", 4)]
    assert first_result.world.objects[0].provenance.source == "child_supplied"

    second = submit(
        service,
        payload(
            object_count("obs_balloons", "balloon", 4),
            object_count("obs_dog", "dog", 1),
        ),
        1,
        "submit-r2",
        "med_r2",
    )
    assert [item.change for item in second.candidates] == ["unchanged", "added"]
    assert len(second.prompts) == 1
    assert second.candidates[0].requires_grounding is False

    r2_request = RevisionResolution.model_validate(
        {
            "expected_state_version": 1,
            "idempotency_key": "resolve-r2",
            "decisions": [{"candidate_id": second.prompts[0].candidate_id, "action": "confirm"}],
        }
    )
    result = service.resolve_revision("ses_synthetic", second.revision_id, r2_request)
    retry = service.resolve_revision("ses_synthetic", second.revision_id, r2_request)
    assert retry == result
    assert result.world.version == 2
    assert sorted((item.type, item.count) for item in result.world.objects) == [
        ("balloon", 4),
        ("dog", 1),
    ]
    assert WorldStateService(engine).get_world("ses_synthetic") == result.world
    with DbSession(engine) as db:
        assert db.scalar(select(func.count()).select_from(EventRow)) == 2


def test_all_observer_kinds_are_safe_and_noncanonical_shapes_cannot_confirm(
    service: WorldStateService,
) -> None:
    observations = payload(
        object_count("obs_count", "ball", 2),
        {
            "observation_id": "obs_object",
            "kind": "object",
            "candidate": {"label": "tree", "color": "green"},
            "confidence": 0.7,
        },
        {
            "observation_id": "obs_character",
            "kind": "character",
            "candidate": {"visible_description": "a figure"},
            "confidence": 0.6,
        },
        {
            "observation_id": "obs_fact",
            "kind": "fact",
            "candidate": {"visible_expression": "smile"},
            "confidence": 0.6,
        },
        {
            "observation_id": "obs_relationship",
            "kind": "relationship",
            "candidate": {"visible": "figures side by side", "relationship": "unknown"},
            "confidence": 0.5,
        },
    )
    revision = submit(service, observations, 0, "submit-all-kinds", "med_all")
    assert [item.observer_kind for item in revision.candidates] == [
        "object_count",
        "object",
        "character",
        "fact",
        "relationship",
    ]
    assert revision.prompts[2].allowed_actions == ["correct", "reject", "skip"]
    result = service.resolve_revision(
        "ses_synthetic",
        revision.revision_id,
        RevisionResolution.model_validate(
            {
                "expected_state_version": 0,
                "idempotency_key": "resolve-all-kinds",
                "decisions": [
                    {
                        "candidate_id": prompt.candidate_id,
                        "action": "confirm" if index < 2 else "skip",
                    }
                    for index, prompt in enumerate(revision.prompts)
                ],
            }
        ),
    )
    assert sorted(item.type for item in result.world.objects) == ["ball", "tree"]
    assert not result.world.characters and not result.world.facts and not result.world.relationships


def test_stale_revision_is_superseded_without_effect_and_fresh_revision_recovers(
    service: WorldStateService,
) -> None:
    stale = submit(service, payload(object_count("obs_old", "ball", 1)), 0, "submit-old", "med_old")
    service.record_observations(
        "ses_synthetic",
        ObservationBatch(
            schema_version="observation.v1",
            batch_id="obsb_other",
            media_id="med_other",
            items=payload(
                {
                    "observation_id": "obs_other",
                    "kind": "object",
                    "candidate": {"label": "kite"},
                    "confidence": 0.9,
                }
            ).to_domain_items(),
        ),
        0,
        "other-mutation",
    )
    outcome = service.resolve_revision(
        "ses_synthetic",
        stale.revision_id,
        RevisionResolution.model_validate(
            {
                "expected_state_version": 0,
                "idempotency_key": "resolve-stale",
                "decisions": [{"candidate_id": stale.prompts[0].candidate_id, "action": "confirm"}],
            }
        ),
    )
    assert outcome.revision.status == "superseded"
    assert outcome.world.version == 1
    assert outcome.world.objects == []
    fresh = submit(service, payload(object_count("obs_new", "ball", 1)), 1, "submit-new", "med_new")
    assert fresh.revision_number == 2
    assert fresh.base_world_version == 1


def test_confirmed_removal_keeps_tombstone_and_event_history(service: WorldStateService) -> None:
    added = submit(
        service, payload(object_count("obs_seed", "kite", 1)), 0, "submit-seed", "med_seed"
    )
    first = service.resolve_revision(
        "ses_synthetic",
        added.revision_id,
        RevisionResolution.model_validate(
            {
                "expected_state_version": 0,
                "idempotency_key": "resolve-seed",
                "decisions": [{"candidate_id": added.prompts[0].candidate_id, "action": "confirm"}],
            }
        ),
    )
    removed_id = first.world.objects[0].object_id
    next_revision = submit(
        service,
        payload(
            {
                "observation_id": "obs_figure_only",
                "kind": "character",
                "candidate": {"visible_description": "one figure"},
                "confidence": 0.7,
            }
        ),
        1,
        "submit-removal",
        "med_removal",
    )
    removed = next(item for item in next_revision.candidates if item.change == "removed")
    result = service.resolve_revision(
        "ses_synthetic",
        next_revision.revision_id,
        RevisionResolution.model_validate(
            {
                "expected_state_version": 1,
                "idempotency_key": "resolve-removal",
                "decisions": [
                    {
                        "candidate_id": prompt.candidate_id,
                        "action": "confirm"
                        if prompt.candidate_id == removed.candidate_id
                        else "skip",
                    }
                    for prompt in next_revision.prompts
                ],
            }
        ),
    )
    assert result.world.objects == []
    assert result.world.removed_entity_ids == [removed_id]
    assert service.event_payloads("ses_synthetic", "DRAWING_REVISION_RESOLVED") == [
        added.revision_id,
        next_revision.revision_id,
    ]
