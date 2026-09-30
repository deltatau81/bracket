"""Add ADMIN account type.

Revision ID: admin_account_type_001
Revises: tournament_sponsors_001
"""

from alembic import op

revision = "admin_account_type_001"
down_revision = "tournament_sponsors_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE account_type ADD VALUE IF NOT EXISTS 'ADMIN'")


def downgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET account_type = 'REGULAR'
        WHERE account_type = 'ADMIN'
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
    op.execute("CREATE TYPE account_type AS ENUM ('REGULAR', 'SCORER', 'DEMO')")
    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN account_type TYPE account_type
        USING account_type::account_type
        """
    )
