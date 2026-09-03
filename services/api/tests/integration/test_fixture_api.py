from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from child_agent_api.fixture_flow import observation_id
from child_agent_api.main import app, get_service
from child_agent_api.persistence.models import EventRow, ObservationRow
from child_agent_api.service import WorldStateService


def client_for(service: WorldStateService) -> TestClient:
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app)


def mutate(client: TestClient, path: str, version: int, key: str, **extra: object):
    return client.post(
        path,
        json={"expected_state_version": version, "idempotency_key": key, **extra},
    )


def test_full_fixture_flow_restore_idempotency_and_stale_write(
    engine, service: WorldStateService
) -> None:
    client = client_for(service)
    created = client.post("/v1/sessions", json={"profile": {}})
    assert created.status_code == 201
    view = created.json()
    session_id = view["session_id"]
    assert view["step"] == "fixture"

    view = mutate(client, f"/v1/sessions/{session_id}/fixture", 0, "fixture-key").json()
    assert view["step"] == "grounding"
    assert service.get_world(session_id).objects == []
    assert client.get(f"/v1/sessions/{session_id}").json() == view

    stale = mutate(
        client,
        f"/v1/sessions/{session_id}/grounding",
        0,
        "stale-key",
        action="correct",
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "state_conflict"
    with DbSession(engine) as db:
        observation = db.get(ObservationRow, observation_id(session_id))
        assert observation is not None
        assert observation.status == "proposed"

    view = mutate(
        client,
        f"/v1/sessions/{session_id}/grounding",
        1,
        "ground-key",
        action="correct",
    ).json()
    assert view["scene_number"] == 1
    assert "氣球" in view["title"] and "球" not in view["narration"].replace("氣球", "")
    world = service.get_world(session_id)
    assert [(item.type, item.provenance.source) for item in world.objects] == [
        ("balloon", "child_supplied")
    ]
    assert client.get(f"/v1/sessions/{session_id}").json() == view

    first = mutate(
        client,
        f"/v1/sessions/{session_id}/choices",
        2,
        "choice-one-key",
        choice_id="choice_tease",
    )
    assert first.status_code == 200
    view = first.json()
    assert view["scene_number"] == 2 and "安靜" in view["narration"]
    duplicate = mutate(
        client,
        f"/v1/sessions/{session_id}/choices",
        2,
        "choice-one-key",
        choice_id="choice_tease",
    )
    assert duplicate.status_code == 200
    assert duplicate.json() == view
    assert client.get(f"/v1/sessions/{session_id}").json() == view

    view = mutate(
        client,
        f"/v1/sessions/{session_id}/choices",
        3,
        "choice-two-key",
        choice_id="choice_give_space",
    ).json()
    assert view["step"] == "ending" and view["scene_number"] == 3
    assert "分數" not in view["narration"] and "答錯" not in view["narration"]
    assert client.get(f"/v1/sessions/{session_id}").json() == view
    assert service.get_world(session_id).version == 4
    with DbSession(engine) as db:
        assert db.scalar(select(func.count()).select_from(EventRow)) == 4

    app.dependency_overrides.clear()


def test_choice_branch_changes_persisted_fact_and_next_scene(service: WorldStateService) -> None:
    client = client_for(service)
    session_id = client.post("/v1/sessions", json={"profile": {}}).json()["session_id"]
    mutate(client, f"/v1/sessions/{session_id}/fixture", 0, "fixture-2")
    mutate(
        client,
        f"/v1/sessions/{session_id}/grounding",
        1,
        "grounding-2",
        action="correct",
    )
    view = mutate(
        client,
        f"/v1/sessions/{session_id}/choices",
        2,
        "choice-2",
        choice_id="choice_ask",
    ).json()
    assert "問朋友" in view["narration"]
    assert service.get_world(session_id).facts[-1].value == "asked_kindly"
    app.dependency_overrides.clear()
