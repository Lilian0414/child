from child_agent_api.domain.models import (
    Provenance,
    ProvenanceSource,
    StorySegment,
    StoryState,
    WorldObject,
    WorldState,
)
from child_agent_api.observer import ImageInput, ObservationPipeline
from child_agent_api.providers.demo import TemplateStoryProvider, demo_observer


def test_demo_observer_runs_the_pipeline_offline_and_yields_grounding_candidates() -> None:
    pipeline = ObservationPipeline(demo_observer())
    result = pipeline.run(
        ImageInput(media_id="med_demo", content=b"fake-bytes", mime_type="image/jpeg"),
        batch_id="obsb_demo",
    )
    labels = {
        item.candidate.get("label") for item in result.batch.items if "label" in item.candidate
    }
    assert "小朋友" in labels
    assert "球" in labels


def test_template_story_provider_opens_with_confirmed_world_entities() -> None:
    provider = TemplateStoryProvider()
    world = WorldState(session_id="ses_demo", version=1)
    story = StoryState(session_id="ses_demo", state_version=1, next_segment_index=0)
    result = provider.propose(world, story)
    assert result.text
    assert result.world_dependencies == []


def test_template_story_provider_varies_continuations_across_calls() -> None:
    provider = TemplateStoryProvider()
    world = WorldState(
        session_id="ses_demo",
        version=1,
        objects=[
            WorldObject(
                object_id="obj_1",
                type="balloon",
                count=4,
                provenance=Provenance(source=ProvenanceSource.CHILD_CONFIRMED, source_ref="src_x"),
            )
        ],
    )
    story_with_segment = StoryState(session_id="ses_demo", state_version=2, next_segment_index=1)
    story_with_segment.segments = [
        StorySegment(
            segment_id="segment_1",
            index=0,
            text="開場白。",
            provenance=Provenance(source=ProvenanceSource.MODEL_OBSERVATION, source_ref="src_x"),
            proposal_id="proposal_1",
        )
    ]
    first = provider.propose(world, story_with_segment)
    second = provider.propose(world, story_with_segment)
    assert first.text != second.text
    assert "obj_1" in first.world_dependencies
