import pytest

from child_agent_api.domain.errors import VersionConflictError
from child_agent_api.domain.models import (
    CandidateDecision,
    ObservationBatch,
    ObservationDecision,
    ObservationItem,
    ObservationKind,
    StoryGrounding,
)
from child_agent_api.service import WorldStateService


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
                    observation_id="obs_dog",
                    kind=ObservationKind.OBJECT,
                    candidate={"label": "dog"},
                    confidence=0.9,
                )
            ],
        ),
        4,
        "revision-dog",
    )
    candidate = revision.prompts[0].candidate_id
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


def test_provider_failure_commits_no_proposal(service: WorldStateService) -> None:
    class BrokenProvider:
        def propose(self, world: object, story: object, proposal_id: str) -> object:
            raise RuntimeError("synthetic provider failure")

    with pytest.raises(RuntimeError):
        service.request_story_proposal("ses_synthetic", 0, BrokenProvider())  # type: ignore[arg-type]
    state = service.get_story("ses_synthetic")
    assert state.state_version == 0
    assert state.current_proposal is None
