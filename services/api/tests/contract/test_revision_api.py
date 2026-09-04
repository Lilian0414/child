from fastapi.testclient import TestClient

from child_agent_api.main import app, get_service
from child_agent_api.service import WorldStateService


def test_revision_api_exposes_typed_reconcile_decide_and_restore(
    service: WorldStateService,
) -> None:
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app)
    payload = {
        "revision_id": "rev_api",
        "expected_state_version": 0,
        "idempotency_key": "revision-api",
        "observations": {
            "schema_version": "observation.v1",
            "batch_id": "obsb_api",
            "media_id": "med_api",
            "items": [
                {
                    "observation_id": "obs_dog",
                    "kind": "object",
                    "candidate": {"label": "dog"},
                    "confidence": 0.9,
                }
            ],
        },
    }
    proposed = client.post("/v1/sessions/ses_synthetic/drawing-revisions", json=payload)
    assert proposed.status_code == 201
    candidate_id = proposed.json()["prompts"][0]["candidate_id"]
    resolved = client.post(
        "/v1/sessions/ses_synthetic/drawing-revisions/rev_api/decisions",
        json={
            "expected_state_version": 0,
            "idempotency_key": "resolve-api",
            "command_id": "ans_api",
            "decisions": [{"candidate_id": candidate_id, "action": "confirm"}],
        },
    )
    assert resolved.status_code == 200
    assert resolved.json()["world"]["objects"][0]["type"] == "dog"
    restored = client.get("/v1/sessions/ses_synthetic/drawing-revisions/rev_api")
    assert restored.json() == resolved.json()
    app.dependency_overrides.clear()
