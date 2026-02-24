"""neutralized migration (do not drop legacy tables)

Revision ID: cf1c11251ae1
Revises:
Create Date: 2026-02-22
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "cf1c11251ae1"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # intentionally empty (legacy cleanup removed)
    pass


def downgrade() -> None:
    # intentionally empty
    pass