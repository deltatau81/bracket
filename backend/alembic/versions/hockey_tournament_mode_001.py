"""Add hockey tournament mode.

Revision ID: hockey_tournament_mode_001
Revises: player_names_team_details_001
"""

import sqlalchemy as sa

from alembic import op


revision = "hockey_tournament_mode_001"
down_revision = "player_names_team_details_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tournaments",
        sa.Column(
            "hockey_mode",
            sa.String(length=20),
            server_default="COMPETITION",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_tournaments_hockey_mode",
        "tournaments",
        "hockey_mode IN ('COMPETITION', 'STANDARD')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tournaments_hockey_mode", "tournaments", type_="check")
    op.drop_column("tournaments", "hockey_mode")
