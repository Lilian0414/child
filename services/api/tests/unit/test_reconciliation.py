from child_agent_api.domain.models import (
    Character,
    ObservationBatch,
    ObservationItem,
    ObservationKind,
    Provenance,
    ProvenanceSource,
    WorldObject,
    WorldState,
)
from child_agent_api.reconciliation import MAX_GROUNDING_PROMPTS, reconcile, select_prompts


def item(identifier: str, label: str, count: int = 1, confidence: float = 0.9) -> ObservationItem:
    return ObservationItem(
        observation_id=identifier,
        kind=ObservationKind.OBJECT_COUNT,
        candidate={"label": label, "count": count},
        confidence=confidence,
    )


def test_reconciliation_emits_all_categories_and_does_not_prompt_unchanged() -> None:
    world = WorldState(
        session_id="ses_test",
        version=1,
        objects=[
            WorldObject(
                object_id="obj_balloon",
                type="balloon",
                count=4,
                provenance=Provenance(source=ProvenanceSource.CHILD_SUPPLIED, source_ref="ans_r1"),
            ),
            WorldObject(
                object_id="obj_kite",
                type="kite",
                provenance=Provenance(
                    source=ProvenanceSource.CHILD_CONFIRMED, source_ref="ans_kite"
                ),
            ),
            WorldObject(
                object_id="obj_hat",
                type="hat",
                provenance=Provenance(
                    source=ProvenanceSource.CHILD_CONFIRMED, source_ref="ans_hat"
                ),
            ),
        ],
        characters=[
            Character(
                character_id="char_child",
                name="child",
                provenance=Provenance(
                    source=ProvenanceSource.CHILD_CONFIRMED, source_ref="ans_child"
                ),
            )
        ],
    )
    batch = ObservationBatch(
        schema_version="observation.v1",
        batch_id="obsb_r2",
        media_id="med_r2",
        items=[
            item("obs_balloons", "balloon", 4),
            item("obs_boat", "boat"),
            item("obs_dog", "dog"),
            item("obs_cloud", "cloud", confidence=0.2),
            ObservationItem(
                observation_id="obs_together",
                kind=ObservationKind.RELATIONSHIP,
                candidate={"visible": "side by side", "relationship": "unknown"},
                confidence=0.9,
            ),
        ],
    )
    candidates = reconcile("rev_r2", batch, world)

    assert {candidate.change.value for candidate in candidates} == {
        "added",
        "changed",
        "removed",
        "unchanged",
        "uncertain",
    }
    prompts = select_prompts(candidates)
    assert all(prompt.change.value != "unchanged" for prompt in prompts)
    assert len(prompts) <= MAX_GROUNDING_PROMPTS


def test_grounding_is_bounded() -> None:
    batch = ObservationBatch(
        schema_version="observation.v1",
        batch_id="obsb_many",
        media_id="med_many",
        items=[item(f"obs_{index}", f"thing-{index}") for index in range(8)],
    )
    assert (
        len(select_prompts(reconcile("rev_many", batch, WorldState(session_id="ses_x", version=0))))
        == 5
    )
