from alembic import op


revision = "scorer_account_type_001"
down_revision = "hockey_match_rules_overrides_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE account_type ADD VALUE IF NOT EXISTS 'SCORER'")


def downgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET account_type = 'REGULAR'
        WHERE account_type = 'SCORER'
        """
    )

    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN account_type TYPE VARCHAR(20)
        USING account_type::text
        """
    )

    op.execute("DROP TYPE account_type")

    op.execute(
        """
        CREATE TYPE account_type AS ENUM ('REGULAR', 'DEMO')
        """
    )

    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN account_type TYPE account_type
        USING account_type::account_type
        """
    )
