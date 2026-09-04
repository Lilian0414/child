"""canonical story state and proposals

Revision ID: 0003_story_state
Revises: 0002_drawing_revisions
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_story_state"
down_revision: str | None = "0002_drawing_revisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "story_snapshots",
        sa.Column(
            "session_id", sa.String(), sa.ForeignKey("sessions.session_id"), primary_key=True
        ),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
    )
    op.create_table(
        "story_proposals",
        sa.Column("proposal_id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.session_id"), nullable=False),
        sa.Column("based_on_state_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("proposal", sa.JSON(), nullable=False),
        sa.UniqueConstraint("session_id", "based_on_state_version"),
    )
    connection = op.get_bind()
    sessions = sa.table(
        "sessions", sa.column("session_id", sa.String()), sa.column("state_version", sa.Integer())
    )
    snapshots = sa.table(
        "story_snapshots",
        sa.column("session_id", sa.String()),
        sa.column("schema_version", sa.String()),
        sa.column("state_version", sa.Integer()),
        sa.column("state", sa.JSON()),
    )
    for session_id, state_version in connection.execute(
        sa.select(sessions.c.session_id, sessions.c.state_version)
    ):
        connection.execute(
            snapshots.insert().values(
                session_id=session_id,
                schema_version="story.v1",
                state_version=state_version,
                state={
                    "schema_version": "story.v1",
                    "session_id": session_id,
                    "state_version": state_version,
                    "next_segment_index": 0,
                    "segments": [],
                    "current_proposal": None,
                },
            )
        )


def downgrade() -> None:
    op.drop_table("story_proposals")
    op.drop_table("story_snapshots")
