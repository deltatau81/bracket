"""Add hockey match events.

Revision ID: hockey_match_events_001
Revises: hockey_tournament_mode_001
"""

import sqlalchemy as sa

from alembic import op


revision = "hockey_match_events_001"
down_revision = "hockey_tournament_mode_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("period", sa.String(length=20), nullable=False),
        sa.Column("game_time_seconds", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.BigInteger(), nullable=True),
        sa.Column("player_number", sa.Integer(), nullable=True),
        sa.Column("player_name", sa.String(), nullable=True),
        sa.Column("assist1_player_id", sa.BigInteger(), nullable=True),
        sa.Column("assist1_number", sa.Integer(), nullable=True),
        sa.Column("assist1_name", sa.String(), nullable=True),
        sa.Column("assist2_player_id", sa.BigInteger(), nullable=True),
        sa.Column("assist2_number", sa.Integer(), nullable=True),
        sa.Column("assist2_name", sa.String(), nullable=True),
        sa.Column("penalty_type", sa.String(), nullable=True),
        sa.Column("penalty_minutes", sa.Integer(), nullable=True),
        sa.Column("infraction", sa.String(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "event_type IN ('GOAL', 'PENALTY')", name="ck_match_events_event_type"
        ),
        sa.CheckConstraint(
            "period IN ('HALF1', 'HALF2', 'PERIOD1', 'PERIOD2', 'PERIOD3', 'OVERTIME')",
            name="ck_match_events_period",
        ),
        sa.CheckConstraint("game_time_seconds >= 0", name="ck_match_events_game_time_positive"),
        sa.CheckConstraint(
            "penalty_minutes IS NULL OR penalty_minutes >= 0",
            name="ck_match_events_penalty_minutes_positive",
        ),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assist1_player_id"], ["players.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assist2_player_id"], ["players.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_match_events_match_id", "match_events", ["match_id"])


def downgrade() -> None:
    op.drop_index("ix_match_events_match_id", table_name="match_events")
    op.drop_table("match_events")
