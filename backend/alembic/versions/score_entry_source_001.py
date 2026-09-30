"""Add explicit score entry source to matches.

Revision ID: score_entry_source_001
Revises: optional_youth_goal_time_001
"""

from alembic import op
import sqlalchemy as sa


revision = "score_entry_source_001"
down_revision = "optional_youth_goal_time_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("score_entry_source", sa.String(10), nullable=True))
    op.create_check_constraint(
        "ck_matches_score_entry_source",
        "matches",
        "score_entry_source IS NULL OR score_entry_source IN ('MANUAL', 'EVENTS')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_matches_score_entry_source", "matches", type_="check")
    op.drop_column("matches", "score_entry_source")