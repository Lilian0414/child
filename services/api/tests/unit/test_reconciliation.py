from child_agent_api.domain.models import Provenance, ProvenanceSource, WorldObject, WorldState
from child_agent_api.observer import ObserverPayload
from child_agent_api.revisions import RevisionSubmission
from child_agent_api.service import WorldStateService


def test_reconciliation_emits_all_categories_and_bounds_questions(
    service: WorldStateService,
) -> None:
    provenance = Provenance(source=ProvenanceSource.CHILD_CONFIRMED, source_ref="ans_seed")
    world = WorldState(
        session_id="ses_synthetic",
        version=3,
        objects=[
            WorldObject(object_id="obj_balloon", type="balloon", count=4, provenance=provenance),
            WorldObject(object_id="obj_dog", type="dog", count=1, provenance=provenance),
            WorldObject(object_id="obj_kite", type="kite", count=1, provenance=provenance),
        ],
    )
    observed = ObserverPayload.model_validate(
        {
            "items": [
                {
                    "observation_id": "obs_same",
                    "kind": "object_count",
                    "candidate": {"label": "balloon", "count": 4},
                    "confidence": 0.9,
                },
                {
                    "observation_id": "obs_changed",
                    "kind": "object",
                    "candidate": {"label": "puppy"},
                    "confidence": 0.8,
                },
                {
                    "observation_id": "obs_uncertain",
                    "kind": "character",
                    "candidate": {"visible_description": "a figure"},
                    "confidence": 0.5,
                },
            ]
        }
    )
    candidates = service._reconcile("rev_categories", observed, world)
    assert {item.change for item in candidates} == {
        "unchanged",
        "changed",
        "removed",
        "uncertain",
    }
    added = service._reconcile("rev_added", observed, WorldState(session_id="ses_x", version=0))
    assert "added" in {item.change for item in added}

    many = ObserverPayload.model_validate(
        {
            "items": [
                {
                    "observation_id": f"obs_character_{index}",
                    "kind": "character",
                    "candidate": {"visible_description": f"figure {index}"},
                    "confidence": 0.5,
                }
                for index in range(6)
            ]
        }
    )
    revision = service.submit_revision(
        "ses_synthetic",
        RevisionSubmission(
            expected_state_version=0,
            idempotency_key="bounded-prompts",
            media_id="med_many",
            observations=many,
        ),
    )
    assert len(revision.prompts) == 5
