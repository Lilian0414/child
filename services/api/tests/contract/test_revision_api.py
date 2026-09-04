from fastapi.testclient import TestClient

from child_agent_api.main import app, get_service
from child_agent_api.service import WorldStateService


def test_revision_ingress_reuses_strict_observer_schema(service: WorldStateService) -> None:
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app)
    try:
        response = client.post(
            "/v1/sessions/ses_synthetic/drawing-revisions",
            json={
                "expected_state_version": 0,
                "idempotency_key": "strict-ingress",
                "media_id": "med_strict",
                "observations": {
                    "items": [
                        {
                            "observation_id": "obs_attack",
                            "kind": "object",
                            "candidate": {"label": "ball", "status": "confirmed"},
                            "confidence": 0.9,
                            "source": "child_confirmed",
                        }
                    ]
                },
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


def test_revision_api_submit_get_and_resolve(service: WorldStateService) -> None:
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app)
    try:
        submitted = client.post(
            "/v1/sessions/ses_synthetic/drawing-revisions",
            json={
                "expected_state_version": 0,
                "idempotency_key": "api-submit",
                "media_id": "med_api",
                "observations": {
                    "items": [
                        {
                            "observation_id": "obs_api",
                            "kind": "object_count",
                            "candidate": {"label": "dog", "count": 1},
                            "confidence": 0.9,
                        }
                    ]
                },
            },
        )
        assert submitted.status_code == 201
        revision = submitted.json()
        restored = client.get(
            f"/v1/sessions/ses_synthetic/drawing-revisions/{revision['revision_id']}"
        )
        resolved = client.post(
            f"/v1/sessions/ses_synthetic/drawing-revisions/{revision['revision_id']}/decisions",
            json={
                "expected_state_version": 0,
                "idempotency_key": "api-resolve",
                "decisions": [
                    {"candidate_id": revision["prompts"][0]["candidate_id"], "action": "confirm"}
                ],
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert restored.json() == revision
    assert resolved.status_code == 200
    assert resolved.json()["world"]["objects"][0]["type"] == "dog"
