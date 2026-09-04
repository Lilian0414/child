from unittest.mock import patch

from fastapi.testclient import TestClient

from child_agent_api.main import app
from child_agent_api.providers.tts_elevenlabs import TTSError


def test_tts_rejects_empty_text() -> None:
    response = TestClient(app).post("/v1/tts", json={"text": ""})
    assert response.status_code == 422


def test_tts_returns_audio_bytes() -> None:
    with patch(
        "child_agent_api.main.synthesize_speech", return_value=b"fake-mp3-bytes"
    ) as mock_synthesize:
        response = TestClient(app).post("/v1/tts", json={"text": "哈囉"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"fake-mp3-bytes"
    mock_synthesize.assert_called_once_with("哈囉")


def test_tts_provider_failure_maps_to_bad_gateway() -> None:
    with patch(
        "child_agent_api.main.synthesize_speech",
        side_effect=TTSError(401, "invalid api key"),
    ):
        response = TestClient(app).post("/v1/tts", json={"text": "哈囉"})
    assert response.status_code == 502
    assert response.json()["code"] == "tts_failed"
