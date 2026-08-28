"""Create interview session tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interview_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("meeting_url", sa.Text(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("resume_name", sa.Text(), nullable=False),
        sa.Column("job_description_name", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=60), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_sessions_state", "interview_sessions", ["state"])
    op.create_table(
        "session_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_events_session_id", "session_events", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_session_events_session_id", table_name="session_events")
    op.drop_table("session_events")
    op.drop_index("ix_interview_sessions_state", table_name="interview_sessions")
    op.drop_table("interview_sessions")
