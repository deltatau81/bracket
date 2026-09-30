"""Add explicit youth club tournament and Stage Item markers.

Revision ID: youth_club_format_001
Revises: pairing_group_001
"""

import sqlalchemy as sa

from alembic import op


revision = "youth_club_format_001"
down_revision = "pairing_group_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tournaments",
        sa.Column(
            "competition_format",
            sa.String(length=20),
            server_default="STANDARD",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_tournaments_competition_format",
        "tournaments",
        "competition_format IN ('STANDARD', 'YOUTH_CLUB')",
    )
    op.add_column(
        "stage_items",
        sa.Column(
            "is_youth_club_group",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("stage_items", "is_youth_club_group")
    op.drop_constraint("ck_tournaments_competition_format", "tournaments", type_="check")
    op.drop_column("tournaments", "competition_format")
