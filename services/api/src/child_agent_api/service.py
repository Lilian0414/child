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
    CandidateDecision,
    Character,
    DomainEvent,
    DrawingRevision,
    Fact,
    FullStory,
    ObservationBatch,
    ObservationDecision,
    ObservationItem,
    Provenance,
    ProvenanceSource,
    ReconciliationCandidate,
    Relationship,
    RevisionState,
    Session,
    SessionStatus,
    StoryGrounding,
    StoryProposal,
    StorySegment,
    StoryState,
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
    ReconciliationCandidateRow,
    SessionRow,
    StoryProposalRow,
    StorySnapshotRow,
    WorldSnapshotRow,
)
from child_agent_api.reconciliation import reconcile, select_prompts
from child_agent_api.story import DeterministicStoryProvider, StoryProvider, StoryProviderResult

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
            story = StoryState(session_id=session_id, state_version=0, next_segment_index=0)
            db.add(
                StorySnapshotRow(
                    session_id=session_id,
                    schema_version="story.v1",
                    state_version=0,
                    state=story.model_dump(mode="json"),
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

    def submit_revision(
        self,
        session_id: str,
        revision_id: str,
        batch: ObservationBatch,
        expected_state_version: int,
        idempotency_key: str,
    ) -> RevisionState:
        """Persist a validated proposal set without promoting it into canonical state."""
        with DbSession(self.engine) as db, db.begin():
            duplicate = db.scalar(
                select(DrawingRevisionRow).where(
                    DrawingRevisionRow.session_id == session_id,
                    DrawingRevisionRow.idempotency_key == idempotency_key,
                )
            )
            if duplicate is not None:
                if duplicate.revision_id != revision_id or duplicate.batch_id != batch.batch_id:
                    raise InvalidReferenceError("idempotency key belongs to another revision")
                return self._revision_state(db, duplicate)
            session = db.get(SessionRow, session_id)
            snapshot = db.get(WorldSnapshotRow, session_id)
            if session is None or snapshot is None:
                raise NotFoundError("session does not exist")
            if session.state_version != expected_state_version:
                raise VersionConflictError(expected_state_version, session.state_version)
            if session.status == SessionStatus.COMPLETE:
                raise InvalidReferenceError("completed session cannot be revised")
            if db.get(DrawingRevisionRow, revision_id) is not None:
                raise InvalidReferenceError("revision already exists")
            if db.get(ObservationBatchRow, batch.batch_id) is not None:
                raise InvalidReferenceError("batch already exists")
            unresolved = db.scalar(
                select(DrawingRevisionRow).where(
                    DrawingRevisionRow.session_id == session_id,
                    DrawingRevisionRow.status == "awaiting_grounding",
                )
            )
            if unresolved is not None:
                raise InvalidReferenceError("previous revision still requires grounding")
            number = (
                db.scalar(
                    select(func.max(DrawingRevisionRow.number)).where(
                        DrawingRevisionRow.session_id == session_id
                    )
                )
                or 0
            ) + 1
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
            db.flush()
            world = WorldState.model_validate(snapshot.state, strict=False)
            candidates = reconcile(revision_id, batch, world)
            status = "awaiting_grounding" if select_prompts(candidates) else "resolved"
            row = DrawingRevisionRow(
                revision_id=revision_id,
                session_id=session_id,
                number=number,
                batch_id=batch.batch_id,
                based_on_world_version=expected_state_version,
                status=status,
                idempotency_key=idempotency_key,
                created_at=datetime.now(UTC),
            )
            db.add(row)
            for candidate in candidates:
                db.add(ReconciliationCandidateRow(**candidate.model_dump(mode="json")))
            db.flush()
            return self._revision_state(db, row)

    def get_revision(self, session_id: str, revision_id: str) -> RevisionState:
        with DbSession(self.engine) as db:
            row = db.get(DrawingRevisionRow, revision_id)
            if row is None or row.session_id != session_id:
                raise NotFoundError("revision does not exist")
            return self._revision_state(db, row)

    def resolve_revision(
        self,
        session_id: str,
        revision_id: str,
        decisions: list[CandidateDecision],
        command_id: str,
        expected_state_version: int,
        idempotency_key: str,
    ) -> RevisionState:
        if len({item.candidate_id for item in decisions}) != len(decisions):
            raise InvalidReferenceError("candidate decisions must be unique")

        # Reconciliation is valid only for the exact canonical snapshot it read. Marking
        # the old work superseded makes the conflict recoverable without touching the world.
        with DbSession(self.engine) as db, db.begin():
            revision = db.get(DrawingRevisionRow, revision_id)
            session = db.get(SessionRow, session_id)
            if revision is None or revision.session_id != session_id:
                raise InvalidReferenceError("revision does not exist in session")
            if session is None:
                raise NotFoundError("session does not exist")
            if (
                revision.status == "awaiting_grounding"
                and revision.based_on_world_version != session.state_version
            ):
                revision.status = "superseded"
                return self._revision_state(db, revision)

        def change(
            db: DbSession, world: WorldState
        ) -> tuple[WorldState, str, Literal["system", "model", "child", "adult"], str]:
            revision = db.get(DrawingRevisionRow, revision_id)
            if revision is None or revision.session_id != session_id:
                raise InvalidReferenceError("revision does not exist in session")
            if revision.status != "awaiting_grounding":
                raise InvalidReferenceError("revision has already been resolved")
            rows = list(
                db.scalars(
                    select(ReconciliationCandidateRow)
                    .where(ReconciliationCandidateRow.revision_id == revision_id)
                    .order_by(ReconciliationCandidateRow.candidate_id)
                )
            )
            allowed = {
                prompt.candidate_id
                for prompt in select_prompts([self._candidate(item) for item in rows])
            }
            if not decisions or any(item.candidate_id not in allowed for item in decisions):
                raise InvalidReferenceError("decision does not target a grounding prompt")
            prompts = {
                prompt.candidate_id: prompt
                for prompt in select_prompts([self._candidate(item) for item in rows])
            }
            if any(
                item.action not in prompts[item.candidate_id].allowed_actions for item in decisions
            ):
                raise InvalidReferenceError("decision action is not allowed for this observation")
            updated = world.model_copy(deep=True)
            updated.version += 1
            supplied = {item.candidate_id: item for item in decisions}
            for row in rows:
                decision = supplied.get(row.candidate_id)
                if row.candidate_id in allowed and decision is None:
                    row.decision = "skip"
                    continue
                if decision is None:
                    continue
                row.decision = decision.action
                self._apply_candidate(updated, self._candidate(row), decision, command_id)
                if row.observation_id is not None:
                    observation = db.get(ObservationRow, row.observation_id)
                    if observation is not None:
                        observation.status = {
                            "confirm": "confirmed",
                            "correct": "corrected",
                            "reject": "rejected",
                            "skip": "expired",
                        }[decision.action]
            revision.status = "resolved"
            return updated, "DRAWING_REVISION_GROUNDED", "child", command_id

        invalidated_refs: set[str] = set()
        with DbSession(self.engine) as db:
            rows = list(
                db.scalars(
                    select(ReconciliationCandidateRow).where(
                        ReconciliationCandidateRow.revision_id == revision_id
                    )
                )
            )
            supplied = {item.candidate_id: item for item in decisions}
            for row in rows:
                decision = supplied.get(row.candidate_id)
                if (
                    row.current_ref is not None
                    and row.change in {"changed", "removed"}
                    and decision is not None
                    and decision.action in {"confirm", "correct"}
                ):
                    invalidated_refs.add(row.current_ref)
        self._mutate(
            session_id,
            expected_state_version,
            idempotency_key,
            change,
            invalidated_story_refs=invalidated_refs,
        )
        return self.get_revision(session_id, revision_id)

    def get_story(self, session_id: str) -> StoryState:
        with DbSession(self.engine) as db:
            row = db.get(StorySnapshotRow, session_id)
            if row is None:
                raise NotFoundError("session does not exist")
            return StoryState.model_validate(row.state, strict=False)

    def request_story_proposal(
        self,
        session_id: str,
        expected_state_version: int,
        provider: StoryProvider | None = None,
    ) -> StoryState:
        """Validate and persist an uncommitted proposal without advancing canonical state."""
        provider = provider or DeterministicStoryProvider()
        with DbSession(self.engine) as db, db.begin():
            session = db.get(SessionRow, session_id)
            snapshot = db.get(StorySnapshotRow, session_id)
            world_row = db.get(WorldSnapshotRow, session_id)
            if session is None or snapshot is None or world_row is None:
                raise NotFoundError("session does not exist")
            if session.status == SessionStatus.COMPLETE:
                raise InvalidReferenceError("completed session cannot continue")
            if session.state_version != expected_state_version:
                raise VersionConflictError(expected_state_version, session.state_version)
            story = StoryState.model_validate(snapshot.state, strict=False)
            if story.current_proposal is not None:
                return story
            # Story snapshots may lag world-only transitions; synchronize their optimistic
            # concurrency token before giving the provider its canonical read model.
            story.state_version = expected_state_version
            provider_result = StoryProviderResult.model_validate(
                provider.propose(
                    WorldState.model_validate(world_row.state, strict=False),
                    story,
                )
            )
            proposal = StoryProposal(
                proposal_id=f"proposal_{uuid4().hex}",
                session_id=session_id,
                based_on_state_version=expected_state_version,
                segment_index=story.next_segment_index,
                text=provider_result.text,
                world_dependencies=provider_result.world_dependencies,
            )
            active = (
                {x.character_id for x in self.get_world(session_id).characters}
                | {x.object_id for x in self.get_world(session_id).objects}
                | {x.fact_id for x in self.get_world(session_id).facts}
            )
            if not set(proposal.world_dependencies) <= active:
                raise InvalidReferenceError("provider returned invalid world dependencies")
            story.current_proposal = proposal
            db.add(
                StoryProposalRow(
                    proposal_id=proposal.proposal_id,
                    session_id=session_id,
                    based_on_state_version=expected_state_version,
                    status="pending",
                    proposal=proposal.model_dump(mode="json"),
                )
            )
            snapshot.state = story.model_dump(mode="json")
            return story

    def ground_story_proposal(
        self,
        session_id: str,
        proposal_id: str,
        grounding: StoryGrounding,
        expected_state_version: int,
        idempotency_key: str,
    ) -> StoryState:
        with DbSession(self.engine) as db, db.begin():
            duplicate = db.scalar(
                select(IdempotencyRow).where(
                    IdempotencyRow.session_id == session_id, IdempotencyRow.key == idempotency_key
                )
            )
            if duplicate is not None:
                row = db.get(StorySnapshotRow, session_id)
                assert row is not None
                return StoryState.model_validate(row.state, strict=False)
            session = db.get(SessionRow, session_id)
            story_row = db.get(StorySnapshotRow, session_id)
            world_row = db.get(WorldSnapshotRow, session_id)
            proposal_row = db.get(StoryProposalRow, proposal_id)
            if session is None or story_row is None or world_row is None:
                raise NotFoundError("session does not exist")
            if session.state_version != expected_state_version:
                raise VersionConflictError(expected_state_version, session.state_version)
            story = StoryState.model_validate(story_row.state, strict=False)
            proposal = story.current_proposal
            if proposal is None or proposal.proposal_id != proposal_id or proposal_row is None:
                raise InvalidReferenceError("proposal is not current")
            if proposal.based_on_state_version != session.state_version:
                raise InvalidReferenceError("proposal is stale")
            text = proposal.text if grounding.action == "accept" else grounding.supplied_text
            assert text is not None
            source = (
                ProvenanceSource.CHILD_CONFIRMED
                if grounding.action == "accept"
                else ProvenanceSource.CHILD_SUPPLIED
            )
            next_version = expected_state_version + 1
            story.segments.append(
                StorySegment(
                    segment_id=f"segment_{uuid4().hex}",
                    index=story.next_segment_index,
                    text=text,
                    provenance=Provenance(source=source, source_ref=proposal_id),
                    proposal_id=proposal_id,
                    world_dependencies=proposal.world_dependencies,
                )
            )
            story.next_segment_index += 1
            story.state_version = next_version
            story.current_proposal = None
            proposal_row.status = "accepted" if grounding.action == "accept" else "superseded"
            world = WorldState.model_validate(world_row.state, strict=False)
            world.version = next_version
            session.state_version = next_version
            world_row.version = next_version
            world_row.state = world.model_dump(mode="json")
            story_row.state_version = next_version
            story_row.state = story.model_dump(mode="json")
            sequence = (
                db.scalar(
                    select(func.max(EventRow.sequence)).where(EventRow.session_id == session_id)
                )
                or 0
            ) + 1
            db.add(
                EventRow(
                    event_id=f"evt_{uuid4().hex}",
                    session_id=session_id,
                    sequence=sequence,
                    event_type="STORY_SEGMENT_GROUNDED",
                    state_version_before=expected_state_version,
                    state_version_after=next_version,
                    actor="child",
                    payload_ref=proposal_id,
                    created_at=datetime.now(UTC),
                )
            )
            db.add(
                IdempotencyRow(
                    session_id=session_id, key=idempotency_key, result=world.model_dump(mode="json")
                )
            )
            return story

    def full_story(self, session_id: str) -> FullStory:
        story = self.get_story(session_id)
        segments = sorted(
            (x for x in story.segments if x.status == "current"), key=lambda x: x.index
        )
        return FullStory(
            session_id=session_id,
            state_version=story.state_version,
            text="\n".join(x.text for x in segments),
            segment_ids=[x.segment_id for x in segments],
        )

    def complete_story(
        self,
        session_id: str,
        expected_state_version: int,
        idempotency_key: str,
    ) -> FullStory:
        """Complete a grounded story without generating or accepting any content."""
        with DbSession(self.engine) as db, db.begin():
            duplicate = db.scalar(
                select(IdempotencyRow).where(
                    IdempotencyRow.session_id == session_id,
                    IdempotencyRow.key == idempotency_key,
                )
            )
            if duplicate is not None:
                return FullStory.model_validate(duplicate.result, strict=False)

            session = db.get(SessionRow, session_id)
            story_row = db.get(StorySnapshotRow, session_id)
            world_row = db.get(WorldSnapshotRow, session_id)
            if session is None or story_row is None or world_row is None:
                raise NotFoundError("session does not exist")
            if session.state_version != expected_state_version:
                raise VersionConflictError(expected_state_version, session.state_version)
            if session.status == SessionStatus.COMPLETE:
                raise InvalidReferenceError("story is already complete")

            story = StoryState.model_validate(story_row.state, strict=False)
            if story.current_proposal is not None:
                raise InvalidReferenceError("pending story proposal must be grounded first")
            segments = sorted(
                (segment for segment in story.segments if segment.status == "current"),
                key=lambda segment: segment.index,
            )
            if not segments:
                raise InvalidReferenceError("story requires a grounded current segment")

            next_version = expected_state_version + 1
            story.state_version = next_version
            world = WorldState.model_validate(world_row.state, strict=False)
            world.version = next_version
            result = FullStory(
                session_id=session_id,
                state_version=next_version,
                text="\n".join(segment.text for segment in segments),
                segment_ids=[segment.segment_id for segment in segments],
            )
            completion_ref = f"completion_{uuid4().hex}"
            sequence = (
                db.scalar(
                    select(func.max(EventRow.sequence)).where(EventRow.session_id == session_id)
                )
                or 0
            ) + 1
            db.add(
                EventRow(
                    event_id=f"evt_{uuid4().hex}",
                    session_id=session_id,
                    sequence=sequence,
                    event_type="STORY_COMPLETED",
                    state_version_before=expected_state_version,
                    state_version_after=next_version,
                    actor="child",
                    payload_ref=completion_ref,
                    created_at=datetime.now(UTC),
                )
            )
            session.status = SessionStatus.COMPLETE
            session.state_version = next_version
            story_row.state_version = next_version
            story_row.state = story.model_dump(mode="json")
            world_row.version = next_version
            world_row.state = world.model_dump(mode="json")
            db.add(
                IdempotencyRow(
                    session_id=session_id,
                    key=idempotency_key,
                    result=result.model_dump(mode="json"),
                )
            )
            if self.before_commit is not None:
                self.before_commit()
            return result

    def _revision_state(self, db: DbSession, row: DrawingRevisionRow) -> RevisionState:
        snapshot = db.get(WorldSnapshotRow, row.session_id)
        assert snapshot is not None
        candidates = [
            self._candidate(item)
            for item in db.scalars(
                select(ReconciliationCandidateRow)
                .where(ReconciliationCandidateRow.revision_id == row.revision_id)
                .order_by(ReconciliationCandidateRow.candidate_id)
            )
        ]
        revision = DrawingRevision.model_validate(
            {
                "revision_id": row.revision_id,
                "session_id": row.session_id,
                "number": row.number,
                "batch_id": row.batch_id,
                "based_on_world_version": row.based_on_world_version,
                "status": row.status,
                "created_at": row.created_at,
            },
            strict=False,
        )
        return RevisionState(
            revision=revision,
            candidates=candidates,
            prompts=(select_prompts(candidates) if row.status == "awaiting_grounding" else []),
            world=WorldState.model_validate(snapshot.state, strict=False),
        )

    @staticmethod
    def _candidate(row: ReconciliationCandidateRow) -> ReconciliationCandidate:
        return ReconciliationCandidate.model_validate(
            {
                "candidate_id": row.candidate_id,
                "revision_id": row.revision_id,
                "change": row.change,
                "kind": row.kind,
                "current_ref": row.current_ref,
                "current_value": row.current_value,
                "observation_id": row.observation_id,
                "proposed_value": row.proposed_value,
                "requires_grounding": row.requires_grounding,
                "decision": row.decision,
            },
            strict=False,
        )

    def _apply_candidate(
        self,
        world: WorldState,
        candidate: ReconciliationCandidate,
        decision: CandidateDecision,
        source_ref: str,
    ) -> None:
        if decision.action in {"reject", "skip"}:
            return
        if candidate.change.value == "removed" and decision.action == "confirm":
            self._remove_canonical(world, candidate.current_ref)
            return
        value = (
            decision.supplied_value if decision.action == "correct" else candidate.proposed_value
        )
        if value is None:
            raise InvalidReferenceError("decision has no canonical value")
        source = (
            ProvenanceSource.CHILD_SUPPLIED
            if decision.action == "correct"
            else ProvenanceSource.CHILD_CONFIRMED
        )
        if candidate.current_ref is not None:
            self._remove_canonical(world, candidate.current_ref)
        observation_id = candidate.observation_id or candidate.current_ref or candidate.candidate_id
        if candidate.current_ref is not None:
            world.retired_ids = [
                item for item in world.retired_ids if item != candidate.current_ref
            ]
        self._promote(
            world,
            candidate.kind.value,
            value,
            source_ref,
            source,
            observation_id,
            candidate.current_ref is not None,
            canonical_id=candidate.current_ref,
        )

    @staticmethod
    def _remove_canonical(world: WorldState, ref: str | None) -> None:
        if ref is None:
            return
        dependent = {
            fact.fact_id
            for fact in world.facts
            if fact.provenance.source == ProvenanceSource.STORY_DERIVED
            and (fact.subject_ref == ref or ref in fact.depends_on)
        }
        world.characters = [item for item in world.characters if item.character_id != ref]
        world.objects = [item for item in world.objects if item.object_id != ref]
        world.relationships = [
            item
            for item in world.relationships
            if item.relationship_id != ref and item.from_ref != ref and item.to_ref != ref
        ]
        world.facts = [item for item in world.facts if item.fact_id != ref]
        world.stale_fact_ids = sorted(set(world.stale_fact_ids) | dependent)
        world.retired_ids = sorted(set(world.retired_ids) | {ref})

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
            row.status = {
                "confirm": "confirmed",
                "reject": "rejected",
                "correct": "corrected",
                "skip": "expired",
            }[decision.action]
            updated = world.model_copy(deep=True)
            updated.version += 1
            if decision.action not in {"reject", "skip"}:
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
        *,
        invalidated_story_refs: set[str] | None = None,
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
            if session.status == SessionStatus.COMPLETE:
                raise InvalidReferenceError("completed session cannot be mutated")
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
            self._invalidate_story_dependencies_in_transaction(
                db, session_id, world, invalidated_story_refs or set()
            )
            db.add(
                IdempotencyRow(session_id=session_id, key=key, result=world.model_dump(mode="json"))
            )
            if self.before_commit is not None:
                self.before_commit()
            return world

    @staticmethod
    def _invalidate_story_dependencies_in_transaction(
        db: DbSession, session_id: str, world: WorldState, invalidated_refs: set[str]
    ) -> None:
        """Synchronize story and invalidate semantically outdated dependencies."""
        row = db.get(StorySnapshotRow, session_id)
        if row is None:
            return
        story = StoryState.model_validate(row.state, strict=False)
        active = (
            {item.character_id for item in world.characters}
            | {item.object_id for item in world.objects}
            | {item.fact_id for item in world.facts}
        )
        for segment in story.segments:
            dependencies = set(segment.world_dependencies)
            if not dependencies <= active or bool(dependencies & invalidated_refs):
                segment.status = "stale"
        if story.current_proposal is not None and (
            story.current_proposal.based_on_state_version != world.version
            or not set(story.current_proposal.world_dependencies) <= active
            or bool(set(story.current_proposal.world_dependencies) & invalidated_refs)
        ):
            proposal = db.get(StoryProposalRow, story.current_proposal.proposal_id)
            if proposal is not None:
                proposal.status = "superseded"
            story.current_proposal = None
        story.state_version = world.version
        row.state_version = world.version
        row.state = story.model_dump(mode="json")

    @staticmethod
    def _promote(
        world: WorldState,
        kind: str,
        value: JsonObject,
        source_ref: str,
        source: ProvenanceSource,
        observation_id: str,
        correcting: bool,
        canonical_id: str | None = None,
    ) -> None:
        provenance = Provenance(source=source, source_ref=source_ref)
        suffix = observation_id.removeprefix("obs_")
        try:
            if kind == "character":
                world.characters.append(
                    Character(
                        character_id=canonical_id or f"char_{suffix}",
                        name=value["name"],
                        attributes=value.get("attributes", {}),
                        provenance=provenance,
                    )
                )
            elif kind in {"object", "object_count"}:
                world.objects.append(
                    WorldObject(
                        object_id=canonical_id or f"obj_{suffix}",
                        type=value["type"] if "type" in value else value["label"],
                        count=value.get("count", 1),
                        provenance=provenance,
                    )
                )
            elif kind == "relationship":
                world.relationships.append(
                    Relationship(
                        relationship_id=canonical_id or f"rel_{suffix}",
                        from_ref=value["from_ref"],
                        to_ref=value["to_ref"],
                        kind=value["kind"],
                        provenance=provenance,
                    )
                )
            elif kind == "fact":
                fact_id = canonical_id or value.get("fact_id", f"fact_{suffix}")
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
