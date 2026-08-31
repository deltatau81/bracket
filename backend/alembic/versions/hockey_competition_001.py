"""Add hockey competition support

Revision ID: hockey_competition_001
Revises: c1ab44651e79
"""

from alembic import op
import sqlalchemy as sa


revision = "hockey_competition_001"
down_revision = "c1ab44651e79"
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ------------------------------------------------------------
    # Competition
    #
    # Ein Competition-Block im Turnierplan.
    # Beispiel:
    #   10:00 - 11:00 Skills Competition
    # ------------------------------------------------------------
    op.create_table(
        "competitions",

        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),

        sa.Column(
            "tournament_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "tournaments.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "name",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "start_time",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.Column(
            "duration_minutes",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),

        sa.Column(
            "court_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "courts.id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),

        sa.Column(
            "created",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),

        sa.CheckConstraint(
            "duration_minutes > 0",
            name="ck_competitions_duration_positive",
        ),
    )

    op.create_index(
        "ix_competitions_tournament_id",
        "competitions",
        ["tournament_id"],
    )

    op.create_index(
        "ix_competitions_start_time",
        "competitions",
        ["start_time"],
    )


    # ------------------------------------------------------------
    # Disziplinen
    #
    # metric_type:
    #
    # TIME
    #   Sprintstaffel
    #
    # COUNT
    #   Penalty-Schießen
    #
    # RATIO
    #   Torwart-Competition
    #
    # MANUAL
    #   Platzierung wird manuell eingetragen
    # ------------------------------------------------------------
    op.create_table(
        "competition_disciplines",

        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),

        sa.Column(
            "competition_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "competitions.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "name",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "metric_type",
            sa.String(20),
            nullable=False,
            server_default="MANUAL",
        ),

        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "created",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),

        sa.CheckConstraint(
            "metric_type IN ('TIME', 'COUNT', 'RATIO', 'MANUAL')",
            name="ck_competition_discipline_metric_type",
        ),
    )

    op.create_index(
        "ix_competition_disciplines_competition_id",
        "competition_disciplines",
        ["competition_id"],
    )


    # ------------------------------------------------------------
    # Punkteverteilung
    #
    # Beispiel:
    #
    # Platz 1 = 2.50
    # Platz 2 = 1.50
    # Platz 3 = 1.00
    # Platz 4 = 0.50
    # ------------------------------------------------------------
    op.create_table(
        "competition_scoring",

        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),

        sa.Column(
            "competition_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "competitions.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "place",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "points",
            sa.Numeric(8, 2),
            nullable=False,
        ),

        sa.CheckConstraint(
            "place > 0",
            name="ck_competition_scoring_place_positive",
        ),

        sa.CheckConstraint(
            "points >= 0",
            name="ck_competition_scoring_points_positive",
        ),

        sa.UniqueConstraint(
            "competition_id",
            "place",
            name="uq_competition_scoring_place",
        ),
    )

    op.create_index(
        "ix_competition_scoring_competition_id",
        "competition_scoring",
        ["competition_id"],
    )


    # ------------------------------------------------------------
    # Ergebnisse pro Team und Disziplin
    #
    # Sprint:
    #   time_ms
    #
    # Penalty:
    #   attempts
    #   successes
    #
    # Torwart:
    #   attempts = Schüsse
    #   successes = gehaltene Schüsse
    #
    # place kann automatisch oder manuell gesetzt werden.
    # ------------------------------------------------------------
    op.create_table(
        "competition_results",

        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),

        sa.Column(
            "discipline_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "competition_disciplines.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "team_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "teams.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "place",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "time_ms",
            sa.BigInteger(),
            nullable=True,
        ),

        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "successes",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "updated",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),

        sa.CheckConstraint(
            "place IS NULL OR place > 0",
            name="ck_competition_results_place_positive",
        ),

        sa.CheckConstraint(
            "time_ms IS NULL OR time_ms >= 0",
            name="ck_competition_results_time_positive",
        ),

        sa.CheckConstraint(
            "attempts IS NULL OR attempts >= 0",
            name="ck_competition_results_attempts_positive",
        ),

        sa.CheckConstraint(
            "successes IS NULL OR successes >= 0",
            name="ck_competition_results_successes_positive",
        ),

        sa.CheckConstraint(
            """
            attempts IS NULL
            OR successes IS NULL
            OR successes <= attempts
            """,
            name="ck_competition_results_successes_lte_attempts",
        ),

        sa.UniqueConstraint(
            "discipline_id",
            "team_id",
            name="uq_competition_result_team",
        ),
    )

    op.create_index(
        "ix_competition_results_discipline_id",
        "competition_results",
        ["discipline_id"],
    )

    op.create_index(
        "ix_competition_results_team_id",
        "competition_results",
        ["team_id"],
    )


    # ------------------------------------------------------------
    # Schütze/Torwart-Paarungen
    #
    # Unterstützt:
    #
    # - externe Auslosung
    # - manuelle Eingabe
    # - spätere automatische Auslosung
    #
    # shooter_name / goalkeeper_name sind absichtlich freie Texte.
    # Dadurch müssen die Spieler nicht zwingend vorher in Bracket
    # angelegt worden sein.
    # ------------------------------------------------------------
    op.create_table(
        "competition_pairings",

        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),

        sa.Column(
            "discipline_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "competition_disciplines.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "shooter_team_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "teams.id",
                ondelete="CASCADE",
            ),
            nullable=True,
        ),

        sa.Column(
            "goalkeeper_team_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "teams.id",
                ondelete="CASCADE",
            ),
            nullable=True,
        ),

        sa.Column(
            "shooter_name",
            sa.String(),
            nullable=True,
        ),

        sa.Column(
            "goalkeeper_name",
            sa.String(),
            nullable=True,
        ),

        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_competition_pairings_discipline_id",
        "competition_pairings",
        ["discipline_id"],
    )


def downgrade() -> None:

    op.drop_index(
        "ix_competition_pairings_discipline_id",
        table_name="competition_pairings",
    )
    op.drop_table("competition_pairings")

    op.drop_index(
        "ix_competition_results_team_id",
        table_name="competition_results",
    )
    op.drop_index(
        "ix_competition_results_discipline_id",
        table_name="competition_results",
    )
    op.drop_table("competition_results")

    op.drop_index(
        "ix_competition_scoring_competition_id",
        table_name="competition_scoring",
    )
    op.drop_table("competition_scoring")

    op.drop_index(
        "ix_competition_disciplines_competition_id",
        table_name="competition_disciplines",
    )
    op.drop_table("competition_disciplines")

    op.drop_index(
        "ix_competitions_start_time",
        table_name="competitions",
    )
    op.drop_index(
        "ix_competitions_tournament_id",
        table_name="competitions",
    )
    op.drop_table("competitions")
