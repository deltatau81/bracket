"""Add tournament sponsors.

Revision ID: tournament_sponsors_001
Revises: hockey_penalty_catalog_001
"""

import sqlalchemy as sa

from alembic import op

revision = "tournament_sponsors_001"
down_revision = "hockey_penalty_catalog_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tournament_sponsors",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tournament_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("logo_path", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("position", sa.String(length=10), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.CheckConstraint(
            "position IN ('LEFT', 'RIGHT')",
            name="ck_tournament_sponsors_position",
        ),
        sa.ForeignKeyConstraint(
            ["tournament_id"], ["tournaments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tournament_sponsors_id"),
        "tournament_sponsors",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tournament_sponsors_tournament_id"),
        "tournament_sponsors",
        ["tournament_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_tournament_sponsors_tournament_id"),
        table_name="tournament_sponsors",
    )
    op.drop_index(
        op.f("ix_tournament_sponsors_id"), table_name="tournament_sponsors"
    )
    op.drop_table("tournament_sponsors")
