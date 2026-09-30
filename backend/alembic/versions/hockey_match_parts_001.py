"""Add hockey match part scores.

Revision ID: hockey_match_parts_001
Revises: match_status_ranking_reset_001
"""

import sqlalchemy as sa

from alembic import op


revision = "hockey_match_parts_001"
down_revision = "match_status_ranking_reset_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "matches",
        sa.Column(
            "stage_item_input1_half1_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "matches",
        sa.Column(
            "stage_item_input2_half1_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "matches",
        sa.Column(
            "stage_item_input1_half2_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "matches",
        sa.Column(
            "stage_item_input2_half2_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "matches",
        sa.Column(
            "stage_item_input1_penalty_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "matches",
        sa.Column(
            "stage_item_input2_penalty_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("matches", "stage_item_input2_penalty_score")
    op.drop_column("matches", "stage_item_input1_penalty_score")
    op.drop_column("matches", "stage_item_input2_half2_score")
    op.drop_column("matches", "stage_item_input1_half2_score")
    op.drop_column("matches", "stage_item_input2_half1_score")
    op.drop_column("matches", "stage_item_input1_half1_score")
