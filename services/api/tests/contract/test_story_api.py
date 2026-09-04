from fastapi.testclient import TestClient

from child_agent_api.main import app, get_service
from child_agent_api.service import WorldStateService


def test_story_api_propose_ground_project_and_restore(service: WorldStateService) -> None:
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app)
    proposed = client.post(
        "/v1/sessions/ses_synthetic/story/proposals", json={"expected_state_version": 0}
    )
    assert proposed.status_code == 200
    proposal_id = proposed.json()["current_proposal"]["proposal_id"]
    grounded = client.post(
        f"/v1/sessions/ses_synthetic/story/proposals/{proposal_id}/ground",
        json={
            "expected_state_version": 0,
            "idempotency_key": "story-api-ground",
            "action": "redirect",
            "supplied_text": "孩子決定先停下來看看。",
        },
    )
    assert grounded.status_code == 200
    assert grounded.json()["segments"][0]["text"] == "孩子決定先停下來看看。"
    assert client.get("/v1/sessions/ses_synthetic/story").json() == grounded.json()
    projected = client.get("/v1/sessions/ses_synthetic/story/full")
    assert projected.status_code == 200
    assert projected.json()["text"] == "孩子決定先停下來看看。"
    app.dependency_overrides.clear()


def test_completed_status_is_restored_through_public_api(
    service: WorldStateService, engine: object
) -> None:
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app)
    proposal = client.post(
        "/v1/sessions/ses_synthetic/story/proposals",
        json={"expected_state_version": 0},
    ).json()["current_proposal"]
    grounded = client.post(
        f"/v1/sessions/ses_synthetic/story/proposals/{proposal['proposal_id']}/ground",
        json={
            "expected_state_version": 0,
            "idempotency_key": "restore-grounded-story",
            "action": "accept",
        },
    )
    assert grounded.status_code == 200
    completed = client.post(
        "/v1/sessions/ses_synthetic/story/complete",
        json={"expected_state_version": 1, "idempotency_key": "restore-completed-story"},
    )
    assert completed.status_code == 200

    rebuilt = WorldStateService(engine)  # type: ignore[arg-type]
    app.dependency_overrides[get_service] = lambda: rebuilt
    refreshed_client = TestClient(app)
    restored = refreshed_client.get("/v1/sessions/ses_synthetic/state")
    assert restored.status_code == 200
    assert restored.json()["status"] == "COMPLETE"
    assert restored.json()["state_version"] == 2
    app.dependency_overrides.clear()
