from unittest.mock import MagicMock, patch

import pytest

from child_agent_api.domain.models import (
    Provenance,
    ProvenanceSource,
    StoryState,
    WorldObject,
    WorldState,
)
from child_agent_api.providers.minimax import (
    MiniMaxConfigError,
    MiniMaxStoryProvider,
    minimax_observer,
)


def test_minimax_observer_requires_gmi_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GMI_API_KEY", raising=False)
    with pytest.raises(MiniMaxConfigError):
        minimax_observer()


def test_minimax_observer_builds_openai_compatible_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GMI_API_KEY", "test-token")
    observer = minimax_observer()
    assert observer.api_key == "test-token"
    assert observer.base_url == "https://api.gmi-serving.com/v1"


def test_minimax_story_provider_requires_gmi_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GMI_API_KEY", raising=False)
    with pytest.raises(MiniMaxConfigError):
        MiniMaxStoryProvider()


def test_minimax_story_provider_proposes_text_and_matched_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GMI_API_KEY", "test-token")
    world = WorldState(
        session_id="ses_test",
        version=1,
        objects=[
            WorldObject(
                object_id="obj_1",
                type="balloon",
                count=4,
                provenance=Provenance(source=ProvenanceSource.CHILD_CONFIRMED, source_ref="src_x"),
            )
        ],
    )
    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content="氣球飄呀飄，balloon 越飛越高。"))]
    with patch("child_agent_api.providers.minimax.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = fake_response
        mock_openai_cls.return_value = mock_client

        provider = MiniMaxStoryProvider()
        result = provider.propose(
            world, StoryState(session_id="ses_test", state_version=1, next_segment_index=0)
        )

    assert result.text == "氣球飄呀飄，balloon 越飛越高。"
    assert result.world_dependencies == ["obj_1"]
