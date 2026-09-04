"""Provider-neutral drawing revision reconciliation and grounding contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from child_agent_api.domain.models import JsonValue, WorldState
from child_agent_api.observer import ObserverItem, ObserverPayload


class StrictModel(BaseModel):
    # These are HTTP/application contracts, so JSON enum strings must parse. The nested
    # ObserverPayload retains its own strict scalar and allowlist boundary.
    model_config = ConfigDict(extra="forbid")


class ChangeKind(StrEnum):
    ADDED = "added"
    CHANGED = "changed"
    REMOVED = "removed"
    UNCHANGED = "unchanged"
    UNCERTAIN = "uncertain"


class RevisionStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"


class GroundingAction(StrEnum):
    CONFIRM = "confirm"
    CORRECT = "correct"
    REJECT = "reject"
    SKIP = "skip"


class CanonicalObjectValue(StrictModel):
    kind: Literal["object"]
    label: str = Field(min_length=1, max_length=100)
    count: int = Field(default=1, ge=1, le=100)


class CanonicalCharacterValue(StrictModel):
    kind: Literal["character"]
    name: str = Field(min_length=1, max_length=100)
    attributes: dict[str, JsonValue] = Field(default_factory=dict)


class CanonicalFactValue(StrictModel):
    kind: Literal["fact"]
    subject_ref: str = Field(pattern=r"^[a-z]+_[A-Za-z0-9_-]+$")
    predicate: str = Field(min_length=1, max_length=100)
    value: JsonValue
    depends_on: list[str] = Field(default_factory=list)


class CanonicalRelationshipValue(StrictModel):
    kind: Literal["relationship"]
    from_ref: str = Field(pattern=r"^[a-z]+_[A-Za-z0-9_-]+$")
    to_ref: str = Field(pattern=r"^[a-z]+_[A-Za-z0-9_-]+$")
    relationship_kind: str = Field(min_length=1, max_length=100)


CanonicalValue = Annotated[
    CanonicalObjectValue
    | CanonicalCharacterValue
    | CanonicalFactValue
    | CanonicalRelationshipValue,
    Field(discriminator="kind"),
]


class ReconciliationCandidate(StrictModel):
    candidate_id: str = Field(pattern=r"^rc_[A-Za-z0-9_-]+$")
    observation_id: str | None = Field(default=None, pattern=r"^obs_[A-Za-z0-9_-]+$")
    change: ChangeKind
    observer_kind: Literal["object_count", "object", "character", "fact", "relationship"]
    observed: dict[str, JsonValue] | None = None
    canonical_ref: str | None = None
    canonical_value: dict[str, JsonValue] | None = None
    requires_grounding: bool
    confirmable: bool


class GroundingPrompt(StrictModel):
    candidate_id: str
    allowed_actions: list[GroundingAction]


class DrawingRevision(StrictModel):
    schema_version: Literal["drawing-revision.v1"] = "drawing-revision.v1"
    revision_id: str = Field(pattern=r"^rev_[A-Za-z0-9_-]+$")
    session_id: str = Field(pattern=r"^ses_[A-Za-z0-9_-]+$")
    revision_number: int = Field(ge=1)
    base_world_version: int = Field(ge=0)
    media_id: str = Field(pattern=r"^med_[A-Za-z0-9_-]+$")
    observations: ObserverPayload
    status: RevisionStatus
    candidates: list[ReconciliationCandidate]
    prompts: list[GroundingPrompt] = Field(max_length=5)
    resulting_world_version: int | None = Field(default=None, ge=0)


class RevisionSubmission(StrictModel):
    expected_state_version: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=100)
    media_id: str = Field(pattern=r"^med_[A-Za-z0-9_-]+$")
    observations: ObserverPayload


class GroundingDecision(StrictModel):
    candidate_id: str = Field(pattern=r"^rc_[A-Za-z0-9_-]+$")
    action: GroundingAction
    supplied_value: CanonicalValue | None = None

    @model_validator(mode="after")
    def correction_only_has_value(self) -> GroundingDecision:
        if (self.action == GroundingAction.CORRECT) != (self.supplied_value is not None):
            raise ValueError("only correction requires supplied_value")
        return self


class RevisionResolution(StrictModel):
    expected_state_version: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=100)
    decisions: list[GroundingDecision] = Field(min_length=1, max_length=5)


class RevisionResult(StrictModel):
    revision: DrawingRevision
    world: WorldState


def observer_item_value(item: ObserverItem) -> dict[str, JsonValue]:
    return item.candidate.model_dump(mode="json", exclude_none=True)
