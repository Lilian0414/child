import pytest
from pydantic import ValidationError

from child_agent_api.domain.errors import InvalidReferenceError, VersionConflictError
from child_agent_api.domain.models import (
    CandidateDecision,
    ObservationBatch,
    ObservationDecision,
    ObservationItem,
    ObservationKind,
    StoryGrounding,
)
from child_agent_api.service import WorldStateService
from child_agent_api.story import StoryProviderResult


def test_corrected_story_survives_world_revision_and_reconstruction(
    service: WorldStateService, engine: object
) -> None:
    service.record_observations(
        "ses_synthetic",
        ObservationBatch(
            schema_version="observation.v1",
            batch_id="obsb_balloons",
            media_id="med_first",
            items=[
                ObservationItem(
                    observation_id="obs_balloons",
                    kind=ObservationKind.OBJECT_COUNT,
                    candidate={"label": "ball"},
                    confidence=0.8,
                )
            ],
        ),
        0,
        "observe-balloons",
    )
    service.decide_observation(
        "ses_synthetic",
        "obs_balloons",
        "ans_balloons",
        ObservationDecision(action="correct", supplied_value={"label": "balloon", "count": 4}),
        1,
        "correct-balloons",
    )

    first = service.request_story_proposal("ses_synthetic", 2)
    first_proposal = first.current_proposal
    assert first_proposal is not None
    assert "balloon" in first_proposal.text
    proposal_id = first_proposal.proposal_id
    corrected = service.ground_story_proposal(
        "ses_synthetic",
        proposal_id,
        StoryGrounding(action="redirect", supplied_text="四個氣球決定飛往月亮。"),
        2,
        "story-ground-1",
    )
    assert corrected.segments[0].provenance.source == "child_supplied"
    second = service.request_story_proposal("ses_synthetic", 3)
    second_proposal = second.current_proposal
    assert second_proposal is not None
    assert "四個氣球決定飛往月亮。" in second_proposal.text
    second_id = second_proposal.proposal_id
    service.ground_story_proposal(
        "ses_synthetic", second_id, StoryGrounding(action="accept"), 3, "story-ground-2"
    )

    revision = service.submit_revision(
        "ses_synthetic",
        "rev_dog",
        ObservationBatch(
            schema_version="observation.v1",
            batch_id="obsb_dog",
            media_id="med_second",
            items=[
                ObservationItem(
                    observation_id="obs_balloons_again",
                    kind=ObservationKind.OBJECT_COUNT,
                    candidate={"label": "balloon", "count": 4},
                    confidence=0.9,
                ),
                ObservationItem(
                    observation_id="obs_dog",
                    kind=ObservationKind.OBJECT,
                    candidate={"label": "dog"},
                    confidence=0.9,
                ),
            ],
        ),
        4,
        "revision-dog",
    )
    candidate = next(
        item.candidate_id for item in revision.candidates if item.observation_id == "obs_dog"
    )
    service.resolve_revision(
        "ses_synthetic",
        "rev_dog",
        [CandidateDecision(candidate_id=candidate, action="confirm")],
        "ans_dog",
        4,
        "resolve-dog",
    )
    third = service.request_story_proposal("ses_synthetic", 5)
    third_proposal = third.current_proposal
    assert third_proposal is not None
    assert "dog" in third_proposal.text
    service.ground_story_proposal(
        "ses_synthetic",
        third_proposal.proposal_id,
        StoryGrounding(action="accept"),
        5,
        "story-ground-3",
    )

    projected = service.full_story("ses_synthetic")
    assert projected.text.startswith("四個氣球決定飛往月亮。")
    assert first_proposal.text not in projected.text
    rebuilt = WorldStateService(engine)  # type: ignore[arg-type]
    assert rebuilt.get_story("ses_synthetic") == service.get_story("ses_synthetic")
    assert rebuilt.full_story("ses_synthetic") == projected


def test_story_grounding_is_idempotent_and_rejects_stale_version(
    service: WorldStateService,
) -> None:
    proposal = service.request_story_proposal("ses_synthetic", 0).current_proposal
    assert proposal is not None
    result = service.ground_story_proposal(
        "ses_synthetic", proposal.proposal_id, StoryGrounding(action="accept"), 0, "same-command"
    )
    assert (
        service.ground_story_proposal(
            "ses_synthetic",
            proposal.proposal_id,
            StoryGrounding(action="accept"),
            0,
            "same-command",
        )
        == result
    )
    with pytest.raises(VersionConflictError):
        service.request_story_proposal("ses_synthetic", 0)


def test_completion_is_persisted_idempotent_and_rejects_pending_or_stale(
    service: WorldStateService, engine: object
) -> None:
    with pytest.raises(InvalidReferenceError, match="grounded current segment"):
        service.complete_story("ses_synthetic", 0, "complete-empty")
    proposal = service.request_story_proposal("ses_synthetic", 0).current_proposal
    assert proposal is not None
    with pytest.raises(InvalidReferenceError, match="pending story proposal"):
        service.complete_story("ses_synthetic", 0, "complete-pending")
    service.ground_story_proposal(
        "ses_synthetic",
        proposal.proposal_id,
        StoryGrounding(action="accept"),
        0,
        "ground-before-complete",
    )
    with pytest.raises(VersionConflictError):
        service.complete_story("ses_synthetic", 0, "complete-stale")

    result = service.complete_story("ses_synthetic", 1, "complete-once")
    assert result.state_version == 2
    assert service.complete_story("ses_synthetic", 1, "complete-once") == result
    rebuilt = WorldStateService(engine)  # type: ignore[arg-type]
    assert rebuilt.get_session("ses_synthetic").status == "COMPLETE"
    assert rebuilt.full_story("ses_synthetic") == result
    assert rebuilt.event_payloads("ses_synthetic", "STORY_COMPLETED") == [
        result.segment_ids[-1]
    ]
    with pytest.raises(InvalidReferenceError, match="session is complete"):
        rebuilt.request_story_proposal("ses_synthetic", 2)


def test_provider_failure_commits_no_proposal(service: WorldStateService) -> None:
    class BrokenProvider:
        def propose(self, world: object, story: object) -> object:
            raise RuntimeError("synthetic provider failure")

    with pytest.raises(RuntimeError):
        service.request_story_proposal("ses_synthetic", 0, BrokenProvider())  # type: ignore[arg-type]
    state = service.get_story("ses_synthetic")
    assert state.state_version == 0
    assert state.current_proposal is None


def test_provider_cannot_supply_canonical_proposal_metadata(
    service: WorldStateService,
) -> None:
    class MetadataProvider:
        def propose(self, world: object, story: object) -> object:
            return {
                "text": "safe provider content",
                "world_dependencies": [],
                "proposal_id": "proposal_provider_owned",
                "session_id": "ses_attacker",
                "based_on_state_version": 999,
                "segment_index": 999,
                "status": "accepted",
            }

    with pytest.raises(ValidationError):
        service.request_story_proposal(
            "ses_synthetic",
            0,
            MetadataProvider(),  # type: ignore[arg-type]
        )
    assert service.get_story("ses_synthetic").current_proposal is None

    class ContentProvider:
        def propose(self, world: object, story: object) -> StoryProviderResult:
            return StoryProviderResult(text="core wraps this content")

    proposal = service.request_story_proposal(
        "ses_synthetic", 0, ContentProvider()
    ).current_proposal
    assert proposal is not None
    assert proposal.proposal_id.startswith("proposal_")
    assert proposal.session_id == "ses_synthetic"
    assert proposal.based_on_state_version == 0
    assert proposal.segment_index == 0
    assert proposal.status == "pending"


def test_world_advance_supersedes_pending_proposal_and_fresh_proposal_sees_change(
    service: WorldStateService,
) -> None:
    old = service.request_story_proposal("ses_synthetic", 0).current_proposal
    assert old is not None
    revision = service.submit_revision(
        "ses_synthetic",
        "rev_add_dog",
        ObservationBatch(
            schema_version="observation.v1",
            batch_id="obsb_add_dog",
            media_id="med_add_dog",
            items=[
                ObservationItem(
                    observation_id="obs_add_dog",
                    kind=ObservationKind.OBJECT,
                    candidate={"label": "dog"},
                    confidence=0.9,
                )
            ],
        ),
        0,
        "revision-add-dog",
    )
    service.resolve_revision(
        "ses_synthetic",
        "rev_add_dog",
        [CandidateDecision(candidate_id=revision.prompts[0].candidate_id, action="confirm")],
        "ans_add_dog",
        0,
        "resolve-add-dog",
    )

    assert service.get_story("ses_synthetic").current_proposal is None
    with pytest.raises(InvalidReferenceError, match="proposal is not current"):
        service.ground_story_proposal(
            "ses_synthetic",
            old.proposal_id,
            StoryGrounding(action="accept"),
            1,
            "ground-stale-proposal",
        )
    assert service.full_story("ses_synthetic").segment_ids == []
    fresh = service.request_story_proposal("ses_synthetic", 1).current_proposal
    assert fresh is not None
    assert fresh.based_on_state_version == 1
    assert "dog" in fresh.text


def test_semantically_changed_ref_invalidates_dependent_story_segment(
    service: WorldStateService,
) -> None:
    seed = service.submit_revision(
        "ses_synthetic",
        "rev_seed_kite",
        ObservationBatch(
            schema_version="observation.v1",
            batch_id="obsb_seed_kite",
            media_id="med_seed_kite",
            items=[
                ObservationItem(
                    observation_id="obs_kite",
                    kind=ObservationKind.OBJECT,
                    candidate={"label": "kite"},
                    confidence=0.9,
                )
            ],
        ),
        0,
        "revision-seed-kite",
    )
    service.resolve_revision(
        "ses_synthetic",
        "rev_seed_kite",
        [CandidateDecision(candidate_id=seed.prompts[0].candidate_id, action="confirm")],
        "ans_seed_kite",
        0,
        "resolve-seed-kite",
    )
    proposal = service.request_story_proposal("ses_synthetic", 1).current_proposal
    assert proposal is not None
    canonical_ref = proposal.world_dependencies[0]
    service.ground_story_proposal(
        "ses_synthetic",
        proposal.proposal_id,
        StoryGrounding(action="accept"),
        1,
        "ground-kite-story",
    )

    changed = service.submit_revision(
        "ses_synthetic",
        "rev_kite_becomes_boat",
        ObservationBatch(
            schema_version="observation.v1",
            batch_id="obsb_kite_becomes_boat",
            media_id="med_kite_becomes_boat",
            items=[
                ObservationItem(
                    observation_id="obs_boat",
                    kind=ObservationKind.OBJECT,
                    candidate={"label": "boat"},
                    confidence=0.9,
                )
            ],
        ),
        2,
        "revision-kite-becomes-boat",
    )
    changed_prompt = next(item for item in changed.prompts if item.change == "changed")
    service.resolve_revision(
        "ses_synthetic",
        "rev_kite_becomes_boat",
        [CandidateDecision(candidate_id=changed_prompt.candidate_id, action="confirm")],
        "ans_kite_becomes_boat",
        2,
        "resolve-kite-becomes-boat",
    )

    story = service.get_story("ses_synthetic")
    assert story.segments[0].world_dependencies == [canonical_ref]
    assert story.segments[0].status == "stale"
    assert service.get_world("ses_synthetic").objects[0].object_id == canonical_ref
    assert service.full_story("ses_synthetic").segment_ids == []
