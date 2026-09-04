from fastapi.testclient import TestClient

from child_agent_api.main import app

client = TestClient(app)


def test_health_contract() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "child-agent-api",
        "version": "0.1.0",
    }


def test_cross_origin_requests_are_not_allowed_by_default() -> None:
    """The web client is served same-origin by the API, so CORS defaults to none."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers
