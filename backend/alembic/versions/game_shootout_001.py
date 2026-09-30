"""Add generic game and shootout hockey mode.

Revision ID: game_shootout_001
Revises: team_participant_club_001
"""

from alembic import op


revision = "game_shootout_001"
down_revision = "team_participant_club_001"
branch_labels = None
depends_on = None

_OLD_MODES = "hockey_mode IN ('COMPETITION', 'STANDARD')"
_NEW_MODES = "hockey_mode IN ('COMPETITION', 'GAME_SHOOTOUT', 'STANDARD')"
_OLD_MATCH_PERIODS = "active_period IS NULL OR active_period IN ('HALF1', 'HALF2', 'SHOOTOUT', 'PERIOD1', 'PERIOD2', 'PERIOD3', 'OVERTIME')"
_NEW_MATCH_PERIODS = "active_period IS NULL OR active_period IN ('GAME', 'HALF1', 'HALF2', 'SHOOTOUT', 'PERIOD1', 'PERIOD2', 'PERIOD3', 'OVERTIME')"
_OLD_EVENT_PERIODS = "period IN ('HALF1', 'HALF2', 'SHOOTOUT', 'PERIOD1', 'PERIOD2', 'PERIOD3', 'OVERTIME')"
_NEW_EVENT_PERIODS = "period IN ('GAME', 'HALF1', 'HALF2', 'SHOOTOUT', 'PERIOD1', 'PERIOD2', 'PERIOD3', 'OVERTIME')"


def _replace_constraint(table: str, name: str, expression: str) -> None:
    op.drop_constraint(name, table, type_="check")
    op.create_check_constraint(name, table, expression)


def upgrade() -> None:
    _replace_constraint("tournaments", "ck_tournaments_hockey_mode", _NEW_MODES)
    _replace_constraint("matches", "ck_matches_active_period", _NEW_MATCH_PERIODS)
    _replace_constraint("match_events", "ck_match_events_period", _NEW_EVENT_PERIODS)


def downgrade() -> None:
    op.execute("UPDATE match_events SET period = 'HALF1' WHERE period = 'GAME'")
    op.execute("UPDATE matches SET active_period = 'HALF1' WHERE active_period = 'GAME'")
    op.execute("UPDATE tournaments SET hockey_mode = 'COMPETITION' WHERE hockey_mode = 'GAME_SHOOTOUT'")
    _replace_constraint("match_events", "ck_match_events_period", _OLD_EVENT_PERIODS)
    _replace_constraint("matches", "ck_matches_active_period", _OLD_MATCH_PERIODS)
    _replace_constraint("tournaments", "ck_tournaments_hockey_mode", _OLD_MODES)
