"""Persist hockey match phase state.

Revision ID: hockey_match_phase_001
Revises: scorer_account_type_001
"""

import sqlalchemy as sa

from alembic import op


revision = "hockey_match_phase_001"
down_revision = "scorer_account_type_001"
branch_labels = None
depends_on = None


_PREVIOUS_EVENT_PERIODS = (
    "period IN ('HALF1', 'HALF2', 'PERIOD1', 'PERIOD2', 'PERIOD3', 'OVERTIME')"
)
_EVENT_PERIODS_WITH_SHOOTOUT = (
    "period IN "
    "('HALF1', 'HALF2', 'SHOOTOUT', 'PERIOD1', 'PERIOD2', 'PERIOD3', 'OVERTIME')"
)
_MATCH_PERIODS = (
    "active_period IS NULL OR active_period IN "
    "('HALF1', 'HALF2', 'SHOOTOUT', 'PERIOD1', 'PERIOD2', 'PERIOD3', 'OVERTIME')"
)
_MATCH_PHASE_STATES = "phase_state IS NULL OR phase_state IN ('ACTIVE', 'BREAK')"


def upgrade() -> None:
    op.add_column("matches", sa.Column("active_period", sa.String(length=20), nullable=True))
    op.add_column("matches", sa.Column("phase_state", sa.String(length=20), nullable=True))
    op.create_check_constraint("ck_matches_active_period", "matches", _MATCH_PERIODS)
    op.create_check_constraint("ck_matches_phase_state", "matches", _MATCH_PHASE_STATES)
    op.drop_constraint("ck_match_events_period", "match_events", type_="check")
    op.create_check_constraint(
        "ck_match_events_period",
        "match_events",
        _EVENT_PERIODS_WITH_SHOOTOUT,
    )


def downgrade() -> None:
    op.drop_constraint("ck_match_events_period", "match_events", type_="check")
    op.create_check_constraint(
        "ck_match_events_period",
        "match_events",
        _PREVIOUS_EVENT_PERIODS,
    )
    op.drop_constraint("ck_matches_phase_state", "matches", type_="check")
    op.drop_constraint("ck_matches_active_period", "matches", type_="check")
    op.drop_column("matches", "phase_state")
    op.drop_column("matches", "active_period")
