"""Add hockey tournament rules configuration.

Revision ID: hockey_tournament_rules_001
Revises: hockey_match_events_001
"""

import sqlalchemy as sa

from alembic import op


revision = "hockey_tournament_rules_001"
down_revision = "hockey_match_events_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tournaments",
        sa.Column("ruleset", sa.String(length=20), server_default="DEB", nullable=False),
    )
    op.add_column(
        "tournaments",
        sa.Column("age_category", sa.String(length=20), server_default="U15", nullable=False),
    )
    op.add_column(
        "tournaments",
        sa.Column(
            "ruleset_season",
            sa.String(length=7),
            server_default="2026/27",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_tournaments_ruleset", "tournaments", "ruleset IN ('DEB', 'IIHF')"
    )
    op.create_check_constraint(
        "ck_tournaments_age_category",
        "tournaments",
        "age_category IN ('U9', 'U11', 'U13', 'U15', 'U17', 'U20', 'SENIOR')",
    )
    op.create_check_constraint(
        "ck_tournaments_ruleset_season",
        "tournaments",
        "ruleset_season ~ '^[0-9]{4}/[0-9]{2}$' "
        "AND substring(ruleset_season from 6 for 2)::integer = "
        "(substring(ruleset_season from 1 for 4)::integer + 1) % 100",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tournaments_ruleset_season", "tournaments", type_="check")
    op.drop_constraint("ck_tournaments_age_category", "tournaments", type_="check")
    op.drop_constraint("ck_tournaments_ruleset", "tournaments", type_="check")
    op.drop_column("tournaments", "ruleset_season")
    op.drop_column("tournaments", "age_category")
    op.drop_column("tournaments", "ruleset")
