"""Deterministic application service for transactional state transitions."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as DbSession

from child_agent_api.domain.errors import InvalidReferenceError, NotFoundError, VersionConflictError
from child_agent_api.domain.models import (
    AccessibilityProfile,
    Character,
    DomainEvent,
    Fact,
    ObservationBatch,
    ObservationDecision,
    Provenance,
    ProvenanceSource,
    Relationship,
    Session,
    SessionStatus,
    WorldObject,
    WorldState,
)
from child_agent_api.persistence.models import (
    EventRow,
    IdempotencyRow,
    ObservationBatchRow,
    ObservationRow,
    SessionRow,
    WorldSnapshotRow,
)

JsonObject = dict[str, Any]


class WorldStateService:
    """Application boundary; each mutation writes event and snapshot in one transaction."""

    def __init__(self, engine: Engine, before_commit: Callable[[], None] | None = None) -> None:
        self.engine = engine
        self.before_commit = before_commit

    def create_session(
        self,
        session_id: str,
        profile: AccessibilityProfile,
        *,
        expires_in: timedelta = timedelta(days=1),
    ) -> Session:
        now = datetime.now(UTC)
        domain = Session(
            session_id=session_id,
            status=SessionStatus.GROUNDING,
            state_version=0,
            profile=profile,
            created_at=now,
            expires_at=now + expires_in,
        )
        world = WorldState(session_id=session_id, version=0)
        with DbSession(self.engine) as db, db.begin():
            db.add(SessionRow(**domain.model_dump(mode="python")))
            db.add(
                WorldSnapshotRow(
                    session_id=session_id,
                    schema_version="world.v1",
                    version=0,
                    state=world.model_dump(mode="json"),
                )
            )
        return domain

    def record_observations(
        self,
        session_id: str,
        batch: ObservationBatch,
        expected_state_version: int,
        idempotency_key: str,
    ) -> WorldState:
        def change(
            db: DbSession, world: WorldState
        ) -> tuple[WorldState, str, Literal["system", "model", "child", "adult"], str]:
            if db.get(ObservationBatchRow, batch.batch_id) is not None:
                raise InvalidReferenceError("batch already exists")
            db.add(
                ObservationBatchRow(
                    batch_id=batch.batch_id,
                    session_id=session_id,
                    schema_version=batch.schema_version,
                    media_id=batch.media_id,
                )
            )
            for item in batch.items:
                db.add(
                    ObservationRow(
                        batch_id=batch.batch_id,
                        session_id=session_id,
                        **item.model_dump(mode="json"),
                    )
                )
            return (
                world.model_copy(update={"version": world.version + 1}),
                "OBSERVATIONS_PROPOSED",
                "model",
                batch.batch_id,
            )

        return self._mutate(session_id, expected_state_version, idempotency_key, change)

    def decide_observation(
        self,
        session_id: str,
        observation_id: str,
        command_id: str,
        decision: ObservationDecision,
        expected_state_version: int,
        idempotency_key: str,
    ) -> WorldState:
        def change(
            db: DbSession, world: WorldState
        ) -> tuple[WorldState, str, Literal["system", "model", "child", "adult"], str]:
            row = db.scalar(
                select(ObservationRow).where(
                    ObservationRow.session_id == session_id,
                    ObservationRow.observation_id == observation_id,
                )
            )
            if row is None:
                raise InvalidReferenceError("observation does not exist in session")
            if row.status != "proposed":
                raise InvalidReferenceError("observation has already been decided")
            row.status = {"confirm": "confirmed", "reject": "rejected", "correct": "corrected"}[
                decision.action
            ]
            updated = world.model_copy(deep=True)
            updated.version += 1
            if decision.action != "reject":
                value = row.candidate if decision.action == "confirm" else decision.supplied_value
                assert value is not None
                source = (
                    ProvenanceSource.CHILD_CONFIRMED
                    if decision.action == "confirm"
                    else ProvenanceSource.CHILD_SUPPLIED
                )
                self._promote(
                    updated,
                    row.kind,
                    value,
                    command_id,
                    source,
                    observation_id,
                    decision.action == "correct",
                )
            event_type = f"OBSERVATION_{row.status.upper()}"
            return updated, event_type, "child", command_id

        return self._mutate(session_id, expected_state_version, idempotency_key, change)

    def get_world(self, session_id: str) -> WorldState:
        with DbSession(self.engine) as db:
            row = db.get(WorldSnapshotRow, session_id)
            if row is None:
                raise NotFoundError("session does not exist")
            return WorldState.model_validate(row.state, strict=False)

    def confirmed_facts(self, session_id: str) -> list[Fact]:
        world = self.get_world(session_id)
        stale = set(world.stale_fact_ids)
        return [fact for fact in world.facts if fact.fact_id not in stale]

    def _mutate(
        self,
        session_id: str,
        expected: int,
        key: str,
        change: Callable[
            [DbSession, WorldState],
            tuple[WorldState, str, Literal["system", "model", "child", "adult"], str],
        ],
    ) -> WorldState:
        with DbSession(self.engine) as db, db.begin():
            duplicate = db.scalar(
                select(IdempotencyRow).where(
                    IdempotencyRow.session_id == session_id, IdempotencyRow.key == key
                )
            )
            if duplicate is not None:
                return WorldState.model_validate(duplicate.result, strict=False)
            session = db.get(SessionRow, session_id)
            snapshot = db.get(WorldSnapshotRow, session_id)
            if session is None or snapshot is None:
                raise NotFoundError("session does not exist")
            if session.state_version != expected:
                raise VersionConflictError(expected, session.state_version)
            world, event_type, actor, payload_ref = change(
                db, WorldState.model_validate(snapshot.state, strict=False)
            )
            sequence = (
                db.scalar(
                    select(func.max(EventRow.sequence)).where(EventRow.session_id == session_id)
                )
                or 0
            ) + 1
            event = DomainEvent(
                event_id=f"evt_{uuid4().hex}",
                session_id=session_id,
                sequence=sequence,
                event_type=event_type,
                state_version_before=expected,
                state_version_after=world.version,
                actor=actor,
                payload_ref=payload_ref,
                created_at=datetime.now(UTC),
            )
            db.add(EventRow(**event.model_dump(mode="python", exclude={"schema_version"})))
            snapshot.version = world.version
            snapshot.state = world.model_dump(mode="json")
            session.state_version = world.version
            db.add(
                IdempotencyRow(session_id=session_id, key=key, result=world.model_dump(mode="json"))
            )
            if self.before_commit is not None:
                self.before_commit()
            return world

    @staticmethod
    def _promote(
        world: WorldState,
        kind: str,
        value: JsonObject,
        source_ref: str,
        source: ProvenanceSource,
        observation_id: str,
        correcting: bool,
    ) -> None:
        provenance = Provenance(source=source, source_ref=source_ref)
        suffix = observation_id.removeprefix("obs_")
        try:
            if kind == "character":
                world.characters.append(
                    Character(
                        character_id=f"char_{suffix}",
                        name=value["name"],
                        attributes=value.get("attributes", {}),
                        provenance=provenance,
                    )
                )
            elif kind in {"object", "object_count"}:
                world.objects.append(
                    WorldObject(
                        object_id=f"obj_{suffix}",
                        type=value["type"] if "type" in value else value["label"],
                        count=value.get("count", 1),
                        provenance=provenance,
                    )
                )
            elif kind == "relationship":
                world.relationships.append(
                    Relationship(
                        relationship_id=f"rel_{suffix}",
                        from_ref=value["from_ref"],
                        to_ref=value["to_ref"],
                        kind=value["kind"],
                        provenance=provenance,
                    )
                )
            elif kind == "fact":
                fact_id = value.get("fact_id", f"fact_{suffix}")
                previous = next((fact for fact in world.facts if fact.fact_id == fact_id), None)
                if previous is not None:
                    world.facts.remove(previous)
                world.facts.append(
                    Fact(
                        fact_id=fact_id,
                        subject_ref=value["subject_ref"],
                        predicate=value["predicate"],
                        value=value["value"],
                        depends_on=value.get("depends_on", []),
                        provenance=provenance,
                    )
                )
                if correcting:
                    affected = {fact_id}
                    changed = True
                    while changed:
                        old_size = len(affected)
                        affected |= {
                            f.fact_id
                            for f in world.facts
                            if f.provenance.source == ProvenanceSource.STORY_DERIVED
                            and set(f.depends_on) & affected
                        }
                        changed = len(affected) != old_size
                    world.stale_fact_ids = sorted(
                        set(world.stale_fact_ids) | (affected - {fact_id})
                    )
            else:
                raise InvalidReferenceError("unsupported observation kind")
            WorldState.model_validate(world.model_dump())
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidReferenceError("candidate cannot form valid canonical state") from exc
