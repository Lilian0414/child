"""SQLAlchemy persistence models; deliberately separate from domain contracts."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"
    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    schema_version: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (CheckConstraint("state_version >= 0"),)


class ObservationBatchRow(Base):
    __tablename__ = "observation_batches"
    batch_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False)
    schema_version: Mapped[str] = mapped_column(String, nullable=False)
    media_id: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (UniqueConstraint("session_id", "batch_id"),)


class ObservationRow(Base):
    __tablename__ = "observations"
    observation_id: Mapped[str] = mapped_column(String, primary_key=True)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("observation_batches.batch_id"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    candidate: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    needs_confirmation: Mapped[bool] = mapped_column(nullable=False)
    evidence_note: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (UniqueConstraint("session_id", "observation_id"),)


class EventRow(Base):
    __tablename__ = "events"
    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    state_version_before: Mapped[int] = mapped_column(Integer, nullable=False)
    state_version_after: Mapped[int] = mapped_column(Integer, nullable=False)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    payload_ref: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_events_session_sequence"),
        CheckConstraint("sequence > 0"),
        CheckConstraint("state_version_after = state_version_before + 1"),
    )


class WorldSnapshotRow(Base):
    __tablename__ = "world_snapshots"
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class IdempotencyRow(Base):
    __tablename__ = "idempotency_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False)
    key: Mapped[str] = mapped_column(String, nullable=False)
    result: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint("session_id", "key", name="uq_idempotency_session_key"),)
