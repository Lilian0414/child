"""session and world-state core

Revision ID: 0001_session_world_core
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_session_world_core"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(), primary_key=True),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("profile", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("state_version >= 0"),
    )
    op.create_table(
        "observation_batches",
        sa.Column("batch_id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.session_id"), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("media_id", sa.String(), nullable=False),
        sa.UniqueConstraint("session_id", "batch_id"),
    )
    op.create_table(
        "observations",
        sa.Column("observation_id", sa.String(), primary_key=True),
        sa.Column(
            "batch_id", sa.String(), sa.ForeignKey("observation_batches.batch_id"), nullable=False
        ),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.session_id"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("candidate", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("needs_confirmation", sa.Boolean(), nullable=False),
        sa.Column("evidence_note", sa.String()),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.UniqueConstraint("session_id", "observation_id"),
    )
    op.create_table(
        "events",
        sa.Column("event_id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.session_id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("state_version_before", sa.Integer(), nullable=False),
        sa.Column("state_version_after", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("payload_ref", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "sequence", name="uq_events_session_sequence"),
        sa.CheckConstraint("sequence > 0"),
        sa.CheckConstraint("state_version_after = state_version_before + 1"),
    )
    op.create_table(
        "world_snapshots",
        sa.Column(
            "session_id", sa.String(), sa.ForeignKey("sessions.session_id"), primary_key=True
        ),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
    )
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.session_id"), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.UniqueConstraint("session_id", "key", name="uq_idempotency_session_key"),
    )


def downgrade() -> None:
    for table in (
        "idempotency_records",
        "world_snapshots",
        "events",
        "observations",
        "observation_batches",
        "sessions",
    ):
        op.drop_table(table)
