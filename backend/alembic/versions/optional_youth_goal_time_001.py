"""Allow unknown match-event game time.

Revision ID: optional_youth_goal_time_001
Revises: game_shootout_001
"""

from alembic import op
import sqlalchemy as sa


revision = "optional_youth_goal_time_001"
down_revision = "game_shootout_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "match_events",
        "game_time_seconds",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        "UPDATE match_events SET game_time_seconds = 0 "
        "WHERE game_time_seconds IS NULL"
    )
    op.alter_column(
        "match_events",
        "game_time_seconds",
        existing_type=sa.Integer(),
        nullable=False,
    )