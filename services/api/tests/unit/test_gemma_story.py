from unittest.mock import MagicMock, patch

import pytest

from child_agent_api.domain.models import (
    Character,
    Provenance,
    ProvenanceSource,
    StoryState,
    WorldObject,
    WorldState,
)
from child_agent_api.providers.gemma_story import (
    GemmaConfigError,
    GemmaStoryProvider,
    gemma_observer,
)


def test_gemma_observer_requires_hf_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    with pytest.raises(GemmaConfigError):
        gemma_observer()


def test_gemma_observer_builds_openai_compatible_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_TOKEN", "test-token")
    observer = gemma_observer()
    assert observer.api_key == "test-token"
    assert observer.base_url == "https://router.huggingface.co/v1"


def test_gemma_story_provider_requires_hf_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    with pytest.raises(GemmaConfigError):
        GemmaStoryProvider()


def _world_with_balloon() -> WorldState:
    return WorldState(
        session_id="ses_test",
        version=1,
        characters=[
            Character(
                character_id="char_1",
                name="小明",
                provenance=Provenance(source=ProvenanceSource.CHILD_CONFIRMED, source_ref="src_x"),
            )
        ],
        objects=[
            WorldObject(
                object_id="obj_1",
                type="balloon",
                count=4,
                provenance=Provenance(source=ProvenanceSource.CHILD_CONFIRMED, source_ref="src_x"),
            )
        ],
    )


def test_gemma_story_provider_proposes_text_and_matched_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_TOKEN", "test-token")
    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content="小明看到了 balloon，很開心。"))]
    with patch("child_agent_api.providers.gemma_story.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = fake_response
        mock_openai_cls.return_value = mock_client

        provider = GemmaStoryProvider()
        result = provider.propose(
            _world_with_balloon(),
            StoryState(session_id="ses_test", state_version=1, next_segment_index=0),
        )

    assert result.text == "小明看到了 balloon，很開心。"
    assert set(result.world_dependencies) == {"char_1", "obj_1"}


def test_gemma_story_provider_falls_back_on_empty_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_TOKEN", "test-token")
    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content=""))]
    with patch("child_agent_api.providers.gemma_story.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = fake_response
        mock_openai_cls.return_value = mock_client

        provider = GemmaStoryProvider()
        result = provider.propose(
            _world_with_balloon(),
            StoryState(session_id="ses_test", state_version=1, next_segment_index=0),
        )

    assert result.text
    assert result.world_dependencies == []
