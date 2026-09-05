from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from child_agent_api.main import app, get_service
from child_agent_api.observer import FakeObserverProvider
from child_agent_api.providers.gemma_story import GemmaConfigError
from child_agent_api.service import WorldStateService


def test_revision_photo_runs_through_the_offline_demo_observer_by_default(
    service: WorldStateService,
) -> None:
    """Without CHILD_LIVE_MODE=gemma/minimax, the photo endpoint never calls Gemma —
    it uses the canned offline demo observer so it works with no network."""
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app)
    with patch("child_agent_api.main.gemma_observer") as mock_gemma_observer:
        response = client.post(
            "/v1/sessions/ses_synthetic/drawing-revisions/photo",
            files={"image": ("drawing.jpg", b"fake-bytes", "image/jpeg")},
            data={"expected_state_version": "0", "idempotency_key": "photo-revision-demo"},
        )
    mock_gemma_observer.assert_not_called()
    assert response.status_code == 201
    body = response.json()
    assert body["revision"]["status"] in {"awaiting_grounding", "resolved"}
    assert len(body["candidates"]) > 0
    app.dependency_overrides.clear()


def test_revision_photo_runs_through_a_fake_observer_and_submits_a_revision(
    service: WorldStateService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("child_agent_api.main.live_mode", "gemma")
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app)
    fake_response = (
        '{"items":[{"observation_id":"obs_1","kind":"object_count",'
        '"candidate":{"label":"dog","count":1},"confidence":0.9}]}'
    )
    with patch(
        "child_agent_api.main.gemma_observer",
        return_value=FakeObserverProvider(fake_response),
    ):
        response = client.post(
            "/v1/sessions/ses_synthetic/drawing-revisions/photo",
            files={"image": ("drawing.jpg", b"fake-bytes", "image/jpeg")},
            data={"expected_state_version": "0", "idempotency_key": "photo-revision-1"},
        )
    assert response.status_code == 201
    body = response.json()
    assert body["revision"]["status"] in {"awaiting_grounding", "resolved"}
    assert len(body["candidates"]) > 0
    app.dependency_overrides.clear()


def test_revision_photo_maps_observer_config_error_to_bad_gateway(
    service: WorldStateService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("child_agent_api.main.live_mode", "gemma")
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app)
    with patch(
        "child_agent_api.main.gemma_observer", side_effect=GemmaConfigError("HF_TOKEN 未設定")
    ):
        response = client.post(
            "/v1/sessions/ses_synthetic/drawing-revisions/photo",
            files={"image": ("drawing.jpg", b"fake-bytes", "image/jpeg")},
            data={"expected_state_version": "0", "idempotency_key": "photo-revision-2"},
        )
    assert response.status_code == 502
    assert response.json()["code"] == "observer_failed"
    app.dependency_overrides.clear()
