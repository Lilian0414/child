from fastapi.testclient import TestClient

from child_agent_api.main import app, get_service
from child_agent_api.service import WorldStateService


def test_public_schema_rejects_unknown_fields(service: WorldStateService) -> None:
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app)
    response = client.post("/v1/sessions", json={"profile": {}, "provider": "live"})
    assert response.status_code == 422
    app.dependency_overrides.clear()


def test_missing_session_maps_to_safe_error(service: WorldStateService) -> None:
    app.dependency_overrides[get_service] = lambda: service
    response = TestClient(app).get("/v1/sessions/ses_missing")
    assert response.status_code == 404
    assert response.json() == {
        "code": "session_not_found",
        "message": "找不到這段故事。",
        "current_state_version": None,
    }
    app.dependency_overrides.clear()
