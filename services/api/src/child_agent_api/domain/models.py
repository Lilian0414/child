"""Strict provider-neutral domain contracts for sessions and world state."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-z]+_[A-Za-z0-9_-]+$", min_length=3)]
type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SessionStatus(StrEnum):
    GROUNDING = "GROUNDING"
    STORY = "STORY"
    COMPLETE = "COMPLETE"
    EXPIRED = "EXPIRED"


class ProvenanceSource(StrEnum):
    MODEL_OBSERVATION = "model_observation"
    CHILD_CONFIRMED = "child_confirmed"
    CHILD_SUPPLIED = "child_supplied"
    ADULT_SETUP = "adult_setup"
    STORY_DERIVED = "story_derived"
    SYSTEM_DEFAULT = "system_default"


class ObservationStatus(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CORRECTED = "corrected"
    EXPIRED = "expired"


class ObservationKind(StrEnum):
    CHARACTER = "character"
    OBJECT = "object"
    RELATIONSHIP = "relationship"
    FACT = "fact"
    OBJECT_COUNT = "object_count"


class AccessibilityProfile(Contract):
    display_name: str | None = Field(default=None, max_length=80)
    text_length: Literal["short", "standard"] = "short"
    bopomofo: bool = False
    choice_count: int = Field(default=2, ge=2, le=4)
    speech_rate: Literal["slow", "standard"] = "slow"
    repeat_prompt: bool = True


class Provenance(Contract):
    source: ProvenanceSource
    source_ref: Identifier


class ObservationItem(Contract):
    observation_id: Identifier
    kind: ObservationKind
    candidate: dict[str, JsonValue]
    confidence: float = Field(ge=0, le=1)
    needs_confirmation: bool = True
    evidence_note: str | None = Field(default=None, max_length=500)
    status: ObservationStatus = ObservationStatus.PROPOSED
    source: Literal[ProvenanceSource.MODEL_OBSERVATION] = ProvenanceSource.MODEL_OBSERVATION


class ObservationBatch(Contract):
    schema_version: Literal["observation.v1"]
    batch_id: Identifier
    media_id: Identifier
    items: list[ObservationItem] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_items(self) -> "ObservationBatch":
        ids = [item.observation_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("observation IDs must be unique")
        return self


class Character(Contract):
    character_id: Identifier
    name: str = Field(min_length=1, max_length=100)
    attributes: dict[str, JsonValue] = Field(default_factory=dict)
    provenance: Provenance


class WorldObject(Contract):
    object_id: Identifier
    type: str = Field(min_length=1, max_length=100)
    count: int = Field(default=1, ge=1)
    provenance: Provenance


class Relationship(Contract):
    relationship_id: Identifier
    from_ref: Identifier
    to_ref: Identifier
    kind: str = Field(min_length=1, max_length=100)
    provenance: Provenance


class Fact(Contract):
    fact_id: Identifier
    subject_ref: Identifier
    predicate: str = Field(min_length=1, max_length=100)
    value: JsonValue
    provenance: Provenance
    depends_on: list[Identifier] = Field(default_factory=list)


class WorldState(Contract):
    schema_version: Literal["world.v1"] = "world.v1"
    session_id: Identifier
    version: int = Field(ge=0)
    characters: list[Character] = Field(default_factory=list)
    objects: list[WorldObject] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    stale_fact_ids: list[Identifier] = Field(default_factory=list)
    retired_ids: list[Identifier] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_references(self) -> "WorldState":
        entity_ids = {x.character_id for x in self.characters} | {x.object_id for x in self.objects}
        fact_ids = {x.fact_id for x in self.facts}
        all_ids = entity_ids | fact_ids | set(self.retired_ids)
        if any(f.subject_ref not in all_ids for f in self.facts):
            raise ValueError("fact subject reference does not exist")
        if any(dep not in all_ids for fact in self.facts for dep in fact.depends_on):
            raise ValueError("fact dependency reference does not exist")
        if not set(self.stale_fact_ids) <= fact_ids:
            raise ValueError("stale fact reference does not exist")
        if set(self.retired_ids) & (entity_ids | fact_ids):
            raise ValueError("active and retired IDs must be disjoint")
        if any(
            r.from_ref not in entity_ids or r.to_ref not in entity_ids for r in self.relationships
        ):
            raise ValueError("relationship reference does not exist")
        return self


class Session(Contract):
    schema_version: Literal["session.v1"] = "session.v1"
    session_id: Identifier
    status: SessionStatus
    state_version: int = Field(ge=0)
    profile: AccessibilityProfile
    created_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def valid_times(self) -> "Session":
        if self.created_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        if self.expires_at <= self.created_at:
            raise ValueError("expiry must follow creation")
        return self


class DomainEvent(Contract):
    schema_version: Literal["event.v1"] = "event.v1"
    event_id: Identifier
    session_id: Identifier
    sequence: int = Field(ge=1)
    event_type: str = Field(pattern=r"^[A-Z][A-Z_]+$")
    state_version_before: int = Field(ge=0)
    state_version_after: int = Field(ge=0)
    actor: Literal["system", "model", "child", "adult"]
    payload_ref: Identifier
    created_at: datetime

    @model_validator(mode="after")
    def advances_once(self) -> "DomainEvent":
        if self.state_version_after != self.state_version_before + 1:
            raise ValueError("event must advance state exactly once")
        if self.created_at.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return self


class ObservationDecision(Contract):
    action: Literal["confirm", "reject", "correct", "skip"]
    supplied_value: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def correction_has_value(self) -> "ObservationDecision":
        if (self.action == "correct") != (self.supplied_value is not None):
            raise ValueError("only correction requires supplied_value")
        return self


class SemanticChange(StrEnum):
    ADDED = "added"
    CHANGED = "changed"
    REMOVED = "removed"
    UNCHANGED = "unchanged"
    UNCERTAIN = "uncertain"


class DrawingRevision(Contract):
    schema_version: Literal["drawing-revision.v1"] = "drawing-revision.v1"
    revision_id: Identifier
    session_id: Identifier
    number: int = Field(ge=1)
    batch_id: Identifier
    based_on_world_version: int = Field(ge=0)
    status: Literal["awaiting_grounding", "resolved", "superseded"]
    created_at: datetime


class ReconciliationCandidate(Contract):
    candidate_id: Identifier
    revision_id: Identifier
    change: SemanticChange
    kind: ObservationKind
    current_ref: Identifier | None = None
    current_value: dict[str, JsonValue] | None = None
    observation_id: Identifier | None = None
    proposed_value: dict[str, JsonValue] | None = None
    requires_grounding: bool
    decision: Literal["confirm", "reject", "correct", "skip"] | None = None


class GroundingPrompt(Contract):
    candidate_id: Identifier
    action: Literal["confirm_or_correct"] = "confirm_or_correct"
    change: SemanticChange
    kind: ObservationKind
    allowed_actions: list[Literal["confirm", "correct", "reject", "skip"]]


class RevisionState(Contract):
    revision: DrawingRevision
    candidates: list[ReconciliationCandidate]
    prompts: list[GroundingPrompt]
    world: WorldState


class CandidateDecision(Contract):
    candidate_id: Identifier
    action: Literal["confirm", "reject", "correct", "skip"]
    supplied_value: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def correction_has_value(self) -> "CandidateDecision":
        if (self.action == "correct") != (self.supplied_value is not None):
            raise ValueError("only correction requires supplied_value")
        return self
