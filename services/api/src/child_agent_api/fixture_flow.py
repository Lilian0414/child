"""Deterministic synthetic vertical slice; no provider or media is involved."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from child_agent_api.domain.errors import InvalidReferenceError
from child_agent_api.domain.models import (
    ObservationBatch,
    ObservationItem,
    ObservationKind,
    WorldState,
)

FIXTURE_ID: Literal["canonical-round-shapes"] = "canonical-round-shapes"


def observation_id(session_id: str) -> str:
    return f"obs_round_{session_id.removeprefix('ses_')}"


def observation_batch(session_id: str) -> ObservationBatch:
    return ObservationBatch(
        schema_version="observation.v1",
        batch_id=f"obsb_{session_id.removeprefix('ses_')}",
        media_id=f"med_{session_id.removeprefix('ses_')}",
        items=[
            ObservationItem(
                observation_id=f"obs_people_{session_id.removeprefix('ses_')}",
                kind=ObservationKind.OBJECT_COUNT,
                candidate={"label": "person", "count": 4},
                confidence=0.99,
                evidence_note="four synthetic figures",
            ),
            ObservationItem(
                observation_id=observation_id(session_id),
                kind=ObservationKind.OBJECT_COUNT,
                candidate={"label": "ball", "count": 4},
                confidence=0.67,
                evidence_note="four synthetic round shapes near four people",
            ),
        ],
    )


class Choice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    choice_id: str
    label: str


class FlowView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fixture_mode: Literal[True] = True
    fixture_id: Literal["canonical-round-shapes"] = FIXTURE_ID
    session_id: str
    state_version: int
    step: Literal["fixture", "grounding", "world_ready", "scene", "ending"]
    title: str
    narration: str
    scene_number: Annotated[int, Field(ge=1, le=3)] | None = None
    prompt: str | None = None
    choices: list[Choice] = Field(default_factory=list)


def build_view(
    session_id: str,
    world: WorldState,
    *,
    has_observation: bool,
    observation_decided: bool,
    choices: list[str],
) -> FlowView:
    if not has_observation:
        return FlowView(
            session_id=session_id,
            state_version=world.version,
            step="fixture",
            title="先看看示範畫作",
            narration="這是四個人和四個圓形物件的合成測試圖，不會上傳真實照片。",
        )
    if not observation_decided:
        return FlowView(
            session_id=session_id,
            state_version=world.version,
            step="grounding",
            title="我先猜猜看",
            narration="我看到四個人，旁邊有四個圓圓的東西。我猜它們是球。",
            prompt="那些圓圓的是四顆球嗎？",
        )
    balloons = next((item for item in world.objects if item.type == "balloon"), None)
    if balloons is None:
        return FlowView(
            session_id=session_id,
            state_version=world.version,
            step="world_ready",
            title="這次示範先停在這裡",
            narration="只有把球修正成氣球的合成示範路線會進入故事。可以開始一段新故事再試一次。",
        )
    if not choices:
        return first_scene(session_id, world)
    if len(choices) == 1:
        return FlowView(
            session_id=session_id,
            state_version=world.version,
            step="scene",
            scene_number=2,
            title="氣球飄到朋友身邊",
            narration=(
                "你先問朋友還好嗎。朋友抬起頭，握住一條氣球繩。"
                if choices[0] == "choice_ask"
                else "你笑了一下。朋友安靜地走到旁邊，氣球繩還在輕輕晃。"
            ),
            prompt="現在你想怎麼做？",
            choices=[
                Choice(choice_id="choice_invite", label="邀請朋友一起玩氣球"),
                Choice(choice_id="choice_give_space", label="先在旁邊等一等"),
            ],
        )
    return FlowView(
        session_id=session_id,
        state_version=world.version,
        step="ending",
        scene_number=3,
        title="氣球回到大家身邊",
        narration=(
            "你邀請朋友一起玩。四顆氣球在四個人中間輕輕飄著。"
            if choices[1] == "choice_invite"
            else "你留了一點空間。過一會兒，朋友帶著氣球慢慢走回來。"
        )
        + " 你做了兩個選擇，故事也跟著有了變化。",
    )


def first_scene(session_id: str, world: WorldState) -> FlowView:
    balloons = next((item for item in world.objects if item.type == "balloon"), None)
    if balloons is None:
        raise InvalidReferenceError("fixture story requires a ball-to-balloon correction")
    return FlowView(
        session_id=session_id,
        state_version=world.version,
        step="scene",
        scene_number=1,
        title="四顆氣球的操場",
        narration=f"四個人在操場上照顧 {balloons.count} 顆氣球。一位朋友低著頭。",
        prompt="你想先怎麼做？",
        choices=[
            Choice(choice_id="choice_ask", label="問問朋友還好嗎"),
            Choice(choice_id="choice_tease", label="笑他抓不到氣球"),
        ],
    )
