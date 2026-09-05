"""Provider-neutral story content boundary and deterministic test implementation."""

from typing import Protocol

from pydantic import Field

from child_agent_api.domain.models import Contract, Identifier, StoryState, WorldState


class StoryProviderResult(Contract):
    """Strict, non-canonical content returned by a story provider."""

    text: str = Field(min_length=1, max_length=500)
    # Optional interactive prompt for the child — never part of canonical story prose.
    question: str | None = Field(default=None, max_length=200)
    # Up to two short suggested answers for `question`, used as button labels.
    question_options: list[str] = Field(default_factory=list, max_length=2)
    world_dependencies: list[Identifier] = Field(default_factory=list, max_length=10)


class StoryProvider(Protocol):
    def propose(self, world: WorldState, story: StoryState) -> StoryProviderResult: ...


class DeterministicStoryProvider:
    """Small deterministic provider; it reads canonical inputs and performs no mutation."""

    def propose(self, world: WorldState, story: StoryState) -> StoryProviderResult:
        if story.segments:
            prefix = story.segments[-1].text
            obj = next((item for item in reversed(world.objects) if item.type == "dog"), None)
            obj = obj or (world.objects[0] if world.objects else None)
            text = f"接著，{prefix} 然後遇見了{obj.type if obj else '新朋友'}。"
        else:
            obj = world.objects[0] if world.objects else None
            text = f"故事開始時，有{obj.count if obj else ''}個{obj.type if obj else '新朋友'}。"
        dependencies = [obj.object_id] if obj else []
        return StoryProviderResult(
            text=text,
            world_dependencies=dependencies,
        )
