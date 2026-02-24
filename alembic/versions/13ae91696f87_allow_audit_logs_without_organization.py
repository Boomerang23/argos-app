"""allow audit logs without organization

Revision ID: 13ae91696f87
Revises: a03798e85fba
Create Date: 2026-02-23 16:38:15.835049

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13ae91696f87'
down_revision: Union[str, Sequence[str], None] = 'a03798e85fba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.alter_column(
        "audit_logs",
        "organization_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

def downgrade() -> None:
    op.alter_column(
        "audit_logs",
        "organization_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
