"""drawing revisions

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
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("base_world_version", sa.Integer(), nullable=False),
        sa.Column("media_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("submission_key", sa.String(), nullable=False),
        sa.Column("resolution_key", sa.String()),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON()),
        sa.UniqueConstraint("session_id", "revision_number", name="uq_revision_order"),
        sa.UniqueConstraint("session_id", "submission_key", name="uq_revision_submission_key"),
        sa.CheckConstraint("revision_number > 0"),
        sa.CheckConstraint("base_world_version >= 0"),
    )


def downgrade() -> None:
    op.drop_table("drawing_revisions")
