"""Provider-neutral story proposal boundary and deterministic test implementation."""

from typing import Protocol

from child_agent_api.domain.models import StoryProposal, StoryState, WorldState


class StoryProvider(Protocol):
    def propose(self, world: WorldState, story: StoryState, proposal_id: str) -> StoryProposal: ...


class DeterministicStoryProvider:
    """Small deterministic provider; it reads canonical inputs and performs no mutation."""

    def propose(self, world: WorldState, story: StoryState, proposal_id: str) -> StoryProposal:
        if story.segments:
            prefix = story.segments[-1].text
            obj = next((item for item in reversed(world.objects) if item.type == "dog"), None)
            obj = obj or (world.objects[0] if world.objects else None)
            text = f"接著，{prefix} 然後遇見了{obj.type if obj else '新朋友'}。"
        else:
            obj = world.objects[0] if world.objects else None
            text = f"故事開始時，有{obj.count if obj else ''}個{obj.type if obj else '新朋友'}。"
        dependencies = [obj.object_id] if obj else []
        return StoryProposal(
            proposal_id=proposal_id,
            session_id=world.session_id,
            based_on_state_version=story.state_version,
            segment_index=story.next_segment_index,
            text=text,
            world_dependencies=dependencies,
        )
