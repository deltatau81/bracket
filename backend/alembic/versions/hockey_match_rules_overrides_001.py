"""Add optional hockey match rules overrides.

Revision ID: hockey_match_rules_overrides_001
Revises: hockey_tournament_rules_001
"""

import sqlalchemy as sa

from alembic import op


revision = "hockey_match_rules_overrides_001"
down_revision = "hockey_tournament_rules_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("ruleset_override", sa.String(20), nullable=True))
    op.add_column("matches", sa.Column("age_category_override", sa.String(20), nullable=True))
    op.add_column(
        "matches", sa.Column("ruleset_season_override", sa.String(7), nullable=True)
    )
    op.create_check_constraint(
        "ck_matches_ruleset_override",
        "matches",
        "ruleset_override IS NULL OR ruleset_override IN ('DEB', 'IIHF')",
    )
    op.create_check_constraint(
        "ck_matches_age_category_override",
        "matches",
        "age_category_override IS NULL OR age_category_override "
        "IN ('U9', 'U11', 'U13', 'U15', 'U17', 'U20', 'SENIOR')",
    )
    op.create_check_constraint(
        "ck_matches_ruleset_season_override",
        "matches",
        "ruleset_season_override IS NULL OR ("
        "ruleset_season_override ~ '^[0-9]{4}/[0-9]{2}$' "
        "AND substring(ruleset_season_override from 6 for 2)::integer = "
        "(substring(ruleset_season_override from 1 for 4)::integer + 1) % 100)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_matches_ruleset_season_override", "matches", type_="check")
    op.drop_constraint("ck_matches_age_category_override", "matches", type_="check")
    op.drop_constraint("ck_matches_ruleset_override", "matches", type_="check")
    op.drop_column("matches", "ruleset_season_override")
    op.drop_column("matches", "age_category_override")
    op.drop_column("matches", "ruleset_override")
