"""drawing revisions and semantic reconciliation

Revision ID: 0002_drawing_revisions
Revises: 0001_session_world_core
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_drawing_revisions"
down_revision: str | None = "0001_session_world_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "drawing_revisions",
        sa.Column("revision_id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.session_id"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column(
            "batch_id",
            sa.String(),
            sa.ForeignKey("observation_batches.batch_id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("based_on_world_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "number", name="uq_revision_session_number"),
        sa.UniqueConstraint("session_id", "idempotency_key", name="uq_revision_session_key"),
        sa.CheckConstraint("number > 0"),
    )
    op.create_table(
        "reconciliation_candidates",
        sa.Column("candidate_id", sa.String(), primary_key=True),
        sa.Column(
            "revision_id",
            sa.String(),
            sa.ForeignKey("drawing_revisions.revision_id"),
            nullable=False,
        ),
        sa.Column("change", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("current_ref", sa.String()),
        sa.Column("current_value", sa.JSON()),
        sa.Column("observation_id", sa.String()),
        sa.Column("proposed_value", sa.JSON()),
        sa.Column("requires_grounding", sa.Boolean(), nullable=False),
        sa.Column("decision", sa.String()),
    )


def downgrade() -> None:
    op.drop_table("reconciliation_candidates")
    op.drop_table("drawing_revisions")
