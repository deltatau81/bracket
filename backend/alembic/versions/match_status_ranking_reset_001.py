"""Reset stale standings for wholly unplayed stage items.

Revision ID: match_status_ranking_reset_001
Revises: match_status_001
"""

from alembic import op


revision = "match_status_ranking_reset_001"
down_revision = "match_status_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # match_status_001 may already have run before its data correction was
    # added. Limit this repair to stage items without any finished match so
    # historical and mixed production standings remain untouched.
    op.execute(
        """
        UPDATE stage_item_inputs AS input
        SET wins = 0,
            draws = 0,
            losses = 0,
            points = CASE
                WHEN stage_items.type = 'SWISS' THEN 1200
                ELSE 0
            END
        FROM stage_items
        WHERE stage_items.id = input.stage_item_id
          AND NOT EXISTS (
              SELECT 1
              FROM matches
              JOIN rounds ON rounds.id = matches.round_id
              WHERE rounds.stage_item_id = input.stage_item_id
                AND matches.status = 'FINISHED'
          )
        """
    )


def downgrade() -> None:
    # The discarded values were stale derived data and cannot be restored.
    pass
