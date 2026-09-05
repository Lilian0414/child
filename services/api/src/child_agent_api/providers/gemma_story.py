"""Live Gemma-backed providers for the Core `ObserverProvider` / `StoryProvider`
protocols, via the Hugging Face OpenAI-compatible inference router. These are
opt-in concrete adapters — Core stays provider-neutral; this module just
implements the two boundaries with a real model instead of a fixture/fake.
"""

import os

from openai import OpenAI

from child_agent_api.domain.models import StoryState, WorldState
from child_agent_api.providers.openai_compatible import OpenAICompatibleObserver
from child_agent_api.story import StoryProviderResult

HF_BASE_URL = "https://router.huggingface.co/v1"
VISION_MODEL = "google/gemma-4-31B-it:novita"
STORY_MODEL = "google/gemma-4-31B-it:novita"


class GemmaConfigError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def gemma_observer() -> OpenAICompatibleObserver:
    """`ObserverProvider`-compatible adapter: turns a photo into observation
    candidates via Gemma vision on the HF router."""
    api_key = os.getenv("HF_TOKEN")
    if not api_key:
        raise GemmaConfigError("HF_TOKEN 未設定")
    return OpenAICompatibleObserver(api_key=api_key, model=VISION_MODEL, base_url=HF_BASE_URL)


def _world_summary(world: WorldState) -> str:
    lines: list[str] = []
    for character in world.characters:
        lines.append(f"角色：{character.name}")
    for obj in world.objects:
        lines.append(f"物件：{obj.count} 個 {obj.type}")
    for fact in world.facts:
        if fact.fact_id in world.stale_fact_ids:
            continue
        lines.append(f"事實：{fact.predicate} = {fact.value}")
    return "\n".join(lines) if lines else "（目前世界還沒有任何已確認的內容）"


def _story_so_far(story: StoryState) -> str:
    segments = sorted(
        (segment for segment in story.segments if segment.status == "current"),
        key=lambda segment: segment.index,
    )
    return "\n".join(segment.text for segment in segments) if segments else "（故事還沒開始）"


class GemmaStoryProvider:
    """`StoryProvider`-compatible adapter: proposes the next short story
    segment from canonical world/story state via Gemma text generation."""

    def __init__(self, *, timeout_seconds: float = 20) -> None:
        api_key = os.getenv("HF_TOKEN")
        if not api_key:
            raise GemmaConfigError("HF_TOKEN 未設定")
        self._client = OpenAI(base_url=HF_BASE_URL, api_key=api_key)
        self._timeout_seconds = timeout_seconds

    def propose(self, world: WorldState, story: StoryState) -> StoryProviderResult:
        response = self._client.chat.completions.create(
            model=STORY_MODEL,
            timeout=self._timeout_seconds,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是兒童故事作家，正在跟孩子共同創作一段持續進行的故事。"
                        "只根據下面提供的「已確認世界」與「已確認故事」內容繼續寫，"
                        "不要引入未被確認的新角色或物件。"
                        "只寫接下來一小段（不超過 150 字），不要重複前面的內容，"
                        "不要下判斷（不寫「答對了」或「這樣不對」），"
                        "只用溫暖、順著孩子觀點的敘述語氣。只回傳故事文字本身，不要其他說明。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"已確認世界：\n{_world_summary(world)}\n\n"
                        f"已確認故事：\n{_story_so_far(story)}\n\n"
                        "請寫下一小段故事。"
                    ),
                },
            ],
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            text = "故事在這裡靜靜地停了一下，等著你告訴我接下來會發生什麼。"
        text = text[:500]

        dependencies: list[str] = []
        for character in world.characters:
            if character.name and character.name in text:
                dependencies.append(character.character_id)
        for obj in world.objects:
            if obj.type and obj.type in text:
                dependencies.append(obj.object_id)
        return StoryProviderResult(text=text, world_dependencies=dependencies[:10])
