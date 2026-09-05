from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from child_agent_api.main import app, get_service
from child_agent_api.providers.minimax import MiniMaxConfigError
from child_agent_api.service import WorldStateService
from child_agent_api.story import StoryProviderResult


def test_story_api_regenerate_redrafts_the_pending_proposal_without_grounding(
    service: WorldStateService,
) -> None:
    """The 'not what I meant, try again' path must redraft the same pending
    proposal via the provider — never take the child's raw text verbatim,
    and never touch canonical world/session state."""
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app)
    fake_provider = MagicMock()
    fake_provider.propose.side_effect = [
        StoryProviderResult(text="故事開始了。"),
        StoryProviderResult(text="故事變成這樣了。"),
    ]
    with patch("child_agent_api.main.MiniMaxStoryProvider", return_value=fake_provider):
        proposed = client.post(
            "/v1/sessions/ses_synthetic/story/proposals",
            json={"expected_state_version": 0},
        )
        proposal = proposed.json()["current_proposal"]
        regenerated = client.post(
            f"/v1/sessions/ses_synthetic/story/proposals/{proposal['proposal_id']}/regenerate",
            json={"expected_state_version": 0, "child_idea": "主角決定去爬山"},
        )
    assert regenerated.status_code == 200
    body = regenerated.json()
    assert body["current_proposal"]["proposal_id"] == proposal["proposal_id"]
    assert body["current_proposal"]["text"] != proposal["text"]
    assert body["current_proposal"]["text"] != "主角決定去爬山"
    assert body["segments"] == []
    assert body["state_version"] == 0
    app.dependency_overrides.clear()


def test_story_api_propose_ground_project_and_restore(service: WorldStateService) -> None:
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app)
    fake_provider = MagicMock()
    fake_provider.propose.return_value = StoryProviderResult(text="故事開始了。")
    with patch("child_agent_api.main.MiniMaxStoryProvider", return_value=fake_provider):
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


def test_story_api_maps_provider_config_error_to_bad_gateway(
    service: WorldStateService,
) -> None:
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app)
    with patch(
        "child_agent_api.main.MiniMaxStoryProvider",
        side_effect=MiniMaxConfigError("GMI_API_KEY 未設定"),
    ):
        response = client.post(
            "/v1/sessions/ses_synthetic/story/proposals", json={"expected_state_version": 0}
        )
    assert response.status_code == 502
    assert response.json()["code"] == "story_provider_failed"
    app.dependency_overrides.clear()


def test_completed_status_is_restored_through_public_api(
    service: WorldStateService, engine: object
) -> None:
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app)
    fake_provider = MagicMock()
    fake_provider.propose.return_value = StoryProviderResult(text="故事開始了。")
    with patch("child_agent_api.main.MiniMaxStoryProvider", return_value=fake_provider):
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
