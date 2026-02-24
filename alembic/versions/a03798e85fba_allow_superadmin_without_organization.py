"""allow superadmin without organization

Revision ID: a03798e85fba
Revises: 1a8294f7dbb8
Create Date: 2026-02-23 14:39:20.635880
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a03798e85fba"
down_revision = "1a8294f7dbb8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "organization_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
        op.alter_column(
        "users",
        "organization_id",
        existing_type=sa.Integer(),
        nullable=False,
    )