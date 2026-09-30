"""Add optional pairing group to tournament teams.

Revision ID: pairing_group_001
Revises: score_entry_source_001
"""

import sqlalchemy as sa

from alembic import op


revision = "pairing_group_001"
down_revision = "score_entry_source_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("pairing_group", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("teams", "pairing_group")