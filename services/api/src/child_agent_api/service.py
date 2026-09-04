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
    ObservationItem,
    Provenance,
    ProvenanceSource,
    Relationship,
    Session,
    SessionStatus,
    WorldObject,
    WorldState,
)
from child_agent_api.observer import (
    OBSERVER_PROMPT_VERSION,
    ImageInput,
    ObservationPipeline,
    ObserverResult,
)
from child_agent_api.persistence.models import (
    DrawingRevisionRow,
    EventRow,
    IdempotencyRow,
    ObservationBatchRow,
    ObservationRow,
    SessionRow,
    WorldSnapshotRow,
)
from child_agent_api.revisions import (
    ChangeKind,
    DrawingRevision,
    GroundingAction,
    GroundingPrompt,
    ReconciliationCandidate,
    RevisionResolution,
    RevisionResult,
    RevisionStatus,
    RevisionSubmission,
    observer_item_value,
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

    def observe_and_record(
        self,
        session_id: str,
        pipeline: ObservationPipeline,
        image: ImageInput,
        *,
        batch_id: str,
        expected_state_version: int,
        idempotency_key: str,
        timeout_seconds: float = 10,
    ) -> tuple[WorldState, ObserverResult]:
        """Persist only after the complete provider/schema/policy boundary succeeds."""
        committed = self._preflight_observation(
            session_id, batch_id, expected_state_version, idempotency_key, pipeline
        )
        if committed is not None:
            return committed
        result = pipeline.run(image, batch_id=batch_id, timeout_seconds=timeout_seconds)
        world = self.record_observations(
            session_id, result.batch, expected_state_version, idempotency_key
        )
        return world, result

    def _preflight_observation(
        self,
        session_id: str,
        batch_id: str,
        expected: int,
        key: str,
        pipeline: ObservationPipeline,
    ) -> tuple[WorldState, ObserverResult] | None:
        """Resolve committed retries and stale requests before external model work."""
        with DbSession(self.engine) as db:
            duplicate = db.scalar(
                select(IdempotencyRow).where(
                    IdempotencyRow.session_id == session_id, IdempotencyRow.key == key
                )
            )
            if duplicate is not None:
                batch_row = db.get(ObservationBatchRow, batch_id)
                if batch_row is None or batch_row.session_id != session_id:
                    raise InvalidReferenceError("idempotency key belongs to another mutation")
                rows = list(
                    db.scalars(
                        select(ObservationRow)
                        .where(ObservationRow.batch_id == batch_id)
                        .order_by(ObservationRow.observation_id)
                    )
                )
                batch = ObservationBatch(
                    schema_version="observation.v1",
                    batch_id=batch_id,
                    media_id=batch_row.media_id,
                    items=[
                        ObservationItem.model_validate(
                            {
                                "observation_id": row.observation_id,
                                "kind": row.kind,
                                "candidate": row.candidate,
                                "confidence": row.confidence,
                                "needs_confirmation": row.needs_confirmation,
                                "evidence_note": row.evidence_note,
                                "status": "proposed",
                                "source": "model_observation",
                            },
                            strict=False,
                        )
                        for row in rows
                    ],
                )
                return (
                    WorldState.model_validate(duplicate.result, strict=False),
                    ObserverResult(
                        batch=batch,
                        provider=pipeline.provider.provider_id,
                        model=pipeline.provider.model_id,
                        prompt_version=OBSERVER_PROMPT_VERSION,
                        repair_used=False,
                        latency_ms=0,
                    ),
                )
            session = db.get(SessionRow, session_id)
            if session is None:
                raise NotFoundError("session does not exist")
            if session.state_version != expected:
                raise VersionConflictError(expected, session.state_version)
        return None

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

    def get_session(self, session_id: str) -> Session:
        """Load the public session aggregate without exposing an ORM row."""
        with DbSession(self.engine) as db:
            row = db.get(SessionRow, session_id)
            if row is None:
                raise NotFoundError("session does not exist")
            return Session.model_validate(
                {
                    "session_id": row.session_id,
                    "schema_version": row.schema_version,
                    "status": row.status,
                    "state_version": row.state_version,
                    "profile": row.profile,
                    "created_at": row.created_at,
                    "expires_at": row.expires_at,
                },
                strict=False,
            )

    def event_payloads(self, session_id: str, event_type: str) -> list[str]:
        """Return immutable fixture progress markers in sequence order."""
        with DbSession(self.engine) as db:
            if db.get(SessionRow, session_id) is None:
                raise NotFoundError("session does not exist")
            return list(
                db.scalars(
                    select(EventRow.payload_ref)
                    .where(EventRow.session_id == session_id, EventRow.event_type == event_type)
                    .order_by(EventRow.sequence)
                )
            )

    def observation_status(self, session_id: str, observation_id: str) -> str | None:
        """Read the persisted proposal state used to reconstruct the fixture view."""
        with DbSession(self.engine) as db:
            row = db.scalar(
                select(ObservationRow).where(
                    ObservationRow.session_id == session_id,
                    ObservationRow.observation_id == observation_id,
                )
            )
            return None if row is None else row.status

    def apply_story_choice(
        self,
        session_id: str,
        choice_id: str,
        expected_state_version: int,
        idempotency_key: str,
    ) -> WorldState:
        """Persist one validated deterministic-fixture choice and its derived fact."""
        allowed = {
            "choice_ask": ("response", "asked_kindly"),
            "choice_tease": ("response", "teased"),
            "choice_invite": ("next_action", "invited_to_play"),
            "choice_give_space": ("next_action", "gave_space"),
        }
        if choice_id not in allowed:
            raise InvalidReferenceError("choice is not available")

        def change(
            db: DbSession, world: WorldState
        ) -> tuple[WorldState, str, Literal["system", "model", "child", "adult"], str]:
            prior = list(
                db.scalars(
                    select(EventRow.payload_ref)
                    .where(
                        EventRow.session_id == session_id,
                        EventRow.event_type == "CHILD_CHOICE_ACCEPTED",
                    )
                    .order_by(EventRow.sequence)
                )
            )
            valid_now = (
                {"choice_ask", "choice_tease"}
                if len(prior) == 0
                else {"choice_invite", "choice_give_space"}
                if len(prior) == 1
                else set()
            )
            if choice_id not in valid_now:
                raise InvalidReferenceError("choice is not available at the current scene")
            if not any(item.type == "balloon" for item in world.objects):
                raise InvalidReferenceError("story requires the corrected balloon world")
            predicate, value = allowed[choice_id]
            updated = world.model_copy(deep=True)
            updated.version += 1
            updated.facts.append(
                Fact(
                    fact_id=f"fact_choice_{len(prior) + 1}",
                    subject_ref=next(
                        item.object_id for item in world.objects if item.type == "balloon"
                    ),
                    predicate=predicate,
                    value=value,
                    provenance=Provenance(
                        source=ProvenanceSource.STORY_DERIVED, source_ref=choice_id
                    ),
                )
            )
            return updated, "CHILD_CHOICE_ACCEPTED", "child", choice_id

        return self._mutate(session_id, expected_state_version, idempotency_key, change)

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

    def submit_revision(self, session_id: str, request: RevisionSubmission) -> DrawingRevision:
        """Persist a strict observer batch reconciled against exactly one world version."""
        with DbSession(self.engine) as db, db.begin():
            duplicate = db.scalar(
                select(DrawingRevisionRow).where(
                    DrawingRevisionRow.session_id == session_id,
                    DrawingRevisionRow.submission_key == request.idempotency_key,
                )
            )
            if duplicate is not None:
                return DrawingRevision.model_validate(duplicate.state, strict=False)
            session = db.get(SessionRow, session_id)
            snapshot = db.get(WorldSnapshotRow, session_id)
            if session is None or snapshot is None:
                raise NotFoundError("session does not exist")
            if session.state_version != request.expected_state_version:
                raise VersionConflictError(request.expected_state_version, session.state_version)
            number = (
                db.scalar(
                    select(func.max(DrawingRevisionRow.revision_number)).where(
                        DrawingRevisionRow.session_id == session_id
                    )
                )
                or 0
            ) + 1
            revision_id = f"rev_{uuid4().hex}"
            world = WorldState.model_validate(snapshot.state, strict=False)
            candidates = self._reconcile(revision_id, request.observations, world)
            prompts = [
                GroundingPrompt(
                    candidate_id=item.candidate_id,
                    allowed_actions=(
                        [
                            GroundingAction.CONFIRM,
                            GroundingAction.CORRECT,
                            GroundingAction.REJECT,
                            GroundingAction.SKIP,
                        ]
                        if item.confirmable
                        else [GroundingAction.CORRECT, GroundingAction.REJECT, GroundingAction.SKIP]
                    ),
                )
                for item in candidates
                if item.requires_grounding
            ][:5]
            revision = DrawingRevision(
                revision_id=revision_id,
                session_id=session_id,
                revision_number=number,
                base_world_version=world.version,
                media_id=request.media_id,
                observations=request.observations,
                status=RevisionStatus.PENDING,
                candidates=candidates,
                prompts=prompts,
            )
            db.add(
                DrawingRevisionRow(
                    revision_id=revision_id,
                    session_id=session_id,
                    revision_number=number,
                    base_world_version=world.version,
                    media_id=request.media_id,
                    status=revision.status,
                    submission_key=request.idempotency_key,
                    state=revision.model_dump(mode="json"),
                )
            )
            return revision

    def get_revision(self, session_id: str, revision_id: str) -> DrawingRevision:
        with DbSession(self.engine) as db:
            row = db.get(DrawingRevisionRow, revision_id)
            if row is None or row.session_id != session_id:
                raise NotFoundError("revision does not exist")
            return DrawingRevision.model_validate(row.state, strict=False)

    def resolve_revision(
        self, session_id: str, revision_id: str, request: RevisionResolution
    ) -> RevisionResult:
        """Apply child decisions atomically, or supersede a revision whose base is stale."""
        with DbSession(self.engine) as db, db.begin():
            row = db.get(DrawingRevisionRow, revision_id)
            session = db.get(SessionRow, session_id)
            snapshot = db.get(WorldSnapshotRow, session_id)
            if row is None or row.session_id != session_id or session is None or snapshot is None:
                raise NotFoundError("revision does not exist")
            if row.resolution_key == request.idempotency_key and row.result is not None:
                return RevisionResult.model_validate(row.result, strict=False)
            revision = DrawingRevision.model_validate(row.state, strict=False)
            world = WorldState.model_validate(snapshot.state, strict=False)
            if revision.status == RevisionStatus.RESOLVED:
                raise InvalidReferenceError("revision was already resolved")
            if revision.status == RevisionStatus.SUPERSEDED:
                return RevisionResult(revision=revision, world=world)
            if revision.base_world_version != world.version:
                revision.status = RevisionStatus.SUPERSEDED
                revision.resulting_world_version = world.version
                row.status = revision.status
                row.state = revision.model_dump(mode="json")
                result = RevisionResult(revision=revision, world=world)
                row.resolution_key = request.idempotency_key
                row.result = result.model_dump(mode="json")
                return result
            if session.state_version != request.expected_state_version:
                raise VersionConflictError(request.expected_state_version, session.state_version)

            by_id = {item.candidate_id: item for item in revision.candidates}
            prompted = {prompt.candidate_id for prompt in revision.prompts}
            decisions = {item.candidate_id: item for item in request.decisions}
            if len(decisions) != len(request.decisions) or set(decisions) != prompted:
                raise InvalidReferenceError(
                    "decisions must cover each grounding prompt exactly once"
                )
            updated = world.model_copy(deep=True)
            changed_refs: set[str] = set()
            for candidate_id, decision in decisions.items():
                candidate = by_id[candidate_id]
                if decision.action == GroundingAction.CONFIRM and not candidate.confirmable:
                    raise InvalidReferenceError(
                        "observer item requires child-supplied canonical details"
                    )
                if decision.action in {GroundingAction.REJECT, GroundingAction.SKIP}:
                    continue
                if candidate.change == ChangeKind.REMOVED:
                    if decision.action == GroundingAction.CONFIRM:
                        self._remove_canonical(updated, candidate.canonical_ref)
                        if candidate.canonical_ref:
                            changed_refs.add(candidate.canonical_ref)
                    else:
                        assert decision.supplied_value is not None
                        self._apply_child_value(
                            updated, candidate, decision.supplied_value.model_dump(), candidate_id
                        )
                    continue
                if decision.action == GroundingAction.CORRECT:
                    assert decision.supplied_value is not None
                    value = decision.supplied_value.model_dump()
                    source = ProvenanceSource.CHILD_SUPPLIED
                else:
                    value = self._confirmable_value(candidate)
                    source = ProvenanceSource.CHILD_CONFIRMED
                self._apply_value(updated, candidate, value, candidate_id, source)
                if candidate.canonical_ref:
                    changed_refs.add(candidate.canonical_ref)

            if changed_refs:
                self._invalidate_dependents(updated, changed_refs)
            updated.version += 1
            revision.status = RevisionStatus.RESOLVED
            revision.resulting_world_version = updated.version
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
                event_type="DRAWING_REVISION_RESOLVED",
                state_version_before=world.version,
                state_version_after=updated.version,
                actor="child",
                payload_ref=revision_id,
                created_at=datetime.now(UTC),
            )
            db.add(EventRow(**event.model_dump(mode="python", exclude={"schema_version"})))
            snapshot.version = updated.version
            snapshot.state = updated.model_dump(mode="json")
            session.state_version = updated.version
            row.status = revision.status
            row.state = revision.model_dump(mode="json")
            result = RevisionResult(revision=revision, world=updated)
            row.resolution_key = request.idempotency_key
            row.result = result.model_dump(mode="json")
            return result

    @staticmethod
    def _reconcile(
        revision_id: str, payload: object, world: WorldState
    ) -> list[ReconciliationCandidate]:
        from child_agent_api.observer import ObserverPayload

        validated = ObserverPayload.model_validate(payload)
        remaining = {item.object_id: item for item in world.objects}
        result: list[ReconciliationCandidate] = []
        index = 0
        for item in validated.items:
            index += 1
            observed = observer_item_value(item)
            canonical = None
            change = ChangeKind.UNCERTAIN
            confirmable = item.kind in {"object", "object_count"}
            if confirmable:
                label = str(observed["label"])
                raw_count = observed.get("count", 1)
                count = raw_count if isinstance(raw_count, int) else 1
                canonical = next(
                    (obj for obj in remaining.values() if obj.type == label and obj.count == count),
                    None,
                )
                if canonical is not None:
                    change = ChangeKind.UNCHANGED
                elif remaining:
                    canonical = next(iter(remaining.values()))
                    change = ChangeKind.CHANGED
                else:
                    change = ChangeKind.ADDED
                if canonical is not None:
                    remaining.pop(canonical.object_id, None)
            result.append(
                ReconciliationCandidate(
                    candidate_id=f"rc_{revision_id.removeprefix('rev_')}_{index}",
                    observation_id=item.observation_id,
                    change=change,
                    observer_kind=item.kind,
                    observed=observed,
                    canonical_ref=canonical.object_id if canonical else None,
                    canonical_value=(
                        {"label": canonical.type, "count": canonical.count} if canonical else None
                    ),
                    requires_grounding=change != ChangeKind.UNCHANGED,
                    confirmable=confirmable,
                )
            )
        for object_id, obj in remaining.items():
            index += 1
            result.append(
                ReconciliationCandidate(
                    candidate_id=f"rc_{revision_id.removeprefix('rev_')}_{index}",
                    change=ChangeKind.REMOVED,
                    observer_kind="object",
                    canonical_ref=object_id,
                    canonical_value={"label": obj.type, "count": obj.count},
                    requires_grounding=True,
                    confirmable=True,
                )
            )
        return result

    @staticmethod
    def _confirmable_value(candidate: ReconciliationCandidate) -> JsonObject:
        if candidate.observed is None:
            raise InvalidReferenceError("removed candidates have no observer value")
        return {
            "kind": "object",
            "label": candidate.observed["label"],
            "count": candidate.observed.get("count", 1),
        }

    @staticmethod
    def _apply_child_value(
        world: WorldState, candidate: ReconciliationCandidate, value: JsonObject, source_ref: str
    ) -> None:
        WorldStateService._apply_value(
            world, candidate, value, source_ref, ProvenanceSource.CHILD_SUPPLIED
        )

    @staticmethod
    def _apply_value(
        world: WorldState,
        candidate: ReconciliationCandidate,
        value: JsonObject,
        source_ref: str,
        source: ProvenanceSource,
    ) -> None:
        provenance = Provenance(source=source, source_ref=source_ref)
        identifier = candidate.canonical_ref or f"obj_{candidate.candidate_id.removeprefix('rc_')}"
        kind = value["kind"]
        if candidate.canonical_ref:
            WorldStateService._remove_canonical(world, candidate.canonical_ref, tombstone=False)
        if kind == "object":
            world.objects.append(
                WorldObject(
                    object_id=identifier,
                    type=value["label"],
                    count=value.get("count", 1),
                    provenance=provenance,
                )
            )
        elif kind == "character":
            identifier = (
                candidate.canonical_ref or f"char_{candidate.candidate_id.removeprefix('rc_')}"
            )
            world.characters.append(
                Character(
                    character_id=identifier,
                    name=value["name"],
                    attributes=value.get("attributes", {}),
                    provenance=provenance,
                )
            )
        elif kind == "fact":
            identifier = (
                candidate.canonical_ref or f"fact_{candidate.candidate_id.removeprefix('rc_')}"
            )
            world.facts.append(
                Fact(
                    fact_id=identifier,
                    subject_ref=value["subject_ref"],
                    predicate=value["predicate"],
                    value=value["value"],
                    depends_on=value.get("depends_on", []),
                    provenance=provenance,
                )
            )
        elif kind == "relationship":
            identifier = (
                candidate.canonical_ref or f"rel_{candidate.candidate_id.removeprefix('rc_')}"
            )
            world.relationships.append(
                Relationship(
                    relationship_id=identifier,
                    from_ref=value["from_ref"],
                    to_ref=value["to_ref"],
                    kind=value["relationship_kind"],
                    provenance=provenance,
                )
            )

    @staticmethod
    def _remove_canonical(
        world: WorldState, reference: str | None, *, tombstone: bool = True
    ) -> None:
        if reference is None:
            raise InvalidReferenceError("candidate has no canonical reference")
        before = len(world.objects)
        world.objects = [item for item in world.objects if item.object_id != reference]
        if len(world.objects) != before:
            if tombstone:
                world.removed_entity_ids = sorted(set(world.removed_entity_ids) | {reference})
            world.relationships = [
                r for r in world.relationships if reference not in {r.from_ref, r.to_ref}
            ]
            return
        world.characters = [item for item in world.characters if item.character_id != reference]
        world.relationships = [
            r for r in world.relationships if reference not in {r.from_ref, r.to_ref}
        ]
        if tombstone:
            world.removed_entity_ids = sorted(set(world.removed_entity_ids) | {reference})

    @staticmethod
    def _invalidate_dependents(world: WorldState, changed_refs: set[str]) -> None:
        stale = set(world.stale_fact_ids)
        expanded = set(changed_refs)
        while True:
            additions = {
                fact.fact_id
                for fact in world.facts
                if fact.provenance.source == ProvenanceSource.STORY_DERIVED
                and set(fact.depends_on) & expanded
            }
            if additions <= expanded:
                break
            expanded |= additions
        stale |= {
            fact.fact_id
            for fact in world.facts
            if (fact.fact_id in expanded or fact.subject_ref in changed_refs)
            and fact.provenance.source == ProvenanceSource.STORY_DERIVED
        }
        world.stale_fact_ids = sorted(stale)
