"""Add structured hockey penalty snapshots.

Revision ID: hockey_penalty_catalog_001
Revises: hockey_match_phase_001
"""

import sqlalchemy as sa

from alembic import op


revision = "hockey_penalty_catalog_001"
down_revision = "hockey_match_phase_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("match_events", sa.Column("penalty_code", sa.String(), nullable=True))
    op.add_column("match_events", sa.Column("penalty_rule", sa.String(), nullable=True))
    op.add_column("match_events", sa.Column("game_misconduct", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("match_events", "game_misconduct")
    op.drop_column("match_events", "penalty_rule")
    op.drop_column("match_events", "penalty_code")