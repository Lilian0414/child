from unittest.mock import patch

from fastapi.testclient import TestClient

from child_agent_api.main import app
from child_agent_api.providers.groq_stt import GroqSTTError


def _upload():
    return {"audio": ("voice.webm", b"fake-audio-bytes", "audio/webm")}


def test_stt_returns_transcribed_text() -> None:
    with patch(
        "child_agent_api.main.transcribe", return_value="小兔子決定去森林裡探險"
    ) as mock_transcribe:
        response = TestClient(app).post("/v1/stt", files=_upload())
    assert response.status_code == 200
    assert response.json() == {"text": "小兔子決定去森林裡探險"}
    mock_transcribe.assert_called_once_with(b"fake-audio-bytes", "voice.webm", "audio/webm")


def test_stt_provider_failure_maps_to_bad_gateway() -> None:
    with patch(
        "child_agent_api.main.transcribe",
        side_effect=GroqSTTError("GROQ_API_KEY 未設定"),
    ):
        response = TestClient(app).post("/v1/stt", files=_upload())
    assert response.status_code == 502
    assert response.json()["code"] == "stt_failed"
