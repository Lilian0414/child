"""Fully offline demo providers: no network calls, no external dependency,
100% reliable for on-stage demoing when the live model (Gemma via HF) is
unavailable or unstable. Same `ObserverProvider` / `StoryProvider` protocols
as the live Gemma adapters — the API surface and frontend never change,
only which provider main.py wires up.
"""

import itertools

from child_agent_api.domain.models import StoryState, WorldState
from child_agent_api.observer import FakeObserverProvider
from child_agent_api.story import StoryProviderResult

# Mirrors the documented demo script: a confident person-count plus a
# low-confidence "ball" reading that's meant to be corrected live to
# "balloon" in front of an audience — the project's own wow moment.
_DEMO_OBSERVATION_RESPONSE = """{
  "items": [
    {
      "observation_id": "obs_people",
      "kind": "object_count",
      "candidate": {"label": "小朋友", "count": 4},
      "confidence": 0.95,
      "evidence_note": "四個人形輪廓"
    },
    {
      "observation_id": "obs_round",
      "kind": "object_count",
      "candidate": {"label": "球", "count": 4},
      "confidence": 0.4,
      "evidence_note": "四個圓形物件，形狀不太確定"
    },
    {
      "observation_id": "obs_mood",
      "kind": "fact",
      "candidate": {"visible_expression": "笑臉"},
      "confidence": 0.85
    },
    {
      "observation_id": "obs_hero",
      "kind": "character",
      "candidate": {"visible_description": "一個戴著帽子、笑咪咪的角色", "visible_gesture": "揮手"},
      "confidence": 0.9
    }
  ]
}"""


def demo_observer() -> FakeObserverProvider:
    """`ObserverProvider`-compatible adapter with a canned, offline response."""
    return FakeObserverProvider(response=_DEMO_OBSERVATION_RESPONSE)


def _world_summary(world: WorldState) -> list[str]:
    lines: list[str] = []
    for character in world.characters:
        lines.append(character.name)
    for obj in world.objects:
        lines.append(f"{obj.count} 個 {obj.type}")
    return lines


_OPENERS = [
    "{items}出現了。你猜接下來會發生什麼事？",
    "{items}靜靜地待在畫裡。",
]
_CONTINUATIONS = [
    "接著，{items}發現了新的角落。",
    "{items}決定往前走走看。要不要跟過去？",
    "{items}好奇地抬起頭。牠看到了什麼呢？",
    "{items}停下來，想了想。",
]


class TemplateStoryProvider:
    """`StoryProvider`-compatible adapter: cycles through a small set of
    Chinese sentence templates filled with confirmed world entities. Fully
    offline and deterministic in structure, but varies enough across calls
    to not feel robotic in a short demo."""

    def __init__(self, *, child_idea: str | None = None) -> None:
        self._continuation_cycle = itertools.cycle(_CONTINUATIONS)
        self._child_idea = child_idea

    def propose(self, world: WorldState, story: StoryState) -> StoryProviderResult:
        names = _world_summary(world)
        items = "、".join(names) if names else "這個故事的主角們"
        if self._child_idea:
            text = f"你說接下來「{self._child_idea}」——於是{items}真的這麼做了！"
        else:
            template = _OPENERS[0] if not story.segments else next(self._continuation_cycle)
            text = template.format(items=items)

        dependencies: list[str] = []
        for character in world.characters:
            dependencies.append(character.character_id)
        for obj in world.objects:
            dependencies.append(obj.object_id)
        return StoryProviderResult(text=text, world_dependencies=dependencies[:10])
