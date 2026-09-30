"""Add explicit match lifecycle status.

Revision ID: match_status_001
Revises: hockey_competition_001
"""

import sqlalchemy as sa

from alembic import op


revision = "match_status_001"
down_revision = "hockey_competition_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "matches",
        sa.Column("status", sa.String(length=20), nullable=True),
    )

    # Preserve standings for historical and mixed stage items. A stage item is
    # only inferred as wholly unplayed when every match is an unscheduled or
    # future 0:0. This avoids reclassifying historical 0:0 draws as planned.
    op.execute(
        """
        UPDATE matches AS target
        SET status = CASE
            WHEN EXISTS (
                SELECT 1
                FROM matches AS evidence
                JOIN rounds AS evidence_round
                  ON evidence_round.id = evidence.round_id
                JOIN rounds AS target_round
                  ON target_round.id = target.round_id
                WHERE evidence_round.stage_item_id = target_round.stage_item_id
                  AND (
                      evidence.stage_item_input1_score <> 0
                      OR evidence.stage_item_input2_score <> 0
                      OR (
                          evidence.start_time IS NOT NULL
                          AND evidence.start_time <= NOW()
                      )
                  )
            ) THEN 'FINISHED'
            ELSE 'PLANNED'
        END
        """
    )

    # Bracket stores calculated standings on stage-item inputs. Clear only
    # wholly unplayed stage items so old phantom 0:0 draws disappear without
    # altering any historical or mixed production standings.
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

    op.alter_column(
        "matches",
        "status",
        existing_type=sa.String(length=20),
        nullable=False,
        server_default="PLANNED",
    )
    op.create_check_constraint(
        "ck_matches_status",
        "matches",
        "status IN ('PLANNED', 'RUNNING', 'FINISHED')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_matches_status", "matches", type_="check")
    op.drop_column("matches", "status")
