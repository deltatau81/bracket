"""Add optional participating club to tournament teams.

Revision ID: team_participant_club_001
Revises: admin_account_type_001
"""

import sqlalchemy as sa

from alembic import op


revision = "team_participant_club_001"
down_revision = "admin_account_type_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column("participant_club_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "teams_participant_club_id_fkey",
        "teams",
        "clubs",
        ["participant_club_id"],
        ["id"],
    )
    op.create_index(
        "ix_teams_tournament_id_participant_club_id",
        "teams",
        ["tournament_id", "participant_club_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_teams_tournament_id_participant_club_id", table_name="teams")
    op.drop_constraint("teams_participant_club_id_fkey", "teams", type_="foreignkey")
    op.drop_column("teams", "participant_club_id")
