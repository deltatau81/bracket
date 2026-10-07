"""Add tournament-wide hockey scoring configuration.

Revision ID: hockey_scoring_rules_001
Revises: youth_club_format_001
"""

import sqlalchemy as sa

from alembic import op

revision = "hockey_scoring_rules_001"
down_revision = "youth_club_format_001"
branch_labels = None
depends_on = None

# Keep migration defaults independent of application models.
SCORING_DEFAULTS = {
    "game_win_points": "2",
    "game_draw_points": "1",
    "game_loss_points": "0",
    "shootout_win_points": "1",
    "shootout_draw_points": "0.5",
    "shootout_loss_points": "0",
}


def upgrade() -> None:
    for field, default in SCORING_DEFAULTS.items():
        op.add_column(
            "tournaments",
            sa.Column(field, sa.Numeric(8, 2), nullable=False, server_default=default),
        )
        op.create_check_constraint(
            f"ck_tournaments_{field}",
            "tournaments",
            f"{field} >= 0 AND {field} <= 999999.99",
        )


def downgrade() -> None:
    for field in reversed(SCORING_DEFAULTS):
        op.drop_constraint(f"ck_tournaments_{field}", "tournaments", type_="check")
        op.drop_column("tournaments", field)
