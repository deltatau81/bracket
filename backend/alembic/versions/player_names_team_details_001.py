"""Add structured player names and team assignment details.

Revision ID: player_names_team_details_001
Revises: hockey_match_parts_001
"""

import sqlalchemy as sa

from alembic import op


revision = "player_names_team_details_001"
down_revision = "hockey_match_parts_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("players", sa.Column("first_name", sa.String(), nullable=True))
    op.add_column("players", sa.Column("last_name", sa.String(), nullable=True))
    op.add_column("players_x_teams", sa.Column("number", sa.Integer(), nullable=True))
    op.add_column("players_x_teams", sa.Column("position", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("players_x_teams", "position")
    op.drop_column("players_x_teams", "number")
    op.drop_column("players", "last_name")
    op.drop_column("players", "first_name")
